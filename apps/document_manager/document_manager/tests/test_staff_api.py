# -*- coding: utf-8 -*-
"""Generic staff API (boot, meta, crud) and the dictionary DocTypes behind module 3 (Danh mục).

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_staff_api
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager.api import boot, crud, meta
from document_manager.document_manager.constants import MASTERS
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _user

ADMIN = "sa.admin@example.com"
CATALOGER = "sa.cataloger@example.com"
OFFICER = "sa.officer@example.com"
PRESERVER = "sa.preserver@example.com"
READER = "sa.reader@example.com"
USERS = (ADMIN, CATALOGER, OFFICER, PRESERVER, READER)
TAG = "SA"


class TestStaffApi(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        _user(ADMIN, ["Document Admin"], "System User")
        _user(CATALOGER, ["Cataloger"], "System User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(PRESERVER, ["Preservation Officer"], "System User")
        _user(READER, ["Reader"], "Website User")

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for email in USERS:
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user(CATALOGER)
        frappe.db.savepoint("sa_test")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="sa_test")

    # ---- registry and boot
    def test_every_registered_doctype_can_be_described(self):
        frappe.set_user(ADMIN)
        for master in MASTERS:
            info = meta.get_doctype_ui(master["doctype"])
            self.assertEqual(info["doctype"], master["doctype"])
            self.assertTrue(info["list_fields"], master["doctype"])
            self.assertTrue(info["layout"], master["doctype"])
            self.assertTrue(info["title_field"], master["doctype"])
            for hidden in ("lft", "rgt", "old_parent"):
                self.assertNotIn(hidden, [f["fieldname"] for f in info["fields"]])

    def test_unregistered_doctypes_are_out_of_reach(self):
        for doctype in ("User", "Role", "Usage Request", "Reader Registration", "Backup Batch"):
            with self.assertRaises(frappe.PermissionError, msg=doctype):
                meta.get_doctype_ui(doctype)
            with self.assertRaises(frappe.PermissionError, msg=doctype):
                crud.get_list(doctype)
            with self.assertRaises(frappe.PermissionError, msg=doctype):
                crud.save(doctype, {"name": "x"})
            with self.assertRaises(frappe.PermissionError, msg=doctype):
                crud.delete(doctype, "x")
        with self.assertRaises(frappe.PermissionError):
            crud.link_search("User", "adm")

    def test_the_generic_api_is_for_the_staff_even_where_frappe_would_allow_the_read(self):
        # a reader may read their own Reader record through Frappe's permissions; the staff app's API still refuses them
        frappe.set_user("Administrator")
        reader = frappe.get_doc({"doctype": "Reader", "full_name": f"{TAG} Độc giả", "email": READER, "user": READER, "is_active": 1}).insert()
        frappe.set_user(READER)
        self.assertTrue(frappe.has_permission("Reader", "read", doc=reader.name))
        for call in (lambda: crud.get_list("Reader"), lambda: crud.get("Reader", reader.name),
                     lambda: crud.save("Reader", {"phone": "0900000000"}, name=reader.name),
                     lambda: crud.delete("Reader", reader.name), lambda: crud.link_search("Fonds", "a"),
                     lambda: crud.tree_children("Fonds"), lambda: meta.get_doctype_ui("Reader")):
            with self.assertRaises(frappe.PermissionError):
                call()

    def test_boot_is_for_staff_and_lists_what_the_user_may_read(self):
        data = boot.get_staff_boot()
        slugs = {m["slug"] for m in data["masters"]}
        self.assertIn("tu-dien", slugs)
        self.assertEqual(data["user"]["name"], CATALOGER)
        self.assertTrue(any(g["group"] == "Danh mục" for g in data["nav"]))
        self.assertEqual(data["legacy"], [])  # what is left of the old pages (backup, log, settings) is not for a cataloguer
        frappe.set_user(READER)
        with self.assertRaises(frappe.PermissionError):
            boot.get_staff_boot()

    def test_the_sidebar_follows_permissions(self):
        frappe.set_user(PRESERVER)  # may read the warehouses but little else
        slugs = {m["slug"] for m in boot.build_boot()["masters"]}
        self.assertIn("kho-luu-tru", slugs)
        self.assertNotIn("loai-tu-dien", slugs)
        legacy = {i["label"] for g in boot.build_boot()["legacy"] for i in g["items"]}
        self.assertIn("Đợt sao lưu", legacy)
        self.assertNotIn("Phiếu yêu cầu sử dụng", legacy)

    def test_description_reflects_the_users_permissions(self):
        self.assertTrue(meta.get_doctype_ui("Dictionary Type")["permissions"]["create"])
        frappe.set_user(OFFICER)
        info = meta.get_doctype_ui("Dictionary Type")
        self.assertEqual({k: v for k, v in info["permissions"].items()},
                         {"read": True, "create": False, "write": False, "delete": False})
        frappe.set_user(PRESERVER)
        with self.assertRaises(frappe.PermissionError):
            meta.get_doctype_ui("Dictionary Type")

    def test_layout_sections_cover_the_form_fields(self):
        info = meta.get_doctype_ui("Fonds")
        laid_out = [name for section in info["layout"] for column in section["columns"] for name in column]
        self.assertEqual(sorted(laid_out), sorted(f["fieldname"] for f in info["fields"]))
        by_name = {f["fieldname"]: f for f in info["fields"]}
        self.assertTrue(by_name["fonds_name"]["reqd"])
        self.assertEqual(by_name["archival_agency"]["options"], "Archival Agency")

    # ---- list / get / save / delete
    def _agency(self, name, **extra):
        return crud.save("Archival Agency", {"agency_name": name, **extra})

    def test_create_read_update_delete_round_trip(self):
        created = self._agency(f"{TAG} Agency", agency_code=f"{TAG}1", is_active=1)
        self.assertEqual(created["name"], f"{TAG} Agency")
        got = crud.get("Archival Agency", created["name"])
        self.assertEqual((got["agency_code"], got["is_active"]), (f"{TAG}1", 1))

        updated = crud.save("Archival Agency", {"agency_code": f"{TAG}2", "modified": got["modified"]}, created["name"])
        self.assertEqual(updated["agency_code"], f"{TAG}2")
        frappe.set_user(ADMIN)  # a cataloger may create and edit, but only an administrator deletes
        self.assertEqual(crud.delete("Archival Agency", created["name"]), {"name": created["name"]})
        with self.assertRaises(frappe.DoesNotExistError):
            crud.get("Archival Agency", created["name"])

    def test_the_name_of_a_record_built_from_a_field_does_not_change_on_edit(self):
        created = self._agency(f"{TAG} Agency")
        crud.save("Archival Agency", {"agency_name": "Renamed"}, created["name"])
        self.assertEqual(frappe.db.get_value("Archival Agency", created["name"], "agency_name"), f"{TAG} Agency")

    def test_system_fields_cannot_be_forged(self):
        created = self._agency(f"{TAG} Agency", owner="Administrator", docstatus=1, creation="2001-01-01 00:00:00")
        row = frappe.db.get_value("Archival Agency", created["name"], ["owner", "docstatus", "creation"], as_dict=True)
        self.assertEqual(row.owner, CATALOGER)
        self.assertEqual(row.docstatus, 0)
        self.assertNotEqual(str(row.creation)[:4], "2001")

    def test_a_stale_edit_is_reported_not_overwritten(self):
        created = self._agency(f"{TAG} Agency")
        frappe.db.set_value("Archival Agency", created["name"], "modified", "2020-01-01 00:00:00", update_modified=False)
        with self.assertRaises(frappe.TimestampMismatchError):
            crud.save("Archival Agency", {"agency_code": "X", "modified": "2019-01-01 00:00:00"}, created["name"])

    def test_required_fields_and_validation_are_enforced_by_frappe(self):
        with self.assertRaises(frappe.ValidationError):  # the name field is mandatory
            crud.save("Archival Agency", {"agency_code": "no name"})
        with self.assertRaises(frappe.ValidationError):  # end year before start year
            crud.save("Fonds", {"fonds_name": "bad", "archival_agency": self._agency(f"{TAG} A")["name"],
                                "start_year": 2000, "end_year": 1990})

    def test_list_search_filter_sort_and_paging(self):
        for i in range(3):
            self._agency(f"{TAG} Agency {i}", agency_code=f"{TAG}-C{i}")
        res = crud.get_list("Archival Agency", search=f"{TAG} Agency", page_size=2, order_by="agency_name desc")
        self.assertEqual((res["total"], len(res["data"]), res["page_size"]), (3, 2, 2))
        self.assertEqual(res["data"][0]["agency_name"], f"{TAG} Agency 2")
        res = crud.get_list("Archival Agency", filters={"agency_code": f"{TAG}-C1"})
        self.assertEqual([r["name"] for r in res["data"]], [f"{TAG} Agency 1"])
        self.assertEqual(crud.get_list("Archival Agency", search=f"{TAG} Agency 99")["total"], 0)
        with self.assertRaises(frappe.ValidationError):
            crud.get_list("Archival Agency", filters={"no_such_column": 1})
        with self.assertRaises(frappe.ValidationError):
            crud.get_list("Archival Agency", order_by="name; drop table x")
        self.assertEqual(crud.get_list("Archival Agency", page_size=100000)["page_size"], 200)

    def test_roles_without_write_access_cannot_change_data(self):
        created = self._agency(f"{TAG} Agency")
        frappe.set_user(OFFICER)  # Reading Room Officer: read only on the catalogues
        self.assertEqual(crud.get("Archival Agency", created["name"])["agency_name"], created["name"])
        with self.assertRaises(frappe.PermissionError):
            crud.save("Archival Agency", {"agency_name": f"{TAG} Other"})
        with self.assertRaises(frappe.PermissionError):
            crud.save("Archival Agency", {"agency_code": "X"}, created["name"])
        with self.assertRaises(frappe.PermissionError):
            crud.delete("Archival Agency", created["name"])
        frappe.set_user(READER)
        with self.assertRaises(frappe.PermissionError):
            crud.get_list("Archival Agency")

    def test_a_cataloger_cannot_delete_but_an_admin_can(self):
        created = self._agency(f"{TAG} Agency")
        with self.assertRaises(frappe.PermissionError):
            crud.delete("Archival Agency", created["name"])
        frappe.set_user(ADMIN)
        crud.delete("Archival Agency", created["name"])

    def test_a_record_that_is_still_used_cannot_be_deleted(self):
        frappe.set_user(ADMIN)
        agency = self._agency(f"{TAG} Agency")["name"]
        crud.save("Fonds", {"fonds_name": f"{TAG} Fonds", "archival_agency": agency})
        with self.assertRaises(frappe.LinkExistsError):
            crud.delete("Archival Agency", agency)

    def test_link_search_returns_labels_and_respects_filters(self):
        agency = self._agency(f"{TAG} Agency")["name"]
        fonds = crud.save("Fonds", {"fonds_name": f"{TAG} Quý hiếm", "archival_agency": agency})
        options = crud.link_search("Fonds", f"{TAG} Quý")
        self.assertEqual([(o["value"], o["label"]) for o in options], [(fonds["name"], f"{TAG} Quý hiếm")])
        self.assertEqual(crud.link_search("Fonds", f"{TAG} Quý", {"name": ["!=", fonds["name"]]}), [])
        self.assertTrue(crud.link_search("Archival Agency", TAG))  # a link target of the registered screens

    # ---- dictionaries (single and multi level)
    def _dictionary(self, name, hierarchical):
        return crud.save("Dictionary Type", {"type_name": name, "is_hierarchical": hierarchical})["name"]

    def test_single_level_dictionary_rejects_parents(self):
        dictionary = self._dictionary(f"{TAG} Flat", 0)
        first = crud.save("Quick Entry Dictionary", {"dictionary_type": dictionary, "entry_value": "Một"})
        with self.assertRaises(frappe.ValidationError):
            crud.save("Quick Entry Dictionary", {"dictionary_type": dictionary, "entry_value": "Hai",
                                                 "parent_entry": first["name"]})
        with self.assertRaises(frappe.ValidationError):  # same value twice at one level
            crud.save("Quick Entry Dictionary", {"dictionary_type": dictionary, "entry_value": "Một"})

    def test_multi_level_dictionary_builds_a_tree_with_the_same_value_under_two_parents(self):
        dictionary = self._dictionary(f"{TAG} Tree", 1)

        def entry(value, parent=None):
            return crud.save("Quick Entry Dictionary", {"dictionary_type": dictionary, "entry_value": value,
                                                        "parent_entry": parent or ""})["name"]
        hanoi, hue = entry("Hà Nội"), entry("Huế")
        ba_dinh = entry("Ba Đình", hanoi)
        entry("Phường Phúc Xá", ba_dinh)
        entry("Trung tâm", hanoi)
        entry("Trung tâm", hue)  # same label, different parent: allowed (the old naming collided)

        filters = {"dictionary_type": dictionary}
        roots = crud.tree_children("Quick Entry Dictionary", None, filters)
        self.assertEqual([r.entry_value for r in roots], ["Hà Nội", "Huế"])
        self.assertEqual({r.entry_value: r.child_count for r in roots}, {"Hà Nội": 2, "Huế": 1})
        self.assertEqual(frappe.db.get_value("Quick Entry Dictionary", hanoi, "is_group"), 1)
        kids = crud.tree_children("Quick Entry Dictionary", hanoi, filters)
        self.assertEqual({k.entry_value for k in kids}, {"Ba Đình", "Trung tâm"})

        other = self._dictionary(f"{TAG} Other", 1)
        with self.assertRaises(frappe.ValidationError):  # a parent from another dictionary
            crud.save("Quick Entry Dictionary", {"dictionary_type": other, "entry_value": "X", "parent_entry": hanoi})
        with self.assertRaises(frappe.ValidationError):  # cannot be made flat while it has nested values
            crud.save("Dictionary Type", {"is_hierarchical": 0}, dictionary)

    def test_deleting_the_last_child_clears_the_group_flag(self):
        frappe.set_user(ADMIN)
        dictionary = self._dictionary(f"{TAG} Tree 2", 1)
        parent = crud.save("Quick Entry Dictionary", {"dictionary_type": dictionary, "entry_value": "Cha"})["name"]
        child = crud.save("Quick Entry Dictionary", {"dictionary_type": dictionary, "entry_value": "Con",
                                                     "parent_entry": parent})["name"]
        self.assertEqual(frappe.db.get_value("Quick Entry Dictionary", parent, "is_group"), 1)
        with self.assertRaises(frappe.ValidationError):  # a node with children is protected
            crud.delete("Quick Entry Dictionary", parent)
        crud.delete("Quick Entry Dictionary", child)
        self.assertEqual(frappe.db.get_value("Quick Entry Dictionary", parent, "is_group"), 0)

    def test_the_warehouse_tree_lists_roots_then_children(self):
        frappe.set_user(ADMIN)
        kho = crud.save("Storage Warehouse", {"warehouse_name": f"{TAG} Kho", "warehouse_type": "Kho", "is_group": 1})["name"]
        crud.save("Storage Warehouse", {"warehouse_name": f"{TAG} Giá 1", "warehouse_type": "Giá", "parent_warehouse": kho})
        roots = crud.tree_children("Storage Warehouse", None, {"warehouse_name": ["like", f"{TAG}%"]})
        self.assertIn(kho, [r.name for r in roots])
        self.assertEqual([r.child_count for r in roots if r.name == kho], [1])
        self.assertEqual([r.name for r in crud.tree_children("Storage Warehouse", kho)], [f"{TAG} Giá 1"])
        with self.assertRaises(frappe.ValidationError):
            crud.tree_children("Fonds")  # not a tree
