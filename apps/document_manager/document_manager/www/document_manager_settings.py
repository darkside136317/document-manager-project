import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    if not frappe.has_permission('Document Manager Settings', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    doc = frappe.get_single('Document Manager Settings')
    can_edit = frappe.has_permission('Document Manager Settings', 'write')
    
    context.update({
        'doc': doc,
        'can_edit': can_edit,
        'page_title': 'Thiết lập Hệ thống',
        'page_icon': 'fa-cogs',
        'breadcrumbs': [
            {'label': 'Quản trị Hệ thống'}
        ]
    })
    
    return context
