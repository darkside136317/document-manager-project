# -*- coding: utf-8 -*-
"""Who may use a fonds (for the fonds screen): its mode and the reader groups and readers it is granted to."""

import frappe
from frappe import _

from document_manager.document_manager.permissions import is_staff
from document_manager.document_manager.services import fonds_access


@frappe.whitelist()
def who_may_use(fonds):
    if not is_staff():
        frappe.throw(_("Chỉ cán bộ mới dùng được chức năng này"), frappe.PermissionError)
    frappe.get_doc("Fonds", fonds).check_permission("read")
    if not (frappe.has_permission("Reader Group", "read") or frappe.has_permission("Reader", "read")):
        return {"fonds": fonds, "mode": frappe.db.get_value("Fonds", fonds, "access_mode"), "grants": None}
    return fonds_access.who_may_use(fonds)
