# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
class RestoreBatch(Document):
    @frappe.whitelist()
    def run_restore(self):
        frappe.enqueue(
            "document_manager.document_manager.services.backup_service.run_restore",
            restore_name=self.name,
            queue="long",
            timeout=3600,
        )
        self.db_set("status", "Đang chạy")
        self.db_set("started_at", frappe.utils.now())
