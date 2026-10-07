import frappe

STAFF_ROLES = {
    "Document Admin", "Cataloger", "Reading Room Officer",
    "Preservation Officer", "System Manager", "Administrator",
}


def execute():
    """Reader-only accounts must be Website Users so they cannot open Desk (/app)."""
    for user in frappe.get_all("Has Role", filters={"role": "Reader", "parenttype": "User"}, pluck="parent"):
        roles = set(frappe.get_all("Has Role", filters={"parent": user, "parenttype": "User"}, pluck="role"))
        if roles & STAFF_ROLES or user in ("Administrator", "Guest"):
            continue
        frappe.db.set_value("User", user, "user_type", "Website User", update_modified=False)
