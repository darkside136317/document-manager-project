# -*- coding: utf-8 -*-
"""The reader's notifications (/portal/thong-bao): what the bell counts."""

import frappe
from frappe.utils import cint, format_datetime

from document_manager.document_manager.services import notify
from document_manager.www._reader_ui import page_context, require_reader
from document_manager.document_manager.services.web import inline_json

PAGE_SIZE = 20


def get_context(context):
    require_reader()
    page_context(context, "Thông báo", active="")
    page = max(1, cint(frappe.form_dict.get("page")) or 1)
    data = notify.list_for(frappe.session.user, (page - 1) * PAGE_SIZE, PAGE_SIZE)
    for row in data["rows"]:
        row["when"] = format_datetime(row.creation, "dd/MM/yyyy HH:mm")
    context.update({
        "rows": data["rows"], "total": data["total"], "unread": data["unread"], "page": page,
        "pages": max(1, -(-data["total"] // PAGE_SIZE)),
        "notes_config": inline_json({"unread": data["unread"]}),
    })
    return context
