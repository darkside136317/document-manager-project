import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    if not frappe.has_permission('Quick Entry Dictionary', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    if docname:
        if not frappe.db.exists('Quick Entry Dictionary', docname):
            frappe.throw(_('Không tìm thấy từ khóa này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Quick Entry Dictionary', docname)
        context.page_title = f'Từ khóa: {doc.entry_value}'
    else:
        if not can_edit:
            frappe.throw(_('Bạn không có quyền tạo từ khóa mới'), frappe.PermissionError)
        context.page_title = 'Thêm Từ khóa mới'
        
    parent_entries = frappe.get_all('Quick Entry Dictionary', fields=['name', 'entry_value'])
        
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'parent_entries': parent_entries,
        'page_icon': 'fa-book',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'},
            {'label': 'Từ điển nhập nhanh', 'link': '/quick_entry_dictionaries'}
        ]
    })
    
    return context
