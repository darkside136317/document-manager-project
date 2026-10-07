import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe.utils import cint

def get_context(context):
    require_staff('/readers')
    if not frappe.has_permission('Reader', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
    
    # Pagination & Search
    start = cint(frappe.form_dict.get('start', 0))
    limit = 20
    search_term = frappe.form_dict.get('search', '')
    
    # Base query filters
    filters = {}
    if search_term:
        filters['full_name'] = ['like', f'%{search_term}%']
        # Note: Frappe ORM doesn't easily do OR across multiple fields in get_all without frappe.db.sql
        # For simplicity, we just search full_name here.
        
    readers = frappe.get_all(
        'Reader',
        filters=filters,
        fields=['name', 'full_name', 'email', 'phone', 'organization', 'is_active', 'registration_date'],
        start=start,
        page_length=limit,
        order_by='modified desc'
    )
    
    total_count = frappe.db.count('Reader', filters=filters)
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'page_title': 'Danh sách Hồ sơ Độc giả',
        'page_icon': 'fa-users',
        'breadcrumbs': [
            {'label': 'Độc giả & Khai thác'}
        ],
        'readers': readers,
        'search_term': search_term,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count
    })
    
    return context
