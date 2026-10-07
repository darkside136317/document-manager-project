# -*- coding: utf-8 -*-
"""Search API — hồ sơ and văn bản, basic and advanced, for the reader portal and the staff UI.

Whitelisted, thin: it checks that the caller may search and hands over to `services.search_service`,
which applies the same visibility rules (confidentiality, fonds scope, published state) in both the
database and the search engine.
"""

import frappe

from document_manager.document_manager.permissions import assert_can_search
from document_manager.document_manager.services import search_service


@frappe.whitelist()
def search_archival_files(
    query=None,
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
    sort_by=None,
    page=1,
    page_size=20,
):
    """Tìm kiếm hồ sơ lưu trữ: cơ bản (`query`) hoặc nâng cao (các điều kiện còn lại, kết hợp bằng AND).

    Returns:
        dict: {data: [...], total: int, page: int, page_size: int}
    """
    assert_can_search()
    return search_service.search_files(
        {
            "query": query, "fonds": fonds, "record_group": record_group, "catalog": catalog,
            "file_title": file_title, "file_number": file_number,
            "confidentiality_level": confidentiality_level, "storage_warehouse": storage_warehouse,
            "document_type_category": document_type_category, "start_date_from": start_date_from,
            "start_date_to": start_date_to, "status": status, "sort_by": sort_by,
        },
        page, page_size,
    )


@frappe.whitelist()
def search_documents(
    query=None,
    archival_file=None,
    fonds=None,
    record_group=None,
    catalog=None,
    file_type=None,
    confidentiality_level=None,
    storage_tier=None,
    document_title=None,
    document_number=None,
    author=None,
    date_from=None,
    date_to=None,
    sort_by=None,
    page=1,
    page_size=20,
):
    """Tìm kiếm văn bản, tài liệu: cơ bản (`query`, gồm cả nội dung) hoặc nâng cao.

    Returns:
        dict: {data: [...], total: int, page: int, page_size: int, engine: "meilisearch" | "database"}
    """
    assert_can_search()
    return search_service.search_documents(
        {
            "query": query, "archival_file": archival_file, "fonds": fonds, "record_group": record_group,
            "catalog": catalog, "file_type": file_type, "confidentiality_level": confidentiality_level,
            "storage_tier": storage_tier, "document_title": document_title, "document_number": document_number,
            "author": author, "date_from": date_from, "date_to": date_to, "sort_by": sort_by,
        },
        page, page_size,
    )


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
    """Tìm kiếm toàn văn (nội dung văn bản) — giữ cho cổng thông tin hiện tại; cùng bộ máy với `search_documents`."""
    assert_can_search()
    if not query:
        return {"data": [], "total": 0, "page": 1, "page_size": page_size, "query": ""}
    return search_service.search_documents(
        {"query": query, "fonds": fonds, "confidentiality_level": confidentiality_level,
         "file_type": file_type, "sort_by": sort_by},
        page, page_size,
    )
