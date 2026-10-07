# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document


class ReaderGroup(Document):
    """Nhóm độc giả — gom phạm vi khai thác (mức mật, phông) và chức năng được dùng.

    Quyền thực tế của từng độc giả do `policy.get_reader_scope` tính từ nhóm này.
    """

    def validate(self):
        self.max_confidentiality_priority = max(1, int(self.max_confidentiality_priority or 1))
        if self.fonds_scope == "Chỉ các phông được chọn":
            if not self.fonds_scopes:
                frappe.throw(_("Hãy chọn ít nhất một phông, hoặc chuyển sang \"Tất cả phông\""))
            seen = set()
            for row in self.fonds_scopes:
                if row.fonds in seen:
                    frappe.throw(_("Dòng {0}: phông {1} bị trùng").format(row.idx, row.fonds))
                seen.add(row.fonds)
        else:
            self.set("fonds_scopes", [])
        if self.is_default and not self.is_active:
            frappe.throw(_("Nhóm mặc định phải đang hoạt động"))

    def on_update(self):
        if self.is_default:  # only one default group
            frappe.db.sql("update `tabReader Group` set is_default=0 where name != %s and is_default=1",
                          self.name)

    def on_trash(self):
        if self.is_default:
            frappe.throw(_("Không thể xóa nhóm mặc định"))
        used = frappe.db.count("Reader", {"reader_group": self.name})
        if used:
            frappe.throw(_("Còn {0} độc giả thuộc nhóm này").format(used))
