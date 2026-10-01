import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
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
