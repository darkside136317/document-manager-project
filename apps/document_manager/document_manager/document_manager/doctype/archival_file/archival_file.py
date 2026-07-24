# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document


class ArchivalFile(Document):
    """Hồ sơ lưu trữ — Tầng 4, đơn vị nghiệp vụ chính."""

    def validate(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            frappe.throw("Ngày bắt đầu không thể sau ngày kết thúc")

    def on_update(self):
        self._update_document_count()
        self._update_fonds_total()

    def on_trash(self):
        self._update_fonds_total()

    def _update_document_count(self):
        """Cập nhật tổng số văn bản thuộc hồ sơ này."""
        count = frappe.db.count("Archive Document", filters={
            "archival_file": self.name
        })
        if count != self.total_documents:
            frappe.db.set_value(
                "Archival File", self.name, "total_documents", count,
                update_modified=False
            )

    def _update_fonds_total(self):
        """Cập nhật tổng số hồ sơ của Phông cha."""
        if self.fonds:
            fonds_doc = frappe.get_doc("Fonds", self.fonds)
            fonds_doc.update_total_files()
