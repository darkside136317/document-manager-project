# -*- coding: utf-8 -*-
"""In-app notifications for readers (the bell of the reader site).

They are Frappe `Notification Log` rows of type "Alert": the type Frappe never e-mails, so nothing
here needs an outgoing mail account. A reader is told when an officer decides on a slip (duyệt,
từ chối, trả, hoàn thành, hủy) or answers a feedback; the reader's own actions notify nobody.
Notifying is best effort: a failure is logged and never blocks the workflow transition.
"""

import frappe
from frappe.utils import cint, format_date

from document_manager.document_manager.services.errors import log_exception

# state -> what the reader is told ("Phiếu ... <text>")
SLIP_STATES = {
    "Chờ lãnh đạo duyệt": "đã chuyển lãnh đạo duyệt",
    "Đã duyệt": "đã được duyệt",
    "Từ chối": "bị từ chối",
    "Đang sử dụng": "đã được giao",
    "Đã trả": "đã được ghi nhận trả",
    "Đã hoàn thành": "đã hoàn thành",
    "Đã hủy": "đã bị hủy",
}
SLIP_KINDS = {
    "Usage Request": ("Phiếu yêu cầu sử dụng", "/portal/phieu", "/dashboard/doc-gia/phieu-su-dung"),
    "Copy Request": ("Phiếu sao chụp", "/portal/sao-chep", "/dashboard/doc-gia/phieu-sao-chup"),
}
FEEDBACK_ROUTE = "/portal/gop-y"
LEADER_ROLE, OFFICER_ROLE = "Archive Leader", "Reading Room Officer"


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


def users_with_role(role: str) -> list[str]:
    """Enabled users holding `role` (a role's users, never Guest/Administrator)."""
    users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
    return frappe.get_all("User", filters={"name": ["in", users or [""]], "enabled": 1}, pluck="name") if users else []


def notify_role(role: str, subject: str, link: str, doctype: str = "", name: str = "") -> int:
    sent = 0
    for user in users_with_role(role):
        if user != frappe.session.user and notify_user(user, subject, link, doctype, name):
            sent += 1
    return sent


def on_slip_change(doc, method=None):
    """doc_events hook of Usage Request / Copy Request: tell the reader about the decision and the staff
    who must act next (the leader when a slip waits for them, the reading room once the leader decided)."""
    if not doc.has_value_changed("workflow_state") or doc.workflow_state not in SLIP_STATES:
        return
    label, reader_route, staff_route = SLIP_KINDS[doc.doctype]
    state = doc.workflow_state
    user = _reader_user(doc.reader)
    if user and user != frappe.session.user:
        subject = f"{label} {doc.name} {SLIP_STATES[state]}"
        if state == "Từ chối" and doc.rejection_reason:
            subject += f". Lý do: {doc.rejection_reason}"
        if state == "Đang sử dụng" and doc.get("due_date"):
            subject += f". Hạn trả: {format_date(doc.due_date, 'dd/MM/yyyy')}"
        notify_user(user, subject, f"{reader_route}/{doc.name}", doc.doctype, doc.name)
    link = f"{staff_route}/{doc.name}"
    if state == "Chờ lãnh đạo duyệt":
        notify_role(LEADER_ROLE, f"{label} {doc.name} của {doc.reader_name or doc.reader} chờ lãnh đạo duyệt", link, doc.doctype, doc.name)
    elif state in ("Đã duyệt", "Từ chối") and doc.get("leader"):
        notify_role(OFFICER_ROLE, f"Lãnh đạo đã xử lý {label.lower()} {doc.name}: {SLIP_STATES[state]}", link, doc.doctype, doc.name)


def on_feedback_change(doc, method=None):
    """doc_events hook of Reader Feedback: the reader hears when it is answered."""
    if doc.status != "Đã phản hồi" or not doc.has_value_changed("status"):
        return
    user = _reader_user(doc.reader)
    if user and user != frappe.session.user:
        notify_user(user, f"Góp ý \"{doc.subject}\" đã được phản hồi", f"{FEEDBACK_ROUTE}/{doc.name}",
                    doc.doctype, doc.name)


def sent_today(user: str, subject: str) -> bool:
    """Has this exact notification already been created today? (the daily job must not repeat itself)"""
    return bool(frappe.db.exists("Notification Log", {
        "for_user": user, "subject": subject, "creation": [">=", frappe.utils.get_datetime(f"{frappe.utils.nowdate()} 00:00:00")]}))


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
