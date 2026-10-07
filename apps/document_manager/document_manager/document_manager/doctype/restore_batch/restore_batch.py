# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document


class RestoreBatch(Document):
    @frappe.whitelist()
    def run_restore(self):
        self.check_permission("write")
        self.db_set("status", "Đang chạy")
        self.db_set("started_at", frappe.utils.now())
        frappe.enqueue(
            "document_manager.document_manager.services.backup_service.run_restore",
            restore_name=self.name,
            queue="long",
            timeout=3600,
            enqueue_after_commit=True,
        )


@frappe.whitelist(methods=["POST"])
def trigger_restore(docname):
    if not frappe.has_permission("Restore Batch", "write", doc=docname):
        frappe.throw("Không có quyền chạy phục hồi", frappe.PermissionError)

    doc = frappe.get_doc("Restore Batch", docname)
    doc.run_restore()
    return True
