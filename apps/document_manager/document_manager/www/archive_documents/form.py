import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe import _

def get_context(context):
    require_staff('/archive_documents/form')
        
    if not frappe.has_permission('Archive Document', 'read'):
        frappe.throw(_('Bạn không có quyền truy cập trang này'), frappe.PermissionError)
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    can_edit = any(r in user_roles for r in ('Document Admin', 'Cataloger', 'System Manager', 'Administrator'))
    
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
    
    attachments = []
    if docname:
        attachments = frappe.get_all('File', filters={
            'attached_to_doctype': 'Archive Document',
            'attached_to_name': docname
        }, fields=['name', 'file_name', 'file_url'])
        
    user_roles = frappe.get_roles()
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    context.update({
        'doc': doc,
        'docname': docname,
        'can_edit': can_edit,
        'archival_files': archival_files,
        'attachments': attachments,
        'page_icon': 'fa-file-text-o',
        'breadcrumbs': [
            {'label': 'Hồ sơ & Tài liệu'},
            {'label': 'Văn bản / Tài liệu', 'link': '/archive_documents'}
        ]
    })
    
    return context
