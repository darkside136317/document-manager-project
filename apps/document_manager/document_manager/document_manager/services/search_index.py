# -*- coding: utf-8 -*-
"""Meilisearch integration — index/search/deindex archival documents.

Manages full-text search index in Meilisearch for Archive Document content.
Documents are indexed with their full hierarchical path (fonds/record_group/catalog/archival_file)
plus extracted text content, enabling combined metadata + content search.
"""

import json

import frappe

_meili_client = None
_meili_index = None
INDEX_NAME = "archive_documents"


def _get_client():
    """Lazy-initialize Meilisearch client."""
    global _meili_client
    if _meili_client is not None:
        return _meili_client

    import meilisearch

    host = frappe.conf.get("meilisearch_host") or "http://localhost:7700"
    master_key = frappe.conf.get("meilisearch_master_key") or ""

    _meili_client = meilisearch.Client(host, master_key)
    return _meili_client


def _get_index():
    """Get or create the archive_documents index with proper settings."""
    global _meili_index
    if _meili_index is not None:
        return _meili_index

    client = _get_client()
    try:
        index = client.get_index(INDEX_NAME)
    except Exception:
        create_task = client.create_index(INDEX_NAME, {"primaryKey": "id"})
        create_result = client.wait_for_task(create_task.task_uid, timeout_in_ms=10000)
        if create_result.status != "succeeded":
            raise RuntimeError(f"Could not create Meilisearch index: {create_result.error}")
        index = client.get_index(INDEX_NAME)

    # Apply settings to new and pre-existing indexes alike.
    settings_task = index.update_settings({
        "searchableAttributes": [
            "document_title", "content_text", "document_number", "author",
            "fonds_name", "archival_file_title",
        ],
        "filterableAttributes": [
            "fonds", "record_group", "catalog", "archival_file",
            "file_type", "confidentiality_level", "confidentiality_priority",
            "storage_tier", "search_index_status",
        ],
        "sortableAttributes": ["document_date", "modified", "created"],
        "displayedAttributes": [
            "id", "document_title", "document_number", "content_text", "archival_file",
            "archival_file_title", "fonds", "fonds_name", "file_type",
            "confidentiality_level", "document_date", "author",
        ],
    })
    settings_result = client.wait_for_task(settings_task.task_uid, timeout_in_ms=10000)
    if settings_result.status != "succeeded":
        raise RuntimeError(f"Could not configure Meilisearch index: {settings_result.error}")

    _meili_index = index
    return _meili_index


def index_document(doc_name: str):
    """Index a document and persist a useful failure state when indexing fails."""
    try:
        return _index_document(doc_name)
    except Exception:
        if frappe.db.exists("Archive Document", doc_name):
            frappe.db.set_value(
                "Archive Document", doc_name, "search_index_status", "Lỗi",
                update_modified=False,
            )
            frappe.db.commit()
        raise


def _index_document(doc_name: str):
    """Index a single Archive Document into Meilisearch."""
    doc = frappe.get_doc("Archive Document", doc_name)

    # Get parent titles for better search results
    fonds_name = ""
    af_title = ""
    if doc.fonds:
        fonds_name = frappe.db.get_value("Fonds", doc.fonds, "fonds_name") or ""
    if doc.archival_file:
        af_title = frappe.db.get_value("Archival File", doc.archival_file, "file_title") or ""

    # Get confidentiality priority for filtering
    conf_priority = 1
    if doc.confidentiality_level:
        conf_priority = frappe.db.get_value(
            "Confidentiality Level", doc.confidentiality_level, "priority"
        ) or 1

    document = {
        "id": doc.name,
        "document_title": doc.document_title or "",
        "document_number": doc.document_number or "",
        "content_text": (doc.content_text or "")[:100000],  # Limit to 100K chars
        "author": doc.author or "",
        "archival_file": doc.archival_file or "",
        "archival_file_title": af_title,
        "catalog": doc.catalog or "",
        "record_group": doc.record_group or "",
        "fonds": doc.fonds or "",
        "fonds_name": fonds_name,
        "file_type": doc.file_type or "",
        "confidentiality_level": doc.confidentiality_level or "Thường",
        "confidentiality_priority": int(conf_priority),
        "storage_tier": doc.storage_tier or "Hot",
        "document_date": str(doc.document_date) if doc.document_date else "",
        "modified": str(doc.modified),
        "created": str(doc.creation),
    }

    index = _get_index()
    index_task = index.add_documents([document])
    index_result = _get_client().wait_for_task(index_task.task_uid, timeout_in_ms=10000)
    if index_result.status != "succeeded":
        raise RuntimeError(f"Could not index document: {index_result.error}")

    frappe.db.set_value(
        "Archive Document", doc_name, "search_index_status", "Đã index",
        update_modified=False,
    )


