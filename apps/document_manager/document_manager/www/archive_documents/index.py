import frappe
from frappe.utils import cint

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
    if not frappe.has_permission('Archive Document', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 20
    search_term = frappe.form_dict.get('search', '')
    archival_file_filter = frappe.form_dict.get('archival_file', '')
    file_type_filter = frappe.form_dict.get('file_type', '')
    
    filters = {}
    if search_term:
        filters['document_title'] = ['like', f'%{search_term}%']
    if archival_file_filter:
        filters['archival_file'] = archival_file_filter
    if file_type_filter:
        filters['file_type'] = file_type_filter
        
    documents = frappe.get_all(
        'Archive Document',
        filters=filters,
        fields=['name', 'document_title', 'document_number', 'archival_file', 'file_type', 'confidentiality_level', 'document_date'],
        start=start,
        page_length=limit,
        order_by='modified desc'
    )
    
    total_count = frappe.db.count('Archive Document', filters=filters)
    
    archival_files = frappe.get_all('Archival File', fields=['name', 'file_title'])
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    user_roles = frappe.get_roles()
    is_staff = any(r in user_roles for r in ('Document Admin', 'Cataloger', 'System Manager', 'Administrator', 'Reading Room Officer', 'Archivist'))
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'page_title': 'Văn bản / Tài liệu',
        'page_icon': 'fa-file-text-o',
        'breadcrumbs': [
            {'label': 'Hồ sơ & Tài liệu'}
        ],
        'documents': documents,
        'archival_files': archival_files,
        'search_term': search_term,
        'archival_file_filter': archival_file_filter,
        'file_type_filter': file_type_filter,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
