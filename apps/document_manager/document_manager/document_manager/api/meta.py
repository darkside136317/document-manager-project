# -*- coding: utf-8 -*-
"""DocType description for the generic staff screens."""

import frappe

from document_manager.document_manager.services.ui import describe


@frappe.whitelist()
def get_doctype_ui(doctype):
    """Fields (limited to what the user may read/write), layout, list columns and permissions."""
    return describe(doctype)
