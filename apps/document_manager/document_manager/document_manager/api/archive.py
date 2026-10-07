# -*- coding: utf-8 -*-
"""Cataloguing API of the staff UI: the Fonds > Record Group > Catalog tree, the overview of a file
or a document, creating documents from uploaded files, and the links for printing.

Everything goes through Frappe permissions (`get_list`, `check_permission`); the checks that are
specific to cataloguing (staff only, which uploaded file may be claimed, which file types) are here.
"""

import os
import re
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint

from document_manager.document_manager.constants import UPLOAD_EXTENSIONS, UPLOAD_MAX_MB
from document_manager.document_manager.permissions import is_staff
from document_manager.document_manager.services.errors import retry_on_deadlock

PRINT_FORMATS = {
    "Archival File": {"standard": "Archival File Standard", "contents": "Archival File Contents"},
    "Archive Document": {"standard": "Archive Document Standard"},
    "Catalog": {"standard": "Catalog Standard"},
}
TREE_LEVELS = {
    None: ("Fonds", "fonds_name", "fonds_code", None),
    "Fonds": ("Record Group", "group_title", "group_code", "fonds"),
    "Record Group": ("Catalog", "catalog_title", "catalog_number", "record_group"),
}


def _require_staff():
    if not is_staff():
        frappe.throw(_("Bạn không có quyền sử dụng chức năng biên mục"), frappe.PermissionError)


def _count(doctype, filters, group_by=None, key=None) -> dict | int:
    """COUNT(*) per `key` (with group_by) or in total, through the permission-aware get_list."""
    fields = [{"COUNT": "name", "as": "c"}]
    if group_by:
        rows = frappe.get_list(doctype, filters=filters, fields=[group_by, *fields], group_by=group_by)
        return {r.get(group_by): r.c for r in rows}
    rows = frappe.get_list(doctype, filters=filters, fields=fields)
    return rows[0].c if rows else 0


def print_urls(doctype: str, name: str) -> dict:
    """{kind: {view, pdf}} for the print formats of a DocType; empty when the user may not print."""
    if not frappe.has_permission(doctype, "print", doc=name):
        return {}
    out = {}
    for kind, fmt in PRINT_FORMATS.get(doctype, {}).items():
        if not frappe.db.exists("Print Format", fmt):
            continue
        query = f"doctype={quote(doctype)}&name={quote(name)}&format={quote(fmt)}&no_letterhead=1"
        out[kind] = {
            "label": fmt,
            "view": f"/printview?{query}",
            "pdf": ("/api/method/document_manager.document_manager.api.archive.download_print_pdf"
                    f"?doctype={quote(doctype)}&name={quote(name)}&kind={quote(kind)}"),
        }
    return out


# ---------------------------------------------------------------------------
# The tree
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_tree(parent_doctype=None, parent_name=None):
    """Children of a node of the cataloguing tree: fonds (roots) > record groups > catalogs.

    Returns [{doctype, name, title, code, child_count, file_count}]. Catalogs are the leaves: their
    archival files are listed beside the tree.
    """
    _require_staff()
    if parent_doctype not in TREE_LEVELS:
        return []
    doctype, title_field, code_field, parent_field = TREE_LEVELS[parent_doctype]
    filters = {parent_field: parent_name} if parent_field else {}
    rows = frappe.get_list(doctype, filters=filters, fields=["name", title_field, code_field],
                           order_by=f"{title_field} asc", page_length=500)

    child_counts = file_counts = {}
    if rows:
        names = [r.name for r in rows]
        if doctype == "Fonds":
            child_counts = _count("Record Group", {"fonds": ["in", names]}, group_by="fonds")
            file_counts = _count("Archival File", {"fonds": ["in", names]}, group_by="fonds")
        elif doctype == "Record Group":
            child_counts = _count("Catalog", {"record_group": ["in", names]}, group_by="record_group")
            file_counts = _count("Archival File", {"record_group": ["in", names]}, group_by="record_group")
        else:
            file_counts = _count("Archival File", {"catalog": ["in", names]}, group_by="catalog")
    return [{
        "doctype": doctype, "name": r.name, "title": r.get(title_field) or r.name, "code": r.get(code_field) or "",
        "child_count": child_counts.get(r.name, 0), "file_count": file_counts.get(r.name, 0),
    } for r in rows]


# ---------------------------------------------------------------------------
# Overview of a file / a document
# ---------------------------------------------------------------------------

