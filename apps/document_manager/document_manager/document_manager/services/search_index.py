# -*- coding: utf-8 -*-
"""Meilisearch integration — index/search/deindex archival documents.

Manages full-text search index in Meilisearch for Archive Document content.
Documents are indexed with their full hierarchical path (fonds/record_group/catalog/archival_file)
plus extracted text content, enabling combined metadata + content search.

Visibility is decided at index time and re-evaluated whenever the parent Archival File changes:
`confidentiality_priority` (fail-closed when the level is unknown) and `is_published`
(draft or disposed files are only visible to staff).
"""

import calendar
import json

import frappe

from document_manager.document_manager.permissions import is_file_published
from document_manager.document_manager.policy import get_reader_scope
from document_manager.document_manager.services.errors import log_exception

_clients = {}  # one client / configured index per site (a bench serves several sites)
_indexes = {}
INDEX_NAME = "archive_documents"
CHUNK = 500
UNKNOWN_LEVEL_PRIORITY = 999  # an unclassified document must never reach a reader


def _get_client():
    """Lazy-initialize the Meilisearch client of the current site."""
    host = frappe.conf.get("meilisearch_host") or "http://localhost:7700"
    master_key = frappe.conf.get("meilisearch_master_key") or ""
    cache_key = (frappe.local.site, host, master_key)
    if cache_key not in _clients:
        import meilisearch

        _clients[cache_key] = meilisearch.Client(host, master_key)
    return _clients[cache_key]


def _get_index():
    """Get or create the archive_documents index with proper settings."""
    client = _get_client()
    site = frappe.local.site
    if site in _indexes and _indexes[site][0] is client:
        return _indexes[site][1]

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
            "storage_tier", "search_index_status", "is_published", "document_ts",
        ],
        "sortableAttributes": ["document_date", "document_ts", "modified", "created"],
        "displayedAttributes": [
            "id", "document_title", "document_number", "content_text", "archival_file",
            "archival_file_title", "fonds", "fonds_name", "file_type",
            "confidentiality_level", "document_date", "author",
        ],
    })
    settings_result = client.wait_for_task(settings_task.task_uid, timeout_in_ms=10000)
    if settings_result.status != "succeeded":
        raise RuntimeError(f"Could not configure Meilisearch index: {settings_result.error}")

    _indexes[site] = (client, index)
    return index


def _build_documents(names) -> list[dict]:
    """Meilisearch payloads for `names`, using a handful of queries instead of one per document."""
    names = list(names)
    if not names:
        return []
    rows = frappe.get_all(
        "Archive Document",
        filters={"name": ["in", names]},
        fields=["name", "document_title", "document_number", "content_text", "author", "archival_file",
                "catalog", "record_group", "fonds", "file_type", "confidentiality_level",
                "storage_tier", "document_date", "modified", "creation"],
        limit_page_length=0,
    )
    file_names = {r.archival_file for r in rows if r.archival_file}
    files = {
        f.name: f for f in frappe.get_all(
            "Archival File", filters={"name": ["in", list(file_names)]},
            fields=["name", "file_title", "status", "disposal_status"], limit_page_length=0)
    } if file_names else {}
    fonds_ids = {r.fonds for r in rows if r.fonds}
    fonds = {
        f.name: f.fonds_name for f in frappe.get_all(
            "Fonds", filters={"name": ["in", list(fonds_ids)]}, fields=["name", "fonds_name"],
            limit_page_length=0)
    } if fonds_ids else {}
    levels = {
        l.name: l.priority for l in frappe.get_all(
            "Confidentiality Level", fields=["name", "priority"], limit_page_length=0)
    }

    documents = []
    for r in rows:
        parent = files.get(r.archival_file)
        level = r.confidentiality_level
        priority = levels.get(level) if level else None
        documents.append({
            "id": r.name,
            "document_title": r.document_title or "",
            "document_number": r.document_number or "",
            "content_text": (r.content_text or "")[:100000],  # Limit to 100K chars
            "author": r.author or "",
            "archival_file": r.archival_file or "",
            "archival_file_title": (parent.file_title if parent else "") or "",
            "catalog": r.catalog or "",
            "record_group": r.record_group or "",
            "fonds": r.fonds or "",
            "fonds_name": fonds.get(r.fonds, ""),
            "file_type": r.file_type or "",
            "confidentiality_level": level or "",
            "confidentiality_priority": int(priority) if priority else UNKNOWN_LEVEL_PRIORITY,
            "is_published": bool(parent and is_file_published(parent.status, parent.disposal_status)),
            "storage_tier": r.storage_tier or "Hot",
            "document_date": str(r.document_date) if r.document_date else "",
            "document_ts": calendar.timegm(r.document_date.timetuple()) if r.document_date else None,
            "modified": str(r.modified),
            "created": str(r.creation),
        })
    return documents


def index_documents(names):
    """Index several documents with one Meilisearch task; mark the failures."""
    documents = _build_documents(names)
    if not documents:
        return 0
    ids = [d["id"] for d in documents]
    try:
        index = _get_index()
        task = index.add_documents(documents)
        result = _get_client().wait_for_task(task.task_uid, timeout_in_ms=60000)
        if result.status != "succeeded":
            raise RuntimeError(f"Could not index documents: {result.error}")
    except Exception:
        frappe.db.sql(
            "update `tabArchive Document` set search_index_status=%s where name in %s",
            ("Lỗi", tuple(ids)),
        )
        frappe.db.commit()
        raise
    frappe.db.sql(
        "update `tabArchive Document` set search_index_status=%s where name in %s",
        ("Đã index", tuple(ids)),
    )
    frappe.db.commit()
    return len(documents)


