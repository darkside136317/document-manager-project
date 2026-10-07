# -*- coding: utf-8 -*-
import hashlib

import frappe
from frappe.model.document import Document

from document_manager.document_manager.services.archive.counters import refresh_file_document_count
from document_manager.document_manager.services.mongodb_storage import enqueue_delete_gridfs_files


class ArchiveDocument(Document):
    """Văn bản/Tài liệu — Tầng 5 (leaf) trong mô hình phân cấp.

    Là đơn vị chứa file thực tế (PDF/DOCX/XLSX/ảnh).
    Tích hợp với MongoDB Atlas GridFS để lưu file gốc và Meilisearch để full-text search.
    """

    def validate(self):
        self._detect_file_type()

    def on_update(self):
        """Keep the document counters of the current and (when moved) the previous file right."""
        before = self.get_doc_before_save()
        for file_name in {self.archival_file, before.archival_file if before else None}:
            refresh_file_document_count(file_name)

    def after_delete(self):
        refresh_file_document_count(self.archival_file)
        # The bytes in GridFS are released only after the deletion has been committed.
        enqueue_delete_gridfs_files([self.gridfs_file_id], "documents")
        enqueue_delete_gridfs_files([self.gridfs_preview_id], "previews")

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

    def compute_checksum(self, file_content: bytes) -> str:
        """Tính SHA-256 checksum cho nội dung file."""
        sha = hashlib.sha256(file_content)
        self.checksum = sha.hexdigest()
        return self.checksum
