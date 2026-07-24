# -*- coding: utf-8 -*-
import frappe
from frappe.utils.nestedset import NestedSet


class ClassificationScheme(NestedSet):
    """Khung phân loại hồ sơ — Tree structure."""

    nsm_parent_field = "parent_scheme"
