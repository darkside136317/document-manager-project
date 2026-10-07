import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe import _

def get_context(context):
    require_staff('/record_groups/form')
        
    if not frappe.has_permission('Record Group', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    if docname:
        if not frappe.db.exists('Record Group', docname):
            frappe.throw(_('Không tìm thấy Khối tài liệu này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Record Group', docname)
        context.page_title = f'Khối tài liệu: {doc.group_title}'
    else:
        if not can_edit:
            frappe.throw(_('Bạn không có quyền tạo Khối tài liệu mới'), frappe.PermissionError)
        context.page_title = 'Thêm Khối tài liệu mới'
        
    fonds_list = frappe.get_all('Fonds', fields=['name', 'fonds_name'])
        
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'fonds_list': fonds_list,
        'page_icon': 'fa-folder-open',
        'breadcrumbs': [
            {'label': 'Hồ sơ & Tài liệu'},
            {'label': 'Khối tài liệu', 'link': '/record_groups'}
        ]
    })
    
    return context
