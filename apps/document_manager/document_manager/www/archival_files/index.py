import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe.utils import cint

def get_context(context):
    require_staff('/archival_files')
    
    if not frappe.has_permission('Archival File', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 20
    search_term = frappe.form_dict.get('search', '')
    catalog_filter = frappe.form_dict.get('catalog', '')
    status_filter = frappe.form_dict.get('status', '')
    
    filters = {}
    if search_term:
        filters['file_title'] = ['like', f'%{search_term}%']
    if catalog_filter:
        filters['catalog'] = catalog_filter
    if status_filter:
        filters['status'] = status_filter
        
    archival_files = frappe.get_all(
        'Archival File',
        filters=filters,
        fields=['name', 'file_number', 'file_title', 'catalog', 'status', 'confidentiality_level', 'start_date', 'end_date'],
        start=start,
        page_length=limit,
        order_by='modified desc'
    )
    
    total_count = frappe.db.count('Archival File', filters=filters)
    
    catalogs = frappe.get_all('Catalog', fields=['name', 'catalog_title'])
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'page_title': 'Hồ sơ lưu trữ',
        'page_icon': 'fa-folder-open-o',
        'breadcrumbs': [
            {'label': 'Hồ sơ & Tài liệu'}
        ],
        'archival_files': archival_files,
        'catalogs': catalogs,
        'search_term': search_term,
        'catalog_filter': catalog_filter,
        'status_filter': status_filter,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
