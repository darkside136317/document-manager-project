# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document


class DataExchangeJob(Document):
    """Một lần xuất hoặc nhập dữ liệu XML: tùy chọn, tiến độ, kết quả và nhật ký lỗi.

    The jobs are created and driven by `services/exchange` (the export job, the analysed upload and the import run);
    the DocType only keeps what they report. The files are private attachments and go away with the job.
    """

    def on_trash(self):
        for url in filter(None, (self.source_file, self.result_file)):
            for name in frappe.get_all("File", filters={"file_url": url}, pluck="name"):
                frappe.delete_doc("File", name, force=True, ignore_permissions=True)
