# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

from document_manager.document_manager.services import audit


class BusinessActivityLog(Document):
    """Log nghiệp vụ — ghi lại mọi thao tác quan trọng (xem `services/audit.py`)."""


def log_activity(activity_type, reference_doctype="", reference_name="", description="", data_json=""):
    """Kept for existing callers; new code uses `services.audit.log_activity`."""
    return audit.log_activity(activity_type, reference_doctype, reference_name, description, data_json,
                              commit=True)


def cleanup_old_logs():
    """Scheduled job — delete logs older than the retention period (batched)."""
    days = frappe.utils.cint(frappe.db.get_single_value("Document Manager Settings", "log_retention_days")) or 90
    cutoff = frappe.utils.add_days(frappe.utils.now(), -days)
    deleted = audit.purge_logs(cutoff)
    frappe.logger().info(f"Cleaned up {deleted} Business Activity Log rows older than {days} days")
