# -*- coding: utf-8 -*-
"""Permission groups (Staff Role Profile) and capabilities: who may use the functions that are not a DocType.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_permission_profiles
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager import policy
from document_manager.document_manager.api import boot, exchange, logs, permissions, preservation, slips, users
from document_manager.document_manager.constants import BUILTIN_CAPABILITIES, CAPABILITY_CODES
from document_manager.document_manager.services import permission_matrix
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _user

TAG = frappe.generate_hash(length=5).lower()
ADMIN = f"pp.admin.{TAG}@example.com"
SYSMAN = f"pp.sysman.{TAG}@example.com"
LEADER = f"pp.leader.{TAG}@example.com"
OFFICER = f"pp.officer.{TAG}@example.com"
CATALOGER = f"pp.cataloger.{TAG}@example.com"
PRESERVER = f"pp.preserver.{TAG}@example.com"
CUSTOM = f"pp.custom.{TAG}@example.com"
READER = f"pp.reader.{TAG}@example.com"
CUSTOM_ROLE = f"PP Kiểm soát {TAG}"
USERS = (ADMIN, SYSMAN, LEADER, OFFICER, CATALOGER, PRESERVER, CUSTOM, READER)


class TestPermissionProfiles(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        if not frappe.db.exists("Role", CUSTOM_ROLE):
            frappe.get_doc({"doctype": "Role", "role_name": CUSTOM_ROLE, "desk_access": 1}).insert(ignore_permissions=True)
        _user(ADMIN, ["Document Admin"], "System User")
        _user(SYSMAN, ["System Manager"], "System User")
        _user(LEADER, ["Archive Leader"], "System User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(CATALOGER, ["Cataloger"], "System User")
        _user(PRESERVER, ["Preservation Officer"], "System User")
        _user(CUSTOM, [CUSTOM_ROLE], "System User")
        _user(READER, ["Reader"], "Website User")
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        frappe.delete_doc("Staff Role Profile", CUSTOM_ROLE, force=True, ignore_permissions=True, ignore_missing=True)
        for email in USERS:
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.delete_doc("Role", CUSTOM_ROLE, force=True, ignore_permissions=True, ignore_missing=True)
        frappe.db.commit()
        policy.clear_cache()
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user("Administrator")
        frappe.db.savepoint("pp_test")
        policy.clear_cache()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="pp_test")
        policy.clear_cache()

    def custom_profile(self, *capabilities):
        return frappe.get_doc({"doctype": "Staff Role Profile", "role": CUSTOM_ROLE, "label": f"Kiểm soát {TAG}",
                               "capabilities": [{"capability": c} for c in capabilities]}).insert(ignore_permissions=True)

    # ---- seeding
    def test_every_staff_role_is_a_built_in_group_with_the_functions_it_had(self):
        profiles = {p.name: p for p in frappe.get_all("Staff Role Profile", fields=["name", "is_builtin", "is_admin"])}
        for role in ("Document Admin", "Archive Leader", "Cataloger", "Reading Room Officer", "Preservation Officer"):
            self.assertTrue(profiles[role].is_builtin, role)
        self.assertTrue(profiles["Document Admin"].is_admin)
        for role, expected in BUILTIN_CAPABILITIES.items():
            got = set(frappe.get_all("Staff Role Capability", filters={"parent": role}, pluck="capability"))
            self.assertEqual(got, set(expected), role)
        self.assertEqual(install.ensure_staff_role_profiles(), 0)  # repeatable, never overwrites

    def test_the_built_in_groups_keep_who_may_do_what(self):
        self.assertTrue(policy.has_capability("slips.leader_approve", user=LEADER))
        self.assertFalse(policy.has_capability("slips.receive", user=LEADER))
        self.assertTrue(policy.has_capability("slips.receive", "readers.registrations", user=OFFICER))
        self.assertTrue(policy.has_capability("inventory.manage", user=CATALOGER))
        self.assertFalse(policy.has_capability("inventory.reopen", "logs.view", "exchange.export", user=CATALOGER))
        self.assertEqual({c for c in policy.capabilities_of(PRESERVER) if c.startswith("preservation.")},
                         {"preservation.backup", "preservation.check", "preservation.restore", "preservation.db_restore"})
        self.assertEqual(policy.capabilities_of(READER), frozenset())

    def test_administrators_hold_every_function(self):
        for user in ("Administrator", ADMIN, SYSMAN):
            self.assertTrue(policy.is_admin(user))
            self.assertTrue(CAPABILITY_CODES <= policy.capabilities_of(user))
            self.assertTrue(policy.has_capability("users.manage", user=user))
        self.assertFalse(policy.is_admin(LEADER))
        self.assertFalse(policy.has_capability("users.manage", user=LEADER))

    # ---- a custom group
    def test_a_custom_group_makes_its_members_staff_with_exactly_its_functions(self):
        self.assertFalse(policy.is_staff(CUSTOM))
        self.custom_profile("logs.view", "exchange.export")
        self.assertTrue(policy.is_staff(CUSTOM))
        self.assertEqual(policy.capabilities_of(CUSTOM), frozenset({"logs.view", "exchange.export"}))
        frappe.set_user(CUSTOM)
        self.assertIn("data", logs.list_logs())
        self.assertIn("levels", exchange.capabilities())
        with self.assertRaises(frappe.PermissionError):
            logs.preview_purge("2020-01-01")  # the clean-up is logs.purge
        with self.assertRaises(frappe.PermissionError):
            exchange.analyze_import("/private/files/x.xml")  # importing is exchange.import
        with self.assertRaises(frappe.PermissionError):
            preservation.overview()
        nav = [item["route"] for group in boot.build_boot()["nav"] for item in group["items"]]
        self.assertIn("/dashboard/quan-tri/nhat-ky", nav)
        self.assertIn("/dashboard/trao-doi-du-lieu", nav)
        self.assertNotIn("/dashboard/quan-tri/nguoi-dung", nav)
        self.assertNotIn("/dashboard/bao-quan/sao-luu", nav)

    def test_editing_a_group_takes_effect_at_once(self):
        profile = self.custom_profile("slips.view")
        frappe.set_user(CUSTOM)
        self.assertIn("usage", slips.queue_summary())
        frappe.set_user("Administrator")
        profile.set("capabilities", [])
        profile.save(ignore_permissions=True)
        frappe.set_user(CUSTOM)
        with self.assertRaises(frappe.PermissionError):
            slips.queue_summary()

    def test_a_group_only_lists_known_functions_and_never_the_administrators_own(self):
        with self.assertRaises(frappe.ValidationError):
            self.custom_profile("does.not.exist")
        with self.assertRaises(frappe.ValidationError):
            self.custom_profile("users.manage")
        with self.assertRaises(frappe.ValidationError):
            self.custom_profile("logs.view", "logs.view")
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({"doctype": "Staff Role Profile", "role": "System Manager", "label": "x"}).insert(ignore_permissions=True)

    def test_the_administrators_group_lists_nothing_and_built_in_groups_stay(self):
        admin = frappe.get_doc("Staff Role Profile", "Document Admin")
        admin.append("capabilities", {"capability": "logs.view"})
        admin.save(ignore_permissions=True)
        self.assertEqual(admin.capabilities, [])
        with self.assertRaises(frappe.ValidationError):
            frappe.delete_doc("Staff Role Profile", "Cataloger", ignore_permissions=True)

    # ---- the gates
    def test_people_outside_a_function_are_refused_with_the_same_message(self):
        frappe.set_user(CATALOGER)
        for call in (logs.list_logs, preservation.overview, slips.queue_summary, users.list_users, exchange.capabilities):
            with self.assertRaises(frappe.PermissionError) as caught:
                call()
            self.assertIn("không có quyền", str(caught.exception))

    def test_a_restore_needs_the_capability_of_its_kind(self):
        self.custom_profile("preservation.restore")
        frappe.set_user(CUSTOM)
        with self.assertRaises(frappe.PermissionError):
            preservation.start_backup()
        with self.assertRaises(frappe.PermissionError):
            preservation.prepare_db_restore("BK-x")

    def test_a_leader_who_also_works_the_reading_room_opens_on_reception(self):
        frappe.set_user(LEADER)
        self.assertEqual(slips.default_view(), "cho_lanh_dao")
        frappe.set_user(OFFICER)
        self.assertEqual(slips.default_view(), "cho_tiep_nhan")

    def test_slip_notifications_go_to_the_groups_that_handle_them(self):
        self.assertIn(LEADER, policy.users_with_capability("slips.leader_approve"))
        self.assertNotIn(ADMIN, policy.users_with_capability("slips.leader_approve"))
        self.assertIn(OFFICER, policy.users_with_capability("slips.receive"))

    def test_the_boot_tells_the_staff_app_what_the_user_may_do(self):
        frappe.set_user(OFFICER)
        data = boot.build_boot()
        self.assertIn("slips.receive", data["user"]["capabilities"])
        self.assertNotIn("logs.view", data["user"]["capabilities"])

    def test_access_answers_for_every_kind_of_user(self):
        self.assertEqual(policy.get_access("Guest").kind, "guest")
        self.assertEqual(policy.get_access(ADMIN).kind, "admin")
        staff = policy.get_access(CATALOGER)
        self.assertEqual((staff.kind, staff.read_fonds, staff.write_fonds), ("staff", None, None))
        reader = policy.get_access(READER)
        self.assertEqual((reader.kind, reader.write_fonds), ("reader", []))


class TestPermissionMatrix(IntegrationTestCase):
    """Editing a group: its rules on each kind of data land in Frappe's own permission rules and are enforced."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        _user(ADMIN, ["Document Admin"], "System User")
        _user(CATALOGER, ["Cataloger"], "System User")
        _user(CUSTOM, [], "System User")
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for email in (ADMIN, CATALOGER, CUSTOM):
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.db.commit()
        _forget_caches()
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user("Administrator")
        frappe.db.savepoint("pm_test")
        _forget_caches()
        frappe.set_user(ADMIN)

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="pm_test")
        _forget_caches()

    def cell(self, matrix, doctype):
        return next(row["cell"] for section in matrix for row in section["rows"] if row["doctype"] == doctype)

    def give(self, user, role):
        frappe.set_user("Administrator")
        frappe.get_doc("User", user).add_roles(role)
        frappe.set_user(ADMIN)

    def test_only_administrators_manage_groups(self):
        frappe.set_user(CATALOGER)
        for call in (permissions.list_groups, lambda: permissions.get_group("Cataloger"),
                     lambda: permissions.create_group("PP x"), lambda: permissions.save_group("Cataloger", {})):
            with self.assertRaises(frappe.PermissionError):
                call()

    def test_the_matrix_shows_the_rules_in_force(self):
        group = permissions.get_group("Cataloger")
        self.assertEqual(group["label"], "Biên mục viên")
        fonds = self.cell(group["matrix"], "Fonds")
        self.assertEqual((fonds["read"], fonds["create"], fonds["write"], fonds["delete"]), (True, True, True, False))
        self.assertFalse(self.cell(group["matrix"], "Reader")["read"])
        columns = {row["doctype"]: row["columns"] for s in group["matrix"] for row in s["rows"]}
        self.assertIn("submit", columns["Usage Request"])
        self.assertNotIn("submit", columns["Fonds"])
        self.assertIn("sensitive", columns["Reader"])
        caps = {i["code"]: i["checked"] for m in group["capabilities"] for i in m["items"]}
        self.assertTrue(caps["inventory.manage"])
        self.assertFalse(caps["logs.view"])
        self.assertIn(CATALOGER, [m["name"] for m in group["members"]])

    def test_taking_a_right_away_is_enforced_by_frappe_and_reset_puts_it_back(self):
        self.assertTrue(frappe.has_permission("Archival File", "delete", user=CATALOGER))
        permissions.save_group("Cataloger", {"matrix": {"Archival File": {"read": 1, "create": 1, "write": 1, "delete": 0}}})
        self.assertTrue(frappe.db.exists("Custom DocPerm", {"parent": "Archival File", "role": "Cataloger"}))
        self.assertFalse(frappe.has_permission("Archival File", "delete", user=CATALOGER))
        self.assertTrue(frappe.has_permission("Archival File", "write", user=CATALOGER))
        self.assertTrue(frappe.has_permission("Archival File", "delete", user=ADMIN))  # other roles keep their rules
        self.assertTrue(frappe.db.exists("Business Activity Log", {"reference_doctype": "Staff Role Profile", "reference_name": "Cataloger"}))
        permissions.reset_group("Cataloger")
        self.assertTrue(frappe.has_permission("Archival File", "delete", user=CATALOGER))
        self.assertFalse(frappe.db.exists("Custom DocPerm", {"parent": "Archival File"}))  # back to the standard rules entirely

    def test_any_right_brings_reading_and_no_reading_means_nothing(self):
        role = permissions.create_group(f"PP Nhóm {TAG}")["role"]
        permissions.save_group(role, {"matrix": {"Fonds": {"write": 1}}})
        cell = self.cell(permissions.get_group(role)["matrix"], "Fonds")
        self.assertEqual((cell["read"], cell["write"], cell["delete"]), (True, True, False))
        permissions.save_group(role, {"matrix": {"Fonds": {"read": 0, "write": 1}}})
        self.assertFalse(any(self.cell(permissions.get_group(role)["matrix"], "Fonds").values()))

    def test_a_new_group_makes_its_members_staff_with_only_its_rights(self):
        group = permissions.create_group(f"PP Tra cứu {TAG}", description="Chỉ xem")
        role = group["role"]
        self.assertTrue(frappe.db.exists("Role", role))
        self.assertFalse(group["is_builtin"])
        permissions.save_group(role, {"matrix": {"Archival File": {"read": 1}}, "capabilities": ["logs.view"]})
        self.give(CUSTOM, role)
        self.assertTrue(policy.is_staff(CUSTOM))
        self.assertTrue(frappe.has_permission("Archival File", "read", user=CUSTOM))
        self.assertFalse(frappe.has_permission("Archival File", "write", user=CUSTOM))
        self.assertFalse(frappe.has_permission("Fonds", "read", user=CUSTOM))
        self.assertEqual(policy.capabilities_of(CUSTOM), frozenset({"logs.view"}))
        self.assertIn(role, [r["role"] for r in users.roles_info()])  # it can be given on the users screen

    def test_a_group_copied_from_another_starts_with_the_same_rights(self):
        group = permissions.create_group(f"PP Biên mục 2 {TAG}", copy_from="Cataloger")
        source = permissions.get_group("Cataloger")
        for section in source["matrix"]:
            for row in section["rows"]:
                self.assertEqual(self.cell(group["matrix"], row["doctype"]), row["cell"], row["doctype"])
        caps = {i["code"] for m in group["capabilities"] for i in m["items"] if i["checked"]}
        self.assertEqual(caps, {"inventory.manage"})

    def test_only_my_own_records(self):
        role = permissions.create_group(f"PP Riêng {TAG}")["role"]
        permissions.save_group(role, {"matrix": {"Archival Agency": {"read": 1, "create": 1, "write": 1, "own_only": 1}}})
        self.give(CUSTOM, role)
        frappe.set_user("Administrator")
        theirs = frappe.get_doc({"doctype": "Archival Agency", "agency_name": f"PP Cơ quan {TAG}"}).insert()
        self.assertFalse(frappe.has_permission("Archival Agency", "write", doc=theirs, user=CUSTOM))
        frappe.set_user(CUSTOM)
        mine = frappe.get_doc({"doctype": "Archival Agency", "agency_name": f"PP Của tôi {TAG}"}).insert()
        self.assertTrue(frappe.has_permission("Archival Agency", "write", doc=mine, user=CUSTOM))

    def test_the_protected_fields_follow_the_sensitive_column(self):
        role = permissions.create_group(f"PP Độc giả {TAG}")["role"]
        permissions.save_group(role, {"matrix": {"Reader": {"read": 1, "write": 1}}})
        rows = frappe.get_all("Custom DocPerm", filters={"parent": "Reader", "role": role}, fields=["permlevel", "read", "write"])
        self.assertEqual({(r.permlevel, r.read, r.write) for r in rows}, {(0, 1, 1), (1, 1, 0)})
        permissions.save_group(role, {"matrix": {"Reader": {"read": 1, "write": 1, "sensitive": 1}}})
        rows = frappe.get_all("Custom DocPerm", filters={"parent": "Reader", "role": role}, fields=["permlevel", "write"])
        self.assertIn((1, 1), {(r.permlevel, r.write) for r in rows})

    def test_a_group_that_receives_slips_can_move_them_in_the_workflow(self):
        role = permissions.create_group(f"PP Phòng đọc 2 {TAG}")["role"]

        def allowed():
            frappe.clear_document_cache("Workflow", "Usage Request Workflow")
            return {t.allowed for t in frappe.get_doc("Workflow", "Usage Request Workflow").transitions if t.action == "Giao tài liệu"}

        self.assertNotIn(role, allowed())
        permissions.save_group(role, {"capabilities": ["slips.view", "slips.receive"]})
        self.assertIn(role, allowed())
        self.assertIn("Reading Room Officer", allowed())
        permissions.delete_group(role)
        self.assertNotIn(role, allowed())
        self.assertFalse(frappe.db.exists("Role", role))

    def test_groups_in_use_and_built_in_groups_are_not_deleted(self):
        group = permissions.create_group(f"PP Đang dùng {TAG}")
        self.give(CUSTOM, group["role"])
        with self.assertRaises(frappe.ValidationError):
            permissions.delete_group(group["role"])
        with self.assertRaises(frappe.ValidationError):
            permissions.delete_group("Cataloger")
        with self.assertRaises(frappe.ValidationError):
            permissions.reset_group(group["role"])  # only a built-in group has defaults

    def test_the_administrators_group_cannot_be_changed(self):
        with self.assertRaises(frappe.ValidationError):
            permissions.save_group("Document Admin", {"capabilities": []})
        with self.assertRaises(frappe.PermissionError):
            permission_matrix.set_cell("Fonds", "Document Admin", {"read": 1})
        group = permissions.get_group("Document Admin")
        self.assertTrue(group["locked"])
        self.assertEqual(group["label"], "Quản trị viên")

    def test_names_and_a_stale_edit_are_checked(self):
        with self.assertRaises(frappe.ValidationError):
            permissions.create_group("x")
        with self.assertRaises(frappe.ValidationError):
            permissions.create_group("Cataloger")  # an existing role
        group = permissions.get_group("Cataloger")
        with self.assertRaises(frappe.ValidationError):
            permissions.save_group("Cataloger", {"description": "khác", "modified": "2000-01-01 00:00:00"})
        permissions.save_group("Cataloger", {"description": "khác", "modified": group["modified"]})

    def test_the_list_counts_the_members_of_each_group(self):
        counts = {g["role"]: g for g in permissions.list_groups()}
        self.assertGreaterEqual(counts["Cataloger"]["members"], 1)
        self.assertTrue(counts["Document Admin"]["is_admin"])
        self.assertEqual(list(counts)[:5], ["Document Admin", "Cataloger", "Reading Room Officer", "Archive Leader", "Preservation Officer"])


def _forget_caches():
    """Permission rules and workflows live in Frappe's caches too: after a rollback they must be read again."""
    frappe.clear_cache()
    frappe.local.role_permissions = {}
    for name in ("Usage Request Workflow", "Copy Request Workflow", "Reader Feedback Workflow"):
        frappe.clear_document_cache("Workflow", name)
    policy.clear_cache()
