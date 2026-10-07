import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe import _

def get_context(context):
    require_staff('/storage_warehouses/form')
        
    if not frappe.has_permission('Storage Warehouse', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    if docname:
        if not frappe.db.exists('Storage Warehouse', docname):
            frappe.throw(_('Không tìm thấy Kho lưu trữ này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Storage Warehouse', docname)
        context.page_title = f'Kho lưu trữ: {doc.warehouse_name}'
    else:
        if not can_edit:
            frappe.throw(_('Bạn không có quyền tạo Kho lưu trữ mới'), frappe.PermissionError)
        context.page_title = 'Thêm Kho lưu trữ mới'
        
    parent_warehouses = frappe.get_all('Storage Warehouse', filters={'is_group': 1}, fields=['name', 'warehouse_name'])
    agencies = frappe.get_all('Archival Agency', fields=['name', 'agency_name'])
        
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'parent_warehouses': parent_warehouses,
        'agencies': agencies,
        'page_icon': 'fa-database',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'},
            {'label': 'Kho lưu trữ', 'link': '/storage_warehouses'}
        ]
    })
    
    return context
