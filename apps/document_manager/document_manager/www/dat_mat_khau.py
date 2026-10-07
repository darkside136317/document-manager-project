# -*- coding: utf-8 -*-
"""Choose a password from the one-time link an officer issued (/dat-mat-khau?key=...)."""

import frappe

from document_manager.document_manager.services.registration import check_link
from document_manager.www._reader_ui import page_context


def get_context(context):
    page_context(context, "Đặt mật khẩu", public=False)  # a link page: never indexed
    key = (frappe.form_dict.get("key") or "").strip()
    user, problem = check_link(key)
    context.key = key
    context.link_user = user
    context.problem = problem  # None | "invalid" | "expired"
    return context
