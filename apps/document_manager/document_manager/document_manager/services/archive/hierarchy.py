# -*- coding: utf-8 -*-
"""Rules of the five-level hierarchy: Fonds > Record Group > Catalog > Archival File > Archive Document.

Children keep a denormalised copy of where they sit (`fonds`, `record_group`, `catalog`, and the
document's `confidentiality_level`): the reader queries and the search index filter on these
columns. When a node is moved or re-classified, `propagate_location` updates everything below it in
the same transaction and queues the affected documents for re-indexing; otherwise readers would keep
seeing (or not seeing) documents according to the old position.
"""

import frappe

from document_manager.document_manager.services.archive.counters import refresh_fonds_file_count

CHUNK = 500


def _set(doctype: str, where: dict, values: dict) -> None:
    frappe.db.set_value(doctype, where, values, update_modified=False)


def reindex_documents(where: dict) -> None:
    """Queue (after commit) a search re-index of the documents matching `where`."""
    names = frappe.get_all("Archive Document", filters=where, pluck="name", limit_page_length=0)
    for start in range(0, len(names), CHUNK):
        frappe.enqueue(
            "document_manager.document_manager.services.search_index.index_documents",
            names=names[start:start + CHUNK], queue="long", timeout=1800, enqueue_after_commit=True,
        )


def propagate_location(doc, before) -> None:
    """Copy a changed position of `doc` (Record Group / Catalog / Archival File) to its descendants."""
    if not before:
        return
    if doc.doctype == "Record Group":
        if before.fonds == doc.fonds:
            return
        for doctype in ("Catalog", "Archival File", "Archive Document"):
            _set(doctype, {"record_group": doc.name}, {"fonds": doc.fonds})
        reindex_documents({"record_group": doc.name})
    elif doc.doctype == "Catalog":
        if (before.record_group, before.fonds) == (doc.record_group, doc.fonds):
            return
        values = {"record_group": doc.record_group, "fonds": doc.fonds}
        for doctype in ("Archival File", "Archive Document"):
            _set(doctype, {"catalog": doc.name}, values)
        reindex_documents({"catalog": doc.name})
    elif doc.doctype == "Archival File":
        # The file's own re-index is queued by the Archival File hook (search_index.enqueue_index_file).
        if (before.catalog, before.record_group, before.fonds) != (doc.catalog, doc.record_group, doc.fonds):
            _set("Archive Document", {"archival_file": doc.name},
                 {"catalog": doc.catalog, "record_group": doc.record_group, "fonds": doc.fonds})
        if before.confidentiality_level != doc.confidentiality_level:
            _set("Archive Document", {"archival_file": doc.name},
                 {"confidentiality_level": doc.confidentiality_level})
    else:
        return
    for fonds in {before.get("fonds"), doc.get("fonds")}:
        refresh_fonds_file_count(fonds)
