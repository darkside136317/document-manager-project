# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

class ReaderFeedback(Document):
    """Góp ý của độc giả."""
    @frappe.whitelist()
    def respond(self, response_text):
        self.response = response_text
        self.responded_by = frappe.session.user
        self.responded_date = frappe.utils.now()
        self.status = "Đã phản hồi"
        self.save(ignore_permissions=True)
