import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe import _

def get_context(context):
    require_staff('/business_activity_log')
        
    if not frappe.has_permission('Business Activity Log', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    # Get filters
    filters = {}
    if frappe.form_dict.get('activity_type'):
        filters['activity_type'] = frappe.form_dict.get('activity_type')
    if frappe.form_dict.get('reference_doctype'):
        filters['reference_doctype'] = frappe.form_dict.get('reference_doctype')
        
    # Get logs
    logs = frappe.get_all('Business Activity Log', 
        filters=filters,
        fields=['name', 'activity_type', 'reference_doctype', 'reference_name', 'user', 'ip_address', 'timestamp', 'description'],
        order_by='timestamp desc',
        limit=100
    )
    
    # Get options for filters
    activity_types = frappe.get_all('Business Activity Log', fields=['activity_type'], distinct=1)
    doctypes = frappe.get_all('Business Activity Log', fields=['reference_doctype'], distinct=1)
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'logs': logs,
        'filters': filters,
        'activity_types': [a.activity_type for a in activity_types if a.activity_type],
        'doctypes': [d.reference_doctype for d in doctypes if d.reference_doctype],
        'page_title': 'Nhật ký Nghiệp vụ',
        'page_icon': 'fa-history',
        'breadcrumbs': [
            {'label': 'Quản trị Hệ thống'}
        ]
    })
    
    return context
