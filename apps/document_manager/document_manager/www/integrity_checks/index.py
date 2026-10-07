import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe.utils import cint

def get_context(context):
    require_staff('/integrity_checks')
    
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
    
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
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
