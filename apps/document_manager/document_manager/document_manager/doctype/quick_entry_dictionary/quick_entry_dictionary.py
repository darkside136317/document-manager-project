# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class QuickEntryDictionary(NestedSet):
    """Giá trị của từ điển nhập nhanh — đơn cấp (phẳng) hoặc đa cấp (cây) tùy loại từ điển."""

    nsm_parent_field = "parent_entry"

    def validate(self):
        self.entry_value = (self.entry_value or "").strip()
        dictionary = frappe.db.get_value("Dictionary Type", self.dictionary_type,
                                         ["is_hierarchical", "is_active"], as_dict=True)
        if not dictionary:
            frappe.throw(_("Loại từ điển {0} không tồn tại").format(self.dictionary_type))
        if self.parent_entry:
            if not dictionary.is_hierarchical:
                frappe.throw(_("Loại từ điển {0} là đơn cấp: không có giá trị cha").format(self.dictionary_type))
            if frappe.db.get_value("Quick Entry Dictionary", self.parent_entry, "dictionary_type") != self.dictionary_type:
                frappe.throw(_("Giá trị cha phải cùng loại từ điển {0}").format(self.dictionary_type))
        duplicate = frappe.db.exists("Quick Entry Dictionary", {
            "dictionary_type": self.dictionary_type, "entry_value": self.entry_value,
            "parent_entry": self.parent_entry or ["is", "not set"], "name": ["!=", self.name]})
        if duplicate:
            frappe.throw(_("Giá trị {0} đã có trong cùng cấp của từ điển này").format(self.entry_value))

    def on_update(self):
        super().on_update()
        if self.parent_entry and not frappe.db.get_value("Quick Entry Dictionary", self.parent_entry, "is_group"):
            frappe.db.set_value("Quick Entry Dictionary", self.parent_entry, "is_group", 1, update_modified=False)
        before = None if self.is_new() else self.get_doc_before_save()
        old = before.parent_entry if before and before.parent_entry != self.parent_entry else None
        if old and not frappe.db.exists("Quick Entry Dictionary", {"parent_entry": old}):
            frappe.db.set_value("Quick Entry Dictionary", old, "is_group", 0, update_modified=False)

    def after_delete(self):
        if self.parent_entry and not frappe.db.exists("Quick Entry Dictionary", {"parent_entry": self.parent_entry}):
            frappe.db.set_value("Quick Entry Dictionary", self.parent_entry, "is_group", 0, update_modified=False)
