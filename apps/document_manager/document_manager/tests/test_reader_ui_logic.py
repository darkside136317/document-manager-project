# -*- coding: utf-8 -*-
"""Reader profile binding, search gating, account safety and document viewing.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_reader_ui_logic
"""

import importlib
import json

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager.api import file_access, requests as req_api, search as search_api
from document_manager.document_manager.doctype.reader.reader import set_reader_password
from document_manager.tests.test_request_workflow import _names, _reader, _seed_archive, _user

READER = "ui.reader@example.com"
READER_NOPROFILE = "ui.noprofile@example.com"
INACTIVE = "ui.inactive@example.com"
STAFF_WITH_PROFILE = "ui.staffprofile@example.com"
STAFF_NO_PROFILE = "ui.staffnoprofile@example.com"
OFFICER = "ui.officer@example.com"
ADMIN = "ui.admin@example.com"
ALL_USERS = (READER, READER_NOPROFILE, INACTIVE, STAFF_WITH_PROFILE, STAFF_NO_PROFILE, OFFICER, ADMIN)


class TestReaderUiLogic(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        for role in ("Reader", "Reading Room Officer", "Document Admin"):
            if not frappe.db.exists("Role", role):
                frappe.get_doc({"doctype": "Role", "role_name": role}).insert(ignore_permissions=True)
        _user(READER, ["Reader"], "Website User")
        _user(READER_NOPROFILE, ["Reader"], "Website User")
        _user(INACTIVE, ["Reader"], "Website User")
        _user(STAFF_WITH_PROFILE, ["Document Admin", "Reading Room Officer", "Reader"], "System User")
        _user(STAFF_NO_PROFILE, ["Document Admin"], "System User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(ADMIN, ["Document Admin"], "System User")
        cls.profiles = {
            READER: _reader(READER, "UI Reader"),
            INACTIVE: _reader(INACTIVE, "UI Inactive"),
            STAFF_WITH_PROFILE: _reader(STAFF_WITH_PROFILE, "UI Staff Reader"),
        }
        frappe.db.set_value("Reader", cls.profiles[INACTIVE], "is_active", 0)

        cls._seeded = _seed_archive(1)  # own data only; the site's real archive is never touched
        cls.file = _names(cls._seeded, "Archival File")[0]
        cls.created = []

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for dt, name in cls.created:
            if frappe.db.exists(dt, name):
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.flags.ignore_permissions = True
                    doc.cancel()
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for profile in cls.profiles.values():
            frappe.delete_doc("Reader", profile, force=True, ignore_permissions=True)
        for email in ALL_USERS:
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        for dt, name in cls._seeded:
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        super().tearDownClass()

    def tearDown(self):
        frappe.set_user("Administrator")

    # ---- reader auto-binding
    def _payload(self, **extra):
        return json.dumps({"items": [{"archival_file": self.file}], **extra})

    def _save(self, user, doctype="Usage Request", **extra):
        frappe.set_user(user)
        res = req_api.save_request(doctype, self._payload(**extra), submit=1)
        self.created.append((doctype, res["name"]))
        return res

    def test_staff_with_profile_defaults_to_own_profile(self):
        res = self._save(STAFF_WITH_PROFILE)
        self.assertEqual(frappe.db.get_value("Usage Request", res["name"], "reader"),
                         self.profiles[STAFF_WITH_PROFILE])

    def test_staff_can_file_on_behalf_of_another_reader(self):
        res = self._save(STAFF_WITH_PROFILE, reader=self.profiles[READER])
        self.assertEqual(frappe.db.get_value("Usage Request", res["name"], "reader"), self.profiles[READER])
        # ...and that reader sees it, although the owner is the staff user
        frappe.set_user(READER)
        self.assertIn(res["name"], frappe.get_list("Usage Request", pluck="name"))
        self.assertTrue(frappe.has_permission("Usage Request", "read", doc=res["name"]))

    def test_staff_without_profile_must_choose_a_reader(self):
        frappe.set_user(STAFF_NO_PROFILE)
        with self.assertRaises(frappe.ValidationError):
            req_api.save_request("Usage Request", self._payload(), submit=1)
        res = self._save(STAFF_NO_PROFILE, reader=self.profiles[READER])
        self.assertEqual(res["state"], "Chờ duyệt")  # Document Admin may send for approval

    def test_reader_without_profile_cannot_file(self):
        frappe.set_user(READER_NOPROFILE)
        with self.assertRaises(frappe.PermissionError):
            req_api.save_request("Usage Request", self._payload(), submit=1)

    def test_inactive_reader_cannot_file(self):
        frappe.set_user(INACTIVE)
        with self.assertRaises(frappe.PermissionError):
            req_api.save_request("Usage Request", self._payload(), submit=1)

    def test_feedback_uses_own_profile_for_everyone(self):
        for user in (READER, STAFF_WITH_PROFILE):
            frappe.set_user(user)
            res = req_api.submit_feedback("UI test", "nội dung")
            self.created.append(("Reader Feedback", res["name"]))
            self.assertEqual(frappe.db.get_value("Reader Feedback", res["name"], "reader"), self.profiles[user])

    def test_feedback_without_profile_is_refused(self):
        frappe.set_user(STAFF_NO_PROFILE)
        with self.assertRaises(frappe.PermissionError):
            req_api.submit_feedback("UI test", "nội dung")

    # ---- search / document gating
    def test_search_requires_reader_profile_or_staff(self):
        for user in (READER_NOPROFILE, INACTIVE):
            frappe.set_user(user)
            for fn in (search_api.search_documents, search_api.search_archival_files):
                with self.assertRaises(frappe.PermissionError, msg=f"{user} {fn.__name__}"):
                    fn()
            with self.assertRaises(frappe.PermissionError):
                search_api.search_fulltext(query="x")
            with self.assertRaises(frappe.PermissionError):
                req_api.search_items("file")
        for user in (READER, OFFICER):
            frappe.set_user(user)
            self.assertIn("data", search_api.search_archival_files())
            self.assertIsInstance(req_api.search_items("file"), list)

    def test_fulltext_hits_do_not_carry_content_text(self):
        from unittest.mock import patch
        hit = {"id": "DOC-1", "document_title": "t", "content_text": "secret " * 1000, "_formatted": {}}
        frappe.set_user(READER)
        with patch("document_manager.document_manager.services.search_index.search",
                   return_value={"hits": [hit], "estimatedTotalHits": 1}):
            data = search_api.search_fulltext(query="x")["data"]
        self.assertEqual(len(data), 1)
        self.assertNotIn("content_text", data[0])

    def test_document_without_level_is_hidden_from_readers(self):
        from document_manager.document_manager.permissions import has_archive_document_permission
        doc = frappe._dict(doctype="Archive Document", confidentiality_level=None)
        self.assertFalse(has_archive_document_permission(doc, "read", READER))
        self.assertTrue(has_archive_document_permission(doc, "read", OFFICER))

    def test_preview_points_to_portal_document_page(self):
        docs = frappe.get_all("Archive Document", pluck="name", limit=1)
        if not docs:
            self.skipTest("no Archive Document in the site")
        frappe.set_user(OFFICER)
        self.assertTrue(file_access.get_preview(docs[0])["document_url"].startswith("/portal_document?name="))

    def test_portal_document_page_gates_access(self):
        page = importlib.import_module("document_manager.www.portal_document")
        frappe.set_user("Guest")
        frappe.local.form_dict = frappe._dict(name="DOC-NOPE")
        with self.assertRaises(frappe.Redirect):
            page.get_context(frappe._dict())
        frappe.set_user(READER)
        with self.assertRaises(frappe.PermissionError):
            page.get_context(frappe._dict())  # unknown document: same answer as "not allowed"

    # ---- reader account safety
    def test_officer_cannot_set_reader_password(self):
        frappe.set_user(OFFICER)
        with self.assertRaises(frappe.PermissionError):
            set_reader_password(self.profiles[READER], "Str0ng!Passw0rd#99")

    def test_password_cannot_target_staff_account(self):
        frappe.set_user(ADMIN)
        with self.assertRaises(frappe.PermissionError):
            set_reader_password(self.profiles[STAFF_WITH_PROFILE], "Str0ng!Passw0rd#99")

    def test_deactivating_reader_disables_user_but_never_staff(self):
        frappe.set_user("Administrator")
        reader = frappe.get_doc("Reader", self.profiles[READER])
        reader.is_active = 0
        reader.save()
        self.assertEqual(frappe.db.get_value("User", READER, "enabled"), 0)
        reader.is_active = 1
        reader.save()
        self.assertEqual(frappe.db.get_value("User", READER, "enabled"), 1)

        staff_reader = frappe.get_doc("Reader", self.profiles[STAFF_WITH_PROFILE])
        staff_reader.is_active = 0
        staff_reader.save()
        self.assertEqual(frappe.db.get_value("User", STAFF_WITH_PROFILE, "enabled"), 1)
        self.assertEqual(frappe.db.get_value("User", STAFF_WITH_PROFILE, "user_type"), "System User")
        staff_reader.is_active = 1
        staff_reader.save()

    def test_linking_a_user_later_grants_reader_role(self):
        _user("ui.late@example.com", [], "System User")
        try:
            doc = frappe.get_doc({"doctype": "Reader", "full_name": "UI Late", "email": "ui.late@example.com",
                                  "max_confidentiality_priority": 1, "is_active": 1}).insert()
            doc.user = "ui.late@example.com"
            doc.save()
            self.assertIn("Reader", frappe.get_roles("ui.late@example.com"))
            self.assertEqual(frappe.db.get_value("User", "ui.late@example.com", "user_type"), "Website User")
            frappe.delete_doc("Reader", doc.name, force=True, ignore_permissions=True)
        finally:
            frappe.delete_doc("User", "ui.late@example.com", force=True, ignore_permissions=True)

    # ---- request page context
    def test_request_form_context_for_each_kind_of_user(self):
        from document_manager.www._request_ui import form_context
        frappe.local.form_dict = frappe._dict()
        expect = {
            READER: dict(needs_profile=False, reader_name="UI Reader", select=False),
            READER_NOPROFILE: dict(needs_profile=True, reader_name=None, select=False),
            STAFF_WITH_PROFILE: dict(needs_profile=False, reader_name="UI Staff Reader", select=True),
            STAFF_NO_PROFILE: dict(needs_profile=False, reader_name=None, select=True),
        }
        for user, want in expect.items():
            frappe.set_user(user)
            ctx = frappe._dict()
            form_context(ctx, "usage_requests")
            self.assertEqual(ctx.needs_profile, want["needs_profile"], user)
            self.assertEqual(ctx.reader_name, want["reader_name"], user)
            self.assertEqual(bool(ctx.readers), want["select"], user)
            self.assertEqual(ctx.can_edit, not want["needs_profile"], user)

    def test_form_context_hides_whether_a_request_exists(self):
        from document_manager.www._request_ui import form_context
        mine = self._save(READER)["name"]
        frappe.set_user(READER_NOPROFILE)
        for name in (mine, "UR-9999-99999"):
            frappe.local.form_dict = frappe._dict(name=name)
            with self.assertRaises(frappe.PermissionError, msg=name):
                form_context(frappe._dict(), "usage_requests")
