import frappe


def execute():
    """Fill states on pre-Workflow records so every document has a valid Workflow State."""
    legacy = {0: "Nháp", 1: "Chờ duyệt", 2: "Từ chối"}
    for doctype in ("Usage Request", "Copy Request"):
        for docstatus, state in legacy.items():
            frappe.db.sql(
                f"update `tab{doctype}` set workflow_state=%s "
                "where docstatus=%s and (workflow_state is null or workflow_state='')",
                (state, docstatus),
            )
    frappe.db.sql("update `tabReader Feedback` set status='Mới' where status is null or status=''")
