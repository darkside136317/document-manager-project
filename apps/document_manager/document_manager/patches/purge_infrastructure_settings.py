import frappe

REMOVED = ("mongodb_atlas_uri", "mongodb_database", "mongodb_status", "meilisearch_host",
           "meilisearch_master_key", "meilisearch_status", "total_indexed")


def execute():
    """Connection settings moved out of the database (site_config / environment).

    Delete the stale values, including any password that was stored encrypted in `__Auth`.
    """
    frappe.db.delete("__Auth", {"doctype": "Document Manager Settings"})
    frappe.db.delete("Singles", {"doctype": "Document Manager Settings", "field": ["in", REMOVED]})
    frappe.db.delete("Singles", {"doctype": "Reader Settings", "field": "default_confidentiality_priority"})
