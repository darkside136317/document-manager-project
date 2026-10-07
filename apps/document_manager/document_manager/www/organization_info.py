import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    if not frappe.has_permission('Organization Info', 'read'):
        frappe.throw(_('Bạn không có quyền xem trang này'), frappe.PermissionError)
    doc = frappe.get_single('Organization Info')
    can_edit = frappe.has_permission('Organization Info', 'write')
    
    context.update({
        'doc': doc,
        'can_edit': can_edit,
        'page_title': 'Thông tin Tổ chức',
        'page_icon': 'fa-building',
        'breadcrumbs': [
            {'label': 'Quản trị Hệ thống'}
        ]
    })
    
    return context
