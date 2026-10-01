import frappe
from frappe.utils import cint

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
    if not frappe.has_permission('Integrity Check', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 20
    status_filter = frappe.form_dict.get('status', '')
    
    filters = {}
    if status_filter:
        filters['status'] = status_filter
        
    checks = frappe.get_all(
        'Integrity Check',
        filters=filters,
        fields=['name', 'check_type', 'status', 'started_at', 'completed_at', 'total_checked', 'errors_found'],
        start=start,
        page_length=limit,
        order_by='creation desc'
    )
    
    total_count = frappe.db.count('Integrity Check', filters=filters)
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Preservation Officer' in user_roles
    
    context.update({
        'page_title': 'Kiểm tra toàn vẹn dữ liệu',
        'page_icon': 'fa-shield',
        'breadcrumbs': [
            {'label': 'Kiểm tra & Báo cáo'}
        ],
        'checks': checks,
        'status_filter': status_filter,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
