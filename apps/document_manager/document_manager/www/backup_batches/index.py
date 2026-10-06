import frappe
from frappe.utils import cint

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
    if not frappe.has_permission('Backup Batch', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 20
    status_filter = frappe.form_dict.get('status', '')
    
    filters = {}
    if status_filter:
        filters['status'] = status_filter
        
    backups = frappe.get_all(
        'Backup Batch',
        filters=filters,
        fields=['name', 'backup_type', 'status', 'started_at', 'completed_at', 'backup_size_mb', 'initiated_by'],
        start=start,
        page_length=limit,
        order_by='creation desc'
    )
    
    total_count = frappe.db.count('Backup Batch', filters=filters)
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Preservation Officer' in user_roles
    
    user_roles = frappe.get_roles()
    is_staff = any(r in user_roles for r in ('Document Admin', 'Cataloger', 'System Manager', 'Administrator', 'Reading Room Officer', 'Archivist'))
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'page_title': 'Sao lưu dữ liệu',
        'page_icon': 'fa-database',
        'breadcrumbs': [
            {'label': 'Kiểm tra & Báo cáo'}
        ],
        'backups': backups,
        'status_filter': status_filter,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
