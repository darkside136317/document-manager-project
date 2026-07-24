# -*- coding: utf-8 -*-
import hashlib

import frappe
from frappe.model.document import Document


class ArchiveDocument(Document):
    """Văn bản/Tài liệu — Tầng 5 (leaf) trong mô hình phân cấp.

    Là đơn vị chứa file thực tế (PDF/DOCX/XLSX/ảnh).
    Tích hợp với MongoDB Atlas GridFS để lưu file gốc và Meilisearch để full-text search.
    """

    def validate(self):
        self._detect_file_type()

    def after_insert(self):
        self._update_parent_count()
        # TODO (Giai đoạn 5): enqueue extract_text + index jobs
        # frappe.enqueue(
        #     "document_manager.document_manager.services.file_processor.extract_and_index",
        #     doc_name=self.name,
        #     queue="long",
        # )

    def on_update(self):
        self._update_parent_count()

    def on_trash(self):
        self._update_parent_count()
        # TODO (Giai đoạn 5): enqueue deindex from Meilisearch
        # TODO (Giai đoạn 5): delete file from MongoDB Atlas GridFS

    def _detect_file_type(self):
        """Tự động phát hiện loại file từ phần mở rộng."""
        if self.file_attachment and not self.file_type:
            ext = self.file_attachment.rsplit(".", 1)[-1].upper() if "." in self.file_attachment else ""
            type_map = {
                "PDF": "PDF",
                "DOCX": "DOCX",
                "DOC": "DOCX",
                "XLSX": "XLSX",
                "XLS": "XLSX",
                "JPG": "JPG",
                "JPEG": "JPG",
                "PNG": "PNG",
                "TIFF": "TIFF",
                "TIF": "TIFF",
            }
            self.file_type = type_map.get(ext, "Khác")

    def _update_parent_count(self):
        """Cập nhật số văn bản trên Hồ sơ cha."""
        if self.archival_file:
            try:
                archival_file = frappe.get_doc("Archival File", self.archival_file)
                archival_file._update_document_count()
            except frappe.DoesNotExistError:
                pass

    def compute_checksum(self, file_content: bytes) -> str:
        """Tính SHA-256 checksum cho nội dung file."""
        sha = hashlib.sha256(file_content)
        self.checksum = sha.hexdigest()
        return self.checksum
