# -*- coding: utf-8 -*-
"""Workflow, ownership and integrity tests for Usage Request, Copy Request and Reader Feedback.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_request_workflow
"""

import json

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager.api import requests as api

READER_A = "rw.reader.a@example.com"
READER_B = "rw.reader.b@example.com"
OFFICER = "rw.officer@example.com"
ADMIN = "rw.admin@example.com"
SECRET_LEVEL = "RW Secret"


LIMIT_FIELDS = ("max_requests_per_day", "max_copy_requests_per_day", "max_items_per_request", "max_open_requests",
                "block_when_overdue")


def relax_limits():
    """Switch the slip limits of Reader Settings off (0 = no limit); returns the function that restores them.

    Tests that file many slips for the same reader without cleaning up would otherwise meet the quota."""
    old = {f: frappe.db.get_single_value("Reader Settings", f) for f in LIMIT_FIELDS}
    for field in LIMIT_FIELDS:
        frappe.db.set_single_value("Reader Settings", field, 0)
    frappe.clear_document_cache("Reader Settings", "Reader Settings")

    def restore():
        for field, value in old.items():
            frappe.db.set_single_value("Reader Settings", field, value or 0)
        frappe.clear_document_cache("Reader Settings", "Reader Settings")
    return restore


def _user(email, roles, user_type):
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, force=True, ignore_permissions=True)
    doc = frappe.get_doc({
        "doctype": "User", "email": email, "first_name": email.split("@")[0],
        "send_welcome_email": 0, "user_type": user_type, "roles": [{"role": r} for r in roles],
    })
    doc.flags.no_welcome_mail = True
    doc.insert(ignore_permissions=True)


def _seed_archive(n=2):
    """Create a minimal Agency > Fonds > Record Group > Catalog > n Archival Files chain.

    Returns [(doctype, name), ...] to delete (children first). A fresh CI site has no archive data.
    """
    made = []

    def make(values):
        doc = frappe.get_doc(values).insert(ignore_permissions=True)
        made.append((values["doctype"], doc.name))
        return doc.name

    if not frappe.db.exists("Confidentiality Level", "Thường"):
        make({"doctype": "Confidentiality Level", "level_name": "Thường", "priority": 1})
    tag = frappe.generate_hash(length=6)  # unique names: a leftover can never block a later run
    agency = make({"doctype": "Archival Agency", "agency_name": f"RW Test Agency {tag}"})
    fonds = make({"doctype": "Fonds", "fonds_name": f"RW Test Fonds {tag}", "archival_agency": agency})
    group = make({"doctype": "Record Group", "group_title": f"RW Test Group {tag}", "fonds": fonds})
    catalog = make({"doctype": "Catalog", "catalog_title": f"RW Test Catalog {tag}",
                    "record_group": group, "fonds": fonds})
    for i in range(n):
        file_name = make({"doctype": "Archival File", "file_title": f"RW Test File {i}", "fonds": fonds,
                          "record_group": group, "catalog": catalog, "confidentiality_level": "Thường",
                          "status": "Đã hoàn thành"})
        make({"doctype": "Archive Document", "document_title": f"RW Test Doc {i}",
              "archival_file": file_name})
    return made[::-1]


def _names(made, doctype):
    """Names of `doctype` records from a `_seed_archive` result, in creation order."""
    return [name for dt, name in made[::-1] if dt == doctype]


def _reader(email, name):
    existing = frappe.db.get_value("Reader", {"user": email})
    if existing:
        frappe.delete_doc("Reader", existing, force=True, ignore_permissions=True)
    doc = frappe.get_doc({"doctype": "Reader", "full_name": name, "user": email, "email": email,
                          "max_confidentiality_priority": 1, "is_active": 1})
    doc.insert(ignore_permissions=True)
    return doc.name


