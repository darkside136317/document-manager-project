import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe import _

def get_context(context):
    require_staff('/document_groups/form')
        
    if not frappe.has_permission('Document Group', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    if docname:
        if not frappe.db.exists('Document Group', docname):
            frappe.throw(_('Không tìm thấy Nhóm tài liệu này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Document Group', docname)
        context.page_title = f'Nhóm tài liệu: {doc.group_name}'
    else:
        if not can_edit:
            frappe.throw(_('Bạn không có quyền tạo Nhóm tài liệu mới'), frappe.PermissionError)
        context.page_title = 'Thêm Nhóm tài liệu mới'
        
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'page_icon': 'fa-folder',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'},
            {'label': 'Nhóm tài liệu', 'link': '/document_groups'}
        ]
    })
    
    return context
