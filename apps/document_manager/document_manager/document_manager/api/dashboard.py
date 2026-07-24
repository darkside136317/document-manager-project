# -*- coding: utf-8 -*-
"""Permission-aware data for the Document Manager workspace overview."""

import frappe


def _permitted_count(doctype, filters=None):
    if not frappe.has_permission(doctype, "read"):
        return 0
    return len(
        frappe.get_list(
            doctype,
            filters=filters or {},
            pluck="name",
            limit_page_length=10000,
        )
    )


@frappe.whitelist()
def get_workspace_summary():
    """Return compact operational metrics for the current Desk user."""
    document_count = _permitted_count("Archive Document")
    indexed_count = _permitted_count(
        "Archive Document", {"search_index_status": "Đã index"}
    )

    recent_documents = []
    if frappe.has_permission("Archive Document", "read"):
        recent_documents = frappe.get_list(
            "Archive Document",
            fields=[
                "name",
                "document_title",
                "file_type",
                "search_index_status",
                "modified",
            ],
            order_by="modified desc",
            limit_page_length=5,
        )

    return {
        "fonds": _permitted_count("Fonds"),
        "archival_files": _permitted_count("Archival File"),
        "documents": document_count,
        "readers": _permitted_count("Reader"),
        "indexed_documents": indexed_count,
        "index_percent": round(indexed_count * 100 / document_count) if document_count else 0,
        "pending_usage": _permitted_count(
            "Usage Request", {"workflow_state": "Chờ duyệt"}
        ),
        "pending_copy": _permitted_count(
            "Copy Request", {"workflow_state": "Chờ duyệt"}
        ),
        "integrity_errors": _permitted_count(
            "Integrity Check", {"status": "Phát hiện lỗi"}
        ),
        "recent_documents": recent_documents,
    }
