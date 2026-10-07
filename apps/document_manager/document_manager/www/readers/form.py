import frappe
from document_manager.document_manager.permissions import is_staff as _is_staff
from document_manager.document_manager.permissions import require_staff
from frappe import _

def get_context(context):
    require_staff('/readers/form')
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    if docname:
        if not frappe.db.exists('Reader', docname):
            frappe.throw(_('Không tìm thấy Độc giả này'), frappe.DoesNotExistError)
        doc = frappe.get_doc('Reader', docname)
        # Check permissions
        if not doc.has_permission('read'):
            frappe.throw(_('Bạn không có quyền xem Độc giả này'), frappe.PermissionError)
            
        context.page_title = f'Hồ sơ Độc giả: {doc.full_name}'
    else:
        # User must have create permission
        if not frappe.has_permission('Reader', 'create'):
            frappe.throw(_('Bạn không có quyền tạo Độc giả mới'), frappe.PermissionError)
            
        context.page_title = 'Thêm Độc giả mới'
    is_staff = _is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if is_staff else "templates/dm_portal_base.html"
    
    levels = frappe.get_all('Confidentiality Level', fields=['name', 'priority'], order_by='priority')
    groups = frappe.get_all('Reader Group', fields=['name', 'is_default'], order_by='group_name')
    # Group and clearance are permlevel-1 fields: only these roles may change them.
    can_set_access = bool({'Document Admin', 'System Manager'} & set(frappe.get_roles()))
    context.update({
        'levels': levels,
        'groups': groups,
        'can_set_access': can_set_access,
        'doc': doc,
        'docname': docname,
        'page_icon': 'fa-user',
        'breadcrumbs': [
            {'label': 'Độc giả & Khai thác'},
            {'label': 'Danh sách Độc giả', 'link': '/readers'}
        ]
    })
    
    return context
