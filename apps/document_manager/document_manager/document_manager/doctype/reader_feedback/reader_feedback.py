# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from frappe.utils.html_utils import clean_html

from document_manager.document_manager.permissions import assert_feature, get_reader_profile, is_staff

STAFF_ONLY_FIELDS = ("status", "response", "responded_by", "responded_date")


class ReaderFeedback(Document):
    """Góp ý của độc giả. Chuyển trạng thái qua Workflow "Reader Feedback"."""

    def before_validate(self):
        if self.is_new():
            # Feedback is always filed as the sender's own reader profile (staff included).
            profile = get_reader_profile()
            if not profile:
                frappe.throw(_("Tài khoản chưa có hồ sơ độc giả nên chưa thể gửi góp ý"), frappe.PermissionError)
            if not is_staff():
                assert_feature("can_feedback")
            self.reader = profile

    def validate(self):
        if self.reader and not self.reader_name:
            self.reader_name = frappe.db.get_value("Reader", self.reader, "full_name")
        if not self.is_new() and not is_staff():
            for fieldname in ("reader", "subject", "content", *STAFF_ONLY_FIELDS):
                if self.has_value_changed(fieldname):
                    frappe.throw(_("Bạn không được sửa góp ý đã gửi"), frappe.PermissionError)
        self.content = clean_html(self.content or "")
        self.response = clean_html(self.response or "")
        if not self.is_new() and self.has_value_changed("status") and self.status == "Đã phản hồi":
            if not (self.response or "").strip():
                frappe.throw(_("Phải nhập nội dung phản hồi"))
            self.responded_by = frappe.session.user
            self.responded_date = now_datetime()
