import frappe
from frappe.utils import cint

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
    if not frappe.has_permission('Document Group', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 20
    search_term = frappe.form_dict.get('search', '')
    
    filters = {}
    if search_term:
        filters['group_name'] = ['like', f'%{search_term}%']
        
    groups = frappe.get_all(
        'Document Group',
        filters=filters,
        fields=['name', 'group_name', 'group_code', 'is_active'],
        start=start,
        page_length=limit,
        order_by='group_name asc'
    )
    
    total_count = frappe.db.count('Document Group', filters=filters)
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    context.update({
        'page_title': 'Nhóm tài liệu',
        'page_icon': 'fa-folder',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'}
        ],
        'groups': groups,
        'search_term': search_term,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
