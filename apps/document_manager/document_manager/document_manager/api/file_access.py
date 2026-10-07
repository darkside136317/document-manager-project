# -*- coding: utf-8 -*-
"""Permission-aware preview and download endpoints for archived documents."""

from pathlib import PurePosixPath
from urllib.parse import quote

import frappe
from frappe import _

from document_manager.document_manager.policy import get_reader_scope


INLINE_FILE_TYPES = {"PDF", "JPG", "PNG"}
TEXT_FILE_TYPES = {"DOCX", "XLSX"}


def _get_permitted_document(doc_name, feature="can_preview"):
    """The Archive Document if the user's group allows `feature` and the document is readable."""
    from document_manager.document_manager.permissions import assert_feature
    assert_feature(feature)
    if not doc_name or not frappe.db.exists("Archive Document", doc_name):
        frappe.throw(_("Không tìm thấy tài liệu."), frappe.DoesNotExistError)

    doc = frappe.get_doc("Archive Document", doc_name)
    doc.check_permission("read")
    return doc


def _read_original_file(doc):
    """Original bytes and filename: the durable GridFS copy first, the uploaded file when GridFS is
    unavailable (not configured, unreachable, or the copy has not been made yet)."""
    if doc.gridfs_file_id:
        try:
            from document_manager.document_manager.services.mongodb_storage import MongoGridFSStorage

            storage = MongoGridFSStorage(collection_name="documents")
            info = storage.get_file_info(doc.gridfs_file_id)
            return storage.download_file(doc.gridfs_file_id), info["filename"]
        except Exception:
            if not doc.file_attachment:
                raise

    if doc.file_attachment:
        from document_manager.document_manager.services.file_processor import read_file_bytes

        content = read_file_bytes(doc.file_attachment)
        if content is None:
            frappe.throw(_("Không đọc được tệp đính kèm."), frappe.DoesNotExistError)
        filename = frappe.db.get_value("File", {"file_url": doc.file_attachment}, "file_name") or PurePosixPath(
            doc.file_attachment).name
        return content, filename

    frappe.throw(_("Tài liệu chưa có tệp đính kèm."))


def _mark_accessed(doc_name):
    """Record the access time (and commit: GET requests are rolled back otherwise).

    The request has already read the document, so its snapshot can be older than a change a
    background job committed meanwhile, and MariaDB then refuses the update ("Record has changed
    since last read"). Finish the read first, write on a fresh snapshot, retry if it still collides.
    """
    from document_manager.document_manager.services.errors import retry_on_deadlock

    def write():
        frappe.db.commit()
        frappe.db.set_value("Archive Document", doc_name, "last_accessed", frappe.utils.now(), update_modified=False)
        frappe.db.commit()

    retry_on_deadlock(write)


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
        "download_url": _download_url(doc.name) if get_reader_scope().can_download else None,
        "document_url": f"/portal/van-ban/{quote(doc.name)}",
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
    _mark_accessed(doc.name)
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "inline"


@frappe.whitelist()
def download_file(doc_name):
    """Download the original file after checking Archive Document permission."""
    doc = _get_permitted_document(doc_name, "can_download")
    content, filename = _read_original_file(doc)
    _mark_accessed(doc.name)
    _log_activity("Tải xuống", "Archive Document", doc.name, f"Tải xuống tệp gốc {filename}")
    
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "attachment"

@frappe.whitelist()
def log_document_access(doc_name, action):
    """Log document access from portal viewer."""
    if action not in ["Xem", "Tải xuống"]:
        action = "Xem"
        
    doc = _get_permitted_document(doc_name, "can_download" if action == "Tải xuống" else "can_preview")
    _log_activity(action, "Archive Document", doc.name, f"{action} tài liệu trên Portal")
    return "OK"

def _log_activity(activity_type, ref_doctype, ref_name, description):
    """GET endpoints are rolled back by Frappe, so these rows are committed explicitly."""
    from document_manager.document_manager.services.audit import log_activity

    log_activity(activity_type, ref_doctype, ref_name, description, commit=True)
