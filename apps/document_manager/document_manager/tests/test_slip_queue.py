# -*- coding: utf-8 -*-
"""The staff queue API of reader slips (api/slips.py): lists with counters, the full slip, access.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_slip_queue
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from document_manager.document_manager.api import basket as basket_api
from document_manager.document_manager.api import requests as request_api
from document_manager.document_manager.api import slips
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _reader, _seed_archive, _user

TAG = frappe.generate_hash(length=5).lower()
READER = f"sq.reader.{TAG}@example.com"
OFFICER = f"sq.officer.{TAG}@example.com"
LEADER = f"sq.leader.{TAG}@example.com"
ADMIN = f"sq.admin.{TAG}@example.com"
PRESERVER = f"sq.preserver.{TAG}@example.com"


class TestSlipQueue(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        _user(READER, ["Reader"], "Website User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(LEADER, ["Archive Leader"], "System User")
        _user(ADMIN, ["Document Admin"], "System User")
        _user(PRESERVER, ["Preservation Officer"], "System User")
        cls.profile = _reader(READER, "SQ Người đọc")
        cls._seeded = _seed_archive()
        cls.file_ok, cls.file_two = _names(cls._seeded, "Archival File")
        frappe.db.set_value("Archival File", cls.file_ok, {"shelf_number": "G5", "box_number": "H12"})
        cls.doc_ok = frappe.get_all("Archive Document", filters={"archival_file": cls.file_ok}, pluck="name")[0]
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for dt in ("Usage Request", "Copy Request"):
            for name in frappe.get_all(dt, filters={"reader": cls.profile}, pluck="name"):
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.flags.ignore_permissions = True
                    doc.cancel()
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for dt, name in cls._seeded:
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        frappe.delete_doc("Reader", cls.profile, force=True, ignore_permissions=True)
        for email in (READER, OFFICER, LEADER, ADMIN, PRESERVER):
            frappe.db.delete("Notification Log", {"for_user": email})
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user("Administrator")
        frappe.db.savepoint("sq_test")
        for field in ("max_requests_per_day", "max_copy_requests_per_day", "max_items_per_request", "max_open_requests"):
            frappe.db.set_single_value("Reader Settings", field, 0)
        frappe.clear_document_cache("Reader Settings", "Reader Settings")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="sq_test")
        frappe.clear_document_cache("Reader Settings", "Reader Settings")

    # ---- helpers
    def _send(self, doctype="Usage Request", items=None):
        frappe.set_user(READER)
        name = request_api.save_request(doctype, json.dumps({"purpose": "SQ nghiên cứu", "items": items or [{"archival_file": self.file_ok}]}), submit=1)["name"]
        frappe.set_user("Administrator")
        return name

    def _act(self, user, name, action, doctype="Usage Request", text=None):
        frappe.set_user(user)
        request_api.apply_action(doctype, name, action, text=text)
        frappe.set_user("Administrator")

    def _mine(self, kind, view, user=OFFICER):
        frappe.set_user(user)
        return [r.name for r in slips.list_slips(kind, view, search="SQ", page_size=100)["rows"]]

    # ---- lists and counters
    def test_each_slip_lands_in_the_view_of_its_state(self):
        waiting, approved, in_use, done = self._send(), self._send(), self._send(), self._send()
        self._act(OFFICER, approved, "Duyệt")
        self._act(OFFICER, in_use, "Duyệt")
        self._act(OFFICER, in_use, "Giao tài liệu")
        self._act(OFFICER, done, "Từ chối", text="Không đủ điều kiện")
        self.assertIn(waiting, self._mine("usage", "cho_tiep_nhan"))
        self.assertNotIn(approved, self._mine("usage", "cho_tiep_nhan"))
        self.assertIn(approved, self._mine("usage", "cho_thuc_hien"))
        self.assertIn(in_use, self._mine("usage", "dang_su_dung"))
        self.assertIn(done, self._mine("usage", "da_dong"))
        self.assertEqual(self._mine("usage", "qua_han"), [])
        self.assertTrue({waiting, approved, in_use, done} <= set(self._mine("usage", "tat_ca")))

    def test_overdue_slips_have_their_own_view_sorted_by_due_date(self):
        late, later = self._send(), self._send()
        for name, days in ((late, -9), (later, -2)):
            self._act(OFFICER, name, "Duyệt")
            self._act(OFFICER, name, "Giao tài liệu")
            frappe.db.set_value("Usage Request", name, {"due_date": add_days(nowdate(), days), "is_overdue": 1})
        self.assertEqual(self._mine("usage", "qua_han"), [late, later])  # the most overdue first
        self.assertEqual(self._mine("usage", "dang_su_dung"), [late, later])

    def test_counters_follow_the_queue(self):
        frappe.set_user(OFFICER)
        before = slips.queue_summary()["usage"]
        self._send()
        self._send(doctype="Copy Request")
        frappe.set_user(OFFICER)
        after = slips.queue_summary()
        self.assertEqual(after["usage"]["cho_tiep_nhan"], before["cho_tiep_nhan"] + 1)
        self.assertIn("cho_tiep_nhan", after["copy"])
        self.assertNotIn("dang_su_dung", after["copy"])  # a copy slip is never "in use"
        self.assertEqual(after["default_view"], "cho_tiep_nhan")
        frappe.set_user(LEADER)
        self.assertEqual(slips.queue_summary()["default_view"], "cho_lanh_dao")  # the leader opens on what waits for them
        frappe.set_user(ADMIN)
        self.assertEqual(slips.queue_summary()["default_view"], "cho_tiep_nhan")

    def test_search_and_paging(self):
        for _i in range(3):
            self._send()
        frappe.set_user(OFFICER)
        page = slips.list_slips("usage", "cho_tiep_nhan", search="SQ nghiên", page=1, page_size=2)
        self.assertEqual((len(page["rows"]), page["page_size"]), (2, 2))
        self.assertGreaterEqual(page["total"], 3)
        self.assertEqual(slips.list_slips("usage", "cho_tiep_nhan", search="SQ Người đọc", page_size=100)["rows"][0].reader_name, "SQ Người đọc")
        self.assertEqual(slips.list_slips("usage", "tat_ca", search="không-có-phiếu-nào-như-vậy")["total"], 0)
        row = page["rows"][0]
        self.assertEqual(row.item_count, 1)
        self.assertIn("due_date", row)  # usage rows carry the due date
        with self.assertRaises(frappe.ValidationError):
            slips.list_slips("copy", "qua_han")  # no such view for copy slips
        with self.assertRaises(frappe.PermissionError):
            slips.list_slips("bogus")

    def test_drafts_are_listed_apart(self):
        frappe.set_user(READER)
        draft = basket_api.add_to_basket("file", self.file_ok, "usage")["request"]
        sent = self._send()
        self.assertIn(draft, self._mine("usage", "nhap"))
        self.assertNotIn(draft, self._mine("usage", "cho_tiep_nhan"))
        self.assertNotIn(sent, self._mine("usage", "nhap"))

    # ---- one slip
    def test_the_slip_carries_what_the_screen_shows(self):
        with patch.object(frappe, "in_test", False):  # Frappe keeps no version history while tests run
            name = self._send(items=[{"archival_file": self.file_ok}, {"archive_document": self.doc_ok}])
            self._act(OFFICER, name, "Duyệt")
            self._act(OFFICER, name, "Giao tài liệu")
        frappe.set_user(OFFICER)
        slip = slips.get_slip("usage", name)
        self.assertEqual((slip["kind"], slip["state"], slip["docstatus"]), ("usage", "Đang sử dụng", 1))
        self.assertEqual((slip["reader"]["full_name"], slip["reader"]["email"]), ("SQ Người đọc", READER))
        self.assertEqual([i["kind"] for i in slip["items"]], ["Hồ sơ", "Văn bản"])
        file_item, doc_item = slip["items"]
        self.assertEqual(file_item["title"], "RW Test File 0")
        self.assertIn("Giá G5", file_item["location"])  # where the officer fetches it
        self.assertIn("Hộp H12", file_item["location"])
        self.assertEqual((doc_item["title"], doc_item["parent_title"]), ("RW Test Doc 0", "RW Test File 0"))
        self.assertEqual({i["item_status"] for i in slip["items"]}, {"Đã giao"})
        self.assertEqual(slip["actions"], ["Nhận trả"])
        self.assertEqual(slip["can"], {"edit_draft": False, "delete_draft": False, "decide_items": False, "receive_return": True, "renew": True})
        self.assertEqual((slip["renewal_count"], slip["max_renewals"]), (0, 2))
        self.assertFalse(slip["is_overdue"])
        texts = [t["text"] for t in slip["timeline"]]
        self.assertEqual(texts[-3:], ["Nháp → Chờ duyệt", "Chờ duyệt → Đã duyệt", "Đã duyệt → Đang sử dụng"])
        self.assertTrue(all(t["who"] for t in slip["timeline"]))

    def test_can_flags_follow_the_role_and_the_step(self):
        name = self._send()
        frappe.set_user(OFFICER)
        self.assertTrue(slips.get_slip("usage", name)["can"]["decide_items"])
        frappe.set_user(LEADER)
        self.assertFalse(slips.get_slip("usage", name)["can"]["decide_items"])  # not at the leader's step yet
        self.assertEqual(slips.get_slip("usage", name)["actions"], [])
        self._act(OFFICER, name, "Chuyển lãnh đạo")
        frappe.set_user(LEADER)
        slip = slips.get_slip("usage", name)
        self.assertTrue(slip["can"]["decide_items"])
        self.assertEqual(slip["actions"], ["Duyệt", "Trả lại phòng đọc", "Từ chối"])
        frappe.set_user(OFFICER)
        self.assertFalse(slips.get_slip("usage", name)["can"]["decide_items"])
        copy = self._send("Copy Request")
        slip = slips.get_slip("copy", copy)
        self.assertEqual(slip["kind"], "copy")
        self.assertNotIn("due_date", slip)
        self.assertFalse(slip["can"]["renew"])

    def test_overdue_shows_even_before_the_daily_job_ran(self):
        name = self._send()
        self._act(OFFICER, name, "Duyệt")
        self._act(OFFICER, name, "Giao tài liệu")
        frappe.db.set_value("Usage Request", name, "due_date", add_days(nowdate(), -1))
        frappe.set_user(OFFICER)
        self.assertEqual(slips.get_slip("usage", name)["is_overdue"], 1)

    def test_a_draft_can_be_deleted_by_the_reading_room_but_a_sent_slip_cannot(self):
        frappe.set_user(READER)
        draft = basket_api.add_to_basket("file", self.file_ok, "usage")["request"]
        sent = self._send()
        frappe.set_user(OFFICER)
        self.assertTrue(slips.get_slip("usage", draft)["can"]["delete_draft"])
        with self.assertRaises(frappe.ValidationError):
            slips.delete_draft("usage", sent)
        slips.delete_draft("usage", draft)
        self.assertFalse(frappe.db.exists("Usage Request", draft))
        frappe.set_user(LEADER)
        with self.assertRaises(frappe.PermissionError):
            slips.delete_draft("usage", draft)

    def test_a_readers_slips_for_the_reader_page(self):
        usage, copy = self._send(), self._send("Copy Request")
        frappe.set_user(OFFICER)
        summary = slips.reader_slips(self.profile)
        self.assertEqual({(r["kind"], r["name"]) for r in summary["slips"]} & {("usage", usage), ("copy", copy)}, {("usage", usage), ("copy", copy)})
        self.assertEqual((summary["open"], summary["overdue"]), (2, 0))
        self.assertIn("card", summary["print"])  # the reader card

    # ---- who may use it
    def test_the_queue_is_for_the_reading_room_leaders_and_admin(self):
        name = self._send()
        calls = [lambda: slips.queue_summary(), lambda: slips.list_slips("usage"), lambda: slips.get_slip("usage", name),
                 lambda: slips.decide_items("usage", name, "[]"), lambda: slips.renew(name), lambda: slips.receive_return(name),
                 lambda: slips.delete_draft("usage", name), lambda: slips.reader_slips(self.profile)]
        for user in (READER, PRESERVER, "Guest"):
            frappe.set_user(user)
            for call in calls:
                with self.assertRaises(frappe.PermissionError, msg=user):
                    call()
        for user in (OFFICER, LEADER, ADMIN):
            frappe.set_user(user)
            self.assertIn("usage", slips.queue_summary())
