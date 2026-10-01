import frappe
from frappe.utils import cint

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
    start = cint(frappe.form_dict.get('start', 0))
    limit = 20
    search_term = frappe.form_dict.get('search', '')
    status_filter = frappe.form_dict.get('status', '')
    
    filters = {}
    
    # If standard Reader user, only see their own requests.
    # We find their Reader profile.
    if 'Reading Room Officer' not in frappe.get_roles() and 'Document Admin' not in frappe.get_roles():
        reader = frappe.db.get_value('Reader', {'user': frappe.session.user}, 'name')
        if reader:
            filters['reader'] = reader
        else:
            # Not linked to any reader profile, show none
            filters['owner'] = frappe.session.user
            
    if search_term:
        filters['name'] = ['like', f'%{search_term}%']
        
    if status_filter:
        filters['workflow_state'] = status_filter
        
    requests = frappe.get_all(
        'Usage Request',
        filters=filters,
        fields=['name', 'reader_name', 'request_date', 'workflow_state', 'purpose', 'docstatus'],
        start=start,
        page_length=limit,
        order_by='modified desc'
    )
    
    total_count = frappe.db.count('Usage Request', filters=filters)
    
    context.update({
        'page_title': 'Danh sách Yêu cầu Khai thác',
        'page_icon': 'fa-check-square-o',
        'breadcrumbs': [
            {'label': 'Độc giả & Khai thác'}
        ],
        'requests': requests,
        'search_term': search_term,
        'status_filter': status_filter,
        'start': start,
        'limit': limit,
        'total_count': total_count,
        'has_more': (start + limit) < total_count
    })
    
    return context
