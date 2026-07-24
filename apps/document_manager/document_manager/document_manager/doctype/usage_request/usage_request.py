# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

class UsageRequest(Document):
    """Phiếu yêu cầu sử dụng tài liệu."""

    def validate(self):
        if not self.items:
            frappe.throw("Phải có ít nhất một hồ sơ/văn bản trong phiếu yêu cầu")

    def on_submit(self):
        self.db_set("workflow_state", "Chờ duyệt")

    def on_cancel(self):
        self.db_set("workflow_state", "Từ chối")

    @frappe.whitelist()
    def approve(self):
        """Duyệt phiếu yêu cầu — chỉ Reading Room Officer / Document Admin."""
        self.db_set("workflow_state", "Đã duyệt")
        self.db_set("approved_by", frappe.session.user)
        self.db_set("approved_date", frappe.utils.now())

    @frappe.whitelist()
    def reject(self, reason=""):
        """Từ chối phiếu yêu cầu."""
        self.db_set("workflow_state", "Từ chối")
        self.db_set("rejection_reason", reason)
        self.db_set("approved_by", frappe.session.user)
        self.db_set("approved_date", frappe.utils.now())

    @frappe.whitelist()
    def mark_returned(self):
        """Đánh dấu đã trả tài liệu."""
        self.db_set("workflow_state", "Đã trả")
        self.db_set("returned_date", frappe.utils.now())
