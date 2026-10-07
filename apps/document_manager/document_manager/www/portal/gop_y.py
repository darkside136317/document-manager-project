# -*- coding: utf-8 -*-
"""Góp ý of the signed-in reader: send a feedback and read the answers (/portal/gop-y[/<name>])."""

import frappe
from frappe.utils import cint
from frappe.utils.html_utils import clean_html

from document_manager.document_manager.policy import get_reader_scope
from document_manager.www._reader_ui import page_context, require_reader

PAGE_SIZE = 15


def get_context(context):
    require_reader()
    scope = get_reader_scope()
    page_context(context, "Góp ý", active="gop-y")
    name = frappe.form_dict.get("name")
    context.can_send = bool(scope.profile and scope.can_feedback)
    context.item = None
    if name:
        if not frappe.db.exists("Reader Feedback", name) or not frappe.has_permission("Reader Feedback", "read", doc=name):
            raise frappe.DoesNotExistError
        doc = frappe.get_doc("Reader Feedback", name)
        context.update({"item": doc, "content_html": clean_html(doc.content or ""),
                        "response_html": clean_html(doc.response or ""), "title": doc.subject})
        return context

    page = max(1, cint(frappe.form_dict.get("page")) or 1)
    total = frappe.get_list("Reader Feedback", fields=[{"COUNT": "name", "as": "c"}])[0].c
    context.update({
        "rows": frappe.get_list("Reader Feedback", fields=["name", "subject", "status", "feedback_date"],
                                order_by="modified desc", start=(page - 1) * PAGE_SIZE, page_length=PAGE_SIZE),
        "page": page, "pages": max(1, -(-total // PAGE_SIZE)), "total": total,
    })
    return context
