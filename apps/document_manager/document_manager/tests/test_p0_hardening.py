# -*- coding: utf-8 -*-
"""Regression tests for the P0 fixes: XML access, reader visibility, cascade, counters, honesty.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_p0_hardening
"""

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager.permissions import (
    archival_file_query,
    archive_document_query,
    has_archival_file_permission,
    has_archive_document_permission,
)
from document_manager.document_manager.services import backup_service, xml_handler
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _reader, _seed_archive, _user

READER = "p0.reader@example.com"
CATALOGER = "p0.cataloger@example.com"
ADMIN = "p0.admin@example.com"
HIDDEN_LEVEL = "P0 Secret"


class TestP0Hardening(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.ensure_roles()
        install.ensure_confidentiality_levels()
        _user(READER, ["Reader"], "Website User")
        _user(CATALOGER, ["Cataloger"], "System User")
        _user(ADMIN, ["Document Admin"], "System User")
        cls.profile = _reader(READER, "P0 Reader")
        if not frappe.db.exists("Confidentiality Level", HIDDEN_LEVEL):
            frappe.get_doc({"doctype": "Confidentiality Level", "level_name": HIDDEN_LEVEL,
                            "priority": 7}).insert(ignore_permissions=True)
        cls._seeded = _seed_archive(2)
        cls.file_a, cls.file_b = _names(cls._seeded, "Archival File")
        cls.doc_a, cls.doc_b = _names(cls._seeded, "Archive Document")

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for dt, name in cls._seeded:
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        frappe.delete_doc("Confidentiality Level", HIDDEN_LEVEL, force=True, ignore_permissions=True)
        for name in frappe.get_all("Notification Log", filters={"for_user": ADMIN}, pluck="name"):
            frappe.delete_doc("Notification Log", name, force=True, ignore_permissions=True)
        frappe.delete_doc("Reader", cls.profile, force=True, ignore_permissions=True)
        for email in (READER, CATALOGER, ADMIN):
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDownClass()

    def setUp(self):
        # The code under test commits (it runs in workers in real life). A commit here would make
        # the test data permanent, so it is neutralised: the framework rolls everything back.
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)

    def tearDown(self):
        frappe.set_user("Administrator")

    # ---- XML exchange
    def test_xml_export_and_import_are_refused_to_readers_and_catalogers(self):
        sample = "<ArchivalData><ArchivalFile><file_title>x</file_title></ArchivalFile></ArchivalData>"
        for user in (READER, CATALOGER):
            frappe.set_user(user)
            with self.assertRaises(frappe.PermissionError, msg=user):
                xml_handler.export_xml("Archival File")
            with self.assertRaises(frappe.PermissionError, msg=user):
                xml_handler.import_xml(sample, "Archival File")

    def test_xml_export_emits_only_whitelisted_columns(self):
        frappe.set_user(ADMIN)
        res = xml_handler.export_xml("Archive Document", fields=json.dumps(
            ["document_title", "content_text", "gridfs_file_id", "owner"]))
        self.assertGreaterEqual(res["count"], 2)
        self.assertIn("<document_title>", res["xml_content"])
        for forbidden in ("content_text", "gridfs_file_id", "<owner>"):
            self.assertNotIn(forbidden, res["xml_content"])

    def test_xml_import_rejects_entity_declarations(self):
        frappe.set_user(ADMIN)
        bomb = '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa">]><ArchivalData>&a;</ArchivalData>'
        with self.assertRaises(frappe.ValidationError):
            xml_handler.import_xml(bomb, "Fonds")

    def test_xml_import_ignores_columns_outside_the_whitelist(self):
        frappe.set_user(ADMIN)
        xml = ("<ArchivalData><Fonds><fonds_name>P0 Import</fonds_name><owner>Administrator</owner>"
               "<docstatus>1</docstatus><total_files>999</total_files></Fonds></ArchivalData>")
        fonds = frappe.db.get_value("Archival File", self.file_a, "fonds")
        agency = frappe.db.get_value("Fonds", fonds, "archival_agency")
        xml = xml.replace("</fonds_name>", f"</fonds_name><archival_agency>{agency}</archival_agency>")
        results = xml_handler._import_xml_worker(xml, "Fonds")
        try:
            self.assertEqual(results["imported"], 1, results)
            name = frappe.db.get_value("Fonds", {"fonds_name": "P0 Import"})
            self.assertEqual(frappe.db.get_value("Fonds", name, "owner"), ADMIN)
            self.assertEqual(frappe.db.get_value("Fonds", name, "docstatus"), 0)
            self.assertEqual(frappe.db.get_value("Fonds", name, "total_files"), 0)
        finally:
            for name in frappe.get_all("Fonds", filters={"fonds_name": "P0 Import"}, pluck="name"):
                frappe.delete_doc("Fonds", name, force=True, ignore_permissions=True)

    def test_retention_job_is_not_callable_from_the_web(self):
        from document_manager.document_manager.doctype.archival_file import archival_file
        self.assertNotIn(archival_file.check_retention_periods, frappe.whitelisted)

    # ---- reader visibility
    def _visible_files(self, user):
        frappe.set_user(user)
        return set(frappe.get_list("Archival File", pluck="name", limit_page_length=0))

    def _visible_docs(self, user):
        frappe.set_user(user)
        return set(frappe.get_list("Archive Document", pluck="name", limit_page_length=0))

    def test_draft_file_and_its_documents_are_hidden_from_readers_but_not_staff(self):
        frappe.db.set_value("Archival File", self.file_a, "status", "Nháp")
        self.assertNotIn(self.file_a, self._visible_files(READER))
        self.assertNotIn(self.doc_a, self._visible_docs(READER))
        self.assertIn(self.file_b, self._visible_files(READER))
        self.assertIn(self.doc_b, self._visible_docs(READER))
        self.assertIn(self.file_a, self._visible_files(CATALOGER))
        self.assertIn(self.doc_a, self._visible_docs(CATALOGER))
        frappe.set_user("Administrator")
        frappe.db.set_value("Archival File", self.file_a, "status", "Đã hoàn thành")
        self.assertIn(self.file_a, self._visible_files(READER))
        self.assertIn(self.doc_a, self._visible_docs(READER))

    def test_disposed_file_is_hidden_from_readers(self):
        frappe.db.set_value("Archival File", self.file_a, "disposal_status", "Đã tiêu hủy")
        try:
            self.assertNotIn(self.file_a, self._visible_files(READER))
            self.assertNotIn(self.doc_a, self._visible_docs(READER))
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value("Archival File", self.file_a, "disposal_status", "Bình thường")

    def test_has_permission_matches_the_query_for_unpublished_files(self):
        frappe.db.set_value("Archival File", self.file_a, "status", "Nháp")
        try:
            file_doc = frappe.get_doc("Archival File", self.file_a)
            doc = frappe.get_doc("Archive Document", self.doc_a)
            self.assertFalse(has_archival_file_permission(file_doc, "read", READER))
            self.assertFalse(has_archive_document_permission(doc, "read", READER))
            self.assertTrue(has_archival_file_permission(file_doc, "read", CATALOGER))
            self.assertTrue(has_archive_document_permission(doc, "read", CATALOGER))
        finally:
            frappe.db.set_value("Archival File", self.file_a, "status", "Đã hoàn thành")

    def test_reader_query_conditions_mention_the_published_state(self):
        frappe.set_user(READER)
        self.assertIn("Nháp", archival_file_query(READER))
        self.assertIn("Đã tiêu hủy", archive_document_query(READER))
        frappe.set_user(CATALOGER)
        self.assertEqual(archival_file_query(CATALOGER), "")

    # ---- cascade of the confidentiality level
    def test_reclassifying_a_file_reclassifies_its_documents(self):
        frappe.set_user("Administrator")
        file_doc = frappe.get_doc("Archival File", self.file_a)
        file_doc.confidentiality_level = HIDDEN_LEVEL
        file_doc.save()
        self.assertEqual(frappe.db.get_value("Archive Document", self.doc_a, "confidentiality_level"),
                         HIDDEN_LEVEL)
        self.assertNotIn(self.doc_a, self._visible_docs(READER))
        frappe.set_user("Administrator")
        file_doc = frappe.get_doc("Archival File", self.file_a)
        file_doc.confidentiality_level = "Thường"
        file_doc.save()
        self.assertIn(self.doc_a, self._visible_docs(READER))

    def test_search_index_payload_is_fail_closed(self):
        from document_manager.document_manager.services import search_index
        frappe.db.set_value("Archival File", self.file_a, "status", "Nháp")
        try:
            by_id = {d["id"]: d for d in search_index._build_documents([self.doc_a, self.doc_b])}
            self.assertFalse(by_id[self.doc_a]["is_published"])
            self.assertTrue(by_id[self.doc_b]["is_published"])
            self.assertEqual(by_id[self.doc_b]["confidentiality_priority"], 1)
            frappe.db.set_value("Archive Document", self.doc_b, "confidentiality_level", None)
            blank = search_index._build_documents([self.doc_b])[0]
            self.assertEqual(blank["confidentiality_priority"], search_index.UNKNOWN_LEVEL_PRIORITY)
        finally:
            frappe.db.set_value("Archival File", self.file_a, "status", "Đã hoàn thành")
            frappe.db.set_value("Archive Document", self.doc_b, "confidentiality_level", "Thường")

    # ---- counters
    def _count(self, file_name):
        return frappe.db.get_value("Archival File", file_name, "total_documents")

    def test_document_counters_follow_adds_moves_and_deletes(self):
        frappe.set_user("Administrator")
        self.assertEqual((self._count(self.file_a), self._count(self.file_b)), (1, 1))
        extra = frappe.get_doc({"doctype": "Archive Document", "document_title": "P0 extra",
                                "archival_file": self.file_a}).insert()
        self.assertEqual(self._count(self.file_a), 2)
        extra.archival_file = self.file_b  # a move updates both parents
        extra.save()
        self.assertEqual((self._count(self.file_a), self._count(self.file_b)), (1, 2))
        frappe.delete_doc("Archive Document", extra.name, force=True)  # not off by one
        self.assertEqual((self._count(self.file_a), self._count(self.file_b)), (1, 1))

    def test_fonds_counter_follows_deletes(self):
        frappe.set_user("Administrator")
        fonds = frappe.db.get_value("Archival File", self.file_a, "fonds")
        self.assertEqual(frappe.db.get_value("Fonds", fonds, "total_files"), 2)
        extra = frappe.get_doc({"doctype": "Archival File", "file_title": "P0 file",
                                "fonds": fonds,
                                "catalog": frappe.db.get_value("Archival File", self.file_a, "catalog")}
                               ).insert()
        self.assertEqual(frappe.db.get_value("Fonds", fonds, "total_files"), 3)
        frappe.delete_doc("Archival File", extra.name, force=True)
        self.assertEqual(frappe.db.get_value("Fonds", fonds, "total_files"), 2)

    def test_deleting_a_document_releases_its_gridfs_files_after_commit(self):
        frappe.set_user("Administrator")
        extra = frappe.get_doc({"doctype": "Archive Document", "document_title": "P0 blob",
                                "archival_file": self.file_a, "gridfs_file_id": "abc123",
                                "gridfs_preview_id": "def456"}).insert()
        with patch("document_manager.document_manager.doctype.archive_document.archive_document."
                   "enqueue_delete_gridfs_files") as enqueue:
            frappe.delete_doc("Archive Document", extra.name, force=True)
        enqueue.assert_any_call(["abc123"], "documents")
        enqueue.assert_any_call(["def456"], "previews")

    # ---- backup / restore tell the truth
    def _batch(self, doctype, **values):
        doc = frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, doctype, doc.name, force=True, ignore_permissions=True)
        return doc

    def test_file_backup_is_never_reported_as_success(self):
        fake = MagicMock(backup_path_db="/nonexistent/db.sql.gz")
        with patch("frappe.utils.backups.new_backup", return_value=fake):
            both = self._batch("Backup Batch", backup_type="Cả hai")
            backup_service.run_backup(both.name, "Cả hai")
            only_files = self._batch("Backup Batch", backup_type="Tệp tài liệu")
            backup_service.run_backup(only_files.name, "Tệp tài liệu")
            only_db = self._batch("Backup Batch", backup_type="Cơ sở dữ liệu")
            backup_service.run_backup(only_db.name, "Cơ sở dữ liệu")
        self.assertEqual(frappe.db.get_value("Backup Batch", both.name, "status"), "Một phần")
        self.assertEqual(frappe.db.get_value("Backup Batch", only_files.name, "status"), "Chưa hỗ trợ")
        self.assertEqual(frappe.db.get_value("Backup Batch", only_db.name, "status"), "Thành công")
        self.assertIn("chưa được hỗ trợ", frappe.db.get_value("Backup Batch", both.name, "error_log"))

    def test_restore_never_claims_success_and_explains_the_manual_step(self):
        backup = self._batch("Backup Batch", backup_type="Cơ sở dữ liệu", backup_path="/tmp/db.sql.gz")
        restore = self._batch("Restore Batch", restore_type="Cơ sở dữ liệu", source_backup=backup.name)
        backup_service.run_restore(restore.name)
        restore.reload()
        self.assertEqual(restore.status, "Cần thao tác thủ công")
        self.assertIn("bench --site", restore.error_log)
        self.assertEqual(restore.records_restored, 0)

        no_source = self._batch("Restore Batch", restore_type="Cơ sở dữ liệu")
        backup_service.run_restore(no_source.name)
        self.assertEqual(frappe.db.get_value("Restore Batch", no_source.name, "status"), "Lỗi")

    # ---- fresh-site seed
    def test_seed_is_idempotent_and_provides_the_default_level(self):
        install.seed_all()
        install.seed_all()
        self.assertTrue(frappe.db.exists("Confidentiality Level", "Thường"))
        self.assertEqual(frappe.db.get_value("Confidentiality Level", "Thường", "priority"), 1)
        self.assertEqual(frappe.db.count("Workflow", {"name": "Usage Request Workflow"}), 1)
        for role in ("Document Admin", "Cataloger", "Reading Room Officer", "Preservation Officer", "Reader"):
            self.assertTrue(frappe.db.exists("Role", role), role)
