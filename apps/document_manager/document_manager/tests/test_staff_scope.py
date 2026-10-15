# -*- coding: utf-8 -*-
"""Scopes of the staff (P3 of permissions v2): the fonds a staff member reads and changes, the highest level they read,
sealed records, protected fields, and every place that must honour them (lists, search, reports, preservation, API).

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_staff_scope
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager import policy
from document_manager.document_manager.api import crud, permissions as perm_api, preservation, users
from document_manager.document_manager.services import reports, search_service
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _seed_archive, _user

TAG = frappe.generate_hash(length=5).lower()
ADMIN = f"ss.admin.{TAG}@example.com"
CATALOGER = f"ss.cataloger.{TAG}@example.com"
OTHER = f"ss.other.{TAG}@example.com"
CUSTOM_ROLE = f"SS Biên mục hẹp {TAG}"
USERS = (ADMIN, CATALOGER, OTHER)


class TestStaffScope(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        _user(ADMIN, ["Document Admin"], "System User")
        _user(CATALOGER, ["Cataloger"], "System User")
        _user(OTHER, ["Cataloger"], "System User")
        cls.seeded = []
        cls.fonds = []
        for _ in range(3):
            made = _seed_archive(1)
            cls.seeded += made
            cls.fonds.append(_names(made, "Fonds")[0])
        cls.a, cls.b, cls.c = cls.fonds
        cls.file_of = {f: frappe.db.get_value("Archival File", {"fonds": f}, "name") for f in cls.fonds}
        cls.doc_of = {f: frappe.db.get_value("Archive Document", {"fonds": f}, "name") for f in cls.fonds}
        cls.catalog_of = {f: frappe.db.get_value("Catalog", {"fonds": f}, "name") for f in cls.fonds}
        cls.group_of = {f: frappe.db.get_value("Record Group", {"fonds": f}, "name") for f in cls.fonds}
        # a confidential file in fonds A
        secret = frappe.get_doc({"doctype": "Archival File", "file_title": f"SS Mật {TAG}", "fonds": cls.a,
                                 "record_group": cls.group_of[cls.a], "catalog": cls.catalog_of[cls.a],
                                 "confidentiality_level": "Mật", "status": "Đã hoàn thành"}).insert(ignore_permissions=True)
        cls.secret = secret.name
        cls.seeded.insert(0, ("Archival File", secret.name))
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for doctype, name in cls.seeded:
            frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        for email in USERS:
            frappe.delete_doc("Staff Access", email, force=True, ignore_permissions=True, ignore_missing=True)
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.db.commit()
        policy.clear_cache()
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user("Administrator")
        frappe.db.savepoint("ss_test")
        policy.clear_cache()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="ss_test")
        frappe.clear_cache()
        frappe.local.role_permissions = {}
        policy.clear_cache()

    # helpers
    def scope(self, user=CATALOGER, read=None, write=None, level=0):
        """read/write: None = every fonds (write None = like reading), else a list of fonds."""
        frappe.set_user("Administrator")
        doc = frappe.get_doc({"doctype": "Staff Access", "user": user,
                              "read_scope": "Tất cả phông" if read is None else "Chỉ các phông được chọn",
                              "write_scope": "Như phạm vi xem" if write is None else "Chỉ các phông được chọn",
                              "read_fonds": [{"fonds": f} for f in read or []], "write_fonds": [{"fonds": f} for f in write or []],
                              "max_confidentiality_priority": level})
        doc.insert(ignore_permissions=True)
        return doc

    def visible_files(self, user=CATALOGER):
        frappe.set_user(user)
        names = set(frappe.get_list("Archival File", pluck="name", limit_page_length=0))
        return {f for f, file in self.file_of.items() if file in names}

    # ---- the scope itself
    def test_without_a_scope_a_staff_member_reads_and_changes_every_fonds(self):
        access = policy.get_access(CATALOGER)
        self.assertEqual((access.kind, access.read_fonds, access.write_fonds), ("staff", None, None))
        self.assertEqual(self.visible_files(), {self.a, self.b, self.c})
        self.assertTrue(frappe.has_permission("Archival File", "write", doc=self.file_of[self.c], user=CATALOGER))

    def test_reading_and_changing_are_scoped_apart(self):
        self.scope(read=[self.a, self.b], write=[self.a])
        access = policy.get_access(CATALOGER)
        self.assertEqual((sorted(access.read_fonds), access.write_fonds), (sorted([self.a, self.b]), [self.a]))
        self.assertEqual(self.visible_files(), {self.a, self.b})
        frappe.set_user(CATALOGER)
        self.assertTrue(frappe.has_permission("Archival File", "read", doc=self.file_of[self.b]))
        self.assertFalse(frappe.has_permission("Archival File", "write", doc=self.file_of[self.b]))
        self.assertTrue(frappe.has_permission("Archival File", "write", doc=self.file_of[self.a]))
        self.assertFalse(frappe.has_permission("Archival File", "read", doc=self.file_of[self.c]))
        self.assertFalse(frappe.has_permission("Fonds", "read", doc=self.c))
        self.assertEqual(set(frappe.get_list("Fonds", filters={"name": ["in", self.fonds]}, pluck="name")), {self.a, self.b})
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc("Archival File", self.file_of[self.b]).save()

    def test_creating_follows_the_fonds_a_record_lands_in(self):
        self.scope(write=[self.a])
        frappe.set_user(CATALOGER)
        mine = frappe.get_doc({"doctype": "Archival File", "file_title": f"SS mới {TAG}", "catalog": self.catalog_of[self.a],
                               "record_group": self.group_of[self.a], "fonds": self.a}).insert()
        self.assertTrue(mine.name)
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc({"doctype": "Archival File", "file_title": f"SS khác {TAG}", "catalog": self.catalog_of[self.b],
                            "record_group": self.group_of[self.b], "fonds": self.b}).insert()
        with self.assertRaises(frappe.PermissionError):  # a document lands in the fonds of its file
            frappe.get_doc({"doctype": "Archive Document", "document_title": f"SS VB {TAG}", "archival_file": self.file_of[self.b]}).insert()

    def test_moving_a_record_needs_both_fonds(self):
        self.scope(write=[self.a, self.b])
        frappe.set_user(CATALOGER)
        catalog = frappe.get_doc("Catalog", self.catalog_of[self.a])
        catalog.record_group = self.group_of[self.b]
        catalog.save()  # A -> B: both writable
        frappe.set_user("Administrator")
        frappe.delete_doc("Staff Access", CATALOGER, force=True, ignore_permissions=True)
        self.scope(read=None, write=[self.a])
        frappe.set_user(CATALOGER)
        catalog = frappe.get_doc("Catalog", self.catalog_of[self.a])  # now in B
        catalog.record_group = self.group_of[self.a]
        with self.assertRaises(frappe.PermissionError):  # leaving B is changing B
            catalog.save()

    def test_a_staff_group_adds_fonds_to_its_members(self):
        self.scope(read=[self.a], write=[self.a])
        frappe.get_doc({"doctype": "Staff Group", "group_name": f"SS Tổ {TAG}", "apply_scope": 1,
                        "read_scope": "Chỉ các phông được chọn", "read_fonds": [{"fonds": self.b}],
                        "write_scope": "Như phạm vi xem", "members": [{"user": CATALOGER}]}).insert(ignore_permissions=True)
        access = policy.get_access(CATALOGER)
        self.assertEqual((sorted(access.read_fonds), sorted(access.write_fonds)), (sorted([self.a, self.b]), sorted([self.a, self.b])))
        self.assertEqual(self.visible_files(), {self.a, self.b})
        self.assertEqual(policy.get_access(OTHER).read_fonds, None)  # not a member: untouched

    def test_the_highest_level_hides_what_is_above_it(self):
        self.scope(level=1)
        frappe.set_user(CATALOGER)
        names = set(frappe.get_list("Archival File", filters={"fonds": self.a}, pluck="name"))
        self.assertNotIn(self.secret, names)
        self.assertIn(self.file_of[self.a], names)
        self.assertFalse(frappe.has_permission("Archival File", "read", doc=self.secret))
        frappe.set_user(ADMIN)
        self.assertTrue(frappe.has_permission("Archival File", "read", doc=self.secret))

    def test_fonds_to_change_stay_within_the_fonds_read(self):
        with self.assertRaises(frappe.ValidationError):
            self.scope(read=[self.a], write=[self.b])
        doc = self.scope(read=[self.a, self.b], write=None)  # "like reading"
        self.assertEqual(sorted(policy.get_access(CATALOGER).write_fonds), sorted([self.a, self.b]))
        self.assertTrue(doc.name)

    def test_administrators_are_never_narrowed(self):
        self.scope(user=ADMIN, read=[self.a], level=1)
        access = policy.get_access(ADMIN)
        self.assertEqual((access.kind, access.read_fonds, access.write_fonds), ("admin", None, None))
        self.assertEqual(self.visible_files(ADMIN), {self.a, self.b, self.c})

    # ---- every place honours it
    def test_search_and_the_generic_lists_show_only_the_fonds_read(self):
        self.scope(read=[self.a])
        frappe.set_user(CATALOGER)
        found = search_service.search_files({"file_title": "RW Test File"}, page_size=100)
        self.assertEqual({r["fonds"] for r in found["data"]} & set(self.fonds), {self.a})
        listed = crud.get_list("Archive Document", page_size=200)
        self.assertNotIn(self.doc_of[self.b], {r["name"] for r in listed["data"]})

    def test_every_report_shows_only_the_fonds_read(self):
        self.scope(read=[self.a])
        frappe.set_user(CATALOGER)
        fonds_names = {f: frappe.db.get_value("Fonds", f, "fonds_name") for f in self.fonds}
        rows = reports.run("phong", {}, 1, 200)["rows"]
        self.assertEqual({r["name"] for r in rows} & set(self.fonds), {self.a})
        files = {r["name"] for r in reports.run("ho-so", {}, 1, 200)["rows"]}
        self.assertIn(self.file_of[self.a], files)
        self.assertNotIn(self.file_of[self.b], files)
        docs = {r["name"] for r in reports.run("van-ban", {}, 1, 200)["rows"]}
        self.assertNotIn(self.doc_of[self.b], docs)
        stats = {r["label"] for r in reports.run("thong-ke-phong", {}, 1, 200)["rows"]}
        self.assertIn(fonds_names[self.a], stats)
        self.assertNotIn(fonds_names[self.b], stats)
        catalogs = {r["name"] for r in reports.run("muc-luc", {}, 1, 200)["rows"]}
        self.assertNotIn(self.catalog_of[self.c], catalogs)
        for report in reports.visible():  # none of the reports the user may run fails for a narrowed scope
            reports.run(report.slug, {}, 1, 20)

    def test_a_record_says_what_the_user_may_do_with_it(self):
        self.scope(read=[self.a, self.b], write=[self.a])
        frappe.set_user(CATALOGER)
        self.assertEqual(crud.get("Archival File", self.file_of[self.b])["_rights"], {"write": False, "delete": False, "locked": ""})
        self.assertTrue(crud.get("Archival File", self.file_of[self.a])["_rights"]["write"])
        with self.assertRaises(frappe.PermissionError):
            crud.get("Archival File", self.file_of[self.c])

    def test_preservation_of_the_whole_archive_needs_every_fonds(self):
        role = perm_api_create_group(CUSTOM_ROLE, ["preservation.backup", "preservation.check"])
        frappe.set_user("Administrator")
        frappe.get_doc("User", CATALOGER).add_roles(role)
        self.scope(read=[self.a])
        frappe.set_user(CATALOGER)
        for call in (lambda: preservation.start_backup("Cơ sở dữ liệu"), lambda: preservation.start_check("Toàn bộ"),
                     lambda: preservation.start_check("Toàn bộ", self.b), preservation.run_retention):
            with self.assertRaises(frappe.PermissionError):
                call()

    # ---- sealed records
    def test_a_closed_file_is_sealed_for_whoever_may_not_change_sealed_records(self):
        frappe.db.set_value("Archival File", self.file_of[self.a], "status", "Đã đóng")
        frappe.set_user(CATALOGER)
        doc = frappe.get_doc("Archival File", self.file_of[self.a])
        doc.file_title = "đổi"
        with self.assertRaises(frappe.PermissionError):
            doc.save()
        with self.assertRaises(frappe.PermissionError):  # nothing is added to it
            frappe.get_doc({"doctype": "Archive Document", "document_title": f"SS thêm {TAG}", "archival_file": self.file_of[self.a]}).insert()
        with self.assertRaises(frappe.PermissionError):  # nor taken out of it
            frappe.delete_doc("Archive Document", self.doc_of[self.a])
        rights = crud.get("Archival File", self.file_of[self.a])["_rights"]
        self.assertEqual((rights["write"], rights["locked"]), (False, "Hồ sơ đã đóng"))
        frappe.set_user(ADMIN)  # administrators may reopen it
        doc = frappe.get_doc("Archival File", self.file_of[self.a])
        doc.status = "Đã hoàn thành"
        doc.save()

    def test_closing_is_a_normal_edit_and_the_capability_lets_a_group_reopen(self):
        frappe.set_user(CATALOGER)
        doc = frappe.get_doc("Archival File", self.file_of[self.b])
        doc.status = "Đã đóng"
        doc.save()  # closing an open file
        role = perm_api_create_group(CUSTOM_ROLE, ["archive.edit_closed"], copy_from="Cataloger")
        frappe.set_user("Administrator")
        frappe.get_doc("User", OTHER).add_roles(role)
        frappe.set_user(OTHER)
        doc = frappe.get_doc("Archival File", self.file_of[self.b])
        doc.status = "Đã hoàn thành"
        doc.save()

    def test_a_closed_fonds_seals_what_it_holds(self):
        frappe.db.set_value("Fonds", self.c, "status", "Đã đóng")
        frappe.set_user(CATALOGER)
        catalog = frappe.get_doc("Catalog", self.catalog_of[self.c])
        catalog.catalog_title = "đổi"
        with self.assertRaises(frappe.PermissionError):
            catalog.save()
        self.assertEqual(crud.get("Archival File", self.file_of[self.c])["_rights"]["locked"], "Phông đã đóng")

    # ---- protected fields
    def test_the_protected_fields_follow_the_permission_level(self):
        role = perm_api_create_group(CUSTOM_ROLE, [], matrix={"Archival File": {"read": 1, "write": 1}})
        frappe.set_user("Administrator")
        frappe.get_doc("User", OTHER).add_roles(role)
        user = frappe.get_doc("User", OTHER)
        user.roles = [r for r in user.roles if r.role != "Cataloger"]
        user.save(ignore_permissions=True)
        frappe.set_user(OTHER)
        doc = frappe.get_doc("Archival File", self.file_of[self.b])
        doc.confidentiality_level = "Mật"
        doc.file_title = f"SS đổi tên {TAG}"
        doc.save()
        stored = frappe.db.get_value("Archival File", self.file_of[self.b], ["confidentiality_level", "file_title"], as_dict=True)
        self.assertEqual((stored.confidentiality_level, stored.file_title), ("Thường", f"SS đổi tên {TAG}"))
        frappe.set_user(CATALOGER)  # the cataloguers keep writing the level by default
        doc = frappe.get_doc("Archival File", self.file_of[self.b])
        doc.confidentiality_level = "Mật"
        doc.save()
        self.assertEqual(frappe.db.get_value("Archival File", self.file_of[self.b], "confidentiality_level"), "Mật")

    # ---- the users screen
    def test_the_administrator_sets_a_scope_on_the_users_screen_and_sees_the_result(self):
        frappe.set_user(ADMIN)
        out = users.save_user({"access": {"read_scope": "Chỉ các phông được chọn", "read_fonds": [{"fonds": self.a}, {"fonds": self.b}],
                                          "write_scope": "Chỉ các phông được chọn", "write_fonds": [self.a],
                                          "max_confidentiality_priority": 1}}, CATALOGER)
        access = out["access"]
        self.assertEqual((access["read_scope"], [r["fonds"] for r in access["write_fonds"]], access["max_confidentiality_priority"]),
                         ("Chỉ các phông được chọn", [self.a], 1))
        effective = access["effective"]
        self.assertEqual(sorted(r["fonds"] for r in effective["read_fonds"]), sorted([self.a, self.b]))
        self.assertEqual(effective["max_priority"], 1)
        self.assertIn(CATALOGER, {r["name"] for r in users.list_users(search=CATALOGER)["data"] if r["scoped"]})
        # back to every fonds: no record is kept
        users.save_user({"access": {"read_scope": "Tất cả phông", "write_scope": "Như phạm vi xem", "max_confidentiality_priority": 0}}, CATALOGER)
        self.assertFalse(frappe.db.exists("Staff Access", CATALOGER))
        with self.assertRaises(frappe.ValidationError):
            users.save_user({"access": {"read_scope": "Chỉ các phông được chọn", "read_fonds": [self.a]}}, ADMIN)  # not one's own


def perm_api_create_group(label, capabilities, copy_from=None, matrix=None):
    """A permission group made through the administrators' API; returns its role."""
    frappe.set_user("Administrator")
    role = perm_api.create_group(label, copy_from=copy_from)["role"]
    values = {"capabilities": capabilities}
    if matrix:
        values["matrix"] = matrix
    perm_api.save_group(role, values)
    return role
