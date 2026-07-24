# -*- coding: utf-8 -*-
"""File processing worker — extract text from uploaded documents.

Pipeline: upload → extract text (PDF/DOCX/XLSX) → store in MongoDB Atlas GridFS →
compute checksum → index in Meilisearch.

Called via frappe.enqueue from doc_events hooks.
"""

import hashlib
import io

import frappe


def extract_and_store(doc_name: str):
    """Main pipeline: extract text from file, store in GridFS, index in Meilisearch.

    Args:
        doc_name: Archive Document name
    """
    doc = frappe.get_doc("Archive Document", doc_name)
    if not doc.file_attachment:
        return

    try:
        frappe.db.set_value(
            "Archive Document", doc_name, "search_index_status", "Đang xử lý",
            update_modified=False,
        )
        # 1. Read file content from Frappe's file system
        file_content = _read_frappe_file(doc.file_attachment)
        if not file_content:
            return

        # 2. Compute checksum
        checksum = hashlib.sha256(file_content).hexdigest()

        # 3. Extract text based on file type
        content_text = ""
        file_type = doc.file_type or ""
        if file_type == "PDF":
            content_text = _extract_text_pdf(file_content)
        elif file_type == "DOCX":
            content_text = _extract_text_docx(file_content)
        elif file_type == "XLSX":
            content_text = _extract_text_xlsx(file_content)

        # 4. Store file in MongoDB Atlas GridFS
        gridfs_file_id = ""
        try:
            from document_manager.document_manager.services.mongodb_storage import (
                upload_document_file,
            )
            filename = doc.file_attachment.rsplit("/", 1)[-1] if "/" in doc.file_attachment else doc.file_attachment
            gridfs_file_id = upload_document_file(doc_name, file_content, filename)
        except Exception as e:
            frappe.log_error(f"GridFS upload failed for {doc_name}: {e}", "File Storage Error")

        # 5. Update document record
        update_values = {
            "checksum": checksum,
            "file_size_kb": round(len(file_content) / 1024, 2),
        }
        if content_text:
            update_values["content_text"] = content_text[:65000]  # MariaDB TEXT limit
        if gridfs_file_id:
            update_values["gridfs_file_id"] = gridfs_file_id

        frappe.db.set_value("Archive Document", doc_name, update_values, update_modified=False)
        frappe.db.commit()

        # 6. Index in Meilisearch
        try:
            from document_manager.document_manager.services.search_index import index_document
            index_document(doc_name)
        except Exception as e:
            frappe.log_error(f"Meilisearch index failed for {doc_name}: {e}", "Search Index Error")
            frappe.db.set_value(
                "Archive Document", doc_name, "search_index_status", "Lỗi",
                update_modified=False,
            )

    except Exception as e:
        frappe.log_error(f"File processing failed for {doc_name}: {e}", "File Processing Error")
        frappe.db.set_value(
            "Archive Document", doc_name, "search_index_status", "Lỗi",
            update_modified=False,
        )


def _read_frappe_file(file_url: str) -> bytes | None:
    """Read file content from Frappe's file system."""
    try:
        file_doc = frappe.get_doc("File", {"file_url": file_url})
        return file_doc.get_content()
    except Exception:
        try:
            file_path = frappe.get_site_path("public", file_url.lstrip("/"))
            with open(file_path, "rb") as f:
                return f.read()
        except Exception:
            return None


def _extract_text_pdf(content: bytes) -> str:
    """Extract text from PDF using pdfplumber."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        frappe.log_error(f"PDF text extraction failed: {e}", "Text Extraction Error")
        return ""


def _extract_text_docx(content: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        paragraphs.append(cell.text.strip())
        return "\n".join(paragraphs)
    except Exception as e:
        frappe.log_error(f"DOCX text extraction failed: {e}", "Text Extraction Error")
        return ""


def _extract_text_xlsx(content: bytes) -> str:
    """Extract text from XLSX using openpyxl."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        text_parts = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                row_text = " ".join(str(cell) for cell in row if cell is not None)
                if row_text.strip():
                    text_parts.append(row_text)
        wb.close()
        return "\n".join(text_parts)
    except Exception as e:
        frappe.log_error(f"XLSX text extraction failed: {e}", "Text Extraction Error")
        return ""


# === Enqueue helper (called from hooks) ===

def enqueue_extract_and_store(doc, method=None):
    """Enqueue the extract_and_store pipeline for a new Archive Document."""
    if doc.file_attachment:
        frappe.enqueue(
            "document_manager.document_manager.services.file_processor.extract_and_store",
            doc_name=doc.name,
            queue="long",
        )


def enqueue_processing_or_index(doc, method=None):
    """Process a newly attached file; otherwise only refresh its search index."""
    file_changed = doc.has_value_changed("file_attachment")
    processing_incomplete = bool(doc.file_attachment and not doc.checksum)

    if file_changed or processing_incomplete:
        enqueue_extract_and_store(doc, method)
        return

    from document_manager.document_manager.services.search_index import enqueue_index
    enqueue_index(doc, method)
