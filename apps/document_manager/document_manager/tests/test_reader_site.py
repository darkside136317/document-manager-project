# -*- coding: utf-8 -*-
"""The reader site (G5): registration, public unit profile, basket, notifications, own account.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_reader_site
"""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase
from frappe.utils.data import sha256_hash

from document_manager.document_manager.api import account, basket as basket_api, registration as reg_api
from document_manager.document_manager.api import requests as request_api
from document_manager.document_manager.policy import is_staff
from document_manager.document_manager.services import basket, notify, public_site, registration
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _reader, _seed_archive, _user

TAG = frappe.generate_hash(length=5).lower()
READER_A = f"rs.a.{TAG}@example.com"
READER_B = f"rs.b.{TAG}@example.com"
OFFICER = f"rs.officer.{TAG}@example.com"
ADMIN = f"rs.admin.{TAG}@example.com"
STAFF_READER = f"rs.staff.{TAG}@example.com"
SECRET_LEVEL = f"RS Secret {TAG}"
NO_COPY_GROUP = f"RS No copy {TAG}"


def _settings(allow=1, approval=1):
    return patch.object(registration, "registration_settings",
                        return_value=frappe._dict(allow_self_registration=allow, require_approval=approval))


def _form(n, **extra):
    return {"full_name": f"Nguyễn Văn {n}", "email": f"rs.new{n}.{TAG}@example.com", "phone": "0912 345 678",
            "organization": "Sở Nội vụ", "purpose": "Nghiên cứu", **extra}


