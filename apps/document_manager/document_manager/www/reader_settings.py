import frappe
from document_manager.document_manager.permissions import require_staff
from frappe import _

def get_context(context):
    require_staff('/reader_settings')
        
    if not frappe.has_permission('Reader Settings', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    doc = frappe.get_single('Reader Settings')
    can_edit = frappe.has_permission('Reader Settings', 'write')
    
    context.update({
        'doc': doc,
        'can_edit': can_edit,
        'page_title': 'Thiết lập Độc giả',
        'page_icon': 'fa-users',
        'breadcrumbs': [
            {'label': 'Quản trị Hệ thống'}
        ]
    })
    
    return context