def index_document(doc_name: str):
    """Index one document (raises on failure after recording the "Lỗi" state)."""
    return index_documents([doc_name])


def deindex_document(doc_name: str):
    """Remove a document from Meilisearch index (a failure is logged; reconcile retries it)."""
    try:
        _get_index().delete_document(doc_name)
    except Exception:
        log_exception("Search Index Error", f"Cannot remove {doc_name} from the search index")


def index_file_documents(file_name: str):
    """Re-index every document of an Archival File, in chunks."""
    names = frappe.get_all("Archive Document", filters={"archival_file": file_name}, pluck="name",
                           limit_page_length=0)
    for start in range(0, len(names), CHUNK):
        index_documents(names[start:start + CHUNK])


def reindex_all():
    """Queue a re-index of every document (after a schema/visibility change of the index)."""
    names = frappe.get_all("Archive Document", pluck="name", limit_page_length=0)
    for start in range(0, len(names), CHUNK):
        frappe.enqueue(
            "document_manager.document_manager.services.search_index.index_documents",
            names=names[start:start + CHUNK],
            queue="long",
            timeout=1800,
        )
    return len(names)


FILTERABLE_EQUALS = ("fonds", "record_group", "catalog", "archival_file", "file_type",
                     "confidentiality_level", "storage_tier")


def search(query: str, filters=None, date_from=None, date_to=None, sort_by=None, offset=0, limit=20,
           fonds=None, confidentiality_level=None, file_type=None) -> dict:
    """Search documents in Meilisearch.

    `filters` maps filterable attributes (FILTERABLE_EQUALS) to a value; `date_from` / `date_to` are
    epoch seconds bounding `document_ts`. `fonds`, `confidentiality_level`, `file_type` stay
    accepted for older callers. Returns the Meilisearch result dict (hits, estimatedTotalHits, ...).
    """
    index = _get_index()

    wanted = {"fonds": fonds, "confidentiality_level": confidentiality_level, "file_type": file_type,
              **(filters or {})}
    filter_parts = [
        f"{field} = {json.dumps(str(value), ensure_ascii=False)}"
        for field, value in wanted.items() if value and field in FILTERABLE_EQUALS
    ]
    if date_from is not None:
        filter_parts.append(f"document_ts >= {int(date_from)}")
    if date_to is not None:
        filter_parts.append(f"document_ts <= {int(date_to)}")

    # Readers: only published documents, up to their clearance, inside their fonds.
    scope = get_reader_scope()
    if not scope.is_staff:
        if not scope.allowed:
            return {"hits": [], "estimatedTotalHits": 0}
        filter_parts.append(f"confidentiality_priority <= {int(scope.max_priority)}")
        filter_parts.append("is_published = true")
        if scope.fonds is not None:
            quoted = ", ".join(json.dumps(f, ensure_ascii=False) for f in scope.fonds) or '""'
            filter_parts.append(f"fonds IN [{quoted}]")

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
# All jobs wait for the surrounding transaction to commit: a worker must never see a state the
# request has not committed yet.

def enqueue_index(doc, method=None):
    """Enqueue index job for an Archive Document (called on on_update)."""
    frappe.enqueue(
        "document_manager.document_manager.services.search_index.index_document",
        doc_name=doc.name,
        queue="short",
        at_front=True,
        enqueue_after_commit=True,
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
        enqueue_after_commit=True,
    )


INDEX_RELEVANT_FILE_FIELDS = (
    "file_title", "confidentiality_level", "status", "disposal_status", "fonds", "catalog", "record_group",
)


def enqueue_index_file(doc, method=None):
    """Re-index the documents of an Archival File when something the index shows changed."""
    if not doc.is_new() and not any(doc.has_value_changed(f) for f in INDEX_RELEVANT_FILE_FIELDS):
        return
    frappe.enqueue(
        "document_manager.document_manager.services.search_index.index_file_documents",
        file_name=doc.name,
        queue="long",
        timeout=1800,
        job_id=f"dm-reindex-file-{doc.name}",
        deduplicate=True,
        enqueue_after_commit=True,
    )


def enqueue_deindex_file(doc, method=None):
    """Deindex all documents under an Archival File when it's trashed."""
    names = frappe.get_all("Archive Document", filters={"archival_file": doc.name}, pluck="name",
                           limit_page_length=0)
    for name in names:
        frappe.enqueue(
            "document_manager.document_manager.services.search_index.deindex_document",
            doc_name=name,
            queue="short",
            enqueue_after_commit=True,
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
    db_ids = set(frappe.get_all("Archive Document", pluck="name", limit_page_length=0))

    # Documents in DB but not in index → index them (in chunks)
    missing = sorted(db_ids - indexed_ids)
    for start in range(0, len(missing), CHUNK):
        frappe.enqueue(
            "document_manager.document_manager.services.search_index.index_documents",
            names=missing[start:start + CHUNK],
            queue="long",
            timeout=1800,
        )

    # Documents in index but not in DB → deindex them
    orphaned = indexed_ids - db_ids
    for doc_name in orphaned:
        deindex_document(doc_name)

    frappe.logger().info(
        f"Reconciliation complete: {len(missing)} to index, {len(orphaned)} orphaned removed."
    )
