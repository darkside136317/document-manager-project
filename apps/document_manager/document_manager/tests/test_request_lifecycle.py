# -*- coding: utf-8 -*-
"""Slip lifecycle (G6): leader approval, per-item decisions, issue / return / renewal, quotas and the daily
overdue job.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_request_lifecycle
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from document_manager.document_manager.api import requests as request_api
from document_manager.document_manager.api import slips
from document_manager.document_manager.policy import get_limits, is_staff
from document_manager.document_manager.services import lifecycle as lc
from document_manager.document_manager.services import notify, overdue
from document_manager.document_manager.setup import install
from document_manager.document_manager.setup_workflows import WORKFLOWS, setup_all
from document_manager.tests.test_request_workflow import _names, _reader, _seed_archive, _user

TAG = frappe.generate_hash(length=5).lower()
READER_A = f"rl.a.{TAG}@example.com"
READER_C = f"rl.c.{TAG}@example.com"
OFFICER = f"rl.officer.{TAG}@example.com"
LEADER = f"rl.leader.{TAG}@example.com"
ADMIN = f"rl.admin.{TAG}@example.com"
LEVEL = f"RL Mật {TAG}"


def _settings(**values):
    for field, value in values.items():
        frappe.db.set_single_value("Reader Settings", field, value)
    frappe.clear_document_cache("Reader Settings", "Reader Settings")


class TestRequestLifecycle(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        _user(READER_A, ["Reader"], "Website User")
        _user(READER_C, ["Reader"], "Website User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(LEADER, ["Archive Leader"], "System User")
        _user(ADMIN, ["Document Admin"], "System User")
        cls.profile_a = _reader(READER_A, "RL Reader A")
        cls.profile_c = _reader(READER_C, "RL Reader C")
        frappe.db.set_value("Reader", cls.profile_c, "max_confidentiality_priority", 2)  # may see the "Mật" level
        frappe.get_doc({"doctype": "Confidentiality Level", "level_name": LEVEL, "priority": 2,
                        "requires_leader_approval": 1}).insert(ignore_permissions=True)
        cls._seeded = _seed_archive()
        cls.file_ok, cls.file_two = _names(cls._seeded, "Archival File")
        base = frappe.get_doc("Archival File", cls.file_ok)
        cls.file_conf = frappe.get_doc({
            "doctype": "Archival File", "file_title": f"RL Mật file {TAG}", "fonds": base.fonds, "record_group": base.record_group,
            "catalog": base.catalog, "confidentiality_level": LEVEL, "status": "Đã hoàn thành"}).insert(ignore_permissions=True).name
        cls.doc_ok = frappe.get_all("Archive Document", filters={"archival_file": cls.file_ok}, pluck="name")[0]
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for dt in ("Usage Request", "Copy Request"):
            for name in frappe.get_all(dt, filters={"reader": ["in", [cls.profile_a, cls.profile_c]]}, pluck="name"):
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.flags.ignore_permissions = True
                    doc.cancel()
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        frappe.delete_doc("Archival File", cls.file_conf, force=True, ignore_permissions=True)
        for dt, name in cls._seeded:
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for profile in (cls.profile_a, cls.profile_c):
            frappe.delete_doc("Reader", profile, force=True, ignore_permissions=True)
        frappe.delete_doc("Confidentiality Level", LEVEL, force=True, ignore_permissions=True)
        for email in (READER_A, READER_C, OFFICER, LEADER, ADMIN):
            frappe.db.delete("Notification Log", {"for_user": email})
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user("Administrator")
        frappe.db.savepoint("rl_test")
        # generous limits: each test that is about a limit sets its own
        _settings(max_requests_per_day=0, max_copy_requests_per_day=0, max_items_per_request=0, max_open_requests=0,
                  max_renewals=2, renewal_days=7, document_hold_days=7, auto_return_overdue=1, reminder_days_before=1,
                  block_when_overdue=1)

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="rl_test")
        frappe.clear_document_cache("Reader Settings", "Reader Settings")

    # ---- helpers
    def _send(self, user=READER_A, items=None, doctype="Usage Request", purpose="Nghiên cứu"):
        frappe.set_user(user)
        items = items or [{"archival_file": self.file_ok}]
        name = request_api.save_request(doctype, json.dumps({"purpose": purpose, "items": items}), submit=1)["name"]
        frappe.set_user("Administrator")
        return name

    def _act(self, user, name, action, text=None, doctype="Usage Request"):
        frappe.set_user(user)
        return request_api.apply_action(doctype, name, action, text=text)

    def _doc(self, name, doctype="Usage Request"):
        return frappe.get_doc(doctype, name)

    def _actions(self, user, name, doctype="Usage Request"):
        frappe.set_user(user)
        return {a["action"] for a in request_api.get_actions(doctype, name)}

    def _approved_and_issued(self, user=READER_A, **kw):
        name = self._send(user, **kw)
        self._act(OFFICER, name, "Duyệt")
        self._act(OFFICER, name, "Giao tài liệu")
        return name

    def _group(self, **values):
        group = frappe.get_doc({"doctype": "Reader Group", "group_name": f"RL group {frappe.generate_hash(length=4)}", "is_active": 1,
                                "max_confidentiality_priority": 2, **values}).insert(ignore_permissions=True)
        return group.name

    def _notices(self, user):
        return frappe.get_all("Notification Log", filters={"for_user": user}, pluck="subject")

    # ---- the leader role
    def test_archive_leader_is_staff_who_reads_the_archive_but_does_not_edit_it(self):
        self.assertTrue(is_staff(LEADER))
        for doctype in ("Archival File", "Archive Document", "Fonds", "Reader", "Usage Request", "Copy Request"):
            self.assertTrue(frappe.has_permission(doctype, "read", user=LEADER), doctype)
        for doctype in ("Archival File", "Archive Document", "Fonds", "Reader"):
            self.assertFalse(frappe.has_permission(doctype, "write", user=LEADER), doctype)
        self.assertFalse(frappe.has_permission("Reader Registration", "read", user=LEADER))  # ID numbers: not their business

    def test_workflow_seed_is_complete_and_repeatable(self):
        setup_all()
        setup_all()
        for doctype, spec in WORKFLOWS.items():
            wf = frappe.get_doc("Workflow", f"{doctype} Workflow")
            expected = sum(len(t[3]) for t in spec["transitions"])
            self.assertEqual(len(wf.transitions), expected, doctype)  # running the seed twice adds nothing
        usage = frappe.get_doc("Workflow", "Usage Request Workflow")
        self.assertEqual({s.state for s in usage.states},
                         {"Nháp", "Chờ duyệt", "Chờ lãnh đạo duyệt", "Đã duyệt", "Từ chối", "Đang sử dụng", "Đã trả", "Đã hủy"})

    # ---- who approves
    def test_a_slip_without_confidential_items_is_approved_by_the_reading_room(self):
        name = self._send(items=[{"archival_file": self.file_ok}, {"archival_file": self.file_two}])
        doc = self._doc(name)
        self.assertEqual((doc.workflow_state, doc.requires_leader), ("Chờ duyệt", 0))
        self.assertTrue(doc.submitted_on)
        self.assertEqual({r.item_status for r in doc.items}, {"Chờ duyệt"})
        self.assertEqual(self._actions(OFFICER, name), {"Duyệt", "Từ chối", "Chuyển lãnh đạo"})
        self._act(OFFICER, name, "Duyệt")
        doc = self._doc(name)
        self.assertEqual((doc.workflow_state, doc.approved_by), ("Đã duyệt", OFFICER))
        self.assertEqual({r.item_status for r in doc.items}, {"Đã duyệt"})

    def test_confidential_items_need_a_leader(self):
        name = self._send(READER_C, items=[{"archival_file": self.file_conf}])
        self.assertEqual(self._doc(name).requires_leader, 1)
        self.assertNotIn("Duyệt", self._actions(OFFICER, name))  # the reading room cannot approve it alone
        with self.assertRaises(Exception):
            self._act(OFFICER, name, "Duyệt")
        self.assertIn("Duyệt", self._actions(ADMIN, name))  # Document Admin always can
        self._act(OFFICER, name, "Chuyển lãnh đạo")
        self.assertEqual(self._doc(name).workflow_state, "Chờ lãnh đạo duyệt")
        self.assertTrue(any("chờ lãnh đạo duyệt" in s for s in self._notices(LEADER)))
        self.assertTrue(any("đã chuyển lãnh đạo duyệt" in s for s in self._notices(READER_C)))
        self.assertEqual(self._actions(LEADER, name), {"Duyệt", "Từ chối", "Trả lại phòng đọc"})
        self.assertEqual(self._actions(OFFICER, name), set())  # while a leader decides, the reading room waits
        with self.assertRaises(Exception):
            self._act(READER_C, name, "Duyệt")
        self._act(LEADER, name, "Duyệt")
        doc = self._doc(name)
        self.assertEqual((doc.workflow_state, doc.leader, doc.approved_by), ("Đã duyệt", LEADER, LEADER))
        self.assertTrue(any("đã được duyệt" in s for s in self._notices(READER_C)))
        self.assertTrue(any("Lãnh đạo đã xử lý" in s for s in self._notices(OFFICER)))  # the officer knows to hand over

    def test_a_leader_can_return_a_slip_to_the_reading_room(self):
        name = self._send(READER_C, items=[{"archival_file": self.file_conf}])
        submitted = self._doc(name).submitted_on
        self._act(OFFICER, name, "Chuyển lãnh đạo")
        self._act(LEADER, name, "Trả lại phòng đọc")
        doc = self._doc(name)
        self.assertEqual((doc.workflow_state, doc.requires_leader, doc.submitted_on), ("Chờ duyệt", 1, submitted))
        self.assertEqual({r.item_status for r in doc.items}, {"Chờ duyệt"})

    def test_the_reader_group_decides_how_slips_are_approved(self):
        always = self._group(approval_mode="Luôn qua lãnh đạo")
        frappe.db.set_value("Reader", self.profile_a, "reader_group", always)
        self.assertEqual(self._doc(self._send()).requires_leader, 1)
        never = self._group(approval_mode="Chỉ phòng đọc duyệt")
        frappe.db.set_value("Reader", self.profile_c, "reader_group", never)
        self.assertEqual(self._doc(self._send(READER_C, items=[{"archival_file": self.file_conf}])).requires_leader, 0)

    def test_copy_slips_follow_the_same_approval_rules(self):
        name = self._send(READER_C, items=[{"archival_file": self.file_conf, "copy_count": 2}], doctype="Copy Request")
        self.assertEqual(self._doc(name, "Copy Request").requires_leader, 1)
        self._act(OFFICER, name, "Chuyển lãnh đạo", doctype="Copy Request")
        self._act(LEADER, name, "Duyệt", doctype="Copy Request")
        self._act(OFFICER, name, "Hoàn thành", doctype="Copy Request")
        doc = self._doc(name, "Copy Request")
        self.assertEqual((doc.workflow_state, doc.leader), ("Đã hoàn thành", LEADER))
        self.assertEqual({r.item_status for r in doc.items}, {"Đã hoàn thành"})

    # ---- item by item
    def test_the_officer_decides_item_by_item(self):
        name = self._send(items=[{"archival_file": self.file_ok}, {"archival_file": self.file_two}])
        rows = [r.name for r in self._doc(name).items]
        frappe.set_user(OFFICER)
        with self.assertRaises(frappe.ValidationError):  # turning an item down needs a reason
            slips.decide_items("usage", name, [{"row": rows[1], "status": "Từ chối"}])
        slip = slips.decide_items("usage", name, [{"row": rows[1], "status": "Từ chối", "note": "Đang tu bổ"}])
        self.assertEqual([i["item_status"] for i in slip["items"]], ["Chờ duyệt", "Từ chối"])
        self._act(OFFICER, name, "Duyệt")
        doc = self._doc(name)
        self.assertEqual([(r.item_status, r.decision_note) for r in doc.items], [("Đã duyệt", None), ("Từ chối", "Đang tu bổ")])

    def test_a_slip_cannot_be_approved_with_every_item_turned_down(self):
        name = self._send()
        row = self._doc(name).items[0].name
        frappe.set_user(OFFICER)
        slips.decide_items("usage", name, [{"row": row, "status": "Từ chối", "note": "Không có trong kho"}])
        with self.assertRaises(frappe.ValidationError):
            self._act(OFFICER, name, "Duyệt")
        self._act(OFFICER, name, "Từ chối", text="Không có tài liệu nào để phục vụ")
        self.assertEqual({r.item_status for r in self._doc(name).items}, {"Từ chối"})

    def test_rejecting_a_slip_rejects_all_its_items(self):
        name = self._send(items=[{"archival_file": self.file_ok}, {"archival_file": self.file_two}])
        self._act(OFFICER, name, "Từ chối", text="Không đủ điều kiện")
        self.assertEqual({r.item_status for r in self._doc(name).items}, {"Từ chối"})

    def test_only_the_right_staff_decide_items(self):
        name = self._send(READER_C, items=[{"archival_file": self.file_conf}])
        row = self._doc(name).items[0].name
        decision = [{"row": row, "status": "Đã duyệt"}]
        for user in (READER_C, LEADER):  # the leader decides only once the slip reaches them
            frappe.set_user(user)
            with self.assertRaises(frappe.PermissionError, msg=user):
                slips.decide_items("usage", name, decision)
        self._act(OFFICER, name, "Chuyển lãnh đạo")
        frappe.set_user(OFFICER)
        with self.assertRaises(frappe.PermissionError):
            slips.decide_items("usage", name, decision)
        frappe.set_user(LEADER)
        self.assertEqual(slips.decide_items("usage", name, decision)["items"][0]["item_status"], "Đã duyệt")
        frappe.set_user("Administrator")
        self._act(LEADER, name, "Duyệt")
        frappe.set_user(LEADER)
        with self.assertRaises(frappe.ValidationError):  # approved: no longer a review step
            slips.decide_items("usage", name, decision)

    # ---- issue, return, renew
    def test_handing_over_starts_the_clock(self):
        group = self._group(hold_days=3)
        frappe.db.set_value("Reader", self.profile_a, "reader_group", group)
        name = self._send(items=[{"archival_file": self.file_ok}, {"archival_file": self.file_two}])
        row = self._doc(name).items[1].name
        frappe.set_user(OFFICER)
        slips.decide_items("usage", name, [{"row": row, "status": "Từ chối", "note": "Mượn rồi"}])
        self._act(OFFICER, name, "Duyệt")
        self._act(OFFICER, name, "Giao tài liệu")
        doc = self._doc(name)
        self.assertEqual(doc.workflow_state, "Đang sử dụng")
        self.assertEqual((doc.issued_by, doc.renewal_count, doc.is_overdue), (OFFICER, 0, 0))
        self.assertEqual(getdate(doc.due_date), getdate(add_days(nowdate(), 3)))  # the group's own holding time
        self.assertEqual([r.item_status for r in doc.items], ["Đã giao", "Từ chối"])
        self.assertTrue(doc.items[0].issued_on)
        self.assertTrue(any("đã được giao" in s and "Hạn trả" in s for s in self._notices(READER_A)))

    def test_receiving_the_return_records_the_condition_of_each_item(self):
        name = self._approved_and_issued(items=[{"archival_file": self.file_ok}, {"archival_file": self.file_two}])
        rows = [r.name for r in self._doc(name).items]
        frappe.set_user(OFFICER)
        with self.assertRaises(frappe.ValidationError):
            slips.receive_return(name, {rows[0]: "Rách nát"})
        slip = slips.receive_return(name, {rows[0]: "Thiếu trang"})
        doc = self._doc(name)
        self.assertEqual((doc.workflow_state, doc.received_by), ("Đã trả", OFFICER))
        self.assertTrue(doc.returned_date)
        self.assertEqual([(r.item_status, r.return_condition) for r in doc.items], [("Đã trả", "Thiếu trang"), ("Đã trả", "Tốt")])
        self.assertEqual(slip["state"], "Đã trả")
        with self.assertRaises(frappe.ValidationError):
            slips.receive_return(name)  # already back

    def test_renewal_extends_within_the_limit(self):
        _settings(max_renewals=2, renewal_days=5)
        name = self._approved_and_issued()
        due = getdate(self._doc(name).due_date)
        frappe.set_user(OFFICER)
        slip = slips.renew(name)
        self.assertEqual((getdate(slip["due_date"]), slip["renewal_count"]), (add_days(due, 5), 1))
        slips.renew(name)
        with self.assertRaises(frappe.ValidationError):
            slips.renew(name)  # the limit is reached
        self.assertEqual(self._doc(name).renewal_count, 2)
        self.assertTrue(any("gia hạn đến" in s for s in self._notices(READER_A)))

    def test_an_overdue_slip_is_extended_from_today_and_loses_its_flag(self):
        name = self._approved_and_issued()
        frappe.db.set_value("Usage Request", name, {"due_date": add_days(nowdate(), -10), "is_overdue": 1})
        frappe.set_user(OFFICER)
        slip = slips.renew(name)
        self.assertEqual(getdate(slip["due_date"]), getdate(add_days(nowdate(), 7)))  # never into the past
        self.assertEqual(self._doc(name).is_overdue, 0)

    def test_only_the_reading_room_renews_and_only_slips_in_use(self):
        name = self._approved_and_issued()
        for user in (READER_A, LEADER):
            frappe.set_user(user)
            with self.assertRaises(frappe.PermissionError, msg=user):
                slips.renew(name)
        waiting = self._send()
        frappe.set_user(OFFICER)
        with self.assertRaises(frappe.ValidationError):
            slips.renew(waiting)

    # ---- limits
    def test_items_per_slip_are_limited(self):
        _settings(max_items_per_request=1)
        frappe.set_user(READER_A)
        with self.assertRaises(frappe.ValidationError):
            request_api.save_request("Usage Request", json.dumps({"purpose": "x", "items": [{"archival_file": self.file_ok}, {"archival_file": self.file_two}]}), submit=1)
        self._send()  # one item is fine
        group = self._group(max_items_per_request=3)  # the group's own value wins over the site's
        frappe.db.set_value("Reader", self.profile_a, "reader_group", group)
        self._send(items=[{"archival_file": self.file_ok}, {"archival_file": self.file_two}])
        self.assertEqual(get_limits(self.profile_a).max_items_per_request, 3)

    def test_slips_per_day_are_limited_per_kind_and_cancelling_frees_one(self):
        _settings(max_requests_per_day=2, max_copy_requests_per_day=1)
        first, second = self._send(), self._send()
        with self.assertRaises(frappe.ValidationError):
            self._send()
        self._send(doctype="Copy Request")  # the copy limit is its own
        with self.assertRaises(frappe.ValidationError):
            self._send(doctype="Copy Request")
        self._act(READER_A, first, "Hủy phiếu")
        self._send()  # one of the two usage slips was withdrawn
        self.assertEqual(self._doc(second).workflow_state, "Chờ duyệt")

    def test_open_slips_are_limited(self):
        _settings(max_open_requests=2)
        self._send()
        done = self._send(doctype="Copy Request")
        with self.assertRaises(frappe.ValidationError):
            self._send()
        self._act(OFFICER, done, "Từ chối", text="x", doctype="Copy Request")  # a decided slip is no longer open
        self._send()

    def test_overdue_documents_block_new_usage_slips_but_not_copies(self):
        name = self._approved_and_issued()
        frappe.db.set_value("Usage Request", name, "due_date", add_days(nowdate(), -1))
        with self.assertRaises(frappe.ValidationError):
            self._send()
        self._send(doctype="Copy Request")
        _settings(block_when_overdue=0)
        self._send()

    def test_staff_filing_for_a_reader_are_not_held_to_the_readers_limits(self):
        _settings(max_items_per_request=1, max_requests_per_day=1)
        frappe.set_user(OFFICER)
        payload = {"reader": self.profile_a, "purpose": "Tại quầy", "items": [{"archival_file": self.file_ok}, {"archival_file": self.file_two}]}
        for _i in range(2):
            self.assertEqual(request_api.save_request("Usage Request", json.dumps(payload), submit=1)["state"], "Chờ duyệt")

    # ---- a sent slip belongs to the reading room
    def test_the_reader_cannot_change_a_sent_slip(self):
        name = self._send()
        frappe.set_user(READER_A)
        doc = self._doc(name)
        doc.purpose = "Đổi mục đích"
        with self.assertRaises(frappe.PermissionError):
            doc.save()
        doc = self._doc(name)
        doc.append("items", {"archival_file": self.file_two})
        with self.assertRaises(frappe.PermissionError):
            doc.save()
        doc = self._doc(name)
        doc.items[0].item_status = "Đã duyệt"
        with self.assertRaises(frappe.PermissionError):
            doc.save()
        doc = self._doc(name)
        doc.notes = "Cần gấp"
        doc.save()  # a note is allowed
        self.assertEqual(self._doc(name).notes, "Cần gấp")
        for field in ("due_date", "is_overdue", "leader", "requires_leader", "issued_on"):
            doc = self._doc(name)
            doc.set(field, 1 if field in ("is_overdue", "requires_leader") else "2030-01-01" if field == "due_date" else LEADER)
            with self.assertRaises(frappe.PermissionError, msg=field):
                doc.save()

    # ---- the daily job
    def test_daily_job_flags_overdue_slips_and_tells_the_reader_once(self):
        name = self._approved_and_issued()
        frappe.db.set_value("Usage Request", name, "due_date", add_days(nowdate(), -3))
        first = overdue.mark_overdue_and_remind()
        self.assertEqual((first["flagged"], first["overdue_notices"]), (1, 1))
        self.assertEqual(self._doc(name).is_overdue, 1)
        self.assertTrue(any("quá hạn trả 3 ngày" in s for s in self._notices(READER_A)))
        again = overdue.mark_overdue_and_remind()
        self.assertEqual((again["flagged"], again["overdue_notices"]), (0, 0))  # nothing twice
        self.assertEqual(len([s for s in self._notices(READER_A) if "quá hạn" in s]), 1)

    def test_daily_job_reminds_before_the_due_date_and_clears_stale_flags(self):
        name = self._approved_and_issued()
        frappe.db.set_value("Usage Request", name, "due_date", add_days(nowdate(), 1))
        result = overdue.mark_overdue_and_remind()
        self.assertEqual(result["due_soon_notices"], 1)
        self.assertTrue(any("đến hạn trả" in s for s in self._notices(READER_A)))
        frappe.db.set_value("Usage Request", name, "is_overdue", 1)  # a flag a renewal should have cleared
        self.assertEqual(overdue.mark_overdue_and_remind()["cleared"], 1)
        self.assertEqual(self._doc(name).is_overdue, 0)
        returned = self._approved_and_issued()
        self._act(OFFICER, returned, "Nhận trả")
        frappe.db.set_value("Usage Request", returned, "is_overdue", 1)
        overdue.mark_overdue_and_remind()
        self.assertEqual(self._doc(returned).is_overdue, 0)  # a returned slip is never overdue

    def test_reminders_can_be_switched_off_but_the_flag_stays(self):
        _settings(auto_return_overdue=0)
        name = self._approved_and_issued()
        frappe.db.set_value("Usage Request", name, "due_date", add_days(nowdate(), -2))
        result = overdue.mark_overdue_and_remind()
        self.assertEqual((result["flagged"], result["overdue_notices"], result["due_soon_notices"]), (1, 0, 0))
        self.assertFalse([s for s in self._notices(READER_A) if "quá hạn" in s])

    def test_daily_job_is_registered(self):
        self.assertIn("document_manager.document_manager.services.overdue.mark_overdue_and_remind",
                      frappe.get_hooks("scheduler_events")["daily"])

    # ---- seed
    def test_defaults_are_stored_once_and_never_override_a_choice(self):
        frappe.db.sql("delete from tabSingles where doctype = 'Reader Settings' and field = 'max_renewals'")
        frappe.clear_document_cache("Reader Settings", "Reader Settings")
        self.assertEqual(install.ensure_reader_settings_defaults(), 1)
        self.assertEqual(frappe.db.get_single_value("Reader Settings", "max_renewals"), 2)
        _settings(max_renewals=0)  # "no limit" is a choice too
        self.assertEqual(install.ensure_reader_settings_defaults(), 0)
        self.assertEqual(frappe.db.get_single_value("Reader Settings", "max_renewals"), 0)

    def test_levels_above_the_public_one_ask_for_a_leader(self):
        frappe.db.set_value("Confidentiality Level", LEVEL, "requires_leader_approval", 0)
        self.assertGreaterEqual(install.flag_levels_needing_leader(), 1)
        self.assertEqual(frappe.db.get_value("Confidentiality Level", LEVEL, "requires_leader_approval"), 1)
        self.assertEqual(frappe.db.get_value("Confidentiality Level", "Thường", "requires_leader_approval"), 0)
