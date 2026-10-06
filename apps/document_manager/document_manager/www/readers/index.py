import frappe
from frappe.utils import cint

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
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
    
    user_roles = frappe.get_roles()
    is_staff = any(r in user_roles for r in ('Document Admin', 'Cataloger', 'System Manager', 'Administrator', 'Reading Room Officer', 'Archivist'))
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
