# -*- coding: utf-8 -*-
"""Regression tests for the P0 fixes: reader visibility, cascade, counters, honesty.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_p0_hardening
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager.permissions import (
    archival_file_query,
    archive_document_query,
    has_archival_file_permission,
    has_archive_document_permission,
)
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

    # (XML exchange: see test_exchange.py)
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

    # (backups and restores that tell the truth are tested in test_preservation)

    # ---- fresh-site seed
    def test_seed_is_idempotent_and_provides_the_default_level(self):
        install.seed_all()
        install.seed_all()
        self.assertTrue(frappe.db.exists("Confidentiality Level", "Thường"))
        self.assertEqual(frappe.db.get_value("Confidentiality Level", "Thường", "priority"), 1)
        self.assertEqual(frappe.db.count("Workflow", {"name": "Usage Request Workflow"}), 1)
        for role in ("Document Admin", "Cataloger", "Reading Room Officer", "Preservation Officer", "Reader"):
            self.assertTrue(frappe.db.exists("Role", role), role)
