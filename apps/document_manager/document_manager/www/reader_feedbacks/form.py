import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
        
    docname = frappe.form_dict.get('name')
    doc = None
    
    user_roles = frappe.get_roles()
    is_officer = 'Reading Room Officer' in user_roles or 'Document Admin' in user_roles
    
    reader_profile = frappe.db.get_value('Reader', {'user': frappe.session.user}, 'name')
    
    if docname:
        if not frappe.db.exists('Reader Feedback', docname):
            frappe.throw(_('Không tìm thấy Phiếu góp ý này'), frappe.DoesNotExistError)
            
        doc = frappe.get_doc('Reader Feedback', docname)
        
        if not is_officer and doc.owner != frappe.session.user and doc.reader != reader_profile:
            frappe.throw(_('Bạn không có quyền xem Phiếu góp ý này'), frappe.PermissionError)
            
        context.page_title = f'Góp ý: {doc.subject}'
        
        # If officer views it for the first time, auto update status to 'Đã xem'
        if is_officer and doc.status == 'Mới':
            frappe.db.set_value('Reader Feedback', docname, 'status', 'Đã xem')
            frappe.db.commit()
            doc.status = 'Đã xem'
    else:
        if not frappe.has_permission('Reader Feedback', 'create'):
            frappe.throw(_('Bạn không có quyền tạo Phiếu góp ý mới'), frappe.PermissionError)
            
        context.page_title = 'Gửi Góp ý mới'
        
    readers_list = []
    if is_officer:
        readers_list = frappe.get_all('Reader', filters={'is_active': 1}, fields=['name', 'full_name'])
        
    context.update({
        'doc': doc,
        'docname': docname,
        'is_officer': is_officer,
        'reader_profile': reader_profile,
        'readers_list': readers_list,
        'page_icon': 'fa-commenting-o',
        'breadcrumbs': [
            {'label': 'Độc giả & Khai thác'},
            {'label': 'Phản hồi & Góp ý', 'link': '/reader_feedbacks'}
        ]
    })
    
    return context
