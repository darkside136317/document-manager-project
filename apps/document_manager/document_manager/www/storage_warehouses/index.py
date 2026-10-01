import frappe
from frappe.utils import cint

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
    if not frappe.has_permission('Storage Warehouse', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 50
    search_term = frappe.form_dict.get('search', '')
    type_filter = frappe.form_dict.get('type', '')
    agency_filter = frappe.form_dict.get('agency', '')
    
    filters = {}
    if search_term:
        filters['warehouse_name'] = ['like', f'%{search_term}%']
    if type_filter:
        filters['warehouse_type'] = type_filter
    if agency_filter:
        filters['archival_agency'] = agency_filter
        
    warehouses = frappe.get_all(
        'Storage Warehouse',
        filters=filters,
        fields=['name', 'warehouse_name', 'warehouse_code', 'warehouse_type', 'parent_warehouse', 'archival_agency', 'is_group'],
        start=start,
        page_length=limit,
        order_by='warehouse_name asc'
    )
    
    total_count = frappe.db.count('Storage Warehouse', filters=filters)
    
    agencies = frappe.get_all('Archival Agency', fields=['name', 'agency_name'])
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    context.update({
        'page_title': 'Kho lưu trữ',
        'page_icon': 'fa-database',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'}
        ],
        'warehouses': warehouses,
        'agencies': agencies,
        'search_term': search_term,
        'type_filter': type_filter,
        'agency_filter': agency_filter,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
