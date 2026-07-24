# -*- coding: utf-8 -*-
"""Thống kê Khai thác — Script Report.

Thống kê phiếu yêu cầu sử dụng và sao chụp tài liệu theo thời gian, độc giả, trạng thái.
"""

import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    return columns, data, None, chart


def get_columns():
    return [
        {"label": "Tháng", "fieldname": "month", "fieldtype": "Data", "width": 120},
        {"label": "Phiếu yêu cầu sử dụng", "fieldname": "usage_count", "fieldtype": "Int", "width": 180},
        {"label": "Phiếu sao chụp", "fieldname": "copy_count", "fieldtype": "Int", "width": 150},
        {"label": "Đã duyệt (SĐ)", "fieldname": "approved_usage", "fieldtype": "Int", "width": 140},
        {"label": "Đã duyệt (SC)", "fieldname": "approved_copy", "fieldtype": "Int", "width": 140},
        {"label": "Từ chối", "fieldname": "rejected", "fieldtype": "Int", "width": 100},
        {"label": "Số độc giả", "fieldname": "reader_count", "fieldtype": "Int", "width": 120},
    ]


def get_data(filters):
    conditions = ""
    values = {}
    if filters:
        if filters.get("from_date"):
            conditions += " AND ur.request_date >= %(from_date)s"
            values["from_date"] = filters["from_date"]
        if filters.get("to_date"):
            conditions += " AND ur.request_date <= %(to_date)s"
            values["to_date"] = filters["to_date"]

    usage_data = frappe.db.sql(f"""
        SELECT
            DATE_FORMAT(ur.request_date, '%%Y-%%m') as month,
            COUNT(*) as usage_count,
            SUM(CASE WHEN ur.workflow_state = 'Đã duyệt' OR ur.workflow_state = 'Đã trả' THEN 1 ELSE 0 END) as approved_usage,
            SUM(CASE WHEN ur.workflow_state = 'Từ chối' THEN 1 ELSE 0 END) as rejected,
            COUNT(DISTINCT ur.reader) as reader_count
        FROM `tabUsage Request` ur
        WHERE ur.docstatus = 1 {conditions}
        GROUP BY DATE_FORMAT(ur.request_date, '%%Y-%%m')
        ORDER BY month DESC
        LIMIT 24
    """, values=values, as_dict=True)

    copy_data = frappe.db.sql("""
        SELECT
            DATE_FORMAT(cr.request_date, '%%Y-%%m') as month,
            COUNT(*) as copy_count,
            SUM(CASE WHEN cr.workflow_state IN ('Đã duyệt', 'Đã hoàn thành') THEN 1 ELSE 0 END) as approved_copy
        FROM `tabCopy Request` cr
        WHERE cr.docstatus = 1
        GROUP BY DATE_FORMAT(cr.request_date, '%%Y-%%m')
    """, as_dict=True)

    copy_map = {r["month"]: r for r in copy_data}

    result = []
    for row in usage_data:
        m = row["month"]
        copy = copy_map.get(m, {})
        result.append({
            "month": m,
            "usage_count": row["usage_count"],
            "copy_count": copy.get("copy_count", 0),
            "approved_usage": row["approved_usage"],
            "approved_copy": copy.get("approved_copy", 0),
            "rejected": row["rejected"],
            "reader_count": row["reader_count"],
        })

    return result


def get_chart(data):
    if not data:
        return None
    labels = [r["month"] for r in data][:12]
    usage = [r["usage_count"] for r in data][:12]
    copies = [r["copy_count"] for r in data][:12]
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": "Phiếu sử dụng", "values": usage},
                {"name": "Phiếu sao chụp", "values": copies},
            ],
        },
        "type": "line",
        "colors": ["#2b5797", "#e67e22"],
    }
