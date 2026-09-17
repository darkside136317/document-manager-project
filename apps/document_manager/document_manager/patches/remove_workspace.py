import frappe

def execute():
    workspace_name = "Document Manager"
    
    if frappe.db.exists("Workspace", workspace_name):
        frappe.delete_doc("Workspace", workspace_name, force=1)
        frappe.db.commit()
