# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

class Reader(Document):
    """Độc giả — người dùng bên ngoài khai thác tài liệu."""

    def validate(self):
        self.max_confidentiality_priority = max(1, int(self.max_confidentiality_priority or 1))
        if self.user and not self.email:
            self.email = frappe.db.get_value("User", self.user, "email")

    def after_insert(self):
        if self.user:
            user_doc = frappe.get_doc("User", self.user)
            if "Reader" not in [r.role for r in user_doc.roles]:
                user_doc.append("roles", {"role": "Reader"})
                user_doc.save(ignore_permissions=True)
