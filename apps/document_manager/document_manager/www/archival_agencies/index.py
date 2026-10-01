import frappe
from frappe.utils import cint

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
    if not frappe.has_permission('Archival Agency', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 20
    search_term = frappe.form_dict.get('search', '')
    
    filters = {}
    if search_term:
        filters['agency_name'] = ['like', f'%{search_term}%']
        
    agencies = frappe.get_all(
        'Archival Agency',
        filters=filters,
        fields=['name', 'agency_name', 'agency_code', 'agency_type', 'is_active', 'phone', 'email'],
        start=start,
        page_length=limit,
        order_by='agency_name asc'
    )
    
    total_count = frappe.db.count('Archival Agency', filters=filters)
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    context.update({
        'page_title': 'Cơ quan lưu trữ',
        'page_icon': 'fa-building',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'}
        ],
        'agencies': agencies,
        'search_term': search_term,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
