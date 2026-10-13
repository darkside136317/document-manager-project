import frappe

from document_manager.document_manager.setup.install import ensure_staff_role_profiles


def execute():
    """Existing sites: every staff role becomes a permission group, and the administrators' group gets its new name."""
    ensure_staff_role_profiles()
    if frappe.db.get_value("Staff Role Profile", "Document Admin", "label") == "Quản trị tài liệu":
        frappe.db.set_value("Staff Role Profile", "Document Admin", "label", "Quản trị viên", update_modified=False)
