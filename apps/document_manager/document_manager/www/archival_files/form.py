import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    if not frappe.has_permission('Archival File', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    if docname:
        if not frappe.db.exists('Archival File', docname):
            frappe.throw(_('Không tìm thấy Hồ sơ này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Archival File', docname)
        context.page_title = f'Hồ sơ: {doc.file_title}'
    else:
        if not can_edit:
            frappe.throw(_('Bạn không có quyền tạo Hồ sơ mới'), frappe.PermissionError)
        context.page_title = 'Thêm Hồ sơ mới'
        
    catalogs = frappe.get_all('Catalog', fields=['name', 'catalog_title'])
    confidentiality_levels = frappe.get_all('Confidentiality Level', fields=['name'])
    warehouses = frappe.get_all('Storage Warehouse', fields=['name', 'warehouse_name'])
        
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'catalogs': catalogs,
        'confidentiality_levels': confidentiality_levels,
        'warehouses': warehouses,
        'page_icon': 'fa-folder-open-o',
        'breadcrumbs': [
            {'label': 'Hồ sơ & Tài liệu'},
            {'label': 'Hồ sơ lưu trữ', 'link': '/archival_files'}
        ]
    })
    
    return context
