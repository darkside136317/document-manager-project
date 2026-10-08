# -*- coding: utf-8 -*-
"""The two Script Reports of the old report pages are replaced by the report screens of the staff app."""

import frappe

LEGACY_REPORTS = ("Thong Ke Tai Lieu", "Thong Ke Khai Thac", "Thống kê Tài liệu", "Thống kê Khai thác")


def execute():
    for name in LEGACY_REPORTS:
        if frappe.db.exists("Report", name):
            frappe.delete_doc("Report", name, force=True, ignore_permissions=True)
