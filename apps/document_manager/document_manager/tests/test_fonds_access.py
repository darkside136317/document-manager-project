# -*- coding: utf-8 -*-
"""Fonds access for readers (P4 of permissions v2): public / licensed / internal fonds, grants to groups and to readers
with a validity, and the slip rules that follow (the reader's own rights at every step, copies, due dates).

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_fonds_access
"""

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from document_manager.document_manager import policy
from document_manager.document_manager.api import account, fonds_access as fonds_api, requests as request_api, slips
from document_manager.document_manager.services import basket, fonds_access, lifecycle as lc, search_index
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _reader, _seed_archive, _user

TAG = frappe.generate_hash(length=5).lower()
READER = f"fa.reader.{TAG}@example.com"
OFFICER = f"fa.officer.{TAG}@example.com"
ADMIN = f"fa.admin.{TAG}@example.com"
CATALOGER = f"fa.cataloger.{TAG}@example.com"
GROUP = f"FA Nhóm {TAG}"
USERS = (READER, OFFICER, ADMIN, CATALOGER)


class TestFondsAccess(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        _user(READER, ["Reader"], "Website User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(ADMIN, ["Document Admin"], "System User")
        _user(CATALOGER, ["Cataloger"], "System User")
        cls.seeded = []
        cls.modes = {}
        for mode in ("Công khai", "Theo cấp phép", "Theo cấp phép", "Nội bộ"):
            made = _seed_archive(1, access_mode=mode)
            cls.seeded += made
            cls.modes.setdefault(mode, []).append(_names(made, "Fonds")[0])
        cls.public = cls.modes["Công khai"][0]
        cls.licensed, cls.licensed_2 = cls.modes["Theo cấp phép"]
        cls.internal = cls.modes["Nội bộ"][0]
        cls.file_of = {f: frappe.db.get_value("Archival File", {"fonds": f}, "name") for f in (cls.public, cls.licensed, cls.licensed_2, cls.internal)}
        frappe.get_doc({"doctype": "Reader Group", "group_name": GROUP, "max_confidentiality_priority": 1}).insert(ignore_permissions=True)
        cls.profile = _reader(READER, "FA Độc giả")
        frappe.db.set_value("Reader", cls.profile, "reader_group", GROUP)
        # a reader the staff files for, without an account
        cls.walk_in = frappe.get_doc({"doctype": "Reader", "full_name": f"FA Không tài khoản {TAG}", "is_active": 1,
                                      "reader_group": GROUP}).insert(ignore_permissions=True).name
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for doctype in ("Usage Request", "Copy Request"):
            for name in frappe.get_all(doctype, filters={"reader": ["in", [cls.profile, cls.walk_in]]}, pluck="name"):
                doc = frappe.get_doc(doctype, name)
                if doc.docstatus == 1:
                    doc.flags.ignore_permissions = True
                    doc.cancel()
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        for name in (cls.profile, cls.walk_in):
            frappe.delete_doc("Reader", name, force=True, ignore_permissions=True)
        frappe.delete_doc("Reader Group", GROUP, force=True, ignore_permissions=True)
        for doctype, name in cls.seeded:
            frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        for email in USERS:
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.db.commit()
        policy.clear_cache()
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user("Administrator")
        frappe.db.savepoint("fa_test")
        policy.clear_cache()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="fa_test")
        policy.clear_cache()

    # helpers
    def grant(self, doctype, name, fonds, valid_from=None, valid_until=None, user=ADMIN):
        frappe.set_user(user)
        doc = frappe.get_doc(doctype, name)
        doc.append("fonds_scopes" if doctype == "Reader Group" else "fonds_grants",
                   {"fonds": fonds, "valid_from": valid_from, "valid_until": valid_until})
        doc.save()
        frappe.set_user("Administrator")
        policy.clear_cache()
        return doc

    def revoke(self, doctype, name, fonds):
        frappe.set_user(ADMIN)
        doc = frappe.get_doc(doctype, name)
        table = "fonds_scopes" if doctype == "Reader Group" else "fonds_grants"
        doc.set(table, [r for r in doc.get(table) if r.fonds != fonds])
        doc.save()
        frappe.set_user("Administrator")
        policy.clear_cache()

    def readable(self, user=READER):
        frappe.set_user(user)
        names = set(frappe.get_list("Archival File", pluck="name", limit_page_length=0))
        frappe.set_user("Administrator")
        return {f for f, file in self.file_of.items() if file in names}

    def send(self, items, doctype="Usage Request", reader=None, user=READER):
        frappe.set_user(user)
        payload = {"purpose": "Nghiên cứu", "items": items}
        if reader:
            payload["reader"] = reader
        name = request_api.save_request(doctype, json.dumps(payload), submit=1)["name"]
        frappe.set_user("Administrator")
        return name

    # ---- the three modes
    def test_a_reader_sees_public_fonds_and_licensed_ones_only_once_granted(self):
        self.assertEqual(self.readable(), {self.public})
        self.grant("Reader Group", GROUP, self.licensed)
        self.assertEqual(self.readable(), {self.public, self.licensed})
        self.grant("Reader", self.profile, self.licensed_2)
        self.assertEqual(self.readable(), {self.public, self.licensed, self.licensed_2})
        frappe.set_user(READER)
        self.assertFalse(frappe.has_permission("Fonds", "read", doc=self.internal))

    def test_an_internal_fonds_is_never_open_to_readers(self):
        with self.assertRaises(frappe.ValidationError):
            self.grant("Reader", self.profile, self.internal)
        # a grant made before the fonds became internal opens nothing
        self.grant("Reader", self.profile, self.licensed)
        frappe.db.set_value("Fonds", self.licensed, "access_mode", "Nội bộ")
        policy.clear_cache()
        self.assertEqual(self.readable(), {self.public})
        self.assertEqual(self.readable(CATALOGER), {self.public, self.licensed, self.licensed_2, self.internal})  # staff see all

    def test_making_a_fonds_public_opens_it_to_every_reader_at_once(self):
        frappe.set_user(ADMIN)
        fonds = frappe.get_doc("Fonds", self.licensed_2)
        fonds.access_mode = "Công khai"
        fonds.save()
        self.assertIn(self.licensed_2, self.readable())

    def test_a_grant_counts_only_within_its_dates(self):
        today = getdate(nowdate())
        self.grant("Reader", self.profile, self.licensed, valid_from=add_days(today, 3))
        self.assertNotIn(self.licensed, self.readable())
        self.revoke("Reader", self.profile, self.licensed)
        self.grant("Reader", self.profile, self.licensed, valid_until=add_days(today, -1))
        self.assertNotIn(self.licensed, self.readable())
        self.revoke("Reader", self.profile, self.licensed)
        self.grant("Reader", self.profile, self.licensed, valid_until=add_days(today, 10))
        scope = policy.reader_scope_of(self.profile)
        self.assertEqual(scope.fonds_until[self.licensed], add_days(today, 10))
        self.assertIsNone(scope.fonds_until[self.public])
        with self.assertRaises(frappe.ValidationError):
            self.grant("Reader Group", GROUP, self.licensed_2, valid_from=add_days(today, 5), valid_until=today)

    def test_the_longest_grant_wins(self):
        today = getdate(nowdate())
        self.grant("Reader Group", GROUP, self.licensed)  # the group: no end
        self.grant("Reader", self.profile, self.licensed, valid_until=add_days(today, 5))
        self.assertIsNone(policy.reader_scope_of(self.profile).fonds_until[self.licensed])

    def test_a_grant_records_who_gave_it_and_needs_the_right_to(self):
        doc = self.grant("Reader", self.profile, self.licensed)
        row = next(r for r in doc.fonds_grants if r.fonds == self.licensed)
        self.assertEqual((row.granted_by, str(row.granted_on)), (ADMIN, nowdate()))
        self.grant("Reader", self.profile, self.licensed_2, user=OFFICER)  # the reading room grants
        role = _group_with_reader_rights_but_no_grant()
        frappe.get_doc("User", CATALOGER).add_roles(role)
        with self.assertRaises(frappe.PermissionError):
            self.grant("Reader", self.profile, self.public, user=CATALOGER)

    # ---- search, account, the fonds screen
    def test_search_and_the_account_page_follow_the_grants(self):
        self.grant("Reader", self.profile, self.licensed, valid_until=add_days(nowdate(), 30))
        index = MagicMock()
        index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
        with patch.object(search_index, "_get_index", return_value=index):
            frappe.set_user(READER)
            search_index.search("x")
            flt = index.search.call_args[0][1]["filter"]
        self.assertIn(f'"{self.licensed}"', flt)
        self.assertIn(f'"{self.public}"', flt)
        self.assertNotIn(f'"{self.licensed_2}"', flt)
        self.assertNotIn(f'"{self.internal}"', flt)
        info = account.get_account()
        rows = {r["fonds"]: r for r in info["fonds"]}
        self.assertEqual(set(rows) & set(self.file_of), {self.public, self.licensed})  # other public fonds may exist on the site
        self.assertEqual(str(rows[self.licensed]["until"]), str(add_days(nowdate(), 30)))
        frappe.set_user(OFFICER)
        who = fonds_api.who_may_use(self.licensed)
        self.assertEqual(who["mode"], "Theo cấp phép")
        self.assertEqual([(g["kind"], g["name"], g["active"]) for g in who["grants"]], [("reader", self.profile, True)])

    # ---- slips
    def test_a_reader_cannot_put_an_ungranted_file_in_a_slip(self):
        frappe.set_user(READER)
        with self.assertRaises(frappe.PermissionError):
            basket.add_item("file", self.file_of[self.licensed], "usage")
        with self.assertRaises(frappe.PermissionError):
            self.send([{"archival_file": self.file_of[self.licensed]}])
        self.assertTrue(basket.add_item("file", self.file_of[self.public], "usage")["added"])

    def test_the_staff_filing_for_a_reader_without_an_account_is_held_to_that_readers_rights(self):
        with self.assertRaises(frappe.PermissionError):
            self.send([{"archival_file": self.file_of[self.licensed]}], reader=self.walk_in, user=OFFICER)
        name = self.send([{"archival_file": self.file_of[self.public]}], reader=self.walk_in, user=OFFICER)
        self.assertEqual(frappe.db.get_value("Usage Request", name, "reader"), self.walk_in)

    def test_a_grant_taken_back_after_sending_stops_the_approval(self):
        self.grant("Reader", self.profile, self.licensed)
        name = self.send([{"archival_file": self.file_of[self.licensed]}])
        self.revoke("Reader", self.profile, self.licensed)
        frappe.set_user(OFFICER)
        with self.assertRaises(frappe.PermissionError) as caught:
            request_api.apply_action("Usage Request", name, "Duyệt")
        self.assertIn("cấp phép phông", str(caught.exception))

    def test_the_due_date_never_passes_the_end_of_the_grant_and_renewal_stops_there(self):
        frappe.db.set_single_value("Reader Settings", {"document_hold_days": 14, "renewal_days": 7, "max_renewals": 3})
        frappe.clear_document_cache("Reader Settings", "Reader Settings")
        end = add_days(nowdate(), 3)
        self.grant("Reader", self.profile, self.licensed, valid_until=end)
        name = self.send([{"archival_file": self.file_of[self.licensed]}])
        frappe.set_user(OFFICER)
        request_api.apply_action("Usage Request", name, "Duyệt")
        request_api.apply_action("Usage Request", name, "Giao tài liệu")
        doc = frappe.get_doc("Usage Request", name)
        self.assertEqual(getdate(doc.due_date), getdate(end))
        with self.assertRaises(frappe.ValidationError):
            slips.renew(name)
        public = self.send([{"archival_file": self.file_of[self.public]}])
        frappe.set_user(OFFICER)
        request_api.apply_action("Usage Request", public, "Duyệt")
        request_api.apply_action("Usage Request", public, "Giao tài liệu")
        self.assertEqual(getdate(frappe.db.get_value("Usage Request", public, "due_date")), getdate(add_days(nowdate(), 14)))

    def test_copies_follow_the_fonds_and_the_level(self):
        public_file = self.file_of[self.public]
        frappe.db.set_value("Fonds", self.public, "allow_copy", 0)
        with self.assertRaises(frappe.PermissionError) as caught:
            self.send([{"archival_file": public_file, "copy_count": 1}], doctype="Copy Request")
        self.assertIn("không cho phép sao chụp", str(caught.exception))
        self.send([{"archival_file": public_file}])  # reading it is still allowed
        frappe.db.set_value("Fonds", self.public, "allow_copy", 1)
        frappe.db.set_value("Confidentiality Level", "Thường", "allow_copy", 0)
        with self.assertRaises(frappe.PermissionError):
            self.send([{"archival_file": public_file, "copy_count": 1}], doctype="Copy Request")
        frappe.db.set_value("Confidentiality Level", "Thường", "allow_copy", 1)
        name = self.send([{"archival_file": public_file, "copy_count": 2, "copy_form": "Bản số", "page_range": "1-3"}], doctype="Copy Request")
        row = frappe.get_doc("Copy Request", name).items[0]
        self.assertEqual((row.copy_form, row.page_range), ("Bản số", "1-3"))

    # ---- reminders and the upgrade
    def test_a_reader_is_told_once_that_a_grant_ends_soon(self):
        self.grant("Reader", self.profile, self.licensed, valid_until=add_days(nowdate(), 5))
        self.grant("Reader", self.profile, self.licensed_2, valid_until=add_days(nowdate(), 40))
        self.assertEqual(fonds_access.remind_expiring(7), 1)
        self.assertEqual(fonds_access.remind_expiring(7), 0)
        self.assertTrue(frappe.db.exists("Notification Log", {"for_user": READER, "link": "/portal/tai-khoan"}))

    def test_the_upgrade_turns_every_fonds_into_explicit_grants_for_groups_that_saw_every_fonds(self):
        if not frappe.db.has_column("Reader Group", "fonds_scope"):
            self.skipTest("a site created after the change never had the old setting")
        frappe.db.sql("update `tabReader Group` set fonds_scope = 'Tất cả phông' where name = %s", GROUP)
        from document_manager.patches import fonds_access_modes

        fonds_access_modes.execute()
        granted = set(frappe.get_all("Reader Group Scope", filters={"parent": GROUP, "parenttype": "Reader Group"}, pluck="fonds"))
        self.assertTrue({self.public, self.licensed, self.licensed_2} <= granted)
        self.assertNotIn(self.internal, granted)
        self.assertEqual(frappe.db.get_value("Confidentiality Level", "Mật", "allow_copy"), 0)

    def test_the_lifecycle_reads_the_fonds_of_an_item(self):
        row = frappe._dict(archival_file=self.file_of[self.licensed], archive_document=None)
        self.assertEqual(lc.item_fonds(row), self.licensed)


def _group_with_reader_rights_but_no_grant() -> str:
    """A permission group that may change readers but not grant fonds; returns its role."""
    from document_manager.document_manager.api import permissions as perm_api

    frappe.set_user("Administrator")
    role = perm_api.create_group(f"FA Sửa độc giả {TAG}")["role"]
    perm_api.save_group(role, {"matrix": {"Reader": {"read": 1, "write": 1}}, "capabilities": []})
    return role
