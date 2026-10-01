import frappe

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect
    
    # Import the report logic directly since it's a python module
    from document_manager.document_manager.report.thong_ke_tai_lieu.thong_ke_tai_lieu import execute
    
    # Get filters from URL
    filters = {}
    if frappe.form_dict.get('fonds'):
        filters['fonds'] = frappe.form_dict.get('fonds')
    if frappe.form_dict.get('document_type_category'):
        filters['document_type_category'] = frappe.form_dict.get('document_type_category')
    if frappe.form_dict.get('storage_warehouse'):
        filters['storage_warehouse'] = frappe.form_dict.get('storage_warehouse')
        
    columns, data, message, chart = execute(filters)
    
    # Get options for filters
    fonds_options = frappe.get_all('Fonds', fields=['name', 'fonds_name'], order_by='fonds_name asc')
    doc_type_options = frappe.get_all('Document Type Category', fields=['name', 'type_name'], order_by='type_name asc')
    warehouse_options = frappe.get_all('Storage Warehouse', fields=['name', 'warehouse_name'], order_by='warehouse_name asc')
    
    # Extract total
    total_files = sum([row.get('file_count', 0) for row in data]) if data else 0
    total_docs = sum([row.get('doc_count', 0) for row in data]) if data else 0
    
    import json
    chart_json = json.dumps(chart) if chart else 'null'

    context.update({
        'page_title': 'Thống kê tài liệu',
        'page_icon': 'fa-bar-chart',
        'breadcrumbs': [
            {'label': 'Thống kê & Báo cáo'}
        ],
        'columns': columns,
        'data': data,
        'chart_json': chart_json,
        'total_files': total_files,
        'total_docs': total_docs,
        'fonds_options': fonds_options,
        'doc_type_options': doc_type_options,
        'warehouse_options': warehouse_options,
        'filters': filters
    })
    
    return context
