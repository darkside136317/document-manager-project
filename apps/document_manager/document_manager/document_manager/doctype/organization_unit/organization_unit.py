# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class OrganizationUnit(NestedSet):
    """Phòng, ban, đơn vị trực thuộc — cây cơ cấu tổ chức hiển thị ở trang /co-cau."""

    nsm_parent_field = "parent_organization_unit"

    def validate(self):
        self.unit_name = (self.unit_name or "").strip()
        if self.parent_organization_unit and self.parent_organization_unit == self.name:
            frappe.throw(_("Đơn vị không thể là cấp trên của chính nó"))

    def on_update(self):
        super().on_update()  # keeps lft/rgt; throws when the parent is one of its own descendants
        parent = self.parent_organization_unit
        if parent and not frappe.db.get_value("Organization Unit", parent, "is_group"):
            frappe.db.set_value("Organization Unit", parent, "is_group", 1, update_modified=False)
        before = None if self.is_new() else self.get_doc_before_save()
        old = before.parent_organization_unit if before and before.parent_organization_unit != parent else None
        if old and not frappe.db.exists("Organization Unit", {"parent_organization_unit": old}):
            frappe.db.set_value("Organization Unit", old, "is_group", 0, update_modified=False)

    def after_delete(self):
        parent = self.parent_organization_unit
        if parent and not frappe.db.exists("Organization Unit", {"parent_organization_unit": parent}):
            frappe.db.set_value("Organization Unit", parent, "is_group", 0, update_modified=False)
