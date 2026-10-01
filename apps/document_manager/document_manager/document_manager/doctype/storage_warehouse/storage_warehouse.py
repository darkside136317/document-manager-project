# -*- coding: utf-8 -*-
import frappe
from frappe.utils.nestedset import NestedSet


class StorageWarehouse(NestedSet):
    """Kho lưu trữ — Tree structure: Kho → Phòng → Giá → Hộp."""

    nsm_parent_field = "parent_warehouse"

    def validate(self):
        if self.warehouse_code:
            self.warehouse_code = self.warehouse_code.strip().upper()
