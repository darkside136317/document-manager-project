import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe import _

def get_context(context):
    require_staff('/backup_batches/form')
        
    if not frappe.has_permission('Backup Batch', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Preservation Officer' in user_roles
    
    if docname:
        if not frappe.db.exists('Backup Batch', docname):
            frappe.throw(_('Không tìm thấy bản ghi này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Backup Batch', docname)
        context.page_title = f'Sao lưu: {doc.name}'
    else:
        if not can_create:
            frappe.throw(_('Bạn không có quyền tạo bản sao lưu mới'), frappe.PermissionError)
        context.page_title = 'Khởi tạo Sao lưu dữ liệu'
        
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'doc': doc,
        'docname': docname,
        'can_create': can_create,
        'page_icon': 'fa-database',
        'breadcrumbs': [
            {'label': 'Kiểm tra & Báo cáo'},
            {'label': 'Sao lưu dữ liệu', 'link': '/backup_batches'}
        ]
    })
    
    return context
