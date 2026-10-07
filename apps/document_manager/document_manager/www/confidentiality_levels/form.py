import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe import _

def get_context(context):
    require_staff('/confidentiality_levels/form')
        
    if not frappe.has_permission('Confidentiality Level', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = 'Document Admin' in user_roles
    
    if docname:
        if not frappe.db.exists('Confidentiality Level', docname):
            frappe.throw(_('Không tìm thấy Mức độ mật này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Confidentiality Level', docname)
        context.page_title = f'Mức độ mật: {doc.level_name}'
    else:
        if not can_edit:
            frappe.throw(_('Bạn không có quyền tạo Mức độ mật mới'), frappe.PermissionError)
        context.page_title = 'Thêm Mức độ mật mới'
        
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'page_icon': 'fa-lock',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'},
            {'label': 'Mức độ mật', 'link': '/confidentiality_levels'}
        ]
    })
    
    return context
