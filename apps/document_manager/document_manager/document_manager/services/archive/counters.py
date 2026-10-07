# -*- coding: utf-8 -*-
"""Denormalised counters of the archive hierarchy.

Every counter is *recomputed* from the child table (never incremented/decremented), so it stays
correct after deletes, moves between parents and failed saves. Call these after the change is
applied (`on_update` / `after_delete`), for the current parent and, when a record moved, the old one.
"""

import frappe


def refresh_file_document_count(file_name: str | None) -> None:
    """Archival File.total_documents = number of Archive Documents inside it."""
    if not file_name or not frappe.db.exists("Archival File", file_name):
        return
    count = frappe.db.count("Archive Document", {"archival_file": file_name})
    if frappe.db.get_value("Archival File", file_name, "total_documents") != count:
        frappe.db.set_value("Archival File", file_name, "total_documents", count, update_modified=False)


def refresh_fonds_file_count(fonds_name: str | None) -> None:
    """Fonds.total_files = number of Archival Files inside it."""
    if not fonds_name or not frappe.db.exists("Fonds", fonds_name):
        return
    count = frappe.db.count("Archival File", {"fonds": fonds_name})
    if frappe.db.get_value("Fonds", fonds_name, "total_files") != count:
        frappe.db.set_value("Fonds", fonds_name, "total_files", count, update_modified=False)
