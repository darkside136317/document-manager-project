# -*- coding: utf-8 -*-
"""File processing worker — extract text from uploaded documents.

Pipeline: upload → extract text (PDF/DOCX/XLSX) → store in MongoDB Atlas GridFS →
compute checksum → index in Meilisearch.

Called via frappe.enqueue from doc_events hooks. Jobs are enqueued *after the request commits*
(otherwise a fast worker can run before the document exists) and are de-duplicated by job id
(inserting a document fires both `after_insert` and `on_update`).
"""

import hashlib
import io

import frappe

from document_manager.document_manager.services.errors import log_exception

OCR_MAX_PAGES = 300
TEXT_LIMIT = 65000  # MariaDB TEXT column


def extract_and_store(doc_name: str):
    """Main pipeline: extract text from file, store in GridFS, index in Meilisearch.

    Args:
        doc_name: Archive Document name
    """
    if not frappe.db.exists("Archive Document", doc_name):
        return
    doc = frappe.get_doc("Archive Document", doc_name)
    if not doc.file_attachment:
        return

    def mark(status):
        frappe.db.set_value("Archive Document", doc_name, "search_index_status", status,
                            update_modified=False)

    try:
        mark("Đang xử lý")
        # 1. Read file content from Frappe's file system
        file_content = _read_frappe_file(doc.file_attachment)
        if not file_content:
            log_exception("File Processing Error", f"Không đọc được tệp {doc.file_attachment} của {doc_name}")
            mark("Lỗi")
            frappe.db.commit()
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
        previous_file_id = doc.gridfs_file_id
        try:
            from document_manager.document_manager.services.mongodb_storage import upload_document_file
            filename = doc.file_attachment.rsplit("/", 1)[-1] if "/" in doc.file_attachment else doc.file_attachment
            gridfs_file_id = upload_document_file(doc_name, file_content, filename)
        except Exception:
            log_exception("File Storage Error", f"GridFS upload failed for {doc_name}")

        # 5. Update document record
        update_values = {
            "checksum": checksum,
            "file_size_kb": round(len(file_content) / 1024, 2),
        }
        if content_text:
            update_values["content_text"] = content_text[:TEXT_LIMIT]
        if gridfs_file_id:
            update_values["gridfs_file_id"] = gridfs_file_id

        frappe.db.set_value("Archive Document", doc_name, update_values, update_modified=False)
        frappe.db.commit()

        # The replaced file is garbage now (never delete before the new one is recorded).
        if gridfs_file_id and previous_file_id and previous_file_id != gridfs_file_id:
            from document_manager.document_manager.services.mongodb_storage import delete_gridfs_files
            delete_gridfs_files([previous_file_id])

        # 6. Index in Meilisearch
        try:
            from document_manager.document_manager.services.search_index import index_document
            index_document(doc_name)
        except Exception:
            log_exception("Search Index Error", f"Meilisearch index failed for {doc_name}")
            mark("Lỗi")
            frappe.db.commit()

    except Exception:
        log_exception("File Processing Error", f"File processing failed for {doc_name}")
        mark("Lỗi")
        frappe.db.commit()


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
    """Extract text from PDF using pdfplumber. Fallback to OCR if scanned."""
    text_parts = []
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        extracted_text = "\n".join(text_parts).strip()

        # Very little text → probably a scanned (image-only) PDF.
        if len(extracted_text) < 100:
            ocr_text = _ocr_pdf(content)
            if ocr_text:
                return ocr_text
        return extracted_text
    except Exception:
        log_exception("Text Extraction Error", "PDF text extraction failed")
        return ""


def _ocr_pdf(content: bytes) -> str:
    """OCR a scanned PDF one page at a time (a whole-document render can exhaust memory)."""
    try:
        import pytesseract
        from pdf2image import convert_from_bytes, pdfinfo_from_bytes
    except ImportError:
        frappe.logger().warning("OCR skipped: pytesseract / pdf2image are not installed")
        return ""
    try:
        pages = min(int(pdfinfo_from_bytes(content).get("Pages", 0)), OCR_MAX_PAGES)
        parts = []
        for number in range(1, pages + 1):
            for image in convert_from_bytes(content, first_page=number, last_page=number):
                parts.append(pytesseract.image_to_string(image, lang="vie+eng"))
        return "\n".join(parts).strip()
    except Exception:
        log_exception("OCR Error", "OCR processing failed")
        return ""


def _extract_text_docx(content: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        paragraphs.append(cell.text.strip())
        return "\n".join(paragraphs)
    except Exception:
        log_exception("Text Extraction Error", "DOCX text extraction failed")
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
    except Exception:
        log_exception("Text Extraction Error", "XLSX text extraction failed")
        return ""


# === Enqueue helpers (called from hooks) ===

def enqueue_extract_and_store(doc, method=None):
    """Enqueue the extract_and_store pipeline for an Archive Document (once per document)."""
    if doc.file_attachment:
        frappe.enqueue(
            "document_manager.document_manager.services.file_processor.extract_and_store",
            doc_name=doc.name,
            queue="long",
            timeout=1800,
            job_id=f"dm-extract-{doc.name}",
            deduplicate=True,
            enqueue_after_commit=True,
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
