import frappe
from frappe.utils import cint

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
    if not frappe.has_permission('Catalog', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 20
    search_term = frappe.form_dict.get('search', '')
    fonds_filter = frappe.form_dict.get('fonds', '')
    record_group_filter = frappe.form_dict.get('record_group', '')
    
    filters = {}
    if search_term:
        filters['catalog_title'] = ['like', f'%{search_term}%']
    if fonds_filter:
        filters['fonds'] = fonds_filter
    if record_group_filter:
        filters['record_group'] = record_group_filter
        
    catalogs = frappe.get_all(
        'Catalog',
        filters=filters,
        fields=['name', 'catalog_number', 'catalog_title', 'record_group', 'fonds', 'start_year', 'end_year'],
        start=start,
        page_length=limit,
        order_by='modified desc'
    )
    
    total_count = frappe.db.count('Catalog', filters=filters)
    
    # Options for filters
    fonds_list = frappe.get_all('Fonds', fields=['name', 'fonds_name'])
    rg_filters = {}
    if fonds_filter:
        rg_filters['fonds'] = fonds_filter
    record_groups = frappe.get_all('Record Group', filters=rg_filters, fields=['name', 'group_title'])
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    user_roles = frappe.get_roles()
    is_staff = any(r in user_roles for r in ('Document Admin', 'Cataloger', 'System Manager', 'Administrator', 'Reading Room Officer', 'Archivist'))
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'page_title': 'Mục lục tài liệu',
        'page_icon': 'fa-book',
        'breadcrumbs': [
            {'label': 'Hồ sơ & Tài liệu'}
        ],
        'catalogs': catalogs,
        'fonds_list': fonds_list,
        'record_groups': record_groups,
        'search_term': search_term,
        'fonds_filter': fonds_filter,
        'record_group_filter': record_group_filter,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
