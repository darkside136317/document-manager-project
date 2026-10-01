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


@frappe.whitelist()
def check_retention_periods():
    """Chạy mỗi đêm (daily) để kiểm tra các Hồ sơ đã hết thời hạn bảo quản."""
    from frappe.utils import getdate, add_years, today
    
    files = frappe.get_all('Archival File', filters={
        'retention_years': ['>', 0],
        'disposal_status': 'Bình thường',
        'end_date': ['is', 'set']
    }, fields=['name', 'end_date', 'retention_years', 'file_title'])
    
    current_date = getdate(today())
    expired_count = 0
    
    for f in files:
        expiry_date = add_years(f.end_date, f.retention_years)
        if current_date > expiry_date:
            frappe.db.set_value('Archival File', f.name, 'disposal_status', 'Cảnh báo tiêu hủy')
            # Create a System Notification
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": f"Hồ sơ {f.file_title} đã đến hạn tiêu hủy",
                "email_content": f"Hồ sơ {f.name} đã kết thúc vào {f.end_date} và có thời hạn {f.retention_years} năm. Đề nghị xem xét tiêu hủy.",
                "document_type": "Archival File",
                "document_name": f.name,
                "for_user": "Administrator",
                "type": "Alert"
            }).insert(ignore_permissions=True)
            expired_count += 1
            
    if expired_count:
        frappe.db.commit()
        
    return expired_count
