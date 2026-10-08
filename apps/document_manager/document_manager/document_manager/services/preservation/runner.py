# -*- coding: utf-8 -*-
"""What the Backup Batch, Integrity Check and Restore Batch jobs have in common: queueing, cancelling, findings, ending."""

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, now_datetime

from document_manager.document_manager.services.audit import log_activity
from document_manager.document_manager.services.errors import log_exception

PAGE = 200
MAX_ITEMS = 5000  # findings kept per run; the counters keep counting
CANCEL_TTL = 6 * 3600
BUSY = ("Đang chờ", "Đang chạy")
STALE_HOURS = 6  # a job cannot legitimately wait or run longer (the queue timeout is 4 hours): it is dead


class Cancelled(Exception):
    """Raised inside a run when the user asked to stop it."""


def settings() -> frappe._dict:
    """Document Manager Settings with defaults for whatever a site has not set yet."""
    row = frappe.get_cached_doc("Document Manager Settings")
    return frappe._dict(
        auto_backup_enabled=cint(row.auto_backup_enabled),
        backup_frequency=row.backup_frequency or "Hàng tuần",
        backup_retention_days=cint(row.backup_retention_days) or 30,
        backup_keep_min=cint(row.get("backup_keep_min")) or 3,
        backup_include_files=0 if row.get("backup_include_files") == 0 else 1,
        auto_integrity_check=cint(row.auto_integrity_check),
        log_retention_days=cint(row.log_retention_days) or 90,
    )


# --- is a job really running? ----------------------------------------------------------------------------------------

def is_stale(status: str, creation, started_at=None) -> bool:
    """A record that says it waits or runs, but has done so for more than STALE_HOURS: its worker is gone."""
    if status not in BUSY:
        return False
    since = started_at if status == "Đang chạy" and started_at else creation
    return bool(since) and frappe.utils.get_datetime(since) < add_to_date(now_datetime(), hours=-STALE_HOURS)


def is_active(doctype: str) -> bool:
    """Is a job of this kind waiting or running right now (dead records left behind do not count)?"""
    cutoff = add_to_date(now_datetime(), hours=-STALE_HOURS)
    return bool(frappe.db.exists(doctype, {"status": "Đang chờ", "creation": [">", cutoff]})
                or frappe.db.exists(doctype, {"status": "Đang chạy", "started_at": [">", cutoff]}))


# --- cancel -----------------------------------------------------------------------------------------------------------

def _cancel_key(doctype: str, name: str) -> str:
    return f"dm_preserve:{doctype}:{name}:cancel"


def request_cancel(doctype: str, name: str) -> None:
    frappe.cache.set_value(_cancel_key(doctype, name), 1, expires_in_sec=CANCEL_TTL)


def check_cancel(doctype: str, name: str) -> None:
    if frappe.cache.get_value(_cancel_key(doctype, name)):
        raise Cancelled()


def clear_cancel(doctype: str, name: str) -> None:
    frappe.cache.delete_value(_cancel_key(doctype, name))


# --- queue ------------------------------------------------------------------------------------------------------------

def enqueue(job_path: str, name: str, timeout: int = 7200) -> None:
    """Queue `job_path(name)` on the long queue once the current transaction is committed."""
    frappe.enqueue(job_path, name=name, queue="long", timeout=timeout, enqueue_after_commit=True)


def mark_running(doc, **extra) -> None:
    doc.db_set({"status": "Đang chạy", "started_at": doc.started_at or now_datetime(), "completed_at": None, **extra},
               update_modified=False)


def finish(doc, status: str, **values) -> None:
    clear_cancel(doc.doctype, doc.name)
    doc.db_set({"status": status, "completed_at": now_datetime(), **values}, update_modified=False)


def notify(doc, subject: str) -> None:
    """Tell whoever started a job (a scheduled job: the administrators) how it ended; also write the activity log."""
    users = [doc.initiated_by] if doc.get("initiated_by") else frappe.get_all(
        "Has Role", filters={"role": "Document Admin", "parenttype": "User"}, pluck="parent")
    for user in dict.fromkeys(u for u in users if u and u != "Administrator"):
        try:
            frappe.get_doc({"doctype": "Notification Log", "type": "Alert", "for_user": user, "subject": subject[:140],
                            "document_type": doc.doctype, "document_name": doc.name}).insert(ignore_permissions=True)
        except Exception:
            log_exception("Preservation", f"Could not notify {user} about {doc.name}")
    kind = {"Backup Batch": "Sao lưu", "Restore Batch": "Phục hồi"}.get(doc.doctype, "Kiểm tra")
    log_activity(kind, doc.doctype, doc.name, subject[:500])


class Findings:
    """Collects the items (errors, warnings) of a run, keeps at most MAX_ITEMS rows, counts all of them."""

    def __init__(self, doctype: str, parent_field: str, parent: str):
        self.doctype, self.parent_field, self.parent = doctype, parent_field, parent
        self.errors = self.warnings = self.kept = 0
        self.truncated = False

    def add(self, severity: str, message: str, document: str | None = None, **extra) -> None:
        if severity == "Lỗi":
            self.errors += 1
        else:
            self.warnings += 1
        if self.kept >= MAX_ITEMS:
            self.truncated = True
            return
        self.kept += 1
        values = {"doctype": self.doctype, self.parent_field: self.parent, "severity": severity,
                  "message": (message or "")[:1000], **extra}
        if document:
            values["document"] = document
        frappe.get_doc(values).insert(ignore_permissions=True)


def explain(error: Exception) -> str:
    return (str(error) or error.__class__.__name__)[:300]


def title(doc) -> str:
    return _("{0} {1}").format(_(doc.doctype), doc.name)
