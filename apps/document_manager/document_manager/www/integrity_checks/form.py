import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    if not frappe.has_permission('Integrity Check', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Preservation Officer' in user_roles
    
    if docname:
        if not frappe.db.exists('Integrity Check', docname):
            frappe.throw(_('Không tìm thấy bản ghi này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Integrity Check', docname)
        context.page_title = f'Kiểm tra: {doc.name}'
    else:
        if not can_create:
            frappe.throw(_('Bạn không có quyền tạo Kiểm tra mới'), frappe.PermissionError)
        context.page_title = 'Chạy Kiểm tra toàn vẹn mới'
        
    context.update({
        'doc': doc,
        'docname': docname,
        'can_create': can_create,
        'page_icon': 'fa-shield',
        'breadcrumbs': [
            {'label': 'Kiểm tra & Báo cáo'},
            {'label': 'Kiểm tra toàn vẹn', 'link': '/integrity_checks'}
        ]
    })
    
    return context
