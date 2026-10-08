import frappe


def execute():
    """Existing sites: the composite indexes the duplicate-number integrity checks group on (a new site gets them from the
    DocTypes' on_doctype_update, which Frappe only runs when the DocType itself changes)."""
    frappe.db.add_index("Archive Document", ["archival_file", "document_number"], "archival_file_document_number")
    frappe.db.add_index("Archival File", ["catalog", "file_number"], "catalog_file_number")
