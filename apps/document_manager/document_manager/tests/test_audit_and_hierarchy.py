# -*- coding: utf-8 -*-
"""Audit trail (Business Activity Log) and the hierarchy rules (moving nodes, propagating position).

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_audit_and_hierarchy
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager.services import audit
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _seed_archive, _user

ADMIN = "ah.admin@example.com"
CATALOGER = "ah.cataloger@example.com"
LOG = "Business Activity Log"


def _rows(**filters):
    return frappe.get_all(LOG, filters=filters, fields=["activity_type", "description", "user", "reference_name"],
                          order_by="creation asc")


class TestAuditAndHierarchy(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.ensure_roles()
        install.ensure_confidentiality_levels()
        _user(ADMIN, ["Document Admin"], "System User")
        _user(CATALOGER, ["Cataloger"], "System User")
        cls._seed_a = _seed_archive(2)
        cls._seed_b = _seed_archive(1)

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for made in (cls._seed_a, cls._seed_b):
            for dt, name in made:
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for email in (ADMIN, CATALOGER):
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user("Administrator")
        frappe.db.savepoint("ah_test")  # the framework only rolls back per class; isolate each test

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="ah_test")

    # ---- audit
    def test_create_update_delete_are_recorded_with_state_changes(self):
        frappe.set_user(CATALOGER)
        agency = frappe.get_doc({"doctype": "Archival Agency", "agency_name": "AH Agency"}).insert()
        fonds = frappe.get_doc({"doctype": "Fonds", "fonds_name": "AH Fonds", "archival_agency": agency.name}).insert()
        fonds.status = "Đã hoàn thành"
        fonds.save()
        fonds.save()  # unchanged save: must not add a row
        frappe.delete_doc("Fonds", fonds.name, ignore_permissions=True)
        rows = _rows(reference_name=fonds.name)
        self.assertEqual([r.activity_type for r in rows], ["Tạo mới", "Cập nhật", "Xóa"])
        self.assertIn("Đang xử lý → Đã hoàn thành", rows[1].description)
        self.assertEqual({r.user for r in rows}, {CATALOGER})
        frappe.delete_doc("Archival Agency", agency.name, force=True, ignore_permissions=True)

    def test_values_of_ordinary_fields_are_not_copied_into_the_log(self):
        frappe.set_user("Administrator")
        agency = frappe.get_doc({"doctype": "Archival Agency", "agency_name": "AH Agency 2"}).insert()
        fonds = frappe.get_doc({"doctype": "Fonds", "fonds_name": "AH Confidential Name", "archival_agency": agency.name,
                                "history": "history-text-must-not-leak"}).insert()
        fonds.history = "another-secret-text"
        fonds.save()
        blob = " ".join((r.description or "") for r in _rows(reference_name=fonds.name))
        self.assertNotIn("another-secret-text", blob)
        self.assertNotIn("history-text-must-not-leak", blob)
        self.assertIn("Đã sửa", blob)
        frappe.delete_doc("Fonds", fonds.name, force=True, ignore_permissions=True)
        frappe.delete_doc("Archival Agency", agency.name, force=True, ignore_permissions=True)

    def test_the_setting_switches_logging_off_and_the_log_does_not_log_itself(self):
        before = frappe.db.count(LOG)
        frappe.db.set_single_value("Document Manager Settings", "enable_activity_log", 0)
        try:
            self.assertIsNone(audit.log_activity("Xem", "Fonds", "X", "disabled"))
            self.assertEqual(frappe.db.count(LOG), before)
        finally:
            frappe.db.set_single_value("Document Manager Settings", "enable_activity_log", 1)
        name = audit.log_activity("Xem", "Fonds", "X", "enabled")
        self.assertTrue(name)
        self.assertEqual(frappe.db.count(LOG), before + 1)  # one row for one call: no row about the row

    def test_login_and_logout_are_recorded(self):
        manager = frappe._dict(user=ADMIN)
        audit.on_login(manager)
        audit.on_logout(manager)
        self.assertEqual([r.activity_type for r in _rows(reference_name=ADMIN, user=ADMIN)],
                         ["Đăng nhập", "Đăng xuất"])

    def test_nobody_can_forge_or_edit_log_rows_through_permissions(self):
        for user in (ADMIN, CATALOGER):
            self.assertFalse(frappe.has_permission(LOG, "create", user=user), user)
            self.assertFalse(frappe.has_permission(LOG, "write", user=user), user)
            self.assertFalse(frappe.has_permission(LOG, "delete", user=user), user)
        self.assertTrue(frappe.has_permission(LOG, "read", user=ADMIN))
        self.assertFalse(frappe.has_permission(LOG, "read", user=CATALOGER))

    def test_purge_deletes_in_batches_and_leaves_a_summary(self):
        old = "2001-01-01 00:00:00"
        for i in range(7):
            frappe.get_doc({"doctype": LOG, "activity_type": "Xem", "reference_name": f"PURGE-{i}",
                            "timestamp": old, "user": "Administrator"}).insert(ignore_permissions=True)
        deleted = audit.purge_logs("2002-01-01 00:00:00", batch_size=3)
        self.assertGreaterEqual(deleted, 7)
        self.assertEqual(frappe.db.count(LOG, {"reference_name": ["like", "PURGE-%"]}), 0)
        summary = _rows(activity_type="Dọn dẹp nhật ký")
        self.assertTrue(summary and "Đã xóa" in summary[-1].description)

    # ---- hierarchy
    def _tree(self, made):
        return {dt: _names(made, dt) for dt in ("Fonds", "Record Group", "Catalog", "Archival File", "Archive Document")}

    def _where(self, doctype, name, *fields):
        return frappe.db.get_value(doctype, name, list(fields), as_dict=True)

    def test_moving_a_file_updates_the_position_of_its_documents_and_both_counters(self):
        a, b = self._tree(self._seed_a), self._tree(self._seed_b)
        file_name, doc_name = a["Archival File"][0], a["Archive Document"][0]
        file_doc = frappe.get_doc("Archival File", file_name)
        file_doc.catalog = b["Catalog"][0]
        file_doc.save()
        self.assertEqual(self._where("Archive Document", doc_name, "catalog", "record_group", "fonds"),
                         {"catalog": b["Catalog"][0], "record_group": b["Record Group"][0], "fonds": b["Fonds"][0]})
        self.assertEqual(frappe.db.get_value("Fonds", a["Fonds"][0], "total_files"), 1)
        self.assertEqual(frappe.db.get_value("Fonds", b["Fonds"][0], "total_files"), 2)

    def test_moving_a_catalog_moves_files_and_documents(self):
        a, b = self._tree(self._seed_a), self._tree(self._seed_b)
        catalog = frappe.get_doc("Catalog", a["Catalog"][0])
        catalog.record_group = b["Record Group"][0]
        catalog.save()
        self.assertEqual(catalog.fonds, b["Fonds"][0])  # a catalog always follows its record group's fonds
        for file_name in a["Archival File"]:
            self.assertEqual(self._where("Archival File", file_name, "record_group", "fonds"),
                             {"record_group": b["Record Group"][0], "fonds": b["Fonds"][0]})
        for doc_name in a["Archive Document"]:
            self.assertEqual(frappe.db.get_value("Archive Document", doc_name, "fonds"), b["Fonds"][0])
        self.assertEqual(frappe.db.get_value("Fonds", a["Fonds"][0], "total_files"), 0)
        self.assertEqual(frappe.db.get_value("Fonds", b["Fonds"][0], "total_files"), 3)

    def test_moving_a_record_group_to_another_fonds_moves_everything_below(self):
        a, b = self._tree(self._seed_a), self._tree(self._seed_b)
        group = frappe.get_doc("Record Group", a["Record Group"][0])
        group.fonds = b["Fonds"][0]
        group.save()
        self.assertEqual(frappe.db.get_value("Catalog", a["Catalog"][0], "fonds"), b["Fonds"][0])
        for file_name in a["Archival File"]:
            self.assertEqual(frappe.db.get_value("Archival File", file_name, "fonds"), b["Fonds"][0])
        for doc_name in a["Archive Document"]:
            self.assertEqual(frappe.db.get_value("Archive Document", doc_name, "fonds"), b["Fonds"][0])
        self.assertEqual(frappe.db.get_value("Fonds", b["Fonds"][0], "total_files"), 3)

    def test_an_unrelated_save_does_not_touch_children(self):
        a = self._tree(self._seed_a)
        doc_name = a["Archive Document"][0]
        before = frappe.db.get_value("Archive Document", doc_name, "modified")
        file_doc = frappe.get_doc("Archival File", a["Archival File"][0])
        file_doc.notes = "just a note"
        file_doc.save()
        self.assertEqual(frappe.db.get_value("Archive Document", doc_name, "modified"), before)

    def test_a_node_that_still_has_children_cannot_be_deleted(self):
        a = self._tree(self._seed_a)
        for doctype in ("Fonds", "Record Group", "Catalog", "Archival File"):
            with self.assertRaises(frappe.LinkExistsError, msg=doctype):
                frappe.delete_doc(doctype, a[doctype][0], ignore_permissions=True)
