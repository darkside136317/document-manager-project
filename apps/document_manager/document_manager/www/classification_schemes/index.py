import frappe
from frappe.utils import cint

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
    if not frappe.has_permission('Classification Scheme', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 50
    search_term = frappe.form_dict.get('search', '')
    
    filters = {}
    if search_term:
        filters['scheme_name'] = ['like', f'%{search_term}%']
        
    schemes = frappe.get_all(
        'Classification Scheme',
        filters=filters,
        fields=['name', 'scheme_name', 'scheme_code', 'parent_scheme', 'is_group'],
        start=start,
        page_length=limit,
        order_by='scheme_name asc'
    )
    
    total_count = frappe.db.count('Classification Scheme', filters=filters)
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    user_roles = frappe.get_roles()
    is_staff = any(r in user_roles for r in ('Document Admin', 'Cataloger', 'System Manager', 'Administrator', 'Reading Room Officer', 'Archivist'))
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'page_title': 'Khung phân loại',
        'page_icon': 'fa-sitemap',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'}
        ],
        'schemes': schemes,
        'search_term': search_term,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
