import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
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
    is_staff = any(r in user_roles for r in ('Document Admin', 'Cataloger', 'System Manager', 'Administrator', 'Reading Room Officer', 'Archivist'))
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
