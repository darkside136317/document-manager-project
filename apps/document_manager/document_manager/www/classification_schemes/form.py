import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe import _

def get_context(context):
    require_staff('/classification_schemes/form')
        
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
        
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
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