def deindex_document(doc_name: str):
    """Remove a document from Meilisearch index."""
    try:
        index = _get_index()
        index.delete_document(doc_name)
    except Exception:
        pass


def search(query: str, fonds=None, confidentiality_level=None, file_type=None,
           sort_by=None, offset=0, limit=20) -> dict:
    """Search documents in Meilisearch.

    Returns Meilisearch result dict with hits, estimatedTotalHits, etc.
    """
    index = _get_index()

    filter_parts = []
    if fonds:
        filter_parts.append(f"fonds = {json.dumps(str(fonds), ensure_ascii=False)}")
    if confidentiality_level:
        filter_parts.append(
            f"confidentiality_level = {json.dumps(str(confidentiality_level), ensure_ascii=False)}"
        )
    if file_type:
        filter_parts.append(f"file_type = {json.dumps(str(file_type), ensure_ascii=False)}")

    # Apply Reader permission filter
    user_roles = frappe.get_roles(frappe.session.user)
    staff_roles = {"Document Admin", "Cataloger", "Reading Room Officer",
                   "Preservation Officer", "System Manager", "Administrator"}
    if not staff_roles.intersection(set(user_roles)):
        max_priority = frappe.db.get_value(
            "Reader", {"user": frappe.session.user}, "max_confidentiality_priority"
        ) or 1
        filter_parts.append(f"confidentiality_priority <= {int(max_priority)}")

    search_params = {
        "offset": offset,
        "limit": limit,
        "attributesToHighlight": ["document_title", "content_text"],
        "highlightPreTag": "<mark>",
        "highlightPostTag": "</mark>",
        "attributesToCrop": ["content_text"],
        "cropLength": 200,
    }
    if filter_parts:
        search_params["filter"] = " AND ".join(filter_parts)

    allowed_sorts = {
        "newest": "document_date:desc",
        "oldest": "document_date:asc",
        "modified": "modified:desc",
    }
    if sort_by in allowed_sorts:
        search_params["sort"] = [allowed_sorts[sort_by]]

    return index.search(query, search_params)


# === Enqueue functions (called from hooks.py doc_events) ===

def enqueue_index(doc, method=None):
    """Enqueue index job for an Archive Document (called on on_update)."""
    frappe.enqueue(
        "document_manager.document_manager.services.search_index.index_document",
        doc_name=doc.name,
        queue="short",
        at_front=True,
    )
    frappe.db.set_value(
        "Archive Document", doc.name, "search_index_status", "Đang xử lý",
        update_modified=False,
    )


def enqueue_deindex(doc, method=None):
    """Enqueue deindex job for an Archive Document (called on on_trash)."""
    frappe.enqueue(
        "document_manager.document_manager.services.search_index.deindex_document",
        doc_name=doc.name,
        queue="short",
    )


def enqueue_index_file(doc, method=None):
    """Re-index all documents under an Archival File when it's updated."""
    docs = frappe.get_all("Archive Document", filters={"archival_file": doc.name}, pluck="name")
    for d in docs:
        frappe.enqueue(
            "document_manager.document_manager.services.search_index.index_document",
            doc_name=d,
            queue="short",
        )


def enqueue_deindex_file(doc, method=None):
    """Deindex all documents under an Archival File when it's trashed."""
    docs = frappe.get_all("Archive Document", filters={"archival_file": doc.name}, pluck="name")
    for d in docs:
        frappe.enqueue(
            "document_manager.document_manager.services.search_index.deindex_document",
            doc_name=d,
            queue="short",
        )


def reconcile_index():
    """Reconciliation job — compare DB and Meilisearch index, fix mismatches.

    Run nightly via scheduler to ensure index consistency.
    """
    frappe.logger().info("Starting Meilisearch reconciliation...")

    # Get all indexed doc names from Meilisearch
    index = _get_index()
    indexed_ids = set()
    offset = 0
    while True:
        result = index.get_documents({"offset": offset, "limit": 1000, "fields": ["id"]})
        docs = result.results if hasattr(result, "results") else result.get("results", [])
        if not docs:
            break
        for d in docs:
            indexed_ids.add(d.get("id") if isinstance(d, dict) else d.id)
        offset += 1000

    # Get all doc names from DB
    db_ids = set(
        frappe.get_all("Archive Document", pluck="name")
    )

    # Documents in DB but not in index → index them
    missing = db_ids - indexed_ids
    for doc_name in missing:
        frappe.enqueue(
            "document_manager.document_manager.services.search_index.index_document",
            doc_name=doc_name,
            queue="long",
        )

    # Documents in index but not in DB → deindex them
    orphaned = indexed_ids - db_ids
    for doc_name in orphaned:
        deindex_document(doc_name)

    frappe.logger().info(
        f"Reconciliation complete: {len(missing)} to index, {len(orphaned)} orphaned removed."
    )
