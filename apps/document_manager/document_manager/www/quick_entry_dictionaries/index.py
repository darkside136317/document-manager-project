import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe.utils import cint

def get_context(context):
    require_staff('/quick_entry_dictionaries')
    
    if not frappe.has_permission('Quick Entry Dictionary', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 50
    search_term = frappe.form_dict.get('search', '')
    type_filter = frappe.form_dict.get('type', '')
    
    filters = {}
    if search_term:
        filters['entry_value'] = ['like', f'%{search_term}%']
    if type_filter:
        filters['dictionary_type'] = type_filter
        
    dictionaries = frappe.get_all(
        'Quick Entry Dictionary',
        filters=filters,
        fields=['name', 'dictionary_type', 'entry_value', 'parent_entry', 'sort_order', 'is_active'],
        start=start,
        page_length=limit,
        order_by='dictionary_type asc, sort_order asc, entry_value asc'
    )
    
    total_count = frappe.db.count('Quick Entry Dictionary', filters=filters)
    
    # Get distinct types for filter
    types = frappe.db.sql('''SELECT DISTINCT dictionary_type FROM `tabQuick Entry Dictionary` WHERE dictionary_type IS NOT NULL AND dictionary_type != '' ORDER BY dictionary_type''', as_dict=1)
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'page_title': 'Từ điển nhập nhanh',
        'page_icon': 'fa-book',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'}
        ],
        'dictionaries': dictionaries,
        'types': types,
        'search_term': search_term,
        'type_filter': type_filter,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
