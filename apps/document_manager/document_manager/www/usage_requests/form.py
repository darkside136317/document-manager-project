import frappe
from frappe import _
import json

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    docname = frappe.form_dict.get('name')
    doc = None
    items = []
    
    # Check if user is a reader
    user_roles = frappe.get_roles()
    is_officer = 'Reading Room Officer' in user_roles or 'Document Admin' in user_roles
    
    reader_profile = frappe.db.get_value('Reader', {'user': frappe.session.user}, 'name')
    
    if docname:
        if not frappe.db.exists('Usage Request', docname):
            frappe.throw(_('Không tìm thấy Phiếu yêu cầu này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Usage Request', docname)
        
        # Access control
        if not is_officer and doc.owner != frappe.session.user and doc.reader != reader_profile:
            frappe.throw(_('Bạn không có quyền xem Phiếu yêu cầu này'), frappe.PermissionError)
            
        items = doc.get('items')
        context.page_title = f'Phiếu Yêu cầu Khai thác: {doc.name}'
    else:
        if not frappe.has_permission('Usage Request', 'create'):
            frappe.throw(_('Bạn không có quyền tạo Phiếu yêu cầu mới'), frappe.PermissionError)
            
        context.page_title = 'Tạo Phiếu Y/C Khai thác mới'
        
    # Get all active readers for dropdown if officer
    readers_list = []
    if is_officer:
        readers_list = frappe.get_all('Reader', filters={'is_active': 1}, fields=['name', 'full_name'])
        
    user_roles = frappe.get_roles()
    is_staff = any(r in user_roles for r in ('Document Admin', 'Cataloger', 'System Manager', 'Administrator', 'Reading Room Officer', 'Archivist'))
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'doc': doc,
        'docname': docname,
        'items': items,
        'is_officer': is_officer,
        'reader_profile': reader_profile,
        'readers_list': readers_list,
        'page_icon': 'fa-file-text-o',
        'breadcrumbs': [
            {'label': 'Độc giả & Khai thác'},
            {'label': 'Phiếu Y/C Khai thác', 'link': '/usage_requests'}
        ]
    })
    
    return context
