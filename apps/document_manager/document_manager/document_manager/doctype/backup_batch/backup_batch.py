# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document


class BackupBatch(Document):
    """Đợt sao lưu: cơ sở dữ liệu và/hoặc tệp tài liệu. Chạy bởi `services/preservation/backup.py` (api/preservation.py)."""

    def on_trash(self):
        if self.status in ("Đang chờ", "Đang chạy") and not self.flags.ignore_permissions:
            frappe.throw(_("Không xóa được đợt sao lưu đang chạy"))
