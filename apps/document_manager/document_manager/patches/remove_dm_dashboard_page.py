import frappe

def execute():
    """Remove the Document Manager Dashboard Frappe Page."""
    if frappe.db.exists("Page", "dm-dashboard"):
        frappe.delete_doc("Page", "dm-dashboard", ignore_missing=True)
