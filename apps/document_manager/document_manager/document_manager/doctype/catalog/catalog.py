# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document

from document_manager.document_manager.services.archive.hierarchy import propagate_location


class Catalog(Document):
    """Mục lục tài liệu — Tầng 3 trong mô hình phân cấp."""

    def validate(self):
        if self.start_year and self.end_year and self.start_year > self.end_year:
            frappe.throw(_("Năm bắt đầu không thể lớn hơn năm kết thúc"))
        if self.record_group:
            # A catalog always belongs to the fonds of its record group.
            self.fonds = frappe.db.get_value("Record Group", self.record_group, "fonds")

    def on_update(self):
        propagate_location(self, self.get_doc_before_save())
