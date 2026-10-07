# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document


class DictionaryType(Document):
    """Loại từ điển nhập nhanh. Mỗi loại là một danh sách giá trị, đơn cấp hoặc đa cấp."""

    def validate(self):
        self.type_name = (self.type_name or "").strip()
        if self.is_new() or not self.has_value_changed("is_hierarchical") or self.is_hierarchical:
            return
        nested = frappe.db.count("Quick Entry Dictionary", {"dictionary_type": self.name, "parent_entry": ["is", "set"]})
        if nested:
            frappe.throw(_("Còn {0} giá trị đang là giá trị con: không thể chuyển về từ điển đơn cấp").format(nested))
