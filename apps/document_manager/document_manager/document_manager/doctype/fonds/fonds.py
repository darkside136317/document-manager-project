# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

from document_manager.document_manager.services.archive.counters import refresh_fonds_file_count


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
        refresh_fonds_file_count(self.name)
