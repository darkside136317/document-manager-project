# -*- coding: utf-8 -*-
"""Sign-in page for readers and staff (/dang-nhap). A visitor who is already in goes to their own home."""

import frappe
from frappe.utils import cint

from document_manager.www._reader_ui import guest_only, page_context


def get_context(context):
    guest_only()
    page_context(context, "Đăng nhập", public=True)
    # The page returns the visitor to where they came from — on this site only (checked again in the browser).
    target = frappe.form_dict.get("redirect-to") or ""
    context.redirect = target if target.startswith("/") and not target.startswith(("//", "/\\")) else ""
    context.digitization_enabled = bool(cint(frappe.db.get_single_value("Document Manager Settings", "digitization_enabled")))
    return context