def _ancestors(doc) -> list:
    """Fonds, record group and catalog above `doc`, as breadcrumb entries the user may read."""
    chain = []
    for doctype, field, title_field in (("Fonds", "fonds", "fonds_name"), ("Record Group", "record_group", "group_title"),
                                        ("Catalog", "catalog", "catalog_title")):
        name = doc.get(field)
        if name and frappe.has_permission(doctype, "read", doc=name):
            chain.append({"doctype": doctype, "name": name,
                          "title": frappe.db.get_value(doctype, name, title_field) or name})
    return chain


def _upload_rules() -> dict:
    return {"extensions": UPLOAD_EXTENSIONS, "max_mb": UPLOAD_MAX_MB}


@frappe.whitelist()
def get_file_overview(name):
    """Breadcrumb, document statistics, permissions and print links of an archival file."""
    _require_staff()
    doc = frappe.get_doc("Archival File", name)
    doc.check_permission("read")

    in_file = {"archival_file": name}
    sizes = frappe.get_list("Archive Document", filters=in_file, fields=[{"SUM": "file_size_kb", "as": "kb"}])
    by_status = _count("Archive Document", in_file, group_by="search_index_status")
    return {
        "ancestors": _ancestors(doc),
        "stats": {
            "documents": sum(by_status.values()),
            "size_kb": float((sizes[0].kb if sizes else 0) or 0),
            "indexed": by_status.get("Đã index", 0),
            "failed": by_status.get("Lỗi", 0),
        },
        "permissions": {
            "write": bool(frappe.has_permission("Archival File", "write", doc=name)),
            "delete": bool(frappe.has_permission("Archival File", "delete", doc=name)),
            "add_documents": bool(frappe.has_permission("Archive Document", "create")),
        },
        "print": print_urls("Archival File", name),
        "upload": _upload_rules(),
    }


@frappe.whitelist()
def get_document_overview(name):
    """System information of a document (stored file, size, index state) plus breadcrumb and print links."""
    _require_staff()
    doc = frappe.get_doc("Archive Document", name)
    doc.check_permission("read")
    filename = ""
    if doc.file_attachment:
        filename = frappe.db.get_value("File", {"file_url": doc.file_attachment}, "file_name") or os.path.basename(
            doc.file_attachment)
    parent = frappe.get_doc("Archival File", doc.archival_file) if doc.archival_file else None
    ancestors = _ancestors(parent) if parent else []
    if parent:
        ancestors.append({"doctype": "Archival File", "name": parent.name, "title": parent.file_title or parent.name})
    return {
        "ancestors": ancestors,
        "file": {
            "name": filename,
            "type": doc.file_type or "",
            "size_kb": doc.file_size_kb or 0,
            "checksum": doc.checksum or "",
            "attached": bool(doc.file_attachment),
            "stored": bool(doc.gridfs_file_id),
            "index_status": doc.search_index_status or "",
            "last_accessed": doc.last_accessed,
            "has_text": bool(doc.content_text),
        },
        "permissions": {
            "write": bool(frappe.has_permission("Archive Document", "write", doc=name)),
            "delete": bool(frappe.has_permission("Archive Document", "delete", doc=name)),
        },
        "print": print_urls("Archive Document", name),
        "upload": _upload_rules(),
    }


# ---------------------------------------------------------------------------
# Documents from uploaded files
# ---------------------------------------------------------------------------

