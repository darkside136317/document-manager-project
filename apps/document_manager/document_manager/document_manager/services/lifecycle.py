# -*- coding: utf-8 -*-
"""Rules of a slip's life: who needs a leader, how many slips a reader may have, when things fall due.

Pure decisions over a Usage Request / Copy Request document and the reader's limits
(`policy.get_limits`). `RequestDocument` (services/request_base.py) calls them at the right
transition; the daily job (services/overdue.py) uses the same date rules.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, getdate, nowdate

from document_manager.document_manager.policy import get_limits

USAGE, COPY = "Usage Request", "Copy Request"
SLIP_DOCTYPES = (USAGE, COPY)

STATE_PENDING = "Chờ duyệt"
STATE_LEADER = "Chờ lãnh đạo duyệt"
STATE_APPROVED = "Đã duyệt"
STATE_REJECTED = "Từ chối"
STATE_IN_USE = "Đang sử dụng"
STATE_RETURNED = "Đã trả"
STATE_COMPLETED = "Đã hoàn thành"
STATE_CANCELLED = "Đã hủy"
STATE_DRAFT = "Nháp"

# A slip the reader still "has": counted against the open-slip limit.
OPEN_STATES = (STATE_PENDING, STATE_LEADER, STATE_APPROVED, STATE_IN_USE)
# States in which an officer or leader decides on the items one by one.
REVIEW_STATES = (STATE_PENDING, STATE_LEADER)

ITEM_PENDING, ITEM_APPROVED, ITEM_REJECTED = "Chờ duyệt", "Đã duyệt", "Từ chối"
ITEM_ISSUED, ITEM_RETURNED, ITEM_COPIED = "Đã giao", "Đã trả", "Đã hoàn thành"
CONDITIONS = ("", "Tốt", "Hư hỏng nhẹ", "Thiếu trang", "Hư hỏng nặng")


def item_levels(doc) -> list[str]:
    """Confidentiality level of every item: the document's own, else its file's."""
    levels = []
    for row in doc.items:
        level = None
        if row.archive_document:
            level = frappe.db.get_value("Archive Document", row.archive_document, "confidentiality_level")
        if not level and row.archival_file:
            level = frappe.db.get_value("Archival File", row.archival_file, "confidentiality_level")
        if level:
            levels.append(level)
    return levels


def needs_leader(doc) -> bool:
    """Does a leader have to approve this slip? The reader group decides how: always, never, or when an
    item's confidentiality level asks for it."""
    mode = get_limits(doc.reader).approval_mode
    if mode == "Luôn qua lãnh đạo":
        return True
    if mode == "Chỉ phòng đọc duyệt":
        return False
    levels = set(item_levels(doc))
    return bool(levels) and bool(frappe.db.exists(
        "Confidentiality Level", {"name": ["in", list(levels)], "requires_leader_approval": 1}))


def overdue_count(profile: str) -> int:
    """Slips of this reader that are in use and past their due date (the daily flag may lag a day)."""
    return frappe.db.count(USAGE, {"reader": profile, "docstatus": 1, "workflow_state": STATE_IN_USE,
                                   "due_date": ["<", nowdate()]})


def check_quota(doc) -> None:
    """Refuse a slip the reader's limits do not allow. Raises ValidationError with the reason."""
    limits = get_limits(doc.reader)
    if limits.max_items_per_request and len(doc.items) > limits.max_items_per_request:
        frappe.throw(_("Một phiếu có tối đa {0} hồ sơ/văn bản (phiếu này có {1})").format(
            limits.max_items_per_request, len(doc.items)))

    per_day = limits.max_requests_per_day if doc.doctype == USAGE else limits.max_copy_requests_per_day
    if per_day:
        today_start = get_datetime(f"{nowdate()} 00:00:00")
        used = frappe.db.count(doc.doctype, {
            "reader": doc.reader, "docstatus": 1, "submitted_on": [">=", today_start],
            "workflow_state": ["!=", STATE_CANCELLED], "name": ["!=", doc.name]})
        if used >= per_day:
            frappe.throw(_("Mỗi ngày chỉ lập tối đa {0} {1}. Hôm nay bạn đã gửi {2}.").format(
                per_day, _("phiếu yêu cầu sử dụng") if doc.doctype == USAGE else _("phiếu sao chụp"), used))

    if limits.max_open_requests:
        open_slips = sum(frappe.db.count(dt, {"reader": doc.reader, "docstatus": 1,
                                              "workflow_state": ["in", list(OPEN_STATES)], "name": ["!=", doc.name]})
                         for dt in SLIP_DOCTYPES)
        if open_slips >= limits.max_open_requests:
            frappe.throw(_("Bạn đang có {0} phiếu chưa xử lý xong (tối đa {1}). Hãy đợi phiếu được xử lý hoặc hủy bớt.").format(
                open_slips, limits.max_open_requests))

    if doc.doctype == USAGE and limits.block_when_overdue and overdue_count(doc.reader):
        frappe.throw(_("Bạn còn tài liệu quá hạn chưa trả. Vui lòng trả tài liệu trước khi lập phiếu mới."))


def due_date_for(profile: str, start=None):
    return add_days(getdate(start or nowdate()), get_limits(profile).hold_days)


def can_renew(doc) -> tuple[bool, str]:
    """(allowed, reason it is not): a slip in use may be extended up to the reader's renewal limit."""
    if doc.doctype != USAGE or doc.workflow_state != STATE_IN_USE:
        return False, _("Chỉ gia hạn được phiếu đang sử dụng")
    limits = get_limits(doc.reader)
    if limits.max_renewals and cint(doc.renewal_count) >= limits.max_renewals:
        return False, _("Phiếu đã gia hạn tối đa {0} lần").format(limits.max_renewals)
    return True, ""


def next_due_date(doc):
    """Renewal adds days to the later of the current due date and today (an overdue slip is not
    extended into the past)."""
    base = max(getdate(doc.due_date or nowdate()), getdate(nowdate()))
    return add_days(base, get_limits(doc.reader).renewal_days)
