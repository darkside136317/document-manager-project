import frappe


def execute():
    """`dictionary_type` was free text and the dictionary a flat table with a loose parent link.

    Create a Dictionary Type for every distinct value (hierarchical when any of its entries has a
    parent), mark the parents, and build the nested-set left/right values.
    """
    from frappe.utils.nestedset import rebuild_tree

    entries = frappe.get_all("Quick Entry Dictionary", fields=["dictionary_type", "parent_entry"],
                             limit_page_length=0)
    hierarchical = {e.dictionary_type for e in entries if e.parent_entry}
    for name in sorted({e.dictionary_type for e in entries if e.dictionary_type}):
        if not frappe.db.exists("Dictionary Type", name):
            frappe.get_doc({"doctype": "Dictionary Type", "type_name": name, "is_active": 1,
                            "is_hierarchical": 1 if name in hierarchical else 0}).insert(ignore_permissions=True)
    for parent in {e.parent_entry for e in entries if e.parent_entry}:
        frappe.db.set_value("Quick Entry Dictionary", parent, "is_group", 1, update_modified=False)
    rebuild_tree("Quick Entry Dictionary")
