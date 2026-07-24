# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document


class QuickEntryDictionary(Document):
    """Từ điển nhập nhanh — hỗ trợ đơn cấp và đa cấp."""

    def validate(self):
        if self.parent_entry:
            # Validate parent exists and has same dictionary_type
            parent = frappe.get_doc("Quick Entry Dictionary", self.parent_entry)
            if parent.dictionary_type != self.dictionary_type:
                frappe.throw(
                    f"Giá trị cha phải cùng loại từ điển '{self.dictionary_type}'"
                )
