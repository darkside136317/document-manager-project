# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document


class IntegrityCheck(Document):
    @frappe.whitelist()
    def run_check(self):
        self.check_permission("write")
        self.db_set("status", "Đang chạy")
        self.db_set("started_at", frappe.utils.now())
        frappe.enqueue(
            "document_manager.document_manager.services.backup_service.run_integrity_check",
            check_name=self.name,
            check_type=self.check_type,
            queue="long",
            timeout=3600,
            enqueue_after_commit=True,
        )


@frappe.whitelist()
def trigger_integrity_check(docname):
    if not frappe.has_permission("Integrity Check", "write", doc=docname):
        frappe.throw("Không có quyền chạy kiểm tra toàn vẹn", frappe.PermissionError)

    doc = frappe.get_doc("Integrity Check", docname)
    doc.run_check()
    return True
