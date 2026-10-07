import frappe


def execute():
    """Slips and feedback filed by readers had no reader name (the name is now set on save): fill it in."""
    for doctype in ("Usage Request", "Copy Request", "Reader Feedback"):
        for row in frappe.get_all(doctype, filters={"reader_name": ["in", ["", None]], "reader": ["is", "set"]},
                                  fields=["name", "reader"], limit_page_length=0):
            full_name = frappe.db.get_value("Reader", row.reader, "full_name")
            if full_name:
                frappe.db.set_value(doctype, row.name, "reader_name", full_name, update_modified=False)
