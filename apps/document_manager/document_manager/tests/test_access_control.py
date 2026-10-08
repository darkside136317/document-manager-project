# -*- coding: utf-8 -*-
"""Access-control tests for the /dashboard (staff) and /portal (staff + Reader) pages.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_access_control
"""

import importlib
import os

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager.doctype.reader.reader import _ensure_website_user
from document_manager.document_manager.permissions import (
    STAFF_ROLES,
    require_portal_user,
    require_staff,
)

STAFF_TEST_ROLES = ["Document Admin", "Cataloger", "Reading Room Officer", "Preservation Officer"]
READER_EMAIL = "ac.reader@example.com"
OUTSIDER_EMAIL = "ac.outsider@example.com"

# Pages only for staff, and pages reader-facing. Derived from the www folder so new pages are covered.
# Pages for readers (and the public pages of the reader site) are tested in test_reader_pages.py.
READER_FACING = {"usage_requests", "copy_requests", "reader_feedbacks", "portal", "search",
                 "don_vi", "dang_nhap", "dang_ky", "quen_mat_khau", "dat_mat_khau"}


def _staff_email(role):
    return f"ac.{role.lower().replace(' ', '.')}@example.com"


def _make_user(email, roles, user_type):
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, force=True, ignore_permissions=True)
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": email.split("@")[0],
        "send_welcome_email": 0,
        "user_type": user_type,
        "roles": [{"role": r} for r in roles],
    })
    user.flags.no_welcome_mail = True
    user.insert(ignore_permissions=True)
    return user


def _redirect_location(fn, *args):
    frappe.local.flags.redirect_location = None
    try:
        fn(*args)
    except frappe.Redirect:
        return frappe.local.flags.redirect_location
    return None


class TestAccessControl(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for role in STAFF_TEST_ROLES + ["Reader"]:
            if not frappe.db.exists("Role", role):
                frappe.get_doc({"doctype": "Role", "role_name": role}).insert(ignore_permissions=True)
        for role in STAFF_TEST_ROLES:
            _make_user(_staff_email(role), [role], "System User")
        _make_user(READER_EMAIL, ["Reader"], "Website User")
        _make_user(OUTSIDER_EMAIL, [], "Website User")

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for email in [_staff_email(r) for r in STAFF_TEST_ROLES] + [READER_EMAIL, OUTSIDER_EMAIL]:
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDownClass()

    def tearDown(self):
        frappe.set_user("Administrator")

    # ---- require_staff ( /dashboard )
    def test_guest_redirected_to_login_from_dashboard(self):
        frappe.set_user("Guest")
        loc = _redirect_location(require_staff)
        self.assertEqual(loc, "/dang-nhap?redirect-to=/dashboard")

    def test_every_staff_role_can_open_dashboard(self):
        for role in STAFF_TEST_ROLES:
            frappe.set_user(_staff_email(role))
            self.assertIsNone(_redirect_location(require_staff), role)

    def test_administrator_can_open_dashboard(self):
        frappe.set_user("Administrator")
        self.assertIsNone(_redirect_location(require_staff))

    def test_reader_cannot_open_dashboard(self):
        frappe.set_user(READER_EMAIL)
        self.assertEqual(_redirect_location(require_staff), "/portal")

    def test_user_without_roles_cannot_open_dashboard(self):
        frappe.set_user(OUTSIDER_EMAIL)
        self.assertEqual(_redirect_location(require_staff), "/portal")

    def test_dashboard_get_context_enforces_gate(self):
        dashboard = importlib.import_module("document_manager.www.dashboard")
        frappe.set_user(READER_EMAIL)
        self.assertEqual(_redirect_location(dashboard.get_context, frappe._dict()), "/portal")
        frappe.set_user(_staff_email("Preservation Officer"))
        self.assertIsNone(_redirect_location(dashboard.get_context, frappe._dict()))

    # ---- require_portal_user ( /portal )
    def test_guest_redirected_to_login_from_portal(self):
        frappe.set_user("Guest")
        self.assertEqual(_redirect_location(require_portal_user), "/dang-nhap?redirect-to=/portal")

    def test_staff_and_reader_can_open_portal(self):
        for email in [_staff_email(r) for r in STAFF_TEST_ROLES] + [READER_EMAIL]:
            frappe.set_user(email)
            self.assertIsNone(_redirect_location(require_portal_user), email)

    def test_user_without_reader_or_staff_role_blocked_from_portal(self):
        frappe.set_user(OUTSIDER_EMAIL)
        with self.assertRaises(frappe.PermissionError):
            require_portal_user()

    # ---- Reader must not get Desk
    def test_reader_is_website_user_without_desk(self):
        self.assertEqual(frappe.db.get_value("User", READER_EMAIL, "user_type"), "Website User")
        for role in STAFF_TEST_ROLES:
            self.assertEqual(frappe.db.get_value("User", _staff_email(role), "user_type"), "System User")

    def test_ensure_website_user_demotes_reader_only_account(self):
        _make_user("ac.demote@example.com", ["Reader"], "System User")
        try:
            _ensure_website_user("ac.demote@example.com")
            self.assertEqual(frappe.db.get_value("User", "ac.demote@example.com", "user_type"), "Website User")
        finally:
            frappe.delete_doc("User", "ac.demote@example.com", force=True, ignore_permissions=True)

    def test_ensure_website_user_keeps_staff_system_user(self):
        _make_user("ac.both@example.com", ["Reader", "Cataloger"], "System User")
        try:
            _ensure_website_user("ac.both@example.com")
            self.assertEqual(frappe.db.get_value("User", "ac.both@example.com", "user_type"), "System User")
        finally:
            frappe.delete_doc("User", "ac.both@example.com", force=True, ignore_permissions=True)

    # ---- staff-only www pages
    def _staff_only_modules(self):
        www = frappe.get_app_path("document_manager", "www")
        mods = []
        for root, _dirs, files in os.walk(www):
            for name in files:
                if not name.endswith(".py") or name.startswith("_"):
                    continue
                folder = os.path.basename(root)
                if folder in READER_FACING or name[:-3] in READER_FACING or name in ("dashboard.py", "portal.py"):
                    continue
                rel = os.path.relpath(os.path.join(root, name), www)[:-3].replace(os.sep, ".")
                mods.append(f"document_manager.www.{rel}")
        return mods

    def test_staff_only_pages_exist_and_are_gated(self):
        mods = self._staff_only_modules()
        self.assertGreater(len(mods), 1)  # guards the discovery itself; almost every staff screen now lives in the SPA
        for mod in mods:
            module = importlib.import_module(mod)
            frappe.set_user("Guest")
            loc = _redirect_location(module.get_context, frappe._dict())
            self.assertTrue(loc and loc.startswith("/dang-nhap"), f"{mod}: guest -> {loc}")
            frappe.set_user(READER_EMAIL)
            loc = _redirect_location(module.get_context, frappe._dict())
            self.assertEqual(loc, "/portal", f"{mod}: reader -> {loc}")

    def test_staff_roles_constant_has_all_business_roles(self):
        for role in STAFF_TEST_ROLES + ["System Manager", "Administrator"]:
            self.assertIn(role, STAFF_ROLES)

    # ---- the staff app's APIs also respect DocType permissions (raw SQL / get_all bypass them)
    def test_staff_without_doctype_permission_is_denied(self):
        from document_manager.document_manager.api import preservation, reports

        frappe.set_user(_staff_email("Cataloger"))
        with self.assertRaises(frappe.PermissionError):
            reports.run_report("doc-gia")  # reader data: not the cataloguer's
        with self.assertRaises(frappe.PermissionError):
            preservation.overview()
