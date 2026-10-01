import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
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
