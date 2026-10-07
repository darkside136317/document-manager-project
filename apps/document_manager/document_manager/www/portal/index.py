# -*- coding: utf-8 -*-
"""Search page of the reader area (/portal): hồ sơ and văn bản, basic and advanced.

The page only prepares the form (fonds and levels the reader may use, what their group allows);
the search itself is `api.search`, called from the browser, which applies the same visibility rules.
"""

import frappe

from document_manager.document_manager.policy import get_reader_scope
from document_manager.document_manager.services.web import inline_json
from document_manager.www._reader_ui import page_context, require_reader

FILE_TYPES = ("PDF", "DOCX", "XLSX", "DOC", "XLS", "JPG", "PNG", "TIF")


def get_context(context):
    require_reader()
    scope = get_reader_scope()
    page_context(context, "Tra cứu tài liệu", active="tra-cuu")
    # get_list applies the reader's fonds scope; levels are limited to the reader's clearance.
    fonds = frappe.get_list("Fonds", fields=["name", "fonds_name"], order_by="fonds_name asc", limit_page_length=0)
    level_filters = {} if scope.is_staff else {"priority": ["<=", scope.max_priority or 1]}
    levels = frappe.get_all("Confidentiality Level", filters=level_filters, pluck="name", order_by="priority asc")
    can_add = {"usage": bool(scope.profile and scope.can_request_usage), "copy": bool(scope.profile and scope.can_request_copy)}
    context.update({
        "fonds": fonds, "levels": levels, "file_types": FILE_TYPES,
        "can_search": scope.can_search, "allowed": scope.allowed, "can_add": can_add,
        "search_config": inline_json({"fonds": {f.name: f.fonds_name for f in fonds}, "canAdd": can_add}),
    })
    return context