def _extension(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lstrip(".").lower()


def _claim_upload(file_url: str):
    """The File record behind `file_url`, if it is the caller's own, still unattached, allowed upload.

    A rejected upload is deleted, so refused files do not pile up in the private folder.
    """
    file = frappe.db.get_value(
        "File", {"file_url": file_url},
        ["name", "file_name", "file_size", "owner", "attached_to_doctype", "attached_to_name"], as_dict=True)
    if not file or (file.owner != frappe.session.user and frappe.session.user != "Administrator"):
        frappe.throw(_("Không tìm thấy tệp đã tải lên"), frappe.PermissionError)
    if file.attached_to_doctype and file.attached_to_name:
        frappe.throw(_("Tệp này đã được đính kèm vào {0} {1}").format(file.attached_to_doctype, file.attached_to_name))

    problem = None
    if _extension(file.file_name) not in UPLOAD_EXTENSIONS:
        problem = _("Định dạng .{0} không được hỗ trợ. Chấp nhận: {1}").format(
            _extension(file.file_name) or "?", ", ".join(UPLOAD_EXTENSIONS))
    elif cint(file.file_size) > UPLOAD_MAX_MB * 1024 * 1024:
        problem = _("Tệp vượt quá {0} MB").format(UPLOAD_MAX_MB)
    if problem:
        frappe.delete_doc("File", file.name, ignore_permissions=True)
        frappe.throw(problem)
    return file


def _bind_file(file, document) -> None:
    frappe.db.set_value("File", file.name, {
        "attached_to_doctype": "Archive Document", "attached_to_name": document.name,
        "attached_to_field": "file_attachment",
    }, update_modified=False)


@frappe.whitelist(methods=["POST"])
def add_document_from_file(archival_file, file_url, title=None):
    """Create a document in `archival_file` from a file that was just uploaded (is_private=1).

    The title defaults to the file name. Text extraction, storage in GridFS and indexing follow
    in the background (document hooks).
    """
    _require_staff()
    frappe.get_doc("Archival File", archival_file).check_permission("read")
    if not frappe.has_permission("Archive Document", "create"):
        frappe.throw(_("Bạn không có quyền thêm văn bản"), frappe.PermissionError)
    file = _claim_upload(file_url)

    def create():
        document = frappe.get_doc({
            "doctype": "Archive Document",
            "document_title": (title or os.path.splitext(file.file_name)[0]).strip()[:140],
            "archival_file": archival_file,
            "file_attachment": file_url,
        }).insert()
        _bind_file(file, document)
        return document

    document = retry_on_deadlock(create)
    return {"name": document.name, "title": document.document_title, "file_type": document.file_type}


@frappe.whitelist(methods=["POST"])
def attach_file(document, file_url):
    """Replace the file of an existing document with a freshly uploaded one."""
    _require_staff()
    doc = frappe.get_doc("Archive Document", document)
    doc.check_permission("write")
    file = _claim_upload(file_url)

    previous = doc.file_attachment

    def replace():
        current = frappe.get_doc("Archive Document", document)  # fresh read: a retry starts clean
        current.file_attachment = file_url
        current.file_type = ""  # detected again from the new extension
        current.checksum = ""
        current.save()
        return current

    doc = retry_on_deadlock(replace)
    _bind_file(file, doc)
    if previous and previous != file_url:  # the old upload is garbage now
        for old in frappe.get_all("File", filters={"file_url": previous, "attached_to_name": document}, pluck="name"):
            frappe.delete_doc("File", old, ignore_permissions=True)
    return {"name": doc.name, "file_type": doc.file_type}


@frappe.whitelist(methods=["POST"])
def reindex_document(document):
    """Queue text extraction, storage and indexing of a document again (after a failure)."""
    _require_staff()
    doc = frappe.get_doc("Archive Document", document)
    doc.check_permission("write")
    if not doc.file_attachment:
        frappe.throw(_("Văn bản chưa có tệp đính kèm"))
    from document_manager.document_manager.services.file_processor import enqueue_extract_and_store

    enqueue_extract_and_store(doc)
    frappe.db.set_value("Archive Document", document, "search_index_status", "Đang xử lý", update_modified=False)
    return {"name": document, "status": "Đang xử lý"}


def _self_contained(html: str) -> str:
    """The print page without external stylesheets and scripts: it only needs its own <style>."""
    html = re.sub(r"<script\b.*?</script\s*>", "", html, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"<link\b[^>]*>", "", html, flags=re.IGNORECASE)


@frappe.whitelist()
def download_print_pdf(doctype, name, kind="standard"):
    """PDF of one of the print formats of `print_urls`.

    Frappe's own PDF download makes wkhtmltopdf fetch the stylesheets from the site's public address,
    which a container cannot reach (connection refused, no PDF). These formats carry their own
    styles, so unreachable resources are ignored instead of failing the whole export.
    """
    from frappe.utils.pdf import get_pdf

    _require_staff()
    fmt = PRINT_FORMATS.get(doctype, {}).get(kind)
    if not fmt or not frappe.db.exists("Print Format", fmt):
        frappe.throw(_("Mẫu in không tồn tại"), frappe.DoesNotExistError)
    frappe.get_doc(doctype, name).check_permission("print")

    html = _self_contained(frappe.get_print(doctype, name, print_format=fmt, no_letterhead=1))
    frappe.local.response.filename = f"{name}.pdf"
    frappe.local.response.filecontent = get_pdf(
        html, options={"load-error-handling": "ignore", "load-media-error-handling": "ignore"})
    frappe.local.response.type = "pdf"

