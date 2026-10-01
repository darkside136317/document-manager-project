import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    if not frappe.has_permission('Classification Scheme', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    if docname:
        if not frappe.db.exists('Classification Scheme', docname):
            frappe.throw(_('Không tìm thấy Khung phân loại này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Classification Scheme', docname)
        context.page_title = f'Khung phân loại: {doc.scheme_name}'
    else:
        if not can_edit:
            frappe.throw(_('Bạn không có quyền tạo Khung phân loại mới'), frappe.PermissionError)
        context.page_title = 'Thêm Khung phân loại mới'
        
    parent_schemes = frappe.get_all('Classification Scheme', filters={'is_group': 1}, fields=['name', 'scheme_name'])
        
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'parent_schemes': parent_schemes,
        'page_icon': 'fa-sitemap',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'},
            {'label': 'Khung phân loại', 'link': '/classification_schemes'}
        ]
    })
    
    return context
