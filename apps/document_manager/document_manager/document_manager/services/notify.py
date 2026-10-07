# -*- coding: utf-8 -*-
"""In-app notifications for readers (the bell of the reader site).

They are Frappe `Notification Log` rows of type "Alert": the type Frappe never e-mails, so nothing
here needs an outgoing mail account. A reader is told when an officer decides on a slip (duyệt,
từ chối, trả, hoàn thành, hủy) or answers a feedback; the reader's own actions notify nobody.
Notifying is best effort: a failure is logged and never blocks the workflow transition.
"""

import frappe
from frappe.utils import cint

from document_manager.document_manager.services.errors import log_exception

# state -> (verb phrase, includes the rejection reason)
SLIP_STATES = {
    "Đã duyệt": "đã được duyệt",
    "Từ chối": "bị từ chối",
    "Đã trả": "đã được ghi nhận trả",
    "Đã hoàn thành": "đã hoàn thành",
    "Đã hủy": "đã bị hủy",
}
SLIP_KINDS = {
    "Usage Request": ("Phiếu yêu cầu sử dụng", "/portal/phieu"),
    "Copy Request": ("Phiếu sao chụp", "/portal/sao-chep"),
}
FEEDBACK_ROUTE = "/portal/gop-y"


def notify_user(user: str, subject: str, link: str, doctype: str = "", name: str = "") -> str | None:
    """Create the notification of `user`. Returns its name, or None when it could not be created."""
    if not user or user in ("Guest", "Administrator"):
        return None
    try:
        log = frappe.get_doc({
            "doctype": "Notification Log", "for_user": user, "from_user": frappe.session.user,
            "type": "Alert", "subject": subject[:500], "link": link,
            "document_type": doctype or None, "document_name": name or None,
        })
        log.insert(ignore_permissions=True)
        return log.name
    except Exception:
        log_exception("Reader notification failed", f"{doctype} {name} -> {user}")
        return None


def _reader_user(reader: str | None) -> str | None:
    return frappe.db.get_value("Reader", reader, "user") if reader else None


def on_slip_change(doc, method=None):
    """doc_events hook of Usage Request / Copy Request."""
    if not doc.has_value_changed("workflow_state") or doc.workflow_state not in SLIP_STATES:
        return
    user = _reader_user(doc.reader)
    if not user or user == frappe.session.user:
        return
    label, route = SLIP_KINDS[doc.doctype]
    subject = f"{label} {doc.name} {SLIP_STATES[doc.workflow_state]}"
    if doc.workflow_state == "Từ chối" and doc.rejection_reason:
        subject += f". Lý do: {doc.rejection_reason}"
    notify_user(user, subject, f"{route}/{doc.name}", doc.doctype, doc.name)


def on_feedback_change(doc, method=None):
    """doc_events hook of Reader Feedback: the reader hears when it is answered."""
    if doc.status != "Đã phản hồi" or not doc.has_value_changed("status"):
        return
    user = _reader_user(doc.reader)
    if user and user != frappe.session.user:
        notify_user(user, f"Góp ý \"{doc.subject}\" đã được phản hồi", f"{FEEDBACK_ROUTE}/{doc.name}",
                    doc.doctype, doc.name)


# --- what the reader site shows ----------------------------------------------------------------

def unread_count(user: str | None = None) -> int:
    user = user or frappe.session.user
    if user == "Guest":
        return 0
    return frappe.db.count("Notification Log", {"for_user": user, "read": 0, "type": "Alert"})


def list_for(user: str, start: int = 0, page_length: int = 20) -> dict:
    filters = {"for_user": user, "type": "Alert"}
    rows = frappe.get_all(
        "Notification Log", filters=filters,
        fields=["name", "subject", "link", "read", "creation", "document_type", "document_name"],
        order_by="creation desc", start=max(0, cint(start)), page_length=max(1, min(cint(page_length) or 20, 100)))
    return {"rows": rows, "total": frappe.db.count("Notification Log", filters), "unread": unread_count(user)}


def mark_read(user: str, names: list[str] | None = None) -> int:
    """Mark the user's own notifications read (all of them when `names` is empty)."""
    filters = {"for_user": user, "read": 0, "type": "Alert"}
    if names:
        filters["name"] = ["in", names]
    frappe.db.set_value("Notification Log", filters, "read", 1, update_modified=False)
    frappe.cache.hdel("notifications", user)
    return unread_count(user)
