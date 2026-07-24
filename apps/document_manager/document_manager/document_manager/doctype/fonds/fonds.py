# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document


class Fonds(Document):
    """Phông lưu trữ — Tầng 1 trong mô hình phân cấp 5 tầng."""

    def validate(self):
        if self.fonds_code:
            self.fonds_code = self.fonds_code.strip().upper()
        if self.start_year and self.end_year:
            if self.start_year > self.end_year:
                frappe.throw("Năm bắt đầu không thể lớn hơn năm kết thúc")

    def on_update(self):
        self.update_total_files()

    def update_total_files(self):
        """Cập nhật tổng số hồ sơ thuộc phông này."""
        count = frappe.db.count("Archival File", filters={
            "fonds": self.name
        })
        if count != self.total_files:
            frappe.db.set_value("Fonds", self.name, "total_files", count, update_modified=False)
