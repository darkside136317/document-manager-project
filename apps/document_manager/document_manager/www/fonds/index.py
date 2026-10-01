import frappe
from frappe.utils import cint

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
    # Readers should only view, not create/edit.
    # Actually, the user wants 'Phông lưu trữ' on the portal. Wait, typically Readers can view Fonds to find documents.
    # Let's get list for everyone who has read access.
    if not frappe.has_permission('Fonds', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
        
    start = cint(frappe.form_dict.get('start', 0))
    limit = 20
    search_term = frappe.form_dict.get('search', '')
    
    filters = {}
    if search_term:
        filters['fonds_name'] = ['like', f'%{search_term}%']
        
    fonds = frappe.get_all(
        'Fonds',
        filters=filters,
        fields=['name', 'fonds_code', 'fonds_name', 'archival_agency', 'start_year', 'end_year', 'status'],
        start=start,
        page_length=limit,
        order_by='fonds_code asc'
    )
    
    total_count = frappe.db.count('Fonds', filters=filters)
    
    user_roles = frappe.get_roles()
    can_create = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    context.update({
        'page_title': 'Danh mục Phông lưu trữ',
        'page_icon': 'fa-archive',
        'breadcrumbs': [
            {'label': 'Hồ sơ & Tài liệu'}
        ],
        'fonds': fonds,
        'search_term': search_term,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count,
        'can_create': can_create
    })
    
    return context
