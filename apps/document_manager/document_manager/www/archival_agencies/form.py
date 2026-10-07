import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe import _

def get_context(context):
    require_staff('/archival_agencies/form')
        
    if not frappe.has_permission('Archival Agency', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    if docname:
        if not frappe.db.exists('Archival Agency', docname):
            frappe.throw(_('Không tìm thấy Cơ quan lưu trữ này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Archival Agency', docname)
        context.page_title = f'Cơ quan: {doc.agency_name}'
    else:
        if not can_edit:
            frappe.throw(_('Bạn không có quyền tạo Cơ quan mới'), frappe.PermissionError)
        context.page_title = 'Thêm Cơ quan lưu trữ mới'
        
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'page_icon': 'fa-building',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'},
            {'label': 'Cơ quan lưu trữ', 'link': '/archival_agencies'}
        ]
    })
    
    return context
