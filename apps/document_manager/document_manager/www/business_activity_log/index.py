import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
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
