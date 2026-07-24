# -*- coding: utf-8 -*-
"""Permission-aware preview and download endpoints for archived documents."""

from pathlib import PurePosixPath
from urllib.parse import quote

import frappe
from frappe import _


INLINE_FILE_TYPES = {"PDF", "JPG", "PNG"}
TEXT_FILE_TYPES = {"DOCX", "XLSX"}


def _get_permitted_document(doc_name):
    if not doc_name or not frappe.db.exists("Archive Document", doc_name):
        frappe.throw(_("Không tìm thấy tài liệu."), frappe.DoesNotExistError)

    doc = frappe.get_doc("Archive Document", doc_name)
    doc.check_permission("read")
    return doc


def _read_original_file(doc):
    """Return original bytes and filename, preferring the durable GridFS copy."""
    if doc.gridfs_file_id:
        from document_manager.document_manager.services.mongodb_storage import (
            MongoGridFSStorage,
        )

        storage = MongoGridFSStorage(collection_name="documents")
        info = storage.get_file_info(doc.gridfs_file_id)
        return storage.download_file(doc.gridfs_file_id), info["filename"]

    if doc.file_attachment:
        file_doc = frappe.get_doc("File", {"file_url": doc.file_attachment})
        filename = file_doc.file_name or PurePosixPath(doc.file_attachment).name
        return file_doc.get_content(), filename

    frappe.throw(_("Tài liệu chưa có tệp đính kèm."))


def _download_url(doc_name):
    return (
        "/api/method/document_manager.document_manager.api.file_access.download_file"
        f"?doc_name={quote(doc_name)}"
    )


@frappe.whitelist()
def get_preview(doc_name):
    """Return preview metadata without exposing GridFS identifiers or private paths."""
    doc = _get_permitted_document(doc_name)
    file_type = (doc.file_type or "").upper()
    filename = (
        PurePosixPath(doc.file_attachment).name
        if doc.file_attachment
        else f"{doc.name}.{file_type.lower()}" if file_type else doc.name
    )

    result = {
        "doc_name": doc.name,
        "title": doc.document_title or doc.name,
        "filename": filename,
        "file_type": file_type or _("Tệp"),
        "download_url": _download_url(doc.name),
        "document_url": f"/app/archive-document/{quote(doc.name)}",
    }

    if file_type in INLINE_FILE_TYPES:
        result.update({
            "kind": "inline",
            "preview_url": (
                "/api/method/document_manager.document_manager.api.file_access.preview_file"
                f"?doc_name={quote(doc.name)}"
            ),
        })
    elif file_type in TEXT_FILE_TYPES and doc.content_text:
        result.update({
            "kind": "text",
            "content": doc.content_text[:50000],
            "notice": _("Bản xem trước là nội dung văn bản được trích xuất từ tệp gốc."),
        })
    elif doc.content_text:
        result.update({
            "kind": "text",
            "content": doc.content_text[:50000],
            "notice": _("Định dạng này được xem trước dưới dạng văn bản trích xuất."),
        })
    else:
        result.update({
            "kind": "unsupported",
            "notice": _("Định dạng tệp này chưa hỗ trợ xem trực tiếp. Bạn có thể tải tệp gốc xuống."),
        })

    return result


@frappe.whitelist()
def preview_file(doc_name):
    """Stream browser-safe formats inline after checking Archive Document permission."""
    doc = _get_permitted_document(doc_name)
    file_type = (doc.file_type or "").upper()
    if file_type not in INLINE_FILE_TYPES:
        frappe.throw(_("Định dạng tệp này không hỗ trợ xem trực tiếp."))

    content, filename = _read_original_file(doc)
    frappe.db.set_value(
        "Archive Document", doc.name, "last_accessed", frappe.utils.now(),
        update_modified=False,
    )
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "inline"


@frappe.whitelist()
def download_file(doc_name):
    """Download the original file after checking Archive Document permission."""
    doc = _get_permitted_document(doc_name)
    content, filename = _read_original_file(doc)
    frappe.db.set_value(
        "Archive Document", doc.name, "last_accessed", frappe.utils.now(),
        update_modified=False,
    )
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "attachment"