class TestRequestWorkflow(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        for role in ("Reader", "Reading Room Officer", "Document Admin"):
            if not frappe.db.exists("Role", role):
                frappe.get_doc({"doctype": "Role", "role_name": role}).insert(ignore_permissions=True)
        _user(READER_A, ["Reader"], "Website User")
        _user(READER_B, ["Reader"], "Website User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(ADMIN, ["Document Admin"], "System User")
        cls.profile_a = _reader(READER_A, "RW Reader A")
        cls.profile_b = _reader(READER_B, "RW Reader B")

        if not frappe.db.exists("Confidentiality Level", SECRET_LEVEL):
            frappe.get_doc({"doctype": "Confidentiality Level", "level_name": SECRET_LEVEL,
                            "priority": 5}).insert(ignore_permissions=True)
        # Own data only: the tests never touch the site's real archive.
        cls._seeded = _seed_archive()
        cls.file_ok, cls.file_secret = _names(cls._seeded, "Archival File")
        secret = frappe.get_doc("Archival File", cls.file_secret)
        secret.confidentiality_level = SECRET_LEVEL
        secret.save(ignore_permissions=True)  # also re-classifies the documents inside
        cls.doc_ok = frappe.get_all("Archive Document", filters={"archival_file": cls.file_ok}, pluck="name")
        cls.doc_other = frappe.get_all("Archive Document", filters={"archival_file": cls.file_secret},
                                       pluck="name")
        cls.created = []
        cls._restore_limits = relax_limits()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        cls._restore_limits()
        for dt, name in cls.created:
            if frappe.db.exists(dt, name):
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.flags.ignore_permissions = True
                    doc.cancel()
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for dt, name in cls._seeded:
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        frappe.delete_doc("Confidentiality Level", SECRET_LEVEL, force=True, ignore_permissions=True)
        for profile in (cls.profile_a, cls.profile_b):
            frappe.delete_doc("Reader", profile, force=True, ignore_permissions=True)
        for email in (READER_A, READER_B, OFFICER, ADMIN):
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDownClass()

    def tearDown(self):
        frappe.set_user("Administrator")

    # ---- helpers
    def _payload(self, **extra):
        return json.dumps({"purpose": "nghiên cứu", "items": [{"archival_file": self.file_ok}], **extra})

    def _submit(self, user=READER_A, doctype="Usage Request", **extra):
        frappe.set_user(user)
        res = api.save_request(doctype, self._payload(**extra), submit=1)
        self.created.append((doctype, res["name"]))
        return res

    def _act(self, user, doctype, name, action, text=None):
        frappe.set_user(user)
        return api.apply_action(doctype, name, action, text=text)

    # ---- request lifecycle
    def test_reader_submit_goes_to_pending_and_is_bound_to_own_profile(self):
        res = self._submit(reader=self.profile_b)  # spoof attempt
        self.assertEqual(res["state"], "Chờ duyệt")
        self.assertEqual(frappe.db.get_value("Usage Request", res["name"], "reader"), self.profile_a)

    def test_reader_cannot_self_approve_by_saving_state(self):
        name = self._submit()["name"]
        frappe.set_user(READER_A)
        doc = frappe.get_doc("Usage Request", name)
        doc.workflow_state = "Đã duyệt"
        with self.assertRaises(Exception):
            doc.save()
        self.assertEqual(frappe.db.get_value("Usage Request", name, "workflow_state"), "Chờ duyệt")

    def test_reader_cannot_run_staff_actions(self):
        name = self._submit()["name"]
        for action in ("Duyệt", "Từ chối", "Chuyển lãnh đạo", "Giao tài liệu", "Nhận trả"):
            with self.assertRaises(Exception, msg=action):
                self._act(READER_A, "Usage Request", name, action, text="x")

    def test_reader_cannot_edit_protected_fields(self):
        name = self._submit()["name"]
        frappe.set_user(READER_A)
        doc = frappe.get_doc("Usage Request", name)
        doc.rejection_reason = "x"
        with self.assertRaises(Exception):
            doc.save()

    def test_officer_approves_and_stamps_approver(self):
        name = self._submit()["name"]
        self._act(OFFICER, "Usage Request", name, "Duyệt")
        doc = frappe.get_doc("Usage Request", name)
        self.assertEqual(doc.workflow_state, "Đã duyệt")
        self.assertEqual(doc.approved_by, OFFICER)
        self.assertTrue(doc.approved_date)

    def test_reject_requires_reason(self):
        name = self._submit()["name"]
        with self.assertRaises(Exception):
            self._act(OFFICER, "Usage Request", name, "Từ chối")
        self._act(OFFICER, "Usage Request", name, "Từ chối", text="Không đủ điều kiện")
        doc = frappe.get_doc("Usage Request", name)
        self.assertEqual((doc.workflow_state, doc.rejection_reason), ("Từ chối", "Không đủ điều kiện"))

    def test_actions_must_follow_order(self):
        name = self._submit()["name"]
        with self.assertRaises(Exception):
            self._act(OFFICER, "Usage Request", name, "Giao tài liệu")  # not yet approved
        self._act(OFFICER, "Usage Request", name, "Duyệt")
        with self.assertRaises(Exception):
            self._act(OFFICER, "Usage Request", name, "Nhận trả")  # not handed over yet
        self._act(OFFICER, "Usage Request", name, "Giao tài liệu")
        self._act(OFFICER, "Usage Request", name, "Nhận trả")
        doc = frappe.get_doc("Usage Request", name)
        self.assertEqual(doc.workflow_state, "Đã trả")
        self.assertTrue(doc.returned_date)
        with self.assertRaises(Exception):
            self._act(OFFICER, "Usage Request", name, "Từ chối", text="x")

    def test_reader_can_cancel_pending_but_not_approved(self):
        pending = self._submit()["name"]
        self._act(READER_A, "Usage Request", pending, "Hủy phiếu")
        self.assertEqual(frappe.db.get_value("Usage Request", pending, "workflow_state"), "Đã hủy")
        approved = self._submit()["name"]
        self._act(OFFICER, "Usage Request", approved, "Duyệt")
        with self.assertRaises(Exception):
            self._act(READER_A, "Usage Request", approved, "Hủy phiếu")

    def test_get_actions_depends_on_role(self):
        name = self._submit()["name"]
        frappe.set_user(READER_A)
        self.assertEqual({a["action"] for a in api.get_actions("Usage Request", name)}, {"Hủy phiếu"})
        frappe.set_user(OFFICER)
        self.assertEqual({a["action"] for a in api.get_actions("Usage Request", name)}, {"Duyệt", "Từ chối", "Chuyển lãnh đạo"})

    def test_copy_request_lifecycle(self):
        frappe.set_user(READER_A)
        payload = json.dumps({"purpose": "sao chụp",
                              "items": [{"archival_file": self.file_ok, "copy_count": 2}]})
        res = api.save_request("Copy Request", payload, submit=1)
        self.created.append(("Copy Request", res["name"]))
        self._act(OFFICER, "Copy Request", res["name"], "Duyệt")
        self._act(OFFICER, "Copy Request", res["name"], "Hoàn thành")
        doc = frappe.get_doc("Copy Request", res["name"])
        self.assertEqual(doc.workflow_state, "Đã hoàn thành")
        self.assertTrue(doc.completed_date)

    # ---- item integrity
    def test_confidential_file_is_rejected(self):
        frappe.set_user(READER_A)
        payload = json.dumps({"items": [{"archival_file": self.file_secret}]})
        with self.assertRaises(frappe.PermissionError):
            api.save_request("Usage Request", payload, submit=1)

    def test_document_must_belong_to_file(self):
        if not (self.doc_ok and self.doc_other):
            self.skipTest("needs documents in two different files")
        frappe.set_user(READER_A)
        payload = json.dumps({"items": [{"archival_file": self.file_ok, "archive_document": self.doc_other[0]}]})
        with self.assertRaises(frappe.ValidationError):
            api.save_request("Usage Request", payload, submit=1)

    def test_file_is_filled_from_document(self):
        if not self.doc_ok:
            self.skipTest("needs a document")
        frappe.set_user(READER_A)
        res = api.save_request("Usage Request", json.dumps({"items": [{"archive_document": self.doc_ok[0]}]}))
        self.created.append(("Usage Request", res["name"]))
        row = frappe.get_doc("Usage Request", res["name"]).items[0]
        self.assertEqual(row.archival_file, self.file_ok)

    def test_empty_request_is_rejected(self):
        frappe.set_user(READER_A)
        with self.assertRaises(frappe.ValidationError):
            api.save_request("Usage Request", json.dumps({"items": []}))

    # ---- isolation between readers
    def test_reader_only_sees_own_requests(self):
        name_a = self._submit(READER_A)["name"]
        name_b = self._submit(READER_B)["name"]
        frappe.set_user(READER_B)
        visible = frappe.get_list("Usage Request", pluck="name")
        self.assertIn(name_b, visible)
        self.assertNotIn(name_a, visible)
        self.assertFalse(frappe.has_permission("Usage Request", "read", doc=name_a))
        with self.assertRaises(frappe.PermissionError):
            api.apply_action("Usage Request", name_a, "Hủy phiếu")
        frappe.set_user(OFFICER)
        self.assertTrue({name_a, name_b} <= set(frappe.get_list("Usage Request", pluck="name")))

    def test_reader_cannot_read_other_reader_profile(self):
        frappe.set_user(READER_B)
        self.assertEqual(frappe.get_list("Reader", pluck="name"), [self.profile_b])
        self.assertFalse(frappe.has_permission("Reader", "write", doc=self.profile_b))

    # ---- feedback
    def test_feedback_flow(self):
        frappe.set_user(READER_A)
        res = api.submit_feedback("Góp ý", "<p>Nội dung</p><script>alert(1)</script>")
        name = res["name"]
        self.created.append(("Reader Feedback", name))
        doc = frappe.get_doc("Reader Feedback", name)
        self.assertEqual((doc.status, doc.reader), ("Mới", self.profile_a))
        self.assertNotIn("<script", doc.content)

        doc.status = "Đã phản hồi"
        doc.response = "tự trả lời"
        with self.assertRaises(Exception):
            doc.save()
        with self.assertRaises(Exception):
            api.apply_action("Reader Feedback", name, "Phản hồi", text="x")

        frappe.set_user(READER_B)
        self.assertNotIn(name, frappe.get_list("Reader Feedback", pluck="name"))

        self._act(OFFICER, "Reader Feedback", name, "Đánh dấu đã xem")
        with self.assertRaises(Exception):
            self._act(OFFICER, "Reader Feedback", name, "Phản hồi")  # reply text required
        self._act(OFFICER, "Reader Feedback", name, "Phản hồi", text="<b>Cảm ơn</b>")
        doc = frappe.get_doc("Reader Feedback", name)
        self.assertEqual((doc.status, doc.responded_by), ("Đã phản hồi", OFFICER))
        self.assertTrue(doc.responded_date)
