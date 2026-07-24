# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

class BusinessActivityLog(Document):
    """Log nghiệp vụ — ghi lại mọi thao tác quan trọng."""
    pass


def log_activity(activity_type, reference_doctype="", reference_name="", description="", data_json=""):
    """Helper function to create a Business Activity Log entry.

    Args:
        activity_type: Loại hoạt động
        reference_doctype: Doctype liên quan
        reference_name: Tên bản ghi liên quan
        description: Mô tả ngắn
        data_json: Dữ liệu bổ sung dạng JSON
    """
    settings = frappe.get_single("Document Manager Settings")
    if not settings.enable_activity_log:
        return

    try:
        log = frappe.new_doc("Business Activity Log")
        log.activity_type = activity_type
        log.reference_doctype = reference_doctype
        log.reference_name = reference_name
        log.user = frappe.session.user
        log.ip_address = frappe.local.request_ip if hasattr(frappe.local, "request_ip") else ""
        log.description = description
        log.data_json = data_json
        log.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        pass  # Don't crash the main operation if logging fails


def cleanup_old_logs():
    """Scheduled job — delete logs older than retention period."""
    settings = frappe.get_single("Document Manager Settings")
    days = settings.log_retention_days or 90
    cutoff = frappe.utils.add_days(frappe.utils.now(), -days)
    frappe.db.delete("Business Activity Log", {"timestamp": ["<", cutoff]})
    frappe.db.commit()
    frappe.logger().info(f"Cleaned up Business Activity Logs older than {days} days")
