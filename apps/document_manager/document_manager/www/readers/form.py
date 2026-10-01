import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    if docname:
        if not frappe.db.exists('Reader', docname):
            frappe.throw(_('Không tìm thấy Độc giả này'), frappe.DoesNotExistError)
        doc = frappe.get_doc('Reader', docname)
        # Check permissions
        if not doc.has_permission('read'):
            frappe.throw(_('Bạn không có quyền xem Độc giả này'), frappe.PermissionError)
            
        context.page_title = f'Hồ sơ Độc giả: {doc.full_name}'
    else:
        # User must have create permission
        if not frappe.has_permission('Reader', 'create'):
            frappe.throw(_('Bạn không có quyền tạo Độc giả mới'), frappe.PermissionError)
            
        context.page_title = 'Thêm Độc giả mới'
        
    context.update({
        'doc': doc,
        'docname': docname,
        'page_icon': 'fa-user',
        'breadcrumbs': [
            {'label': 'Độc giả & Khai thác'},
            {'label': 'Danh sách Độc giả', 'link': '/readers'}
        ]
    })
    
    return context
