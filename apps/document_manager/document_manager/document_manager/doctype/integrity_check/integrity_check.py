# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

class IntegrityCheck(Document):
    @frappe.whitelist()
    def run_check(self):
        frappe.enqueue(
            "document_manager.document_manager.services.backup_service.run_integrity_check",
            check_name=self.name,
            check_type=self.check_type,
            queue="long",
            timeout=3600,
        )
        self.db_set("status", "Đang chạy")
        self.db_set("started_at", frappe.utils.now())
