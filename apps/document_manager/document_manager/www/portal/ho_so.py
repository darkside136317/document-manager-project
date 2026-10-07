# -*- coding: utf-8 -*-
"""One hồ sơ (/portal/ho-so/<name>): its description and the văn bản inside it, with "add to slip"."""

import frappe
from frappe.utils import cint
from frappe.utils.html_utils import clean_html

from document_manager.document_manager.api.file_access import _log_activity
from document_manager.document_manager.policy import get_reader_scope
from document_manager.www._reader_ui import page_context, require_reader

PAGE_SIZE = 20
DOCUMENT_FIELDS = ["name", "document_title", "document_number", "document_date", "author", "file_type",
                   "confidentiality_level", "page_count"]


def _label(doctype, name, field):
    return (frappe.db.get_value(doctype, name, field) or name) if name else ""


def get_context(context):
    require_reader()
    name = frappe.form_dict.get("name")
    # One answer for "missing" and "not allowed", so names cannot be probed.
    if not name or not frappe.db.exists("Archival File", name) or not frappe.has_permission("Archival File", "read", doc=name):
        raise frappe.DoesNotExistError
    doc = frappe.get_doc("Archival File", name)
    scope = get_reader_scope()
    page = max(1, cint(frappe.form_dict.get("page")) or 1)

    filters = {"archival_file": name}
    total = frappe.get_list("Archive Document", filters=filters, fields=[{"COUNT": "name", "as": "c"}])[0].c
    documents = frappe.get_list("Archive Document", filters=filters, fields=DOCUMENT_FIELDS,
                                order_by="document_date asc, name asc", start=(page - 1) * PAGE_SIZE,
                                page_length=PAGE_SIZE)
    _log_activity("Xem", "Archival File", name, "Xem hồ sơ trên cổng độc giả")

    page_context(context, doc.file_title or doc.name, active="tra-cuu")
    context.update({
        "file": doc,
        "description_html": clean_html(doc.description or ""),
        "facts": [(label, value) for label, value in (
            ("Số, ký hiệu", doc.file_number),
            ("Phông", _label("Fonds", doc.fonds, "fonds_name")),
            ("Khối tài liệu", _label("Record Group", doc.record_group, "group_title")),
            ("Mục lục", _label("Catalog", doc.catalog, "catalog_title")),
            ("Thời gian", " – ".join(str(d.strftime("%d/%m/%Y")) for d in (doc.start_date, doc.end_date) if d)),
            ("Số trang", doc.total_pages or ""),
            ("Số văn bản", doc.total_documents or ""),
            ("Mức độ mật", doc.confidentiality_level),
        ) if value],
        "documents": documents, "total": total, "page": page, "pages": max(1, -(-total // PAGE_SIZE)),
        "can_add": {"usage": bool(scope.profile and scope.can_request_usage), "copy": bool(scope.profile and scope.can_request_copy)},
    })
    return context
