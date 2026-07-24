# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

class Catalog(Document):
    """Mục lục tài liệu — Tầng 3 trong mô hình phân cấp."""

    def validate(self):
        if self.start_year and self.end_year and self.start_year > self.end_year:
            frappe.throw("Năm bắt đầu không thể lớn hơn năm kết thúc")
