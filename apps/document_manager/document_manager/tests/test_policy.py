# -*- coding: utf-8 -*-
"""Reader groups and the access policy: scope, features, fonds scope, clearance override.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_policy
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager.api import file_access, requests as req_api
from document_manager.document_manager.permissions import assert_can_search
from document_manager.document_manager.policy import UNLIMITED_PRIORITY, get_reader_scope
from document_manager.document_manager.services import search_index
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _reader, _seed_archive, _user

TAG = "pol"
READER_OPEN = f"{TAG}.open@example.com"          # default group
READER_CAPPED = f"{TAG}.capped@example.com"      # group with no features and a single fonds
READER_OVERRIDE = f"{TAG}.override@example.com"  # personal clearance above the group's
READER_NOGROUPFLAGS = f"{TAG}.nogroup@example.com"
OFFICER = f"{TAG}.officer@example.com"
ADMIN = f"{TAG}.admin@example.com"
STAFF_PROFILE = f"{TAG}.staff@example.com"
USERS = (READER_OPEN, READER_CAPPED, READER_OVERRIDE, READER_NOGROUPFLAGS, OFFICER, ADMIN, STAFF_PROFILE)
LEVEL = "POL Secret"
GROUP_CAPPED = "POL Capped"
GROUP_WIDE = "POL Wide"


class TestPolicy(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.ensure_roles()
        install.ensure_confidentiality_levels()
        install.ensure_default_reader_group()
        _user(READER_OPEN, ["Reader"], "Website User")
        _user(READER_CAPPED, ["Reader"], "Website User")
        _user(READER_OVERRIDE, ["Reader"], "Website User")
        _user(READER_NOGROUPFLAGS, ["Reader"], "Website User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(ADMIN, ["Document Admin"], "System User")
        _user(STAFF_PROFILE, ["Document Admin", "Reader"], "System User")

        if not frappe.db.exists("Confidentiality Level", LEVEL):
            frappe.get_doc({"doctype": "Confidentiality Level", "level_name": LEVEL, "priority": 8}
                           ).insert(ignore_permissions=True)

        # two separate trees = two fonds
        cls._seed_a = _seed_archive(2)
        cls._seed_b = _seed_archive(1)
        cls.fonds_a = _names(cls._seed_a, "Fonds")[0]
        cls.fonds_b = _names(cls._seed_b, "Fonds")[0]
        cls.files_a = _names(cls._seed_a, "Archival File")
        cls.file_b = _names(cls._seed_b, "Archival File")[0]
        cls.docs_a = _names(cls._seed_a, "Archive Document")
        cls.doc_b = _names(cls._seed_b, "Archive Document")[0]

        frappe.get_doc({
            "doctype": "Reader Group", "group_name": GROUP_CAPPED, "max_confidentiality_priority": 1,
            "fonds_scope": "Chỉ các phông được chọn", "fonds_scopes": [{"fonds": cls.fonds_a}],
            "can_search": 1, "can_preview": 1, "can_download": 0,
            "can_request_usage": 0, "can_request_copy": 1, "can_feedback": 0,
        }).insert(ignore_permissions=True)
        frappe.get_doc({"doctype": "Reader Group", "group_name": GROUP_WIDE, "max_confidentiality_priority": 8,
                        }).insert(ignore_permissions=True)

        cls.profiles = {
            READER_OPEN: _reader(READER_OPEN, "POL Open"),
            READER_CAPPED: _reader(READER_CAPPED, "POL Capped"),
            READER_OVERRIDE: _reader(READER_OVERRIDE, "POL Override"),
            STAFF_PROFILE: _reader(STAFF_PROFILE, "POL Staff"),
        }
        frappe.db.set_value("Reader", cls.profiles[READER_OPEN], {"reader_group": None, "max_confidentiality_priority": 0})
        frappe.db.set_value("Reader", cls.profiles[READER_CAPPED], {"reader_group": GROUP_CAPPED,
                                                                    "max_confidentiality_priority": 0})
        frappe.db.set_value("Reader", cls.profiles[READER_OVERRIDE], {"reader_group": GROUP_CAPPED,
                                                                      "max_confidentiality_priority": 2})
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
        for name in (GROUP_CAPPED, GROUP_WIDE):
            frappe.delete_doc("Reader Group", name, force=True, ignore_permissions=True)
        for made in (cls._seed_a, cls._seed_b):
            for dt, name in made:
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        frappe.delete_doc("Confidentiality Level", LEVEL, force=True, ignore_permissions=True)
        for email in USERS:
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)

    def tearDown(self):
        frappe.set_user("Administrator")

    def _visible(self, doctype, user):
        frappe.set_user(user)
        return set(frappe.get_list(doctype, pluck="name", limit_page_length=0))

    # ---- the scope object
    def test_guest_staff_and_profileless_scopes(self):
        self.assertFalse(get_reader_scope("Guest").allowed)
        for staff in (OFFICER, ADMIN, "Administrator"):
            scope = get_reader_scope(staff)
            self.assertTrue(scope.is_staff and scope.allowed and scope.can_download, staff)
            self.assertEqual((scope.max_priority, scope.fonds), (UNLIMITED_PRIORITY, None))
        self.assertFalse(get_reader_scope(READER_NOGROUPFLAGS).allowed)  # Reader role, but no profile

    def test_default_group_applies_when_a_reader_has_none(self):
        scope = get_reader_scope(READER_OPEN)
        self.assertTrue(scope.allowed)
        self.assertEqual(scope.group, frappe.db.get_value("Reader Group", {"is_default": 1}, "name"))
        self.assertEqual((scope.max_priority, scope.fonds), (1, None))
        self.assertTrue(scope.can_search and scope.can_download)

    def test_group_defines_features_and_fonds(self):
        scope = get_reader_scope(READER_CAPPED)
        self.assertEqual(scope.group, GROUP_CAPPED)
        self.assertEqual(scope.fonds, [self.fonds_a])
        self.assertTrue(scope.can_search and scope.can_request_copy)
        self.assertFalse(scope.can_download or scope.can_request_usage or scope.can_feedback)

    def test_personal_clearance_overrides_the_group_for_that_reader_only(self):
        self.assertEqual(get_reader_scope(READER_OVERRIDE).max_priority, 2)
        self.assertEqual(get_reader_scope(READER_CAPPED).max_priority, 1)

    def test_disabled_group_and_inactive_reader_get_nothing(self):
        frappe.db.set_value("Reader Group", GROUP_CAPPED, "is_active", 0)
        try:
            self.assertFalse(get_reader_scope(READER_CAPPED).allowed)
        finally:
            frappe.db.set_value("Reader Group", GROUP_CAPPED, "is_active", 1)
        frappe.db.set_value("Reader", self.profiles[READER_OPEN], "is_active", 0)
        try:
            self.assertFalse(get_reader_scope(READER_OPEN).allowed)
        finally:
            frappe.db.set_value("Reader", self.profiles[READER_OPEN], "is_active", 1)

    def test_group_validation_and_single_default(self):
        with self.assertRaises(frappe.ValidationError):  # fonds scope without any fonds
            frappe.get_doc({"doctype": "Reader Group", "group_name": "POL Bad",
                            "fonds_scope": "Chỉ các phông được chọn"}).insert(ignore_permissions=True)
        default = frappe.db.get_value("Reader Group", {"is_default": 1}, "name")
        wide = frappe.get_doc("Reader Group", GROUP_WIDE)
        wide.is_default = 1
        wide.save()
        self.assertEqual(frappe.db.get_value("Reader Group", default, "is_default"), 0)
        self.assertEqual(frappe.db.count("Reader Group", {"is_default": 1}), 1)
        with self.assertRaises(frappe.ValidationError):  # the default group cannot be deleted
            frappe.delete_doc("Reader Group", GROUP_WIDE, ignore_permissions=True)
        wide.is_default = 0
        wide.save()
        frappe.db.set_value("Reader Group", default, "is_default", 1)

    # ---- fonds scope, in every query
    def test_fonds_scope_limits_the_hierarchy_and_the_content(self):
        files = self._visible("Archival File", READER_CAPPED)
        self.assertTrue(set(self.files_a) <= files)
        self.assertNotIn(self.file_b, files)
        self.assertIn(self.docs_a[0], self._visible("Archive Document", READER_CAPPED))
        self.assertNotIn(self.doc_b, self._visible("Archive Document", READER_CAPPED))
        self.assertEqual(self._visible("Fonds", READER_CAPPED) & {self.fonds_a, self.fonds_b}, {self.fonds_a})
        # the unrestricted reader sees both trees
        self.assertTrue({self.file_b, *self.files_a} <= self._visible("Archival File", READER_OPEN))
        self.assertTrue({self.fonds_a, self.fonds_b} <= self._visible("Fonds", READER_OPEN))

    def test_has_permission_follows_the_fonds_scope(self):
        frappe.set_user(READER_CAPPED)
        self.assertTrue(frappe.has_permission("Archival File", "read", doc=self.files_a[0]))
        self.assertFalse(frappe.has_permission("Archival File", "read", doc=self.file_b))
        self.assertFalse(frappe.has_permission("Archive Document", "read", doc=self.doc_b))
        self.assertFalse(frappe.has_permission("Fonds", "read", doc=self.fonds_b))

    def test_a_reader_without_a_profile_reads_nothing_through_the_resource_api(self):
        for doctype in ("Archival File", "Archive Document", "Fonds", "Record Group", "Catalog"):
            self.assertEqual(self._visible(doctype, READER_NOGROUPFLAGS), set(), doctype)

    def test_meilisearch_filter_is_built_from_the_scope(self):
        index = MagicMock()
        index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
        with patch.object(search_index, "_get_index", return_value=index):
            frappe.set_user(READER_CAPPED)
            search_index.search("x")
            flt = index.search.call_args[0][1]["filter"]
            self.assertIn("is_published = true", flt)
            self.assertIn("confidentiality_priority <= 1", flt)
            self.assertIn(f'fonds IN ["{self.fonds_a}"]', flt)

            frappe.set_user(READER_OVERRIDE)
            search_index.search("x")
            self.assertIn("confidentiality_priority <= 2", index.search.call_args[0][1]["filter"])

            frappe.set_user(OFFICER)
            search_index.search("x")
            self.assertNotIn("filter", index.search.call_args[0][1])  # staff: no restriction

            index.search.reset_mock()
            frappe.set_user(READER_NOGROUPFLAGS)
            self.assertEqual(search_index.search("x")["hits"], [])
            index.search.assert_not_called()  # the engine is not even asked

    # ---- features
    def test_search_needs_the_search_feature(self):
        frappe.db.set_value("Reader Group", GROUP_CAPPED, "can_search", 0)
        try:
            frappe.set_user(READER_CAPPED)
            with self.assertRaises(frappe.PermissionError):
                assert_can_search()
        finally:
            frappe.db.set_value("Reader Group", GROUP_CAPPED, "can_search", 1)

    def test_download_and_preview_are_separate_features(self):
        frappe.set_user(READER_CAPPED)
        doc = self.docs_a[0]
        with self.assertRaises(frappe.PermissionError):
            file_access.download_file(doc)  # can_download = 0
        preview = file_access.get_preview(doc)  # can_preview = 1
        self.assertIsNone(preview["download_url"])
        frappe.set_user(READER_OPEN)
        self.assertTrue(file_access.get_preview(doc)["download_url"])

    def test_requests_and_feedback_need_the_matching_feature(self):
        import json
        payload = json.dumps({"items": [{"archival_file": self.files_a[0]}]})
        frappe.set_user(READER_CAPPED)
        with self.assertRaises(frappe.PermissionError):
            req_api.save_request("Usage Request", payload)  # can_request_usage = 0
        with self.assertRaises(frappe.PermissionError):
            req_api.submit_feedback("POL", "x")  # can_feedback = 0
        res = req_api.save_request("Copy Request", payload)  # can_request_copy = 1
        self.created.append(("Copy Request", res["name"]))
        frappe.set_user(READER_OPEN)
        res = req_api.save_request("Usage Request", payload)
        self.created.append(("Usage Request", res["name"]))
        # staff may still file on behalf of a reader whose group forbids it
        frappe.set_user(ADMIN)
        res = req_api.save_request("Usage Request", json.dumps(
            {"reader": self.profiles[READER_CAPPED], "items": [{"archival_file": self.files_a[0]}]}))
        self.created.append(("Usage Request", res["name"]))

    # ---- who may change a reader's access
    def test_only_admins_can_change_group_and_clearance(self):
        profile = self.profiles[READER_OPEN]
        frappe.set_user(OFFICER)
        reader = frappe.get_doc("Reader", profile)
        reader.reader_group = GROUP_WIDE
        reader.max_confidentiality_priority = 8
        reader.save()
        self.assertNotEqual(frappe.db.get_value("Reader", profile, "reader_group"), GROUP_WIDE)
        self.assertEqual(frappe.db.get_value("Reader", profile, "max_confidentiality_priority"), 0)

        frappe.set_user(ADMIN)
        reader = frappe.get_doc("Reader", profile)
        reader.reader_group = GROUP_WIDE
        reader.max_confidentiality_priority = 3
        reader.save()
        self.assertEqual(frappe.db.get_value("Reader", profile, "reader_group"), GROUP_WIDE)
        self.assertEqual(frappe.db.get_value("Reader", profile, "max_confidentiality_priority"), 3)

    def test_an_officer_can_create_a_reader_who_lands_in_the_default_group(self):
        frappe.set_user(OFFICER)
        reader = frappe.get_doc({"doctype": "Reader", "full_name": "POL Created", "is_active": 1}).insert()
        self.created.append(("Reader", reader.name))
        self.assertEqual(reader.reader_group, frappe.db.get_value("Reader Group", {"is_default": 1}, "name"))
        self.assertEqual(reader.max_confidentiality_priority, 0)
