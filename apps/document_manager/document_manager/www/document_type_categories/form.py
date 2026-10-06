import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    if not frappe.has_permission('Document Type Category', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    if docname:
        if not frappe.db.exists('Document Type Category', docname):
            frappe.throw(_('Không tìm thấy Loại hình tài liệu này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Document Type Category', docname)
        context.page_title = f'Loại hình: {doc.type_name}'
    else:
        if not can_edit:
            frappe.throw(_('Bạn không có quyền tạo Loại hình tài liệu mới'), frappe.PermissionError)
        context.page_title = 'Thêm Loại hình tài liệu mới'
        
    user_roles = frappe.get_roles()
    is_staff = any(r in user_roles for r in ('Document Admin', 'Cataloger', 'System Manager', 'Administrator', 'Reading Room Officer', 'Archivist'))
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'page_icon': 'fa-tags',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'},
            {'label': 'Loại hình tài liệu', 'link': '/document_type_categories'}
        ]
    })
    
    return context
