# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document

from document_manager.document_manager.services.archive.hierarchy import propagate_location
from document_manager.document_manager.services.archive.locks import assert_move_allowed, assert_unlocked


class RecordGroup(Document):
    """Khối tài liệu — Tầng 2 trong mô hình phân cấp."""

    def validate(self):
        assert_unlocked(self)
        assert_move_allowed(self)
        if self.start_year and self.end_year and self.start_year > self.end_year:
            frappe.throw(_("Năm bắt đầu không thể lớn hơn năm kết thúc"))

    def on_update(self):
        propagate_location(self, self.get_doc_before_save())

    def on_trash(self):
        assert_unlocked(self, "delete")
