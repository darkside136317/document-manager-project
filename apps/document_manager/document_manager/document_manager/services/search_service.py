# -*- coding: utf-8 -*-
"""Search for archival files (hồ sơ) and documents (văn bản), basic and advanced.

One service behind every UI (reader portal, staff dashboard, API):

* files    — always MariaDB (metadata);
* documents — Meilisearch when there is a free-text query that the engine can answer (title,
  number, author, extracted content, plus equality / date filters), otherwise MariaDB. When
  Meilisearch is down the query silently falls back to MariaDB metadata search, so a search
  engine outage never blanks the portal.

Every MariaDB query goes through `frappe.get_list`, i.e. through the permission query conditions
(confidentiality, fonds scope, published state), and the Meilisearch filter is built from the
same `policy.get_reader_scope`: both engines show a reader exactly the same set. Extracted text
(`content_text`) is never returned, only the short cropped snippet of a hit.
"""

import calendar

import frappe
from frappe.utils import cint, getdate

from document_manager.document_manager.services import search_index
from document_manager.document_manager.services.errors import log_exception

MAX_PAGE_SIZE = 100

FILE_FIELDS = [
    "name", "file_title", "file_number", "fonds", "record_group", "catalog", "confidentiality_level",
    "storage_warehouse", "status", "start_date", "end_date", "total_pages", "total_documents",
]
DOCUMENT_FIELDS = [
    "name", "document_title", "document_number", "author", "archival_file", "fonds", "record_group", "catalog",
    "file_type", "confidentiality_level", "storage_tier", "search_index_status", "document_date",
]
FILE_SORTS = {
    "newest": "start_date desc", "oldest": "start_date asc", "title": "file_title asc", "modified": "modified desc",
}
DOCUMENT_SORTS = {
    "newest": "document_date desc", "oldest": "document_date asc", "title": "document_title asc",
    "modified": "modified desc",
}
# Filters answered by equality in both engines.
DOCUMENT_EQUALS = ("archival_file", "fonds", "record_group", "catalog", "file_type", "confidentiality_level",
                   "storage_tier")
# Filters that need a substring match: only MariaDB can answer them.
DOCUMENT_LIKES = ("document_title", "document_number", "author")


def _paging(page, page_size) -> tuple[int, int]:
    return max(1, cint(page) or 1), min(MAX_PAGE_SIZE, max(1, cint(page_size) or 20))


def _clean(params: dict) -> dict:
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in params.items() if v not in (None, "")}


def _count(doctype: str, filters, or_filters=None) -> int:
    rows = frappe.get_list(doctype, filters=filters, or_filters=or_filters, fields=[{"COUNT": "name", "as": "c"}])
    return rows[0].c if rows else 0


# ---------------------------------------------------------------------------
# Archival files
# ---------------------------------------------------------------------------

def search_files(params: dict, page=1, page_size=20) -> dict:
    """Basic (`query`) and advanced (any other key) search of archival files."""
    params = _clean(params)
    page, page_size = _paging(page, page_size)
    filters = [["Archival File", f, "=", params[f]] for f in (
        "fonds", "record_group", "catalog", "confidentiality_level", "storage_warehouse",
        "document_type_category", "status") if f in params]
    if "file_title" in params:
        filters.append(["Archival File", "file_title", "like", f"%{params['file_title']}%"])
    if "file_number" in params:
        filters.append(["Archival File", "file_number", "like", f"%{params['file_number']}%"])
    if "start_date_from" in params:
        filters.append(["Archival File", "start_date", ">=", getdate(params["start_date_from"])])
    if "start_date_to" in params:
        filters.append(["Archival File", "start_date", "<=", getdate(params["start_date_to"])])
    or_filters = None
    if "query" in params:
        like = f"%{params['query']}%"
        or_filters = [["Archival File", f, "like", like] for f in ("file_title", "file_number", "name")]

    data = frappe.get_list(
        "Archival File", filters=filters, or_filters=or_filters, fields=FILE_FIELDS,
        order_by=FILE_SORTS.get(params.get("sort_by"), FILE_SORTS["modified"]),
        start=(page - 1) * page_size, page_length=page_size,
    )
    return {"data": data, "total": _count("Archival File", filters, or_filters), "page": page,
            "page_size": page_size, "engine": "database"}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def search_documents(params: dict, page=1, page_size=20) -> dict:
    """Basic (`query`) and advanced search of documents; see the module docstring for the engines."""
    params = _clean(params)
    page, page_size = _paging(page, page_size)
    use_meili = "query" in params and not any(k in params for k in DOCUMENT_LIKES)
    if use_meili:
        try:
            return _search_documents_meili(params, page, page_size)
        except frappe.PermissionError:
            raise
        except Exception:
            log_exception("Full-text Search Error", "Meilisearch query failed; using the database search")
    return _search_documents_db(params, page, page_size)


def _document_filters(params: dict) -> list:
    filters = [["Archive Document", f, "=", params[f]] for f in DOCUMENT_EQUALS if f in params]
    filters += [["Archive Document", f, "like", f"%{params[f]}%"] for f in DOCUMENT_LIKES if f in params]
    if "date_from" in params:
        filters.append(["Archive Document", "document_date", ">=", getdate(params["date_from"])])
    if "date_to" in params:
        filters.append(["Archive Document", "document_date", "<=", getdate(params["date_to"])])
    return filters


def _search_documents_db(params: dict, page: int, page_size: int) -> dict:
    filters = _document_filters(params)
    or_filters = None
    if "query" in params:
        like = f"%{params['query']}%"
        or_filters = [["Archive Document", f, "like", like]
                      for f in ("document_title", "document_number", "author", "name")]
    rows = frappe.get_list(
        "Archive Document", filters=filters, or_filters=or_filters, fields=DOCUMENT_FIELDS,
        order_by=DOCUMENT_SORTS.get(params.get("sort_by"), DOCUMENT_SORTS["modified"]),
        start=(page - 1) * page_size, page_length=page_size,
    )
    data = [{**row, "id": row.name, "_formatted": {}} for row in rows]
    return {"data": data, "total": _count("Archive Document", filters, or_filters), "page": page,
            "page_size": page_size, "query": params.get("query", ""), "engine": "database"}


def _to_timestamp(value, end_of_day=False) -> int:
    ts = calendar.timegm(getdate(value).timetuple())
    return ts + 86399 if end_of_day else ts


def _search_documents_meili(params: dict, page: int, page_size: int) -> dict:
    result = search_index.search(
        query=params["query"],
        filters={f: params[f] for f in DOCUMENT_EQUALS if f in params},
        date_from=_to_timestamp(params["date_from"]) if "date_from" in params else None,
        date_to=_to_timestamp(params["date_to"], end_of_day=True) if "date_to" in params else None,
        sort_by=params.get("sort_by"),
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    data = []
    for hit in result.get("hits", []):
        row = {k: v for k, v in hit.items() if k != "content_text"}  # never ship the extracted text
        row.setdefault("name", row.get("id"))
        data.append(row)
    return {"data": data, "total": result.get("estimatedTotalHits", 0), "page": page, "page_size": page_size,
            "query": params["query"], "engine": "meilisearch"}
