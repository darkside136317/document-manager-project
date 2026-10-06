# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

class BackupBatch(Document):
    """Đợt sao lưu — quản lý backup DB và file."""

    @frappe.whitelist()
    def run_backup(self):
        """Enqueue backup job."""
        frappe.enqueue(
            "document_manager.document_manager.services.backup_service.run_backup",
            batch_name=self.name,
            backup_type=self.backup_type,
            queue="long",
            timeout=1800,
        )
        self.db_set("status", "Đang chạy")
        self.db_set("started_at", frappe.utils.now())

@frappe.whitelist()
def trigger_backup(docname):
    if not frappe.has_permission("Backup Batch", "write", doc=docname):
        frappe.throw("Không có quyền chạy sao lưu", frappe.PermissionError)
        
    doc = frappe.get_doc("Backup Batch", docname)
    doc.run_backup()
    return True
