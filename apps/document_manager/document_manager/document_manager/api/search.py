# -*- coding: utf-8 -*-
"""Advanced Search API — tìm kiếm nâng cao hồ sơ và văn bản.

Provides whitelisted API endpoints for both Desk UI and Portal:
- search_archival_files: tìm kiếm nâng cao hồ sơ lưu trữ
- search_documents: tìm kiếm nâng cao văn bản (metadata + full-text via Meilisearch)
- search_fulltext: full-text search qua Meilisearch
"""

import frappe
from frappe import _


@frappe.whitelist()
def search_archival_files(
    fonds=None,
    record_group=None,
    catalog=None,
    file_title=None,
    file_number=None,
    confidentiality_level=None,
    storage_warehouse=None,
    document_type_category=None,
    start_date_from=None,
    start_date_to=None,
    status=None,
    page=1,
    page_size=20,
):
    """Tìm kiếm nâng cao hồ sơ lưu trữ (metadata search via MariaDB).

    Returns:
        dict: {data: [...], total: int, page: int, page_size: int}
    """
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))

    filters = {}
    if fonds:
        filters["fonds"] = fonds
    if record_group:
        filters["record_group"] = record_group
    if catalog:
        filters["catalog"] = catalog
    if confidentiality_level:
        filters["confidentiality_level"] = confidentiality_level
    if storage_warehouse:
        filters["storage_warehouse"] = storage_warehouse
    if document_type_category:
        filters["document_type_category"] = document_type_category
    if status:
        filters["status"] = status

    or_filters = {}
    if file_title:
        or_filters["file_title"] = ["like", f"%{file_title}%"]
    if file_number:
        or_filters["file_number"] = ["like", f"%{file_number}%"]

    date_filters = []
    if start_date_from:
        date_filters.append(["start_date", ">=", start_date_from])
    if start_date_to:
        date_filters.append(["start_date", "<=", start_date_to])

    # Apply permission filters for Reader role
    _apply_confidentiality_filter(filters)

    total = frappe.db.count("Archival File", filters=filters)
    data = frappe.get_all(
        "Archival File",
        filters=filters,
        or_filters=or_filters if or_filters else None,
        fields=[
            "name", "file_title", "file_number", "fonds", "record_group",
            "catalog", "confidentiality_level", "storage_warehouse",
            "status", "start_date", "end_date", "total_pages", "total_documents",
        ],
        order_by="modified desc",
        start=(page - 1) * page_size,
        page_length=page_size,
    )

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@frappe.whitelist()
def search_documents(
    archival_file=None,
    fonds=None,
    file_type=None,
    document_title=None,
    document_number=None,
    confidentiality_level=None,
    storage_tier=None,
    page=1,
    page_size=20,
):
    """Tìm kiếm nâng cao văn bản/tài liệu (metadata search via MariaDB).

    Returns:
        dict: {data: [...], total: int, page: int, page_size: int}
    """
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))

    filters = {}
    if archival_file:
        filters["archival_file"] = archival_file
    if fonds:
        filters["fonds"] = fonds
    if file_type:
        filters["file_type"] = file_type
    if confidentiality_level:
        filters["confidentiality_level"] = confidentiality_level
    if storage_tier:
        filters["storage_tier"] = storage_tier

    or_filters = {}
    if document_title:
        or_filters["document_title"] = ["like", f"%{document_title}%"]
    if document_number:
        or_filters["document_number"] = ["like", f"%{document_number}%"]

    _apply_confidentiality_filter(filters)

    total = frappe.db.count("Archive Document", filters=filters)
    data = frappe.get_all(
        "Archive Document",
        filters=filters,
        or_filters=or_filters if or_filters else None,
        fields=[
            "name", "document_title", "document_number", "archival_file",
            "fonds", "file_type", "confidentiality_level",
            "storage_tier", "search_index_status", "document_date",
        ],
        order_by="modified desc",
        start=(page - 1) * page_size,
        page_length=page_size,
    )

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@frappe.whitelist()
def search_fulltext(
    query=None,
    fonds=None,
    confidentiality_level=None,
    file_type=None,
    sort_by=None,
    page=1,
    page_size=20,
):
    """Full-text search qua Meilisearch.

    Tìm nội dung văn bản (PDF/DOCX/XLSX extracted text) kết hợp filter metadata.

    Returns:
        dict: {data: [...], total: int, page: int, page_size: int, query: str}
    """
    if not query:
        return {"data": [], "total": 0, "page": 1, "page_size": page_size, "query": ""}

    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))

    try:
        from document_manager.document_manager.services.search_index import search as meili_search
        results = meili_search(
            query=query,
            fonds=fonds,
            confidentiality_level=confidentiality_level,
            file_type=file_type,
            sort_by=sort_by,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {
            "data": results.get("hits", []),
            "total": results.get("estimatedTotalHits", 0),
            "page": page,
            "page_size": page_size,
            "query": query,
        }
    except Exception as e:
        frappe.log_error(f"Meilisearch error: {e}", "Full-text Search Error")
        return {"data": [], "total": 0, "page": page, "page_size": page_size, "query": query, "error": str(e)}


def _apply_confidentiality_filter(filters):
    """Apply confidentiality level filter based on current user's role.

    Readers can only see documents with access levels they're authorized for.
    Staff roles (Cataloger, Reading Room Officer, etc.) see everything.
    """
    user_roles = frappe.get_roles(frappe.session.user)
    staff_roles = {"Document Admin", "Cataloger", "Reading Room Officer", "Preservation Officer", "System Manager"}

    if not staff_roles.intersection(set(user_roles)):
        # Reader or guest — restrict to 'Thường' by default
        max_level = frappe.db.get_value(
            "Reader", {"user": frappe.session.user}, "max_confidentiality_priority"
        )
        if max_level:
            allowed_levels = frappe.get_all(
                "Confidentiality Level",
                filters={"priority": ["<=", max_level]},
                pluck="name",
            )
            if allowed_levels:
                filters["confidentiality_level"] = ["in", allowed_levels]
            else:
                filters["confidentiality_level"] = "Thường"
        else:
            filters["confidentiality_level"] = "Thường"
