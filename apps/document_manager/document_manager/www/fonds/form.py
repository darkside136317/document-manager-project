import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    if not frappe.has_permission('Fonds', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    if docname:
        if not frappe.db.exists('Fonds', docname):
            frappe.throw(_('Không tìm thấy Phông lưu trữ này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Fonds', docname)
        context.page_title = f'Phông: {doc.fonds_name}'
    else:
        if not can_edit:
            frappe.throw(_('Bạn không có quyền tạo Phông mới'), frappe.PermissionError)
        context.page_title = 'Thêm Phông lưu trữ mới'
        
    # Get options for select fields/links
    agencies = frappe.get_all('Archival Agency', fields=['name', 'agency_name'])
    doc_types = frappe.get_all('Document Type Category', fields=['name'])
    doc_groups = frappe.get_all('Document Group', fields=['name', 'group_name'])
    classifications = frappe.get_all('Classification Scheme', fields=['name', 'scheme_name'])
        
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'agencies': agencies,
        'doc_types': doc_types,
        'doc_groups': doc_groups,
        'classifications': classifications,
        'page_icon': 'fa-archive',
        'breadcrumbs': [
            {'label': 'Hồ sơ & Tài liệu'},
            {'label': 'Phông lưu trữ', 'link': '/fonds'}
        ]
    })
    
    return context
