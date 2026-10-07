# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint
from frappe.utils.html_utils import clean_html

REGISTRATION = "Đăng ký độc giả"


class RequestTemplate(Document):
    """Mẫu phiếu yêu cầu sử dụng, phiếu sao chụp hoặc mẫu đăng ký độc giả.

    Chỉ một mẫu đang dùng cho mỗi loại; trang web độc giả và bản in đọc mẫu qua `services/templates.py`.
    """

    def validate(self):
        self.template_name = (self.template_name or "").strip()
        self.instructions = clean_html(self.instructions or "")
        seen = set()
        for row in self.get("form_fields") or []:
            if row.field_name in seen:
                frappe.throw(_("Trường {0} xuất hiện hai lần trong mẫu").format(row.field_name))
            seen.add(row.field_name)
        if self.kind != REGISTRATION and self.get("form_fields"):
            self.set("form_fields", [])  # the field table belongs to the registration form only
        if self.kind == REGISTRATION and self.get("purposes"):
            self.set("purposes", [])
        purposes = [(row.purpose or "").strip() for row in self.get("purposes") or []]
        if len(set(p.lower() for p in purposes)) != len(purposes):
            frappe.throw(_("Danh sách mục đích có giá trị trùng nhau"))

    def on_update(self):
        if cint(self.is_active):
            frappe.db.sql(
                "update `tabRequest Template` set is_active = 0 where kind = %s and name != %s and is_active = 1",
                (self.kind, self.name))
