# -*- coding: utf-8 -*-
"""One văn bản (/portal/van-ban/<name>): metadata, preview and download within the reader's rights.

Access is decided by the Archive Document permission hooks (confidentiality, fonds scope, published
file); preview and download additionally follow the feature flags of the reader's group.
"""

import frappe

from document_manager.document_manager.api.file_access import _log_activity, get_preview
from document_manager.document_manager.policy import get_reader_scope
from document_manager.www._reader_ui import page_context, require_reader

FIELDS = (
    ("document_number", "Số, ký hiệu"),
    ("document_date", "Ngày văn bản"),
    ("author", "Tác giả, cơ quan ban hành"),
    ("fonds", "Phông"),
    ("archival_file", "Hồ sơ"),
    ("confidentiality_level", "Mức độ mật"),
    ("page_count", "Số trang"),
    ("file_type", "Định dạng"),
)


def get_context(context):
    require_reader()
    name = frappe.form_dict.get("name")
    if not name or not frappe.db.exists("Archive Document", name) or not frappe.has_permission("Archive Document", "read", doc=name):
        raise frappe.DoesNotExistError  # one answer for "missing" and "not allowed"
    doc = frappe.get_doc("Archive Document", name)
    scope = get_reader_scope()

    preview, preview_note = None, ""
    if scope.can_preview:
        preview = get_preview(name)
        _log_activity("Xem", "Archive Document", name, "Xem tài liệu trên cổng độc giả")
    else:
        preview_note = "Nhóm độc giả của bạn không được phép xem trước tài liệu."

    facts = []
    for field, label in FIELDS:
        value = doc.get(field)
        if not value:
            continue
        if field == "document_date":
            value = value.strftime("%d/%m/%Y")
        elif field == "fonds":
            value = frappe.db.get_value("Fonds", value, "fonds_name") or value
        facts.append((label, value, "/portal/ho-so/" + value if field == "archival_file" else ""))

    page_context(context, doc.document_title or doc.name, active="tra-cuu")
    context.update({
        "doc": doc, "preview": preview, "preview_note": preview_note, "facts": facts,
        "can_download": bool(preview and preview.get("download_url")),
        "can_add": {"usage": bool(scope.profile and scope.can_request_usage), "copy": bool(scope.profile and scope.can_request_copy)},
    })
    return context
