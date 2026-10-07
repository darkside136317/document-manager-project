# -*- coding: utf-8 -*-
"""The one place that writes the Business Activity Log.

* `log_activity` is the explicit entry point (views, downloads, searches, admin actions).
* `audit_doc_event` is attached to the business DocTypes through `doc_events` (hooks.py) and records
  create / update / delete — for workflow DocTypes the state change too — without touching the
  feature code.
* `on_login` / `on_logout` record sessions.

Every writer honours `Document Manager Settings.enable_activity_log`, never raises into the
calling operation, and does not commit unless asked to (a GET request is rolled back otherwise).
Values are not copied into the log except for state-like fields (status, level): the log must not
become a second, unprotected copy of confidential data.
"""

import frappe

from document_manager.document_manager.services.errors import log_exception

LOG_DOCTYPE = "Business Activity Log"
SETTINGS = "Document Manager Settings"

AUDITED_DOCTYPES = (
    "Fonds", "Record Group", "Catalog", "Archival File", "Archive Document",
    "Archival Agency", "Document Group", "Document Type Category", "Classification Scheme",
    "Confidentiality Level", "Storage Warehouse", "Quick Entry Dictionary",
    "Reader", "Reader Group", "Usage Request", "Copy Request", "Reader Feedback",
    "Backup Batch", "Restore Batch", "Integrity Check",
    "Organization Info", "Reader Settings", "Document Manager Settings",
)

# Fields whose old → new value is worth keeping in the description.
STATE_FIELDS = ("status", "workflow_state", "confidentiality_level", "disposal_status", "is_active",
                "reader_group", "max_confidentiality_priority")
IGNORED_FIELDS = {"modified", "modified_by", "creation", "owner", "idx", "docstatus", "content_text",
                  "gridfs_file_id", "gridfs_preview_id", "search_index_status", "last_accessed",
                  "total_documents", "total_files"}

_EVENT_TYPES = {"after_insert": "Tạo mới", "on_update": "Cập nhật", "on_update_after_submit": "Cập nhật",
                "on_trash": "Xóa"}


def is_enabled() -> bool:
    value = frappe.db.get_single_value(SETTINGS, "enable_activity_log")
    return True if value is None else bool(frappe.utils.cint(value))


def log_activity(activity_type, reference_doctype="", reference_name="", description="",
                 data_json="", commit=False, user=None):
    """Write one Business Activity Log row. Returns its name, or None when disabled/failed."""
    try:
        if not is_enabled():
            return None
        log = frappe.get_doc({
            "doctype": LOG_DOCTYPE,
            "activity_type": activity_type,
            "reference_doctype": reference_doctype or "",
            "reference_name": reference_name or "",
            "user": user or frappe.session.user,
            "ip_address": getattr(frappe.local, "request_ip", None) or "",
            "description": (description or "")[:2000],
            "data_json": data_json or "",
        }).insert(ignore_permissions=True)
        if commit:
            frappe.db.commit()
        return log.name
    except Exception:
        log_exception("Activity Log Error", "Failed to write the activity log")
        return None


def _skip() -> bool:
    flags = frappe.flags
    return bool(flags.in_migrate or flags.in_install or flags.in_patch or flags.in_import
                or flags.in_test_audit_off)


def _describe_changes(doc) -> str:
    before = doc.get_doc_before_save()
    if not before:
        return ""
    names, states = [], []
    for df in doc.meta.fields:
        field = df.fieldname
        if not field or field in IGNORED_FIELDS or df.fieldtype in ("Section Break", "Column Break", "Tab Break",
                                                                  "Table", "Table MultiSelect", "Password"):
            continue
        old, new = before.get(field), doc.get(field)
        if (old or "") == (new or ""):
            continue
        names.append(df.label or field)
        if field in STATE_FIELDS:
            states.append(f"{df.label or field}: {old or '∅'} → {new or '∅'}")
    return "; ".join(states) if states else ("Đã sửa: " + ", ".join(names) if names else "")


def audit_doc_event(doc, method=None):
    """`doc_events` handler for the audited DocTypes."""
    try:
        if doc.doctype == LOG_DOCTYPE or _skip():
            return
        activity_type = _EVENT_TYPES.get(method)
        if not activity_type:
            return
        if method == "on_update" and doc.flags.in_insert:
            return  # `after_insert` already recorded the creation
        description = doc.get("title") or doc.get(doc.meta.title_field or "name") or doc.name
        if method in ("on_update", "on_update_after_submit"):
            changes = _describe_changes(doc)
            if not changes:
                return
            description = f"{description} — {changes}"
        log_activity(activity_type, doc.doctype, doc.name, str(description))
    except Exception:
        log_exception("Activity Log Error", f"Audit failed for {doc.doctype} {doc.name}")


def on_login(login_manager=None):
    user = getattr(login_manager, "user", None) or frappe.session.user
    if user and user != "Guest":
        log_activity("Đăng nhập", "User", user, "Đăng nhập hệ thống", user=user)


def on_logout(login_manager=None):
    user = getattr(login_manager, "user", None) or frappe.session.user
    if user and user != "Guest":
        log_activity("Đăng xuất", "User", user, "Đăng xuất", user=user)


def purge_logs(before, batch_size: int = 5000) -> int:
    """Delete log rows older than `before` in batches (one huge DELETE would lock the table).

    Records its own summary row so the clean-up itself stays auditable. Returns the number deleted.
    """
    deleted = 0
    while True:
        frappe.db.sql(
            f"delete from `tab{LOG_DOCTYPE}` where `timestamp` < %s limit {int(batch_size)}", (before,)
        )
        count = frappe.db.sql("select row_count()")[0][0] or 0
        deleted += count
        frappe.db.commit()
        if count < batch_size:
            break
    log_activity("Dọn dẹp nhật ký", LOG_DOCTYPE, "", f"Đã xóa {deleted} dòng nhật ký trước {before}", commit=True)
    return deleted
