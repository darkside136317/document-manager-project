# -*- coding: utf-8 -*-
"""Search portal page — public search interface for Readers."""
import frappe


def get_context(context):
    context.no_cache = 1
    context.title = "Tìm kiếm Tài liệu"
    context.fonds_list = frappe.get_all("Fonds", fields=["name", "fonds_name"], order_by="fonds_name")
    context.confidentiality_levels = frappe.get_all(
        "Confidentiality Level", fields=["name", "priority"], order_by="priority"
    )
