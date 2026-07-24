# -*- coding: utf-8 -*-
"""Thống kê Tài liệu — Script Report.

Thống kê hồ sơ/tài liệu theo phông lưu trữ, loại hình tài liệu, kho lưu trữ.
Hỗ trợ filter theo phông, loại hình, kho, và thời gian.
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
        {"label": "Phông lưu trữ", "fieldname": "fonds", "fieldtype": "Link", "options": "Fonds", "width": 200},
        {"label": "Tên phông", "fieldname": "fonds_name", "fieldtype": "Data", "width": 250},
        {"label": "Số hồ sơ", "fieldname": "file_count", "fieldtype": "Int", "width": 120},
        {"label": "Số văn bản", "fieldname": "doc_count", "fieldtype": "Int", "width": 120},
        {"label": "Loại hình tài liệu", "fieldname": "document_type_category", "fieldtype": "Link", "options": "Document Type Category", "width": 180},
        {"label": "Kho lưu trữ", "fieldname": "storage_warehouse", "fieldtype": "Link", "options": "Storage Warehouse", "width": 180},
    ]


def get_data(filters):
    conditions = ""
    values = {}
    if filters:
        if filters.get("fonds"):
            conditions += " AND af.fonds = %(fonds)s"
            values["fonds"] = filters["fonds"]
        if filters.get("document_type_category"):
            conditions += " AND af.document_type_category = %(doc_type)s"
            values["doc_type"] = filters["document_type_category"]
        if filters.get("storage_warehouse"):
            conditions += " AND af.storage_warehouse = %(warehouse)s"
            values["warehouse"] = filters["storage_warehouse"]

    data = frappe.db.sql(f"""
        SELECT
            af.fonds,
            f.fonds_name,
            COUNT(DISTINCT af.name) as file_count,
            COUNT(DISTINCT ad.name) as doc_count,
            af.document_type_category,
            af.storage_warehouse
        FROM `tabArchival File` af
        LEFT JOIN `tabFonds` f ON f.name = af.fonds
        LEFT JOIN `tabArchive Document` ad ON ad.archival_file = af.name
        WHERE 1=1 {conditions}
        GROUP BY af.fonds, af.document_type_category, af.storage_warehouse
        ORDER BY f.fonds_name
    """, values=values, as_dict=True)

    return data


def get_chart(data):
    if not data:
        return None

    # Aggregate by fonds
    fonds_map = {}
    for row in data:
        name = row.get("fonds_name") or row.get("fonds") or "Chưa phân loại"
        fonds_map[name] = fonds_map.get(name, 0) + (row.get("file_count") or 0)

    labels = list(fonds_map.keys())[:15]
    values = [fonds_map[l] for l in labels]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": "Số hồ sơ", "values": values}],
        },
        "type": "bar",
        "colors": ["#2b5797"],
    }
