# -*- coding: utf-8 -*-
"""Reader management in the staff app (G6): request templates, table fields in the generic forms, reader screens,
online access for readers, the feedback list, printouts and the sidebar.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_reader_admin
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager.api import boot, crud, feedback, meta, slips
from document_manager.document_manager.api import registration as reg_api
from document_manager.document_manager.api import requests as request_api
from document_manager.document_manager.services import registration, templates
from document_manager.document_manager.services.ui import link_targets
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _reader, _seed_archive, _user

TAG = frappe.generate_hash(length=5).lower()
READER_A = f"ra.a.{TAG}@example.com"
OFFICER = f"ra.officer.{TAG}@example.com"
LEADER = f"ra.leader.{TAG}@example.com"
ADMIN = f"ra.admin.{TAG}@example.com"
PRESERVER = f"ra.preserver.{TAG}@example.com"
STAFF_READER = f"ra.staffreader.{TAG}@example.com"


def _clear_templates(*kinds):
    for name in frappe.get_all("Request Template", filters={"kind": ["in", list(kinds)]}, pluck="name"):
        frappe.delete_doc("Request Template", name, force=True, ignore_permissions=True)


class TestReaderAdmin(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        _user(READER_A, ["Reader"], "Website User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(LEADER, ["Archive Leader"], "System User")
        _user(ADMIN, ["Document Admin"], "System User")
        _user(PRESERVER, ["Preservation Officer"], "System User")
        _user(STAFF_READER, ["Reading Room Officer", "Reader"], "System User")
        cls.profile = _reader(READER_A, "RA Người đọc")
        cls.staff_profile = _reader(STAFF_READER, "RA Cán bộ độc giả")
        cls._seeded = _seed_archive()
        cls.file_ok = _names(cls._seeded, "Archival File")[0]
        frappe.db.set_value("Archival File", cls.file_ok, {"shelf_number": "G9", "box_number": "H3"})
        cls.fonds = frappe.db.get_value("Archival File", cls.file_ok, "fonds")
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for dt in ("Usage Request", "Copy Request", "Reader Feedback"):
            for name in frappe.get_all(dt, filters={"reader": ["in", [cls.profile, cls.staff_profile]]}, pluck="name"):
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.flags.ignore_permissions = True
                    doc.cancel()
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for dt, name in cls._seeded:
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for profile in (cls.profile, cls.staff_profile):
            frappe.delete_doc("Reader", profile, force=True, ignore_permissions=True)
        for email in (READER_A, OFFICER, LEADER, ADMIN, PRESERVER, STAFF_READER):
            frappe.db.delete("Notification Log", {"for_user": email})
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user("Administrator")
        frappe.db.savepoint("ra_test")
        for field in ("max_requests_per_day", "max_copy_requests_per_day", "max_items_per_request", "max_open_requests"):
            frappe.db.set_single_value("Reader Settings", field, 0)
        frappe.clear_document_cache("Reader Settings", "Reader Settings")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="ra_test")
        frappe.clear_document_cache("Reader Settings", "Reader Settings")

    # ---- request templates
    def test_a_site_gets_one_active_template_per_kind(self):
        _clear_templates(templates.USAGE, templates.COPY, templates.REGISTRATION)
        self.assertEqual(templates.ensure_default_templates(), 3)
        self.assertEqual(templates.ensure_default_templates(), 0)  # once
        for kind in (templates.USAGE, templates.COPY, templates.REGISTRATION):
            self.assertEqual(frappe.db.count("Request Template", {"kind": kind, "is_active": 1}), 1, kind)
        self.assertIn("Nghiên cứu khoa học", templates.slip_options(templates.USAGE).purposes)

    def test_without_a_template_the_built_in_defaults_apply(self):
        _clear_templates(templates.USAGE, templates.REGISTRATION)
        options = templates.slip_options(templates.USAGE)
        self.assertTrue(options.require_purpose)
        self.assertEqual(options.template, None)
        form = templates.registration_form()
        self.assertEqual([f["fieldname"] for f in form.fields], ["phone", "id_number", "organization", "position", "address", "purpose"])
        self.assertTrue(all(f["visible"] and not f["required"] for f in form.fields))

    def test_only_one_template_of_a_kind_is_active(self):
        _clear_templates(templates.USAGE)
        first = frappe.get_doc({"doctype": "Request Template", "template_name": f"RA mẫu 1 {TAG}", "kind": templates.USAGE, "is_active": 1}).insert()
        second = frappe.get_doc({"doctype": "Request Template", "template_name": f"RA mẫu 2 {TAG}", "kind": templates.USAGE, "is_active": 1}).insert()
        self.assertEqual(frappe.db.get_value("Request Template", first.name, "is_active"), 0)  # the newer one took over
        self.assertEqual(templates.slip_options(templates.USAGE).template, second.name)

    def test_template_rules_are_validated(self):
        base = {"doctype": "Request Template", "template_name": f"RA mẫu {TAG}", "kind": templates.USAGE, "is_active": 0}
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({**base, "purposes": [{"purpose": "A"}, {"purpose": "a"}]}).insert()  # duplicate purposes
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({**base, "kind": templates.REGISTRATION, "form_fields": [{"field_name": "phone"}, {"field_name": "phone"}]}).insert()
        doc = frappe.get_doc({**base, "instructions": "<p>Điền đủ</p><script>alert(1)</script>"}).insert()
        self.assertNotIn("<script", doc.instructions)

    def test_registration_template_decides_which_fields_are_asked(self):
        _clear_templates(templates.REGISTRATION)
        frappe.get_doc({"doctype": "Request Template", "template_name": f"RA đăng ký {TAG}", "kind": templates.REGISTRATION, "is_active": 1,
                        "title": "Đăng ký độc giả RA", "instructions": "<p>Mang theo CCCD</p>",
                        "form_fields": [{"field_name": "phone", "visible": 1, "required": 1, "label": "Số di động"},
                                        {"field_name": "id_number", "visible": 0, "required": 1},   # hidden: never required
                                        {"field_name": "address", "visible": 1, "required": 0}]}).insert()
        form = templates.registration_form()
        by_name = {f["fieldname"]: f for f in form.fields}
        self.assertEqual((form.title, by_name["phone"]["label"], by_name["phone"]["required"]), ("Đăng ký độc giả RA", "Số di động", True))
        self.assertEqual((by_name["id_number"]["visible"], by_name["id_number"]["required"]), (False, False))
        self.assertTrue(by_name["organization"]["visible"])  # not listed: shown, not required
        settings = frappe._dict(allow_self_registration=1, require_approval=1)
        with patch.object(registration, "registration_settings", return_value=settings):
            with self.assertRaises(frappe.ValidationError):  # the phone is now required
                registration.submit_registration({"full_name": "Người Mới", "email": f"ra.new1.{TAG}@example.com"})
            registration.submit_registration({"full_name": "Người Mới", "email": f"ra.new1.{TAG}@example.com", "phone": "0912345678",
                                              "id_number": "123456789"})
        saved = frappe.get_doc("Reader Registration", {"email": f"ra.new1.{TAG}@example.com"})
        self.assertEqual(saved.phone, "0912345678")
        self.assertFalse(saved.id_number)  # the hidden field was dropped

    def test_a_slip_needs_a_purpose_only_when_the_template_says_so(self):
        frappe.set_user(READER_A)
        payload = json.dumps({"items": [{"archival_file": self.file_ok}]})
        with self.assertRaises(frappe.ValidationError):
            request_api.save_request("Usage Request", payload, submit=1)
        frappe.set_user("Administrator")
        _clear_templates(templates.USAGE)
        frappe.get_doc({"doctype": "Request Template", "template_name": f"RA phiếu {TAG}", "kind": templates.USAGE, "is_active": 1,
                        "require_purpose": 0}).insert()
        frappe.set_user(READER_A)
        self.assertEqual(request_api.save_request("Usage Request", payload, submit=1)["state"], "Chờ duyệt")

    def test_print_options_carry_the_header_and_footer(self):
        _clear_templates(templates.USAGE)
        frappe.get_doc({"doctype": "Request Template", "template_name": f"RA in {TAG}", "kind": templates.USAGE, "is_active": 1,
                        "title": "PHIẾU RA", "print_header": "Cộng hòa RA", "print_footer": "Giữ gìn tài liệu"}).insert()
        options = templates.dm_print_options("Usage Request")
        self.assertEqual((options.title, options.header, options.footer), ("PHIẾU RA", "Cộng hòa RA", "Giữ gìn tài liệu"))
        self.assertEqual(templates.dm_print_options("Fonds").header, "")

    # ---- table fields in the generic forms
    def test_a_table_field_is_described_with_its_columns(self):
        frappe.set_user(ADMIN)
        info = meta.get_doctype_ui("Reader Group")
        table = next(f for f in info["fields"] if f["fieldname"] == "fonds_scopes")
        self.assertEqual(table["fieldtype"], "Table")
        self.assertEqual([c["fieldname"] for c in table["table"]["columns"]], ["fonds", "fonds_name"])
        self.assertTrue(next(c for c in table["table"]["columns"] if c["fieldname"] == "fonds_name")["read_only"])  # fetched, not typed

    def test_table_rows_are_saved_replaced_and_read_back(self):
        frappe.set_user(ADMIN)
        saved = crud.save("Reader Group", {"group_name": f"RA nhóm {TAG}", "fonds_scope": "Chỉ các phông được chọn",
                                           "fonds_scopes": [{"fonds": self.fonds, "junk": "ignored"}]})
        self.assertEqual([r["fonds"] for r in saved["fonds_scopes"]], [self.fonds])
        again = crud.save("Reader Group", {"fonds_scopes": [], "fonds_scope": "Tất cả phông", "modified": saved["modified"]}, name=saved["name"])
        self.assertEqual(again["fonds_scopes"], [])
        with self.assertRaises(frappe.ValidationError):
            crud.save("Reader Group", {"fonds_scopes": "not a list"}, name=saved["name"])
        with self.assertRaises(frappe.ValidationError):
            crud.save("Reader Group", {"fonds_scopes": [{}] * 500}, name=saved["name"])

    def test_the_template_screen_edits_its_tables(self):
        frappe.set_user(ADMIN)
        saved = crud.save("Request Template", {"template_name": f"RA mẫu {TAG}", "kind": templates.USAGE, "is_active": 0,
                                               "purposes": [{"purpose": "Nghiên cứu"}, {"purpose": "Học tập"}]})
        self.assertEqual([r["purpose"] for r in saved["purposes"]], ["Nghiên cứu", "Học tập"])

    def test_link_search_offers_what_the_forms_link_to_but_never_users(self):
        frappe.set_user(ADMIN)
        targets = link_targets()
        self.assertIn("Fonds", targets)  # the link inside the reader group's table
        self.assertIn("Reader Group", targets)
        for forbidden in ("User", "Role", "DocType"):
            self.assertNotIn(forbidden, targets)
            with self.assertRaises(frappe.PermissionError):
                crud.link_search(forbidden, "a")

    # ---- the reader screens
    def test_readers_are_managed_through_the_generic_screen(self):
        frappe.set_user(OFFICER)
        info = meta.get_doctype_ui("Reader")
        fields = {f["fieldname"]: f for f in info["fields"]}
        self.assertTrue(fields["user"]["read_only"])  # the account is created by an action, never typed
        self.assertTrue(fields["reader_group"]["read_only"])  # clearance is Document Admin's
        saved = crud.save("Reader", {"full_name": "RA Người mới", "email": f"ra.walkin.{TAG}@example.com", "phone": "0912345678", "is_active": 1})
        self.assertEqual(saved["email"], f"ra.walkin.{TAG}@example.com")
        self.assertFalse(saved.get("user"))
        crud.save("Reader", {"reader_group": "", "user": READER_A, "full_name": "Đổi tên", "modified": saved["modified"]}, name=saved["name"])
        reader = frappe.get_doc("Reader", saved["name"])
        self.assertEqual((reader.full_name, reader.user), ("Đổi tên", None))  # user stays unlinked
        frappe.set_user(LEADER)
        self.assertFalse(meta.get_doctype_ui("Reader")["permissions"]["write"])

    def test_the_reader_settings_form_is_a_single_document(self):
        frappe.set_user(ADMIN)
        info = meta.get_doctype_ui("Reader Settings")
        self.assertTrue(info["is_single"])
        self.assertIn("max_renewals", {f["fieldname"] for f in info["fields"]})
        current = crud.get("Reader Settings", "Reader Settings")
        saved = crud.save("Reader Settings", {"renewal_days": 9, "modified": current["modified"]}, name="Reader Settings")
        self.assertEqual(saved["renewal_days"], 9)
        frappe.set_user(LEADER)
        with self.assertRaises(frappe.PermissionError):
            crud.save("Reader Settings", {"renewal_days": 1}, name="Reader Settings")

    # ---- online access
    def test_online_access_creates_the_account_once_and_then_reissues_the_link(self):
        reader = frappe.get_doc({"doctype": "Reader", "full_name": "RA Tại quầy", "email": f"ra.counter.{TAG}@example.com", "is_active": 1}).insert()
        frappe.set_user(OFFICER)
        first = reg_api.issue_reader_access(reader.name)
        self.assertTrue(first["created"])
        self.assertTrue(first["set_password_path"].startswith("/dat-mat-khau?key="))
        user = frappe.get_doc("User", f"ra.counter.{TAG}@example.com")
        self.assertEqual((user.user_type, [r.role for r in user.roles]), ("Website User", ["Reader"]))
        self.assertEqual(frappe.db.get_value("Reader", reader.name, "user"), user.name)
        second = reg_api.issue_reader_access(reader.name)
        self.assertFalse(second["created"])
        self.assertNotEqual(first["set_password_path"], second["set_password_path"])  # the earlier link stops working
        self.assertEqual(frappe.db.count("User", {"name": user.name}), 1)

    def test_online_access_refuses_what_it_should(self):
        no_email = frappe.get_doc({"doctype": "Reader", "full_name": "RA Không email", "is_active": 1}).insert()
        taken = frappe.get_doc({"doctype": "Reader", "full_name": "RA Trùng", "email": READER_A, "is_active": 1}).insert()
        locked = frappe.get_doc({"doctype": "Reader", "full_name": "RA Khóa", "email": f"ra.locked.{TAG}@example.com", "is_active": 0}).insert()
        frappe.set_user(OFFICER)
        for name in (no_email.name, taken.name, locked.name):
            with self.assertRaises(frappe.ValidationError, msg=name):
                reg_api.issue_reader_access(name)
        with self.assertRaises(frappe.PermissionError):  # a staff account keeps the normal password flow
            reg_api.issue_reader_access(self.staff_profile)
        for user in (READER_A, LEADER, PRESERVER, "Guest"):
            frappe.set_user(user)
            with self.assertRaises(frappe.PermissionError, msg=user):
                reg_api.issue_reader_access(no_email.name)

    # ---- feedback
    def _feedback(self, subject="RA Cần bổ sung"):
        frappe.set_user(READER_A)
        name = request_api.submit_feedback(subject, "Nội dung <b>góp ý</b>")["name"]
        frappe.set_user("Administrator")
        return name

    def test_feedback_list_and_detail(self):
        name = self._feedback()
        frappe.set_user(OFFICER)
        result = feedback.list_feedback(status="Mới", search="RA Cần")
        self.assertIn(name, [r.name for r in result["rows"]])
        self.assertGreaterEqual(result["counts"]["Mới"], 1)
        item = feedback.get_feedback(name)
        self.assertEqual((item["reader_name"], item["status"]), ("RA Người đọc", "Mới"))
        self.assertIn("Đánh dấu đã xem", item["actions"])
        self.assertIn("Phản hồi", item["actions"])
        request_api.apply_action("Reader Feedback", name, "Phản hồi", text="Đã bổ sung")
        self.assertEqual(feedback.get_feedback(name)["status"], "Đã phản hồi")
        self.assertIn("Đã bổ sung", feedback.get_feedback(name)["response"])
        self.assertEqual(feedback.list_feedback(status="Mới", search="RA Cần")["rows"], [])

    def test_feedback_is_for_the_reading_room_and_leaders(self):
        name = self._feedback()
        for user in (READER_A, PRESERVER, "Guest"):
            frappe.set_user(user)
            with self.assertRaises(frappe.PermissionError, msg=user):
                feedback.list_feedback()
            with self.assertRaises(frappe.PermissionError, msg=user):
                feedback.get_feedback(name)
        frappe.set_user(LEADER)
        self.assertEqual(feedback.get_feedback(name)["name"], name)
        self.assertEqual(feedback.get_feedback(name)["actions"], [])  # leaders read, the reading room answers

    # ---- printouts
    def _slip(self, kind="Usage Request", approved=True):
        frappe.set_user(READER_A)
        name = request_api.save_request(kind, json.dumps({"purpose": "RA in ấn", "items": [{"archival_file": self.file_ok, "copy_count": 2}]}), submit=1)["name"]
        frappe.set_user(OFFICER)
        if approved:
            request_api.apply_action(kind, name, "Duyệt")
        frappe.set_user("Administrator")
        return name

    def test_slips_print_with_their_items_and_where_to_find_them(self):
        name = self._slip()
        standard = frappe.get_print("Usage Request", name, print_format="Usage Request Standard", no_letterhead=1)
        for expected in ("RA Người đọc", "RA in ấn", "RW Test File 0", "Đã duyệt", name):
            self.assertIn(expected, standard)
        pickup = frappe.get_print("Usage Request", name, print_format="Usage Request Pickup", no_letterhead=1)
        for expected in ("Phiếu lấy tài liệu", "Giá G9", "Hộp H3", "RW Test File 0"):
            self.assertIn(expected.lower(), pickup.lower())  # the heading is upper-cased by the stylesheet, not the text
        copy = self._slip("Copy Request")
        self.assertIn("Số bản", frappe.get_print("Copy Request", copy, print_format="Copy Request Standard", no_letterhead=1))

    def test_print_formats_use_the_template_texts_and_leave_out_turned_down_items(self):
        _clear_templates(templates.USAGE)
        frappe.get_doc({"doctype": "Request Template", "template_name": f"RA in {TAG}", "kind": templates.USAGE, "is_active": 1,
                        "print_header": "Cộng hòa RA", "print_footer": "Chân trang RA"}).insert()
        name = self._slip(approved=False)
        frappe.set_user(OFFICER)
        row = frappe.get_doc("Usage Request", name).items[0].name
        slips.decide_items("usage", name, json.dumps([{"row": row, "status": "Từ chối", "note": "Đang tu bổ"}]))
        frappe.set_user("Administrator")
        standard = frappe.get_print("Usage Request", name, print_format="Usage Request Standard", no_letterhead=1)
        self.assertIn("Cộng hòa RA", standard)
        self.assertIn("Chân trang RA", standard)
        self.assertIn("Đang tu bổ", standard)
        pickup = frappe.get_print("Usage Request", name, print_format="Usage Request Pickup", no_letterhead=1)
        self.assertNotIn("Giá G9", pickup)  # nothing to fetch for a turned-down item

    def test_the_reader_card_prints(self):
        card = frappe.get_print("Reader", self.profile, print_format="Reader Card", no_letterhead=1)
        for expected in ("THẺ ĐỘC GIẢ", "RA Người đọc", self.profile):
            self.assertIn(expected, card)

    def test_print_links_reach_the_slip_screen(self):
        name = self._slip()
        frappe.set_user(OFFICER)
        urls = slips.get_slip("usage", name)["print"]
        self.assertEqual(set(urls), {"standard", "pickup"})
        self.assertIn("download_print_pdf", urls["pickup"]["pdf"])
        frappe.set_user(READER_A)
        from document_manager.document_manager.api import archive

        with self.assertRaises(frappe.PermissionError):
            archive.download_print_pdf("Usage Request", name, "standard")  # printing is for staff

    # ---- the sidebar
    def _nav(self, user):
        frappe.set_user(user)
        data = boot.build_boot()
        return {g["group"]: {i["label"]: i for i in g["items"]} for g in data["nav"]}, data

    def test_the_reading_room_sees_the_queues_and_the_reader_screens(self):
        self._slip(approved=False)
        nav, data = self._nav(OFFICER)
        self.assertEqual(set(nav["Khai thác tài liệu"]), {"Phiếu yêu cầu sử dụng", "Phiếu sao chụp", "Góp ý của độc giả"})
        self.assertGreaterEqual(nav["Khai thác tài liệu"]["Phiếu yêu cầu sử dụng"]["badge"], 1)
        self.assertEqual(nav["Khai thác tài liệu"]["Phiếu yêu cầu sử dụng"]["route"], "/dashboard/doc-gia/phieu-su-dung")
        self.assertTrue({"Đăng ký độc giả", "Danh sách độc giả", "Nhóm độc giả", "Mẫu phiếu, mẫu đăng ký", "Thiết lập độc giả"} <= set(nav["Độc giả"]))
        self.assertEqual({e["slug"] for e in data["readers"]}, {"doc-gia", "nhom-doc-gia", "mau-phieu"})
        self.assertEqual([e["slug"] for e in data["settings"]], ["thiet-lap-doc-gia"])

    def test_a_leader_sees_what_waits_for_a_leader(self):
        name = self._slip(approved=False)
        frappe.set_user(OFFICER)
        request_api.apply_action("Usage Request", name, "Chuyển lãnh đạo")
        nav, _data = self._nav(LEADER)
        self.assertGreaterEqual(nav["Khai thác tài liệu"]["Phiếu yêu cầu sử dụng"]["badge"], 1)
        self.assertNotIn("Đăng ký độc giả", nav.get("Độc giả", {}))  # registrations hold ID numbers
        self.assertEqual(slips.waiting_counts()["feedback"], 0)

    def test_staff_without_a_role_here_see_none_of_it(self):
        nav, data = self._nav(PRESERVER)
        self.assertNotIn("Khai thác tài liệu", nav)
        self.assertNotIn("Độc giả", nav)
        self.assertEqual((data["readers"], data["settings"]), ([], []))

    def test_queue_badges_follow_the_counts(self):
        self._slip(approved=False)
        frappe.set_user(OFFICER)
        badges = slips.queue_badges()
        self.assertGreaterEqual(badges["/dashboard/doc-gia/phieu-su-dung"], 1)
        self.assertIn("/dashboard/doc-gia/dang-ky", badges)
        frappe.set_user(READER_A)
        with self.assertRaises(frappe.PermissionError):
            slips.queue_badges()

    def test_backfill_gives_old_slips_their_reader_name(self):
        name = self._slip(approved=False)
        frappe.db.set_value("Usage Request", name, "reader_name", "")
        from document_manager.patches import backfill_reader_names

        backfill_reader_names.execute()
        self.assertEqual(frappe.db.get_value("Usage Request", name, "reader_name"), "RA Người đọc")
