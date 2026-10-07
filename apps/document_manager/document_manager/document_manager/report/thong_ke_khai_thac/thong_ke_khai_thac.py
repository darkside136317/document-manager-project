# -*- coding: utf-8 -*-
"""Thống kê Khai thác — Script Report.

Thống kê phiếu yêu cầu sử dụng và sao chụp tài liệu theo tháng. Chỉ tính phiếu đã gửi
(docstatus = 1) và bỏ qua phiếu đã hủy; bộ lọc ngày áp dụng cho cả hai loại phiếu.
"""

import frappe

APPROVED = ("Đã duyệt", "Đã trả", "Đã hoàn thành")


def execute(filters=None):
    data = get_data(filters or {})
    return get_columns(), data, None, get_chart(data)


def get_columns():
    return [
        {"label": "Tháng", "fieldname": "month", "fieldtype": "Data", "width": 120},
        {"label": "Phiếu yêu cầu sử dụng", "fieldname": "usage_count", "fieldtype": "Int", "width": 180},
        {"label": "Phiếu sao chụp", "fieldname": "copy_count", "fieldtype": "Int", "width": 150},
        {"label": "Đã duyệt (SD)", "fieldname": "approved_usage", "fieldtype": "Int", "width": 140},
        {"label": "Đã duyệt (SC)", "fieldname": "approved_copy", "fieldtype": "Int", "width": 140},
        {"label": "Từ chối", "fieldname": "rejected", "fieldtype": "Int", "width": 100},
        {"label": "Số độc giả", "fieldname": "reader_count", "fieldtype": "Int", "width": 120},
    ]


def _per_month(table, filters):
    conditions, values = "", {"approved": APPROVED}
    if filters.get("from_date"):
        conditions += " AND request_date >= %(from_date)s"
        values["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conditions += " AND request_date <= %(to_date)s"
        values["to_date"] = filters["to_date"]
    rows = frappe.db.sql(f"""
        SELECT DATE_FORMAT(request_date, '%%Y-%%m') AS month,
               COUNT(*) AS total,
               SUM(workflow_state IN %(approved)s) AS approved,
               SUM(workflow_state = 'Từ chối') AS rejected
        FROM `tab{table}`
        WHERE docstatus = 1 AND workflow_state != 'Đã hủy' {conditions}
        GROUP BY month
    """, values=values, as_dict=True)
    readers = frappe.db.sql(f"""
        SELECT DATE_FORMAT(request_date, '%%Y-%%m') AS month, reader
        FROM `tab{table}`
        WHERE docstatus = 1 AND workflow_state != 'Đã hủy' {conditions}
    """, values=values, as_dict=True)
    return {r.month: r for r in rows}, readers


def get_data(filters):
    usage, usage_readers = _per_month("Usage Request", filters)
    copy, copy_readers = _per_month("Copy Request", filters)

    readers = {}
    for row in usage_readers + copy_readers:
        readers.setdefault(row.month, set()).add(row.reader)

    result = []
    for month in sorted(set(usage) | set(copy), reverse=True)[:24]:
        u, c = usage.get(month), copy.get(month)
        result.append({
            "month": month,
            "usage_count": int(u.total) if u else 0,
            "copy_count": int(c.total) if c else 0,
            "approved_usage": int(u.approved or 0) if u else 0,
            "approved_copy": int(c.approved or 0) if c else 0,
            "rejected": int((u.rejected or 0) if u else 0) + int((c.rejected or 0) if c else 0),
            "reader_count": len(readers.get(month, ())),
        })
    return result


def get_chart(data):
    if not data:
        return None
    rows = data[:12][::-1]
    return {
        "data": {
            "labels": [r["month"] for r in rows],
            "datasets": [
                {"name": "Phiếu sử dụng", "values": [r["usage_count"] for r in rows]},
                {"name": "Phiếu sao chụp", "values": [r["copy_count"] for r in rows]},
            ],
        },
        "type": "line",
        "colors": ["#2b5797", "#e67e22"],
    }
