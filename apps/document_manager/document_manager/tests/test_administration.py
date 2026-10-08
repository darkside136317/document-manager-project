# -*- coding: utf-8 -*-
"""Administration (module 8): staff accounts and groups, the role matrix, the system log and its clean-up, the monitor and
the settings that reach Frappe.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_administration
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from document_manager.document_manager.api import admin, logs, users
from document_manager.document_manager.services import audit, registration
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _reader, _user

TAG = frappe.generate_hash(length=5).lower()
ADMIN = f"ad.admin.{TAG}@example.com"
SECOND_ADMIN = f"ad.second.{TAG}@example.com"
SYSMAN = f"ad.sysman.{TAG}@example.com"
CATALOGER = f"ad.cataloger.{TAG}@example.com"
OFFICER = f"ad.officer.{TAG}@example.com"
READER = f"ad.reader.{TAG}@example.com"
NEW = f"ad.new.{TAG}@example.com"
BASE_USERS = (ADMIN, SECOND_ADMIN, SYSMAN, CATALOGER, OFFICER, READER)


class TestAdministration(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        _user(ADMIN, ["Document Admin"], "System User")
        _user(SECOND_ADMIN, ["Document Admin"], "System User")
        _user(SYSMAN, ["System Manager", "Document Admin"], "System User")
        _user(CATALOGER, ["Cataloger"], "System User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(READER, ["Reader"], "Website User")
        cls.profile = _reader(READER, "AD Người đọc")
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        frappe.delete_doc("Reader", cls.profile, force=True, ignore_permissions=True)
        for group in frappe.get_all("Staff Group", filters={"group_name": ["like", f"AD %{TAG}"]}, pluck="name"):
            frappe.delete_doc("Staff Group", group, force=True, ignore_permissions=True)
        for email in (*BASE_USERS, NEW):
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        original = frappe.db.rollback
        self.commits, self.last_commit = 0, "ad_test"

        def commit():
            self.commits += 1
            self.last_commit = f"ad_commit_{self.commits}"
            frappe.db.savepoint(self.last_commit)

        def rollback(**kw):
            return original(**(kw if kw.get("save_point") else {"save_point": self.last_commit}))

        for target, replacement in (("commit", commit), ("rollback", rollback)):
            patcher = patch.object(frappe.db, target, side_effect=replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.original_rollback = original
        frappe.set_user(ADMIN)
        frappe.db.savepoint("ad_test")

    def tearDown(self):
        frappe.set_user("Administrator")
        self.original_rollback(save_point="ad_test")

    def mine(self, **kw):
        return users.list_users(search=TAG, **kw)

    # ---- who may use the user screens
    def test_only_administrators_manage_users_and_see_the_log(self):
        calls = (lambda: users.list_users(), lambda: users.get_user(CATALOGER), lambda: users.save_user({"first_name": "x"}, CATALOGER),
                 lambda: users.role_matrix(), lambda: users.roles_info(), lambda: users.set_enabled(OFFICER, 0), lambda: users.delete_user(OFFICER),
                 lambda: users.issue_password_link(OFFICER), lambda: logs.list_logs(), lambda: logs.filter_options(), lambda: logs.get_log("LOG-1"),
                 lambda: logs.preview_purge("2020-01-01"), lambda: logs.purge("2020-01-01", 0), lambda: logs.download_logs(), lambda: admin.monitor())
        for user in (CATALOGER, OFFICER, READER, "Guest"):
            frappe.set_user(user)
            for call in calls:
                with self.assertRaises(frappe.PermissionError, msg=user):
                    call()
        frappe.set_user(SYSMAN)
        self.assertIn("data", users.list_users())

    # ---- listing and searching
    def test_the_list_holds_staff_only_and_can_be_searched_and_filtered(self):
        result = self.mine()
        names = {u["name"] for u in result["data"]}
        self.assertEqual(names, {ADMIN, SECOND_ADMIN, SYSMAN, CATALOGER, OFFICER})  # not the reader, not Administrator
        by_name = {u["name"]: u for u in result["data"]}
        self.assertEqual(by_name[CATALOGER]["roles"], ["Cataloger"])
        self.assertTrue(by_name[SYSMAN]["protected"])
        self.assertFalse(by_name[CATALOGER]["protected"])
        self.assertTrue(by_name[ADMIN]["is_me"])
        self.assertEqual({u["name"] for u in self.mine(role="Cataloger")["data"]}, {CATALOGER})
        self.assertEqual({u["name"] for u in users.list_users(search=f"ad.second.{TAG}")["data"]}, {SECOND_ADMIN})
        frappe.db.set_value("User", OFFICER, "enabled", 0)
        self.assertEqual({u["name"] for u in self.mine(enabled=0)["data"]}, {OFFICER})
        page = self.mine(page=2, page_size=2)
        self.assertEqual((page["total"], len(page["data"]), page["page"]), (5, 2, 2))
        with self.assertRaises(frappe.ValidationError):
            users.list_users(role="System Manager")

    # ---- creating and editing
    def test_a_new_account_gets_its_roles_and_a_one_time_link_to_set_the_password(self):
        out = users.save_user({"email": NEW.upper(), "first_name": "Người", "last_name": "Mới", "phone": "0912345678",
                               "roles": ["Cataloger", "Preservation Officer"]})
        self.assertEqual((out["name"], out["full_name"], out["enabled"], out["roles"]), (NEW, "Người Mới", 1, ["Cataloger", "Preservation Officer"]))
        self.assertTrue(out["set_password_path"].startswith("/dat-mat-khau?key="))
        user, problem = registration.check_link(out["set_password_path"].split("key=")[1])
        self.assertEqual((user, problem), (NEW, None))
        self.assertEqual(frappe.db.get_value("User", NEW, "user_type"), "System User")
        self.assertTrue(frappe.db.exists("Business Activity Log", {"reference_name": NEW, "activity_type": "Quản lý người dùng"}))

    def test_account_creation_is_checked(self):
        with self.assertRaises(frappe.ValidationError):
            users.save_user({"email": "không phải email", "first_name": "x"})
        with self.assertRaises(frappe.ValidationError):
            users.save_user({"email": CATALOGER, "first_name": "x"})  # taken
        with self.assertRaises(frappe.ValidationError):
            users.save_user({"email": NEW, "first_name": " "})
        with self.assertRaises(frappe.ValidationError):
            users.save_user({"email": NEW, "first_name": "x", "roles": ["System Manager"]})
        with self.assertRaises(frappe.ValidationError):
            users.save_user({"email": NEW, "first_name": "x", "roles": ["Reader"]})
        self.assertFalse(frappe.db.exists("User", NEW))

    def test_editing_syncs_the_staff_roles_and_leaves_the_others_alone(self):
        frappe.set_user("Administrator")
        frappe.get_doc("User", CATALOGER).add_roles("Desk User")
        frappe.set_user(ADMIN)
        out = users.save_user({"roles": ["Reading Room Officer"], "phone": "0987654321", "last_name": "Đổi"}, CATALOGER)
        self.assertEqual(out["roles"], ["Reading Room Officer"])
        roles = set(frappe.get_roles(CATALOGER))
        self.assertIn("Desk User", roles)
        self.assertNotIn("Cataloger", roles)
        self.assertEqual((out["phone"], out["last_name"]), ("0987654321", "Đổi"))
        again = users.save_user({"first_name": "Chỉ tên"}, CATALOGER)  # roles not mentioned: unchanged
        self.assertEqual(again["roles"], ["Reading Room Officer"])

    def test_accounts_that_are_not_staff_or_not_ours_cannot_be_touched(self):
        for name in ("Administrator", "Guest", READER):
            with self.assertRaises((frappe.PermissionError, frappe.DoesNotExistError), msg=name):
                users.save_user({"first_name": "x"}, name)
        with self.assertRaises(frappe.DoesNotExistError):
            users.get_user("Administrator")
        with self.assertRaises(frappe.DoesNotExistError):
            users.save_user({"first_name": "x"}, "khong.co@example.com")
        with self.assertRaises(frappe.PermissionError):
            users.save_user({"first_name": "Hack"}, SYSMAN)  # holds System Manager: a Document Admin may not touch it
        frappe.set_user(SYSMAN)
        self.assertEqual(users.save_user({"first_name": "Được"}, SYSMAN)["first_name"], "Được")  # a System Manager may

    def test_nobody_locks_themselves_out_or_demotes_themselves(self):
        with self.assertRaises(frappe.ValidationError):
            users.set_enabled(ADMIN, 0)
        with self.assertRaises(frappe.ValidationError):
            users.save_user({"roles": ["Cataloger"]}, ADMIN)
        with self.assertRaises(frappe.ValidationError):
            users.delete_user(ADMIN)
        self.assertEqual(users.save_user({"roles": ["Document Admin", "Cataloger"]}, ADMIN)["roles"], ["Document Admin", "Cataloger"])

    def test_the_last_administrator_cannot_be_locked_demoted_or_deleted(self):
        holders = frappe.get_all("Has Role", filters={"role": ["in", ["Document Admin", "System Manager"]], "parenttype": "User"}, pluck="parent")
        for holder in set(holders) - {SECOND_ADMIN, "Administrator"}:
            frappe.db.set_value("User", holder, "enabled", 0)  # no other administrator is available (rolled back with the test)
        frappe.set_user("Administrator")
        for call in (lambda: users.set_enabled(SECOND_ADMIN, 0), lambda: users.save_user({"roles": ["Cataloger"]}, SECOND_ADMIN),
                     lambda: users.delete_user(SECOND_ADMIN)):
            with self.assertRaises(frappe.ValidationError):
                call()
        # another enabled administrator makes it fine
        frappe.db.set_value("User", ADMIN, "enabled", 1)
        self.assertEqual(users.set_enabled(SECOND_ADMIN, 0)["enabled"], 0)

    def test_locking_unlocking_and_the_password_link(self):
        self.assertEqual(users.set_enabled(OFFICER, 0)["enabled"], 0)
        with self.assertRaises(frappe.ValidationError):
            users.issue_password_link(OFFICER)  # a locked account gets no link
        self.assertEqual(users.set_enabled(OFFICER, 1)["enabled"], 1)
        link = users.issue_password_link(OFFICER)
        self.assertEqual(registration.check_link(link["set_password_path"].split("key=")[1]), (OFFICER, None))
        with self.assertRaises(frappe.PermissionError):
            users.issue_password_link(READER)  # readers have their own screen

    def test_an_account_with_records_is_locked_not_deleted_and_a_clean_one_goes(self):
        created = users.save_user({"email": NEW, "first_name": "Tạm", "roles": ["Cataloger"]})
        frappe.get_doc({"doctype": "Backup Batch", "backup_type": "Cơ sở dữ liệu", "initiated_by": NEW}).insert(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError) as caught:
            users.delete_user(NEW)
        self.assertIn("khóa tài khoản", str(caught.exception))
        self.assertTrue(frappe.db.exists("User", NEW))
        self.assertTrue(created)
        frappe.db.delete("Backup Batch", {"initiated_by": NEW})
        self.assertEqual(users.delete_user(NEW), {"name": NEW})
        self.assertFalse(frappe.db.exists("User", NEW))

    # ---- groups
    def group(self, name, roles=(), members=()):
        return frappe.get_doc({"doctype": "Staff Group", "group_name": f"AD {name} {TAG}", "roles": [{"role": r} for r in roles],
                               "members": [{"user": m} for m in members]}).insert()

    def test_saving_a_group_gives_its_roles_to_the_members_and_never_takes_one_away(self):
        group = self.group("Bảo quản", roles=["Preservation Officer"], members=[CATALOGER, OFFICER])
        for user in (CATALOGER, OFFICER):
            self.assertIn("Preservation Officer", frappe.get_roles(user))
        self.assertIn("Cataloger", frappe.get_roles(CATALOGER))  # what they had stays
        group.members = [m for m in group.members if m.user != OFFICER]
        group.save()
        self.assertIn("Preservation Officer", frappe.get_roles(OFFICER))  # leaving a group does not revoke

    def test_a_group_takes_only_staff_roles_and_staff_members_once_each(self):
        with self.assertRaises(frappe.ValidationError):
            self.group("Sai vai trò", roles=["System Manager"])
        with self.assertRaises(frappe.ValidationError):
            self.group("Độc giả", members=[READER])
        with self.assertRaises(frappe.ValidationError):
            self.group("Quản trị hệ thống", members=[SYSMAN])
        with self.assertRaises(frappe.ValidationError):
            self.group("Trùng", members=[CATALOGER, CATALOGER])
        with self.assertRaises(frappe.ValidationError):
            self.group("Trùng vai trò", roles=["Cataloger", "Cataloger"])

    def test_groups_appear_on_users_filter_the_list_and_follow_edits_and_deletion(self):
        self.group("Biên mục", members=[CATALOGER])
        name = f"AD Biên mục {TAG}"
        self.assertEqual({u["name"] for u in users.list_users(group=name)["data"]}, {CATALOGER})
        self.assertEqual(users.get_user(CATALOGER)["groups"], [name])
        users.save_user({"groups": [name]}, OFFICER)
        self.assertEqual({u["name"] for u in users.list_users(group=name)["data"]}, {CATALOGER, OFFICER})
        users.save_user({"groups": []}, CATALOGER)
        self.assertEqual({u["name"] for u in users.list_users(group=name)["data"]}, {OFFICER})
        with self.assertRaises(frappe.ValidationError):
            users.save_user({"groups": ["Không có nhóm này"]}, CATALOGER)
        users.delete_user(OFFICER)
        self.assertEqual(frappe.get_doc("Staff Group", name).members, [])

    # ---- the matrix
    def test_the_matrix_says_what_each_role_may_do(self):
        matrix = users.role_matrix()
        self.assertEqual([r["role"] for r in matrix["roles"]], list(users.STAFF_ASSIGNABLE_ROLES))
        perms = {row["doctype"]: row["perms"] for section in matrix["sections"] for row in section["doctypes"]}
        self.assertTrue(perms["Fonds"]["Cataloger"]["write"])
        self.assertFalse(perms["Fonds"]["Reading Room Officer"]["write"])
        self.assertTrue(perms["Fonds"]["Reading Room Officer"]["read"])
        self.assertTrue(perms["Backup Batch"]["Preservation Officer"]["write"])
        self.assertFalse(perms["Backup Batch"]["Cataloger"]["read"])
        self.assertTrue(perms["Staff Group"]["Document Admin"]["delete"])
        self.assertTrue(perms["Usage Request"]["Archive Leader"]["read"])
        self.assertFalse(perms["Usage Request"]["Archive Leader"]["delete"])

    # ---- the log
    def log(self, kind="Xem", user=None, when="2020-01-01 10:00:00", doctype="Fonds", name=None, text=""):
        row = frappe.get_doc({"doctype": "Business Activity Log", "activity_type": kind, "user": user or ADMIN, "reference_doctype": doctype,
                              "reference_name": name or f"AD-{TAG}", "timestamp": when, "description": text or f"thử {TAG}"})
        row.flags.ignore_permissions = True
        return row.insert()

    def test_the_log_is_listed_filtered_paged_and_read(self):
        a = self.log("Xem", when="2020-01-01 10:00:00", name=f"AD-1-{TAG}")
        self.log("Tạo mới", user=OFFICER, when="2020-01-02 10:00:00", name=f"AD-2-{TAG}", doctype="Catalog")
        self.log("Xem", when="2020-01-03 10:00:00", name=f"AD-3-{TAG}")
        everything = logs.list_logs(search=TAG)
        self.assertEqual(everything["total"], 3)
        self.assertEqual([r["reference_name"] for r in everything["data"]], [f"AD-3-{TAG}", f"AD-2-{TAG}", f"AD-1-{TAG}"])  # newest first
        self.assertEqual(logs.list_logs(search=TAG, activity_type="Tạo mới")["total"], 1)
        self.assertEqual(logs.list_logs(search=TAG, user=OFFICER)["data"][0]["reference_name"], f"AD-2-{TAG}")
        self.assertEqual(logs.list_logs(search=TAG, reference_doctype="Catalog")["total"], 1)
        self.assertEqual(logs.list_logs(search=TAG, date_from="2020-01-02", date_to="2020-01-02")["total"], 1)
        self.assertEqual(logs.list_logs(reference_name=f"AD-2-{TAG}")["total"], 1)
        page = logs.list_logs(search=TAG, page=2, page_size=2)
        self.assertEqual((page["total"], len(page["data"])), (3, 1))
        self.assertEqual(logs.get_log(a.name)["reference_name"], f"AD-1-{TAG}")
        options = logs.filter_options()
        self.assertIn("Dọn dẹp nhật ký", options["activity_types"])
        self.assertIn(OFFICER, options["users"])
        self.assertIn("Catalog", options["doctypes"])

    def test_the_log_downloads_as_csv_and_the_download_is_itself_logged(self):
        self.log("Xem", name=f"AD-csv-{TAG}", text="có dấu, và dấu phẩy")
        before = frappe.db.count("Business Activity Log", {"activity_type": "Tải xuống", "reference_doctype": "Business Activity Log"})
        logs.download_logs(search=TAG)
        response = frappe.local.response
        text = response["filecontent"].decode("utf-8")
        self.assertTrue(text.startswith("﻿Thời gian"))
        self.assertIn(f"AD-csv-{TAG}", text)
        self.assertIn('"có dấu, và dấu phẩy"', text)
        self.assertEqual(frappe.db.count("Business Activity Log", {"activity_type": "Tải xuống", "reference_doctype": "Business Activity Log"}), before + 1)
        with patch.object(logs, "MAX_EXPORT", 0):
            with self.assertRaises(frappe.ValidationError):
                logs.download_logs(search=TAG)

    def test_a_cleanup_shows_what_it_would_delete_and_refuses_recent_logs(self):
        for day in range(3):
            self.log("Xem", when=f"2020-02-0{day + 1} 10:00:00", name=f"AD-p{day}-{TAG}")
        self.log("Tạo mới", when="2020-02-04 10:00:00", name=f"AD-p3-{TAG}")
        preview = logs.preview_purge("2020-03-01", ["Xem", "Tạo mới"])
        counted = {r["activity_type"]: r["count"] for r in preview["by_type"]}
        self.assertGreaterEqual(counted["Xem"], 3)
        self.assertGreaterEqual(counted["Tạo mới"], 1)
        self.assertEqual(preview["total"], sum(counted.values()))
        self.assertLessEqual(str(preview["oldest"]), "2020-02-01 10:00:00")
        with self.assertRaises(frappe.ValidationError):
            logs.preview_purge(add_days(nowdate(), -3))  # the last week is never cleaned
        self.assertEqual(logs.preview_purge(add_days(nowdate(), -7))["min_keep_days"], 7)

    def test_a_cleanup_needs_the_count_typed_back_and_deletes_exactly_that(self):
        for day in range(3):
            self.log("Xem", when=f"2020-02-0{day + 1} 10:00:00", name=f"AD-d{day}-{TAG}")
        survivor = self.log("Tạo mới", when="2020-02-05 10:00:00", name=f"AD-keep-{TAG}")
        preview = logs.preview_purge("2020-03-01", ["Xem"])
        with self.assertRaises(frappe.ValidationError):
            logs.purge("2020-03-01", preview["total"] + 1, ["Xem"])  # a stale preview
        self.assertEqual(frappe.db.count("Business Activity Log", {"reference_name": ["like", f"AD-d%-{TAG}"]}), 3)
        result = logs.purge("2020-03-01", preview["total"], ["Xem"])
        self.assertEqual(result["deleted"], preview["total"])
        self.assertEqual(frappe.db.count("Business Activity Log", {"reference_name": ["like", f"AD-d%-{TAG}"]}), 0)
        self.assertTrue(frappe.db.exists("Business Activity Log", survivor.name))  # another type is left
        trace = frappe.get_all("Business Activity Log", filters={"activity_type": "Dọn dẹp nhật ký"}, fields=["description"], order_by="creation desc", limit=1)
        self.assertIn(f"Đã xóa {preview['total']} dòng", trace[0].description)
        with self.assertRaises(frappe.ValidationError):
            logs.purge("2020-03-01", 0, ["Xem"])  # nothing left to clean

    # ---- the monitor
    def test_the_monitor_gathers_the_state_of_the_system(self):
        data = admin.monitor()
        for key in ("services", "documents", "jobs", "storage", "users", "log", "backups", "site"):
            self.assertIn(key, data)
        self.assertEqual(set(data["services"]), {"mongodb", "meilisearch"})
        self.assertGreaterEqual(data["documents"]["total"], data["documents"]["indexed"])
        self.assertLessEqual(data["documents"]["percent"], 100)
        self.assertGreaterEqual(data["users"]["staff"], 5)
        self.assertIn("free_gb", data["storage"]["disk"])
        self.assertEqual(data["site"], frappe.local.site)

    def test_settings_added_to_an_existing_site_start_from_their_defaults_or_from_what_is_in_force(self):
        """A settings page that exists before its new fields were added reads them as 0: the first save must neither fail
        nor switch the password policy off."""
        frappe.db.set_single_value("System Settings", {"enable_password_policy": 1, "minimum_password_score": "3",
                                                       "allow_consecutive_login_attempts": 5, "allow_login_after_fail": 0})
        new_fields = ("backup_keep_min", "login_max_attempts", "login_lock_seconds", "enforce_password_policy", "minimum_password_score")
        frappe.db.sql("delete from tabSingles where doctype = 'Document Manager Settings' and field in %s", (new_fields,))
        frappe.clear_document_cache("Document Manager Settings", "Document Manager Settings")
        self.assertEqual(install.ensure_settings_defaults(), len(new_fields))
        settings = frappe.get_doc("Document Manager Settings")
        self.assertEqual((settings.backup_keep_min, settings.login_max_attempts, settings.login_lock_seconds), (3, 5, 60))
        self.assertEqual((settings.enforce_password_policy, str(settings.minimum_password_score)), (1, "3"))
        settings.save()  # the first save passes validation and keeps the policy in force
        self.assertEqual(frappe.db.get_single_value("System Settings", "enable_password_policy"), 1)
        # a form that was once saved empty left zeros behind: the screen still shows what is in force, and saving keeps it
        frappe.db.sql("update tabSingles set value = '0' where doctype = 'Document Manager Settings' and field in ('login_max_attempts', 'enforce_password_policy')")
        frappe.clear_document_cache("Document Manager Settings", "Document Manager Settings")
        again = frappe.get_doc("Document Manager Settings")
        self.assertEqual((again.login_max_attempts, again.enforce_password_policy), (5, 1))
        again.backup_keep_min = None  # an empty number is "not set"
        again.save()
        self.assertEqual((again.backup_keep_min, frappe.db.get_single_value("System Settings", "allow_consecutive_login_attempts")), (3, 5))
        again.backup_keep_min = 0  # a typed zero is a mistake, not "not set"
        with self.assertRaises(frappe.ValidationError):
            again.save()
        frappe.db.sql("update tabSingles set value = '0' where doctype = 'Document Manager Settings' and field = 'backup_keep_min'")
        self.assertGreaterEqual(install.ensure_settings_defaults(), 1)  # a zero left by an empty form is put back to the default
        self.assertEqual(frappe.db.get_single_value("Document Manager Settings", "backup_keep_min"), 3)
        self.assertEqual(install.ensure_settings_defaults(), 0)  # nothing left to fill, and a value an administrator chose stays

    def test_deleting_an_account_takes_it_out_of_its_groups_first(self):
        users.save_user({"email": NEW, "first_name": "Tạm", "roles": ["Cataloger"]})
        group = self.group("Có thành viên", roles=["Cataloger"], members=[NEW, CATALOGER])
        users.delete_user(NEW)
        self.assertFalse(frappe.db.exists("User", NEW))
        self.assertEqual([m.user for m in frappe.get_doc("Staff Group", group.name).members], [CATALOGER])
