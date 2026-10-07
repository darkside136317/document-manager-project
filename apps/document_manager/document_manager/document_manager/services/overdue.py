# -*- coding: utf-8 -*-
"""Daily job: flag usage slips past their due date and remind readers.

`Usage Request.is_overdue` is a flag, not a workflow state: a slip stays "Đang sử dụng" while the
documents are out, and the flag only marks that the due date has passed (the queue's "Quá hạn" tab,
reports and the quota rule that blocks new slips use it). The job is idempotent: running it twice a
day changes nothing the second time and sends no reminder twice. Reminders follow Reader Settings
("Tự động nhắc trả quá hạn", "Nhắc trước hạn trả").
"""

import frappe
from frappe.utils import add_days, format_date, getdate, nowdate

from document_manager.document_manager.policy import get_limits
from document_manager.document_manager.services import lifecycle as lc
from document_manager.document_manager.services import notify
from document_manager.document_manager.services.errors import log_exception

PORTAL_ROUTE = "/portal/phieu"


def _in_use(extra: dict) -> list:
    return frappe.get_all(
        lc.USAGE, filters={"docstatus": 1, "workflow_state": lc.STATE_IN_USE, **extra},
        fields=["name", "reader", "due_date"], limit_page_length=0)


def _remind(slip, subject: str) -> bool:
    user = frappe.db.get_value("Reader", slip.reader, "user")
    if not user or notify.sent_today(user, subject):
        return False
    return bool(notify.notify_user(user, subject, f"{PORTAL_ROUTE}/{slip.name}", lc.USAGE, slip.name))


def mark_overdue_and_remind() -> dict:
    """Scheduler entry point. Returns what it did, for the log and the tests."""
    today = getdate(nowdate())
    summary = {"flagged": 0, "cleared": 0, "overdue_notices": 0, "due_soon_notices": 0}
    try:
        for slip in _in_use({"due_date": ["<", today], "is_overdue": 0}):
            frappe.db.set_value(lc.USAGE, slip.name, "is_overdue", 1, update_modified=False)
            summary["flagged"] += 1

        # a renewal or a return moved the date: the flag no longer applies
        stale = frappe.get_all(lc.USAGE, filters={"is_overdue": 1, "docstatus": 1}, fields=["name", "workflow_state", "due_date"],
                               limit_page_length=0)
        for slip in stale:
            if slip.workflow_state != lc.STATE_IN_USE or not slip.due_date or getdate(slip.due_date) >= today:
                frappe.db.set_value(lc.USAGE, slip.name, "is_overdue", 0, update_modified=False)
                summary["cleared"] += 1

        settings = get_limits()
        if settings.remind_overdue:
            for slip in _in_use({"due_date": ["<", today]}):
                days = (today - getdate(slip.due_date)).days
                if _remind(slip, f"Phiếu yêu cầu sử dụng {slip.name} đã quá hạn trả {days} ngày. Vui lòng trả tài liệu cho phòng đọc."):
                    summary["overdue_notices"] += 1
            if settings.reminder_days_before:
                due_on = add_days(today, settings.reminder_days_before)
                for slip in _in_use({"due_date": due_on}):
                    if _remind(slip, f"Phiếu yêu cầu sử dụng {slip.name} đến hạn trả vào {format_date(slip.due_date, 'dd/MM/yyyy')}."):
                        summary["due_soon_notices"] += 1
        frappe.db.commit()
    except Exception:
        log_exception("Overdue job failed", "mark_overdue_and_remind")
        raise
    return summary
