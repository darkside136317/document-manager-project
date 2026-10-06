import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    if not frappe.has_permission('Restore Batch', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Preservation Officer' in user_roles
    
    if docname:
        if not frappe.db.exists('Restore Batch', docname):
            frappe.throw(_('Không tìm thấy bản ghi này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Restore Batch', docname)
        context.page_title = f'Phục hồi: {doc.name}'
    else:
        if not can_create:
            frappe.throw(_('Bạn không có quyền tạo bản phục hồi mới'), frappe.PermissionError)
        context.page_title = 'Khởi tạo Khôi phục dữ liệu'
        
    backups = frappe.get_all('Backup Batch', filters={'status': 'Thành công'}, fields=['name', 'backup_type'], order_by='creation desc')
        
    user_roles = frappe.get_roles()
    is_staff = any(r in user_roles for r in ('Document Admin', 'Cataloger', 'System Manager', 'Administrator', 'Reading Room Officer', 'Archivist'))
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'doc': doc,
        'docname': docname,
        'can_create': can_create,
        'backups': backups,
        'page_icon': 'fa-history',
        'breadcrumbs': [
            {'label': 'Kiểm tra & Báo cáo'},
            {'label': 'Khôi phục dữ liệu', 'link': '/restore_batches'}
        ]
    })
    
    return context
