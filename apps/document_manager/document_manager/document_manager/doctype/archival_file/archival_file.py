# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

from document_manager.document_manager.services.archive.hierarchy import propagate_location
from document_manager.document_manager.services.archive.counters import (
    refresh_file_document_count,
    refresh_fonds_file_count,
)


class ArchivalFile(Document):
    """Hồ sơ lưu trữ — Tầng 4, đơn vị nghiệp vụ chính."""

    def validate(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            frappe.throw("Ngày bắt đầu không thể sau ngày kết thúc")

    def on_update(self):
        before = self.get_doc_before_save()
        # Documents carry a copy of their file's position and level (they drive the reader query
        # and the search index): moving or re-classifying the file must update them in this
        # same transaction, otherwise readers keep seeing documents under the old rules.
        propagate_location(self, before)
        refresh_file_document_count(self.name)
        # a file moved to another fonds changes both totals
        for fonds in {self.fonds, before.fonds if before else None}:
            refresh_fonds_file_count(fonds)

    def after_delete(self):
        refresh_fonds_file_count(self.fonds)

    def _update_document_count(self):
        """Kept for callers outside the controller."""
        refresh_file_document_count(self.name)


def check_retention_periods():
    """Scheduler (daily): flag Archival Files whose retention period has elapsed.

    Not whitelisted: it must only run from the scheduler or a server-side call.
    """
    from frappe.utils import add_years, getdate, today

    files = frappe.get_all("Archival File", filters={
        "retention_years": [">", 0],
        "disposal_status": "Bình thường",
        "end_date": ["is", "set"],
    }, fields=["name", "end_date", "retention_years", "file_title"], limit_page_length=0)

    current_date = getdate(today())
    expired_count = 0

    for f in files:
        expiry_date = add_years(f.end_date, f.retention_years)
        if current_date > expiry_date:
            frappe.db.set_value("Archival File", f.name, "disposal_status", "Cảnh báo tiêu hủy")
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": f"Hồ sơ {f.file_title} đã đến hạn tiêu hủy",
                "email_content": (
                    f"Hồ sơ {f.name} đã kết thúc vào {f.end_date} và có thời hạn "
                    f"{f.retention_years} năm. Đề nghị xem xét tiêu hủy."
                ),
                "document_type": "Archival File",
                "document_name": f.name,
                "for_user": "Administrator",
                "type": "Alert",
            }).insert(ignore_permissions=True)
            expired_count += 1

    if expired_count:
        frappe.db.commit()

    return expired_count
