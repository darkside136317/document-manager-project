import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    if not frappe.has_permission('Archive Document', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = 'Document Admin' in user_roles or 'Cataloger' in user_roles
    
    if docname:
        if not frappe.db.exists('Archive Document', docname):
            frappe.throw(_('Không tìm thấy Văn bản này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Archive Document', docname)
        context.page_title = f'Văn bản: {doc.document_title}'
    else:
        if not can_edit:
            frappe.throw(_('Bạn không có quyền tạo Văn bản mới'), frappe.PermissionError)
        context.page_title = 'Thêm Văn bản mới'
        
    archival_files = frappe.get_all('Archival File', fields=['name', 'file_title', 'catalog', 'record_group', 'fonds', 'confidentiality_level'])
        
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'archival_files': archival_files,
        'page_icon': 'fa-file-text-o',
        'breadcrumbs': [
            {'label': 'Hồ sơ & Tài liệu'},
            {'label': 'Văn bản / Tài liệu', 'link': '/archive_documents'}
        ]
    })
    
    return context
