# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

class CopyRequest(Document):
    """Phiếu đăng ký sao chụp tài liệu."""
    def validate(self):
        if not self.items:
            frappe.throw("Phải có ít nhất một tài liệu trong phiếu sao chụp")

    def on_submit(self):
        self.db_set("workflow_state", "Chờ duyệt")

    def on_cancel(self):
        self.db_set("workflow_state", "Từ chối")

    @frappe.whitelist()
    def approve(self):
        self.db_set("workflow_state", "Đã duyệt")
        self.db_set("approved_by", frappe.session.user)
        self.db_set("approved_date", frappe.utils.now())

    @frappe.whitelist()
    def reject(self, reason=""):
        self.db_set("workflow_state", "Từ chối")
        self.db_set("rejection_reason", reason)
        self.db_set("approved_by", frappe.session.user)
        self.db_set("approved_date", frappe.utils.now())

    @frappe.whitelist()
    def mark_completed(self):
        self.db_set("workflow_state", "Đã hoàn thành")
        self.db_set("completed_date", frappe.utils.now())
