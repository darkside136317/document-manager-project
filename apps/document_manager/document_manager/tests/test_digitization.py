# -*- coding: utf-8 -*-
"""Digitization mode: who may send record groups to the AI engine, read and review its jobs, the engine's callback key,
and the administrators' configuration of the fields shown in each mode. Nothing here reaches a real engine.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_digitization
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager import policy
from document_manager.document_manager.api import ai_integration as ai_api, digitization, meta
from document_manager.document_manager.services import ai_integration, digitization_fields
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _seed_archive, _user

TAG = frappe.generate_hash(length=5).lower()
ADMIN = f"dg.admin.{TAG}@example.com"
EDITOR = f"dg.editor.{TAG}@example.com"
REVIEWER = f"dg.reviewer.{TAG}@example.com"
CATALOGER = f"dg.cataloger.{TAG}@example.com"
READER = f"dg.reader.{TAG}@example.com"
USERS = (ADMIN, EDITOR, REVIEWER, CATALOGER, READER)
SETTINGS = "Document Manager Settings"
NO_JOB = "AIJ-khong-co"


class TestDigitization(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        _user(ADMIN, ["Document Admin"], "System User")
        _user(EDITOR, ["Digitization Editor"], "System User")
        _user(REVIEWER, ["Digitization Reviewer"], "System User")
        _user(CATALOGER, ["Cataloger"], "System User")
        _user(READER, ["Reader"], "Website User")
        cls.seeded = _seed_archive(1)
        cls.group = _names(cls.seeded, "Record Group")[0]
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
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
        frappe.db.savepoint("dg_test")
        self._switch(1)  # the settings changed by a test are rolled back with it

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="dg_test")
        policy.clear_cache()

    def _switch(self, enabled):
        frappe.db.set_single_value(SETTINGS, "digitization_enabled", enabled)

    def _as(self, user):
        frappe.set_user(user)
        policy.clear_cache()

    # ---- AI extraction jobs
    def test_everything_is_refused_while_digitization_is_off(self):
        self._switch(0)
        self._as(ADMIN)
        for call in (lambda: ai_api.start(self.group), lambda: ai_api.status(NO_JOB),
                     lambda: ai_api.review(NO_JOB, "DOC-x", "[]")):
            with self.assertRaisesRegex(frappe.PermissionError, "Chế độ số hóa đang tắt"):
                call()
        self._as(CATALOGER)
        with self.assertRaisesRegex(frappe.PermissionError, "chế độ số hóa"):
            meta.get_doctype_ui("Archival File", "digitization")

    def test_only_administrators_send_a_job(self):
        for user in (EDITOR, REVIEWER):
            self._as(user)
            with self.assertRaisesRegex(frappe.PermissionError, "Chỉ quản trị viên được gửi job AI", msg=user):
                ai_api.start(self.group)

    def test_a_job_needs_a_known_selection_and_record_group(self):
        self._as(ADMIN)
        with self.assertRaisesRegex(frappe.ValidationError, "Phạm vi bóc tách không hợp lệ"):
            ai_api.start(self.group, "bogus")
        with self.assertRaises(frappe.DoesNotExistError):
            ai_api.start("RG-khong-co")

    def test_reading_a_job_needs_a_digitization_right(self):
        self._as(ADMIN)
        with self.assertRaisesRegex(frappe.DoesNotExistError, "Không tìm thấy job AI"):
            ai_api.status(NO_JOB)
        self._as(CATALOGER)
        with self.assertRaisesRegex(frappe.PermissionError, "không có quyền xem job số hóa"):
            ai_api.status(NO_JOB)
        self._as(READER)
        with self.assertRaises(frappe.PermissionError):
            ai_api.latest(self.group)
        self._as(EDITOR)
        self.assertEqual(ai_api.latest(self.group), {})  # no job sent for this record group yet

    def test_only_reviewers_approve_results(self):
        self._as(EDITOR)
        with self.assertRaisesRegex(frappe.PermissionError, "không có quyền duyệt"):
            ai_api.review(NO_JOB, "DOC-x", "[]")
        self._as(REVIEWER)
        with self.assertRaisesRegex(frappe.DoesNotExistError, "Không tìm thấy job AI"):
            ai_api.review(NO_JOB, "DOC-x", "[]")

    def test_the_engine_callback_needs_the_shared_key(self):
        event = {"job_id": NO_JOB, "status": "done", "event_seq": 1}
        self._as("Guest")
        with patch.dict(frappe.conf, {"ai_callback_api_key": "khoa-dung"}):
            for key in ("khoa-sai", ""):
                with self.assertRaisesRegex(frappe.AuthenticationError, "API key callback", msg=key or "no key"):
                    ai_integration.receive_callback(dict(event), key)
            with self.assertRaisesRegex(frappe.DoesNotExistError, "Không tìm thấy job AI"):
                ai_integration.receive_callback(dict(event), "khoa-dung")  # the key passes; the job is checked next
        with patch.dict(frappe.conf, {"ai_callback_api_key": ""}):
            with self.assertRaises(frappe.AuthenticationError):  # a site without a key accepts no callback at all
                ai_integration.receive_callback(dict(event), "")

    def test_the_digitization_mode_shows_the_form_to_digitization_staff(self):
        self._as(EDITOR)
        self.assertTrue(meta.get_doctype_ui("Archival File", "digitization")["fields"])

    # ---- the field configuration
    def test_only_administrators_read_and_change_the_field_configuration(self):
        self._as(ADMIN)
        config = digitization.configuration()
        self.assertIs(config["enabled"], True)
        self.assertIn("Archival File", config["fields"])
        self._as(CATALOGER)
        with self.assertRaisesRegex(frappe.PermissionError, "Chỉ quản trị viên"):
            digitization.configuration()
        with self.assertRaisesRegex(frappe.PermissionError, "Chỉ quản trị viên"):
            digitization.add_field("Archival File", f"custom_ghi_chu_{TAG}", "Ghi chú")
        self._as(EDITOR)
        with self.assertRaisesRegex(frappe.PermissionError, "Chỉ quản trị viên"):
            digitization.save_field("Archival File", "file_title", json.dumps({"visibility": "both"}))

    def test_a_field_configuration_is_checked_before_it_is_saved(self):
        self._as(ADMIN)
        for doctype, fieldname, values, message in (
            ("User", "first_name", {"visibility": "both"}, "Loại dữ liệu không hợp lệ"),
            ("Archival File", "fonds", {"visibility": "both"}, "không thể cấu hình"),  # a protected link of the tree
            ("Archival File", "file_title", {"visibility": "bogus"}, "Chế độ hiển thị không hợp lệ"),
            ("Archival File", "file_title", {"visibility": "digitization"}, "Trường bắt buộc"),  # required: both modes
            ("Archival File", "file_title", {"visibility": "both", "position": -1}, "Thứ tự trường"),
        ):
            with self.assertRaisesRegex(frappe.ValidationError, message, msg=f"{fieldname} {values}"):
                digitization.save_field(doctype, fieldname, json.dumps(values))

    def test_a_valid_field_configuration_is_saved(self):
        self._as(ADMIN)
        saved = digitization.save_field("Archival File", "file_title", json.dumps({"visibility": "both", "label": "Tiêu đề hồ sơ"}))
        self.assertEqual((saved["field_id"], saved["visibility"], saved["label"]), ("Archival File.file_title", "both", "Tiêu đề hồ sơ"))
        self.assertEqual(digitization_fields.load_config()["Archival File.file_title"]["visibility"], "both")

    def test_a_new_field_is_checked_before_any_column_is_made(self):
        self._as(ADMIN)
        for fieldname, label, fieldtype, message in (
            ("ghi_chu_moi", "Ghi chú mới", "Data", "custom_"),
            (f"custom_tep_{TAG}", "Tệp", "Attach", "kiểu trường không hợp lệ"),
            (f"custom_ghi_chu_{TAG}", "   ", "Data", "Tên trường không hợp lệ"),
        ):
            with self.assertRaisesRegex(frappe.ValidationError, message, msg=fieldname):
                digitization.add_field("Archival File", fieldname, label, fieldtype)
        self.assertFalse(frappe.get_meta("Archival File").has_field(f"custom_ghi_chu_{TAG}"))

    def test_only_existing_custom_fields_are_removed(self):
        self._as(ADMIN)
        with self.assertRaisesRegex(frappe.ValidationError, "Chỉ xóa được trường tùy chỉnh"):
            digitization.remove_field("Archival File", "file_title")
        with self.assertRaisesRegex(frappe.ValidationError, "Không tìm thấy trường tùy chỉnh"):
            digitization.remove_field("Archival File", f"custom_khong_co_{TAG}")
