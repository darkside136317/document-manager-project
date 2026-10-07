# -*- coding: utf-8 -*-
"""Reader-facing document viewer: metadata, preview and download of one Archive Document.

Access is decided by Archive Document permissions (confidentiality hooks in permissions.py),
so a reader can only open documents within their clearance.
"""

import frappe
from frappe import _

from document_manager.document_manager.api.file_access import _log_activity, get_preview
from document_manager.document_manager.permissions import require_portal_user

FIELDS = (
    ("document_number", "Số/ký hiệu"),
    ("document_date", "Ngày văn bản"),
    ("author", "Tác giả / cơ quan ban hành"),
    ("fonds", "Phông"),
    ("archival_file", "Hồ sơ"),
    ("confidentiality_level", "Mức độ mật"),
    ("page_count", "Số trang"),
    ("file_type", "Định dạng"),
)


def get_context(context):
    context.no_cache = 1
    require_portal_user("/portal")
    name = frappe.form_dict.get("name")
    if not name or not frappe.db.exists("Archive Document", name) or not frappe.has_permission(
        "Archive Document", "read", doc=name
    ):
        # One answer for "missing" and "not allowed", so names cannot be probed.
        frappe.throw(_("Không tìm thấy tài liệu hoặc bạn không có quyền xem"), frappe.PermissionError)

    doc = frappe.get_doc("Archive Document", name)
    preview = get_preview(name)
    _log_activity("Xem", "Archive Document", name, "Xem tài liệu trên Portal")

    context.update({
        "doc": doc,
        "preview": preview,
        "fields": [(label, doc.get(field)) for field, label in FIELDS if doc.get(field)],
        "page_title": doc.document_title or doc.name,
        "page_icon": "fa-file-text-o",
        "breadcrumbs": [
            {"label": "Tìm kiếm tài liệu", "link": "/portal"},
            {"label": doc.document_title or doc.name},
        ],
    })
