import frappe
from document_manager.document_manager.permissions import require_staff

def get_context(context):
    require_staff('/reports/thong_ke_khai_thac')
    if not frappe.has_permission('Usage Request', 'read'):
        frappe.throw('Bạn không có quyền truy cập', frappe.PermissionError)
    
    # Import the report logic directly since it's a python module
    from document_manager.document_manager.report.thong_ke_khai_thac.thong_ke_khai_thac import execute
    
    # Get filters from URL
    filters = {}
    if frappe.form_dict.get('from_date'):
        filters['from_date'] = frappe.form_dict.get('from_date')
    if frappe.form_dict.get('to_date'):
        filters['to_date'] = frappe.form_dict.get('to_date')
        
    columns, data, message, chart = execute(filters)
    
    # Extract total
    total_usage = sum([row.get('usage_count', 0) for row in data]) if data else 0
    total_copy = sum([row.get('copy_count', 0) for row in data]) if data else 0
    
    import json
    chart_json = json.dumps(chart) if chart else 'null'

    context.update({
        'page_title': 'Thống kê khai thác',
        'page_icon': 'fa-pie-chart',
        'breadcrumbs': [
            {'label': 'Thống kê & Báo cáo'}
        ],
        'columns': columns,
        'data': data,
        'chart_json': chart_json,
        'total_usage': total_usage,
        'total_copy': total_copy,
        'filters': filters
    })
    
    return context
