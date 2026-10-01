import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
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