class TestReaderSite(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        _user(READER_A, ["Reader"], "Website User")
        _user(READER_B, ["Reader"], "Website User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(ADMIN, ["Document Admin"], "System User")
        _user(STAFF_READER, ["Reader", "Reading Room Officer"], "System User")
        cls.profile_a = _reader(READER_A, "RS Reader A")
        cls.profile_b = _reader(READER_B, "RS Reader B")
        cls.staff_profile = _reader(STAFF_READER, "RS Staff Reader")
        frappe.get_doc({"doctype": "Reader Group", "group_name": NO_COPY_GROUP, "is_active": 1,
                        "max_confidentiality_priority": 1, "can_request_copy": 0}).insert(ignore_permissions=True)
        if not frappe.db.exists("Confidentiality Level", SECRET_LEVEL):
            frappe.get_doc({"doctype": "Confidentiality Level", "level_name": SECRET_LEVEL,
                            "priority": 5}).insert(ignore_permissions=True)
        cls._seeded = _seed_archive()
        cls.file_ok, cls.file_secret = _names(cls._seeded, "Archival File")
        secret = frappe.get_doc("Archival File", cls.file_secret)
        secret.confidentiality_level = SECRET_LEVEL
        secret.save(ignore_permissions=True)
        cls.doc_ok = frappe.get_all("Archive Document", filters={"archival_file": cls.file_ok}, pluck="name")[0]
        cls.doc_secret = frappe.get_all("Archive Document", filters={"archival_file": cls.file_secret}, pluck="name")[0]
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for dt in ("Usage Request", "Copy Request"):
            for name in frappe.get_all(dt, filters={"reader": ["in", [cls.profile_a, cls.profile_b, cls.staff_profile]]},
                                       pluck="name"):
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.flags.ignore_permissions = True
                    doc.cancel()
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for dt, name in cls._seeded:
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for profile in (cls.profile_a, cls.profile_b, cls.staff_profile):
            frappe.delete_doc("Reader", profile, force=True, ignore_permissions=True)
        frappe.delete_doc("Reader Group", NO_COPY_GROUP, force=True, ignore_permissions=True)
        frappe.delete_doc("Confidentiality Level", SECRET_LEVEL, force=True, ignore_permissions=True)
        for email in (READER_A, READER_B, OFFICER, ADMIN, STAFF_READER):
            frappe.db.delete("Notification Log", {"for_user": email})
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user("Administrator")
        frappe.db.savepoint("rs_test")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="rs_test")

    # ---------------------------------------------------------------- registration (guest side)
    def test_registration_waits_for_an_officer(self):
        with _settings(approval=1):
            result = registration.submit_registration(_form(1), ip="10.0.0.1")
        self.assertEqual(result["status"], "pending")
        doc = frappe.get_doc("Reader Registration", {"email": _form(1)["email"]})
        self.assertEqual((doc.status, doc.request_type, doc.ip_address), ("Mới", "Đăng ký tài khoản", "10.0.0.1"))
        self.assertFalse(frappe.db.exists("User", doc.email))  # nothing is created before approval

    def test_registration_is_refused_when_the_site_does_not_take_sign_ups(self):
        with _settings(allow=0), self.assertRaises(frappe.ValidationError):
            registration.submit_registration(_form(2))
        self.assertFalse(frappe.db.exists("Reader Registration", {"email": _form(2)["email"]}))

    def test_registration_input_is_validated_and_cleaned(self):
        with _settings():
            for bad in ({"email": "not-an-email"}, {"full_name": " "}, {"phone": "abc"}, {"full_name": "x" * 200}):
                with self.assertRaises(frappe.ValidationError, msg=str(bad)):
                    registration.submit_registration(_form(3, **bad))
            registration.submit_registration(_form(4, full_name="  <b>An</b>   Nguyễn  ", email=f"RS.New4.{TAG}@Example.com"))
        doc = frappe.get_doc("Reader Registration", {"email": _form(4)["email"]})
        self.assertEqual(doc.full_name, "An Nguyễn")  # tags and extra blanks gone, email lower-cased

    def test_nobody_learns_whether_an_email_has_an_account(self):
        with _settings():
            known = registration.submit_registration(_form(5, email=READER_A))
            fresh = registration.submit_registration(_form(6))
            again = registration.submit_registration(_form(6))
        self.assertEqual(known, fresh)
        self.assertEqual(again, fresh)
        self.assertFalse(frappe.db.exists("Reader Registration", {"email": READER_A}))  # existing account: nothing queued
        self.assertEqual(frappe.db.count("Reader Registration", {"email": _form(6)["email"]}), 1)  # no double queue

    def test_api_honeypot_stores_nothing(self):
        with _settings():
            result = reg_api.register_reader(**_form(7), website="http://spam.example")
        self.assertEqual(result["status"], "pending")
        self.assertFalse(frappe.db.exists("Reader Registration", {"email": _form(7)["email"]}))

    def test_site_can_approve_registrations_by_itself(self):
        with _settings(approval=0):
            result = registration.submit_registration(_form(8))
        self.assertEqual(result["status"], "approved")
        self.assertTrue(result["set_password_path"].startswith("/dat-mat-khau?key="))
        self.assertTrue(frappe.db.get_value("Reader", {"email": _form(8)["email"]}, "user"))

    # ---------------------------------------------------------------- registration (officer side)
    def _pending(self, n):
        with _settings(approval=1):
            registration.submit_registration(_form(n))
        return frappe.db.get_value("Reader Registration", {"email": _form(n)["email"]}, "name")

    def test_officer_approval_creates_the_account_and_a_one_time_link(self):
        name = self._pending(10)
        frappe.set_user(OFFICER)
        result = reg_api.approve_registration(name)
        email = _form(10)["email"]
        user = frappe.get_doc("User", email)
        self.assertEqual(user.user_type, "Website User")
        self.assertEqual([r.role for r in user.roles], ["Reader"])
        self.assertFalse(is_staff(email))
        reader = frappe.get_doc("Reader", result["reader"])
        self.assertEqual((reader.user, reader.email, reader.organization), (email, email, "Sở Nội vụ"))
        self.assertTrue(reader.reader_group)  # the default group
        key = result["set_password_path"].split("key=")[1]
        self.assertEqual(frappe.db.get_value("User", email, "reset_password_key"), sha256_hash(key))  # only the hash is stored
        reg = frappe.get_doc("Reader Registration", name)
        self.assertEqual((reg.status, reg.decided_by, reg.user, reg.reader), ("Đã duyệt", OFFICER, email, reader.name))
        with self.assertRaises(frappe.ValidationError):  # already decided
            reg_api.approve_registration(name)

    def test_approval_that_cannot_finish_leaves_nothing_behind(self):
        name = self._pending(11)
        email = _form(11)["email"]
        _user(email, ["Reader"], "Website User")  # somebody took the email meanwhile
        frappe.set_user(OFFICER)
        with self.assertRaises(frappe.ValidationError):
            reg_api.approve_registration(name)
        self.assertEqual(frappe.db.get_value("Reader Registration", name, "status"), "Mới")
        self.assertFalse(frappe.db.exists("Reader", {"email": email}))

    def test_rejection_needs_a_reason(self):
        name = self._pending(12)
        frappe.set_user(OFFICER)
        with self.assertRaises(frappe.ValidationError):
            reg_api.reject_registration(name, "  ")
        reg_api.reject_registration(name, "Không đủ điều kiện")
        reg = frappe.get_doc("Reader Registration", name)
        self.assertEqual((reg.status, reg.rejection_reason, reg.decided_by), ("Từ chối", "Không đủ điều kiện", OFFICER))
        self.assertFalse(frappe.db.exists("User", _form(12)["email"]))
        with self.assertRaises(frappe.ValidationError):
            reg_api.approve_registration(name)

    def test_staff_boot_lists_the_queue_with_its_counter(self):
        from document_manager.document_manager.api import boot

        self._pending(15)
        frappe.set_user(OFFICER)
        group = next(g for g in boot.build_boot()["nav"] if g["group"] == "Độc giả")
        self.assertEqual(group["items"][0]["route"], "/dashboard/doc-gia/dang-ky")
        self.assertGreaterEqual(group["items"][0]["badge"], 1)
        frappe.set_user(ADMIN)
        self.assertEqual(reg_api.reader_groups()[0]["is_default"], 1)  # the default group comes first
        frappe.set_user(READER_A)
        with self.assertRaises(frappe.PermissionError):
            reg_api.reader_groups()

    def test_only_officers_work_the_queue(self):
        name = self._pending(13)
        for user in (READER_A, "Guest"):
            frappe.set_user(user)
            for call in (lambda: reg_api.list_registrations(), lambda: reg_api.pending_registrations(),
                         lambda: reg_api.approve_registration(name), lambda: reg_api.reject_registration(name, "x"),
                         lambda: reg_api.reissue_link(name)):
                with self.assertRaises(frappe.PermissionError, msg=user):
                    call()
        frappe.set_user(OFFICER)
        listing = reg_api.list_registrations(status="Mới", search=_form(13)["email"][:12])
        self.assertEqual([r.name for r in listing["rows"]], [name])
        self.assertEqual(listing["total"], 1)
        self.assertGreaterEqual(reg_api.pending_registrations(), 1)

    def test_lost_link_can_be_issued_again_only_after_approval(self):
        name = self._pending(14)
        frappe.set_user(ADMIN)
        with self.assertRaises(frappe.ValidationError):
            reg_api.reissue_link(name)
        first = reg_api.approve_registration(name)["set_password_path"]
        second = reg_api.reissue_link(name)["set_password_path"]
        self.assertNotEqual(first, second)  # the earlier link stops working

    def test_forgotten_password_goes_through_an_officer(self):
        unknown = registration.submit_password_help(f"nobody.{TAG}@example.com")
        known = registration.submit_password_help(READER_A.upper())
        self.assertEqual(unknown, known)  # the same answer, whoever asks
        self.assertEqual(frappe.db.count("Reader Registration", {"email": f"nobody.{TAG}@example.com"}), 0)
        registration.submit_password_help(READER_A)  # asking twice queues once
        rows = frappe.get_all("Reader Registration", filters={"user": READER_A}, fields=["name", "request_type", "status"])
        self.assertEqual([(r.request_type, r.status) for r in rows], [("Quên mật khẩu", "Mới")])
        frappe.set_user(OFFICER)
        result = reg_api.approve_registration(rows[0].name)
        self.assertEqual(result["user"], READER_A)
        self.assertTrue(result["set_password_path"].startswith("/dat-mat-khau?key="))
        self.assertEqual(frappe.db.count("User", {"name": READER_A}), 1)  # no new account

    def test_staff_accounts_never_get_a_link_or_a_reset_request(self):
        for email in (OFFICER, ADMIN, STAFF_READER):
            registration.submit_password_help(email)
            self.assertFalse(frappe.db.exists("Reader Registration", {"email": email}), email)
            with self.assertRaises(frappe.PermissionError, msg=email):
                registration.issue_password_link(email)

    # ---------------------------------------------------------------- public profile of the unit
    def _profile_from(self, **values):
        info = frappe._dict({"org_name": "Trung tâm A", "leaders": [], **values})
        with patch.object(public_site.frappe, "get_cached_doc", return_value=info):
            return public_site.get_org_profile()

    def test_profile_has_defaults_when_nothing_is_filled_in(self):
        profile = self._profile_from(org_name=None)
        self.assertEqual(profile["name"], public_site.DEFAULT_ORG_NAME)
        self.assertEqual(profile["leaders"], [])
        self.assertTrue(profile["show_leaders"] and profile["show_structure"])

    def test_profile_hides_hidden_leaders_and_orders_the_rest(self):
        leaders = [frappe._dict(idx=1, full_name="Ba", position="PGĐ", display_order=2, is_visible=1, photo="/files/b.png", bio=""),
                   frappe._dict(idx=2, full_name="Ẩn", position="X", display_order=0, is_visible=0, photo="", bio=""),
                   frappe._dict(idx=3, full_name="Một", position="GĐ", display_order=1, is_visible=1, photo="javascript:alert(1)", bio="")]
        profile = self._profile_from(leaders=leaders)
        self.assertEqual([l["full_name"] for l in profile["leaders"]], ["Một", "Ba"])
        self.assertEqual(profile["leaders"][0]["photo"], "")  # unsafe link dropped
        self.assertEqual(profile["leaders"][1]["photo"], "/files/b.png")

    def test_profile_text_is_sanitised_and_links_are_checked(self):
        profile = self._profile_from(introduction='<p>Xin chào</p><script>alert(1)</script>', website="javascript:alert(1)",
                                     map_url="https://maps.example/x", logo="//evil.example/x.png",
                                     reading_room_hours="Thứ Hai: 8h\n\n Thứ Ba: 8h ")
        self.assertNotIn("<script", profile["introduction"])
        self.assertIn("Xin chào", profile["introduction"])
        self.assertEqual((profile["website"], profile["logo"]), ("", ""))
        self.assertEqual(profile["map_url"], "https://maps.example/x")
        self.assertEqual(profile["hours"], ["Thứ Hai: 8h", "Thứ Ba: 8h"])

    def test_profile_can_switch_pages_off(self):
        profile = self._profile_from(hide_leaders=1, hide_structure=1)
        self.assertFalse(profile["show_leaders"] or profile["show_structure"])

    def test_unit_tree_nests_and_hides_with_the_parent(self):
        def unit(name, parent=None, **extra):
            return frappe.get_doc({"doctype": "Organization Unit", "unit_name": f"{name} {TAG}",
                                   "parent_organization_unit": f"{parent} {TAG}" if parent else None, **extra}
                                  ).insert(ignore_permissions=True)

        unit("Phòng A", display_order=2)
        unit("Phòng B", display_order=1)
        unit("Tổ A1", "Phòng A")
        unit("Phòng Ẩn", is_visible=0)
        unit("Tổ Ẩn1", "Phòng Ẩn")
        mine = [n for n in public_site.get_org_units() if n["unit_name"].endswith(TAG)]
        self.assertEqual([n["unit_name"] for n in mine], [f"Phòng B {TAG}", f"Phòng A {TAG}"])  # by display order
        self.assertEqual([c["unit_name"] for c in mine[1]["children"]], [f"Tổ A1 {TAG}"])
        flat = {n["unit_name"] for n in mine} | {c["unit_name"] for n in mine for c in n["children"]}
        self.assertNotIn(f"Phòng Ẩn {TAG}", flat)
        self.assertNotIn(f"Tổ Ẩn1 {TAG}", flat)  # a hidden unit takes its children with it
        self.assertTrue(frappe.db.get_value("Organization Unit", f"Phòng A {TAG}", "is_group"))

    def test_unit_cannot_be_its_own_parent(self):
        doc = frappe.get_doc({"doctype": "Organization Unit", "unit_name": f"Vòng {TAG}"}).insert(ignore_permissions=True)
        doc.parent_organization_unit = doc.name
        with self.assertRaises(frappe.ValidationError):
            doc.save()

    # ---------------------------------------------------------------- basket
    def test_adding_to_the_basket_builds_one_open_draft(self):
        frappe.set_user(READER_A)
        first = basket_api.add_to_basket("file", self.file_ok, "usage")
        self.assertTrue(first["added"])
        self.assertEqual(first["count"], 1)
        again = basket_api.add_to_basket("file", self.file_ok, "usage")
        self.assertFalse(again["added"])  # the same item twice is a no-op
        self.assertEqual(again["request"], first["request"])
        doc_added = basket_api.add_to_basket("document", self.doc_ok, "usage")
        self.assertTrue(doc_added["added"])
        self.assertEqual(doc_added["count"], 2)
        draft = frappe.get_doc("Usage Request", first["request"])
        self.assertEqual((draft.docstatus, draft.reader, draft.workflow_state), (0, self.profile_a, "Nháp"))
        row = [r for r in draft.items if r.archive_document][0]
        self.assertEqual(row.archival_file, self.file_ok)  # the document's file is filled in
        self.assertEqual(frappe.db.count("Usage Request", {"reader": self.profile_a, "docstatus": 0}), 1)
        summary = basket_api.get_basket()
        self.assertEqual((summary["usage"]["count"], summary["usage"]["name"]), (2, first["request"]))
        self.assertEqual(summary["copy"]["count"], 0)

    def test_copy_and_usage_baskets_are_separate(self):
        frappe.set_user(READER_A)
        usage = basket_api.add_to_basket("file", self.file_ok, "usage")
        copy = basket_api.add_to_basket("file", self.file_ok, "copy")
        self.assertNotEqual(usage["request"], copy["request"])
        self.assertTrue(copy["request"].startswith("CR-"))

    def test_basket_refuses_what_the_reader_may_not_see(self):
        frappe.set_user(READER_A)
        for kind, name in (("file", self.file_secret), ("document", self.doc_secret), ("file", "NO-SUCH-FILE"),
                           ("document", "")):
            with self.assertRaises(frappe.PermissionError, msg=name):
                basket_api.add_to_basket(kind, name, "usage")
        with self.assertRaises(frappe.PermissionError):
            basket_api.add_to_basket("file", self.file_ok, "bogus")
        with self.assertRaises(frappe.ValidationError):
            basket_api.add_to_basket("folder", self.file_ok, "usage")
        self.assertEqual(basket_api.get_basket()["usage"]["count"], 0)

    def test_basket_follows_the_feature_flags_of_the_group(self):
        frappe.db.set_value("Reader", self.profile_b, "reader_group", NO_COPY_GROUP)
        frappe.set_user(READER_B)
        with self.assertRaises(frappe.PermissionError):
            basket_api.add_to_basket("file", self.file_ok, "copy")
        self.assertTrue(basket_api.add_to_basket("file", self.file_ok, "usage")["added"])  # usage is still allowed

    def test_staff_without_a_reader_profile_has_no_basket(self):
        frappe.set_user(OFFICER)
        with self.assertRaises(frappe.PermissionError):
            basket_api.add_to_basket("file", self.file_ok, "usage")
        self.assertEqual(basket_api.get_basket()["usage"]["count"], 0)

    def test_staff_with_a_reader_profile_can_use_the_basket(self):
        frappe.set_user(STAFF_READER)
        self.assertTrue(basket_api.add_to_basket("file", self.file_secret, "usage")["added"])

    def test_removing_rows_and_discarding(self):
        frappe.set_user(READER_A)
        added = basket_api.add_to_basket("file", self.file_ok, "usage")
        basket_api.add_to_basket("document", self.doc_ok, "usage")
        draft = frappe.get_doc("Usage Request", added["request"])
        result = basket_api.remove_from_basket("Usage Request", draft.name, draft.items[0].name)
        self.assertEqual(result["count"], 1)
        last = frappe.get_doc("Usage Request", draft.name).items[0].name
        result = basket_api.remove_from_basket("Usage Request", draft.name, last)
        self.assertIsNone(result["request"])  # the emptied draft is gone
        self.assertFalse(frappe.db.exists("Usage Request", draft.name))
        again = basket_api.add_to_basket("file", self.file_ok, "usage")
        basket_api.discard_draft("Usage Request", again["request"])
        self.assertFalse(frappe.db.exists("Usage Request", again["request"]))

    def test_nobody_edits_another_readers_basket_or_a_sent_slip(self):
        frappe.set_user(READER_A)
        added = basket_api.add_to_basket("file", self.file_ok, "usage")
        row = frappe.get_doc("Usage Request", added["request"]).items[0].name
        frappe.set_user(READER_B)
        with self.assertRaises(frappe.PermissionError):
            basket_api.remove_from_basket("Usage Request", added["request"], row)
        with self.assertRaises(frappe.PermissionError):
            basket_api.discard_draft("Usage Request", added["request"])
        frappe.set_user(READER_A)
        request_api.save_request("Usage Request", frappe.as_json({"purpose": "Nghiên cứu"}), name=added["request"], submit=1)
        for call in (lambda: basket_api.remove_from_basket("Usage Request", added["request"], row),
                     lambda: basket_api.discard_draft("Usage Request", added["request"])):
            with self.assertRaises(frappe.PermissionError):
                call()
        fresh = basket_api.add_to_basket("file", self.file_ok, "usage")  # a sent slip is no longer the basket
        self.assertNotEqual(fresh["request"], added["request"])
        self.assertTrue(fresh["added"])

    # ---------------------------------------------------------------- notifications
    def _sent_slip(self, reader_user=READER_A):
        frappe.set_user(reader_user)
        added = basket_api.add_to_basket("file", self.file_ok, "usage")
        request_api.save_request("Usage Request", frappe.as_json({"purpose": "Nghiên cứu"}), name=added["request"], submit=1)
        return added["request"]

    def test_reader_is_told_when_an_officer_decides(self):
        name = self._sent_slip()
        self.assertEqual(notify.unread_count(READER_A), 0)  # the reader's own "Gửi duyệt" notifies nobody
        emails_before = frappe.db.count("Email Queue")
        frappe.set_user(OFFICER)
        request_api.apply_action("Usage Request", name, "Duyệt")
        logs = frappe.get_all("Notification Log", filters={"for_user": READER_A}, fields=["subject", "link", "type", "read"])
        self.assertEqual(len(logs), 1)
        self.assertIn(name, logs[0].subject)
        self.assertIn("đã được duyệt", logs[0].subject)
        self.assertEqual((logs[0].link, logs[0].type, logs[0].read), (f"/portal/phieu/{name}", "Alert", 0))
        self.assertEqual(frappe.db.count("Email Queue"), emails_before)  # in-app only, no mail attempted
        request_api.apply_action("Usage Request", name, "Giao tài liệu")
        request_api.apply_action("Usage Request", name, "Nhận trả")
        self.assertEqual(notify.unread_count(READER_A), 3)  # duyệt, giao, trả

    def test_rejection_reason_reaches_the_reader(self):
        name = self._sent_slip()
        frappe.set_user(OFFICER)
        request_api.apply_action("Usage Request", name, "Từ chối", text="Tài liệu đang số hóa")
        subject = frappe.get_all("Notification Log", filters={"for_user": READER_A}, pluck="subject")[0]
        self.assertIn("bị từ chối", subject)
        self.assertIn("Tài liệu đang số hóa", subject)

    def test_copy_slip_and_feedback_notify_with_their_own_links(self):
        frappe.set_user(READER_A)
        added = basket_api.add_to_basket("file", self.file_ok, "copy")
        request_api.save_request("Copy Request", frappe.as_json({"purpose": "In"}), name=added["request"], submit=1)
        feedback = request_api.submit_feedback("Cần thêm bản quét", "Xin bổ sung")["name"]
        frappe.set_user(OFFICER)
        request_api.apply_action("Copy Request", added["request"], "Duyệt")
        request_api.apply_action("Reader Feedback", feedback, "Phản hồi", text="Đã bổ sung")
        links = sorted(frappe.get_all("Notification Log", filters={"for_user": READER_A}, pluck="link"))
        self.assertEqual(links, sorted([f"/portal/sao-chep/{added['request']}", f"/portal/gop-y/{feedback}"]))

    def test_notifications_are_private_and_can_be_marked_read(self):
        name = self._sent_slip(READER_A)
        frappe.set_user(OFFICER)
        request_api.apply_action("Usage Request", name, "Duyệt")
        notify.notify_user(READER_B, "Dành cho B", "/portal")
        frappe.set_user(READER_B)
        mine = account.get_notifications()
        self.assertEqual([r.subject for r in mine["rows"]], ["Dành cho B"])
        self.assertEqual(account.get_unread_count(), 1)
        frappe.set_user(READER_A)
        theirs = account.get_notifications()["rows"][0].name
        frappe.set_user(READER_B)
        self.assertEqual(account.mark_notifications_read(frappe.as_json([theirs])), 1)  # not B's: ignored
        self.assertEqual(account.mark_notifications_read(), 0)
        frappe.set_user(READER_A)
        self.assertEqual(account.get_unread_count(), 1)  # A's own bell is untouched
        self.assertEqual(account.mark_notifications_read(frappe.as_json([theirs])), 0)

    def test_notifying_never_breaks_the_caller(self):
        self.assertIsNone(notify.notify_user("Guest", "x", "/"))
        self.assertIsNone(notify.notify_user("", "x", "/"))
        self.assertIsNone(notify.notify_user("nobody@example.com", "x", "/"))  # unknown user: logged, not raised

    # ---------------------------------------------------------------- own account
    def test_account_shows_the_profile_and_what_the_group_allows(self):
        frappe.db.set_value("Reader", self.profile_a, "reader_group", NO_COPY_GROUP)
        frappe.set_user(READER_A)
        data = account.get_account()
        self.assertEqual(data["profile"]["full_name"], "RS Reader A")
        self.assertEqual(data["group"], NO_COPY_GROUP)
        allowed = {f["feature"]: f["allowed"] for f in data["features"]}
        self.assertFalse(allowed["can_request_copy"])
        self.assertTrue(allowed["can_request_usage"])

    def test_profile_edit_is_limited_to_contact_fields(self):
        frappe.set_user(READER_A)
        account.update_profile(phone="0987654321", address="<i>1 Phố Huế</i>", organization="Viện Sử học", position="NCV")
        reader = frappe.get_doc("Reader", self.profile_a)
        self.assertEqual((reader.phone, reader.address, reader.organization, reader.position),
                         ("0987654321", "1 Phố Huế", "Viện Sử học", "NCV"))
        self.assertEqual((reader.full_name, reader.email, reader.is_active), ("RS Reader A", READER_A, 1))
        group_before = reader.reader_group
        # Fields outside the allow-list are not even parameters: nothing can raise a reader's clearance.
        with self.assertRaises(TypeError):
            account.update_profile(max_confidentiality_priority=9)
        self.assertEqual(frappe.db.get_value("Reader", self.profile_a, ["reader_group", "max_confidentiality_priority"]),
                         (group_before, 1))

    def test_account_needs_a_reader_profile(self):
        frappe.set_user(OFFICER)
        for call in (account.get_account, account.update_profile):
            with self.assertRaises(frappe.PermissionError):
                call()

    def test_a_wrong_current_password_is_a_message_not_an_authentication_error(self):
        # AuthenticationError makes the framework end the session: the reader must stay signed in
        frappe.set_user(READER_A)
        with self.assertRaises(frappe.ValidationError) as caught:
            account.change_password("not-the-password", "Abc!12345xyz-new")
        self.assertNotIsInstance(caught.exception, frappe.AuthenticationError)

    def test_password_change_asks_for_both_passwords(self):
        frappe.set_user(READER_A)
        for old, new in (("", "Abc!12345xyz"), ("Abc!12345xyz", ""), ("Same!12345xyz", "Same!12345xyz")):
            with self.assertRaises(frappe.ValidationError):
                account.change_password(old, new)

    # ---------------------------------------------------------------- seed
    def test_set_password_link_expiry_only_replaces_the_factory_value(self):
        frappe.db.set_single_value("System Settings", "reset_password_link_expiry_duration", 1200)
        self.assertTrue(install.set_password_link_expiry())
        self.assertEqual(frappe.utils.cint(frappe.db.get_single_value("System Settings", "reset_password_link_expiry_duration")),
                         install.PASSWORD_LINK_EXPIRY_SECONDS)
        frappe.db.set_single_value("System Settings", "reset_password_link_expiry_duration", 6 * 3600)
        self.assertFalse(install.set_password_link_expiry())  # an administrator's choice stays
        self.assertEqual(frappe.utils.cint(frappe.db.get_single_value("System Settings", "reset_password_link_expiry_duration")), 6 * 3600)

    def test_seed_registers_the_officer_notification(self):
        install.seed_all()
        self.assertTrue(frappe.db.exists("Notification", "Đăng ký độc giả mới"))
