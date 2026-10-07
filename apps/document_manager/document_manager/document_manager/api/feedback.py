# -*- coding: utf-8 -*-
"""Whitelisted API of the staff list of reader feedback (góp ý). Answering goes through the workflow
(`api.requests.apply_action`, actions "Đánh dấu đã xem" and "Phản hồi")."""

import frappe
from frappe import _
from frappe.model.workflow import get_transitions
from frappe.utils import cint
from frappe.utils.html_utils import clean_html

from document_manager.document_manager.permissions import assert_roles

STATUSES = ("Mới", "Đã xem", "Đã phản hồi")
FIELDS = ["name", "reader", "reader_name", "subject", "status", "feedback_date", "creation"]


@frappe.whitelist()
def list_feedback(status=None, search=None, page=1, page_size=20):
    assert_roles("Reading Room Officer", "Document Admin", "Archive Leader")
    filters = {"status": status} if status in STATUSES else {}
    or_filters = None
    search = (search or "").strip()
    if search:
        like = f"%{search}%"
        or_filters = [["Reader Feedback", f, "like", like] for f in ("subject", "reader_name", "name")]
    page = max(1, cint(page) or 1)
    page_size = max(1, min(100, cint(page_size) or 20))
    rows = frappe.get_list("Reader Feedback", filters=filters, or_filters=or_filters, fields=FIELDS,
                           order_by="creation desc", start=(page - 1) * page_size, page_length=page_size)
    total = frappe.get_list("Reader Feedback", filters=filters, or_filters=or_filters, fields=[{"COUNT": "name", "as": "c"}])[0].c
    counts = {r.status: r.c for r in frappe.get_list("Reader Feedback", fields=["status", {"COUNT": "name", "as": "c"}], group_by="status")}
    return {"rows": rows, "total": total, "counts": {s: counts.get(s, 0) for s in STATUSES}}


@frappe.whitelist()
def get_feedback(name):
    assert_roles("Reading Room Officer", "Document Admin", "Archive Leader")
    doc = frappe.get_doc("Reader Feedback", name)
    doc.check_permission("read")
    return {
        "name": doc.name, "reader": doc.reader, "reader_name": doc.reader_name, "subject": doc.subject, "status": doc.status,
        "feedback_date": doc.feedback_date, "content": clean_html(doc.content or ""), "response": clean_html(doc.response or ""),
        "responded_by": doc.responded_by, "responded_date": doc.responded_date,
        "actions": sorted({t.action for t in get_transitions(doc)}),
    }
