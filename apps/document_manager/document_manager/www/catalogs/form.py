import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe import _

def get_context(context):
    require_staff('/catalogs/form')
        
    if not frappe.has_permission('Catalog', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    if docname:
        if not frappe.db.exists('Catalog', docname):
            frappe.throw(_('Không tìm thấy Mục lục này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Catalog', docname)
        context.page_title = f'Mục lục: {doc.catalog_title}'
    else:
        if not can_edit:
            frappe.throw(_('Bạn không có quyền tạo Mục lục mới'), frappe.PermissionError)
        context.page_title = 'Thêm Mục lục mới'
        
    record_groups = frappe.get_all('Record Group', fields=['name', 'group_title', 'fonds'])
        
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'record_groups': record_groups,
        'page_icon': 'fa-book',
        'breadcrumbs': [
            {'label': 'Hồ sơ & Tài liệu'},
            {'label': 'Mục lục tài liệu', 'link': '/catalogs'}
        ]
    })
    
    return context
