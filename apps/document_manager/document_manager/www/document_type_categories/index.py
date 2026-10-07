import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe.utils import cint

def get_context(context):
    require_staff('/document_type_categories')
    
    if not frappe.has_permission('Document Type Category', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 20
    search_term = frappe.form_dict.get('search', '')
    
    filters = {}
    if search_term:
        filters['type_name'] = ['like', f'%{search_term}%']
        
    categories = frappe.get_all(
        'Document Type Category',
        filters=filters,
        fields=['name', 'type_name', 'type_code', 'is_active'],
        start=start,
        page_length=limit,
        order_by='type_name asc'
    )
    
    total_count = frappe.db.count('Document Type Category', filters=filters)
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'page_title': 'Loại hình tài liệu',
        'page_icon': 'fa-tags',
        'breadcrumbs': [
            {'label': 'Danh mục dùng chung'}
        ],
        'categories': categories,
        'search_term': search_term,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
