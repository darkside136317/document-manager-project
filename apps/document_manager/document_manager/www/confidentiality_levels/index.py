import frappe
from frappe.utils import cint

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
    if not frappe.has_permission('Confidentiality Level', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 20
    search_term = frappe.form_dict.get('search', '')
    
    filters = {}
    if search_term:
        filters['level_name'] = ['like', f'%{search_term}%']
        
    levels = frappe.get_all(
        'Confidentiality Level',
        filters=filters,
        fields=['name', 'level_name', 'level_code', 'priority'],
        start=start,
        page_length=limit,
        order_by='priority asc, level_name asc'
    )
    
    total_count = frappe.db.count('Confidentiality Level', filters=filters)
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles
    
    user_roles = frappe.get_roles()
    is_staff = any(r in user_roles for r in ('Document Admin', 'Cataloger', 'System Manager', 'Administrator', 'Reading Room Officer', 'Archivist'))
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'page_title': 'Mức độ mật',
        'page_icon': 'fa-lock',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'}
        ],
        'levels': levels,
        'search_term': search_term,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
