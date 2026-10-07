# -*- coding: utf-8 -*-
"""XML export/import of archival data (interim hardening — the full exchange module comes later).

Rules enforced here:
- Only Document Admin / System Manager may export or import.
- Export reads through `frappe.get_list` (permission query conditions apply) and only emits
  whitelisted columns: no extracted text, GridFS ids or system columns.
- Import runs as the calling user (no `ignore_permissions`), writes whitelisted columns only
  (no mass assignment of `owner`, `docstatus`, `workflow_state`, ...), rejects DTD/entity
  declarations (XXE / entity-expansion bombs) and reports the outcome to the user.
"""

import json
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom

import frappe
from frappe import _

from document_manager.document_manager.permissions import assert_roles
from document_manager.document_manager.services.errors import log_exception

EXCHANGE_ROLES = ("Document Admin", "System Manager")
EXPORT_LIMIT = 5000

# Columns that may be exported / imported per DocType (import never accepts `name`).
FIELDS = {
    "Fonds": ["fonds_name", "fonds_code", "archival_agency", "start_year", "end_year", "status"],
    "Record Group": ["group_title", "group_code", "fonds", "start_year", "end_year"],
    "Catalog": ["catalog_title", "catalog_number", "record_group", "fonds"],
    "Archival File": ["file_title", "file_number", "catalog", "record_group", "fonds",
                      "confidentiality_level", "storage_warehouse", "status", "start_date", "end_date"],
    "Archive Document": ["document_title", "document_number", "archival_file", "fonds",
                         "file_type", "document_date", "author", "confidentiality_level"],
}
_ILLEGAL_XML_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _check_doctype(doctype):
    if doctype not in FIELDS:
        frappe.throw(_("Không hỗ trợ trao đổi XML cho {0}").format(doctype))


def _as_list(value):
    if isinstance(value, str):
        return json.loads(value) if value else None
    return value


def _clean(value) -> str:
    return _ILLEGAL_XML_CHARS.sub("", "" if value is None else str(value))


@frappe.whitelist()
def export_xml(doctype, filters=None, fields=None):
    """Export records as XML.

    Returns: {xml_content: str, count: int, truncated: bool}
    """
    assert_roles(*EXCHANGE_ROLES)
    _check_doctype(doctype)

    filters = _as_list(filters) or {}
    requested = _as_list(fields)
    allowed = FIELDS[doctype]
    columns = [f for f in (requested or allowed) if f in allowed]
    if not columns:
        frappe.throw(_("Không có trường hợp lệ để xuất"))

    rows = frappe.get_list(doctype, filters=filters, fields=["name", *columns],
                           order_by="name asc", limit=EXPORT_LIMIT + 1)
    truncated = len(rows) > EXPORT_LIMIT
    rows = rows[:EXPORT_LIMIT]

    root = ET.Element("ArchivalData")
    root.set("doctype", doctype)
    root.set("exported_at", str(frappe.utils.now()))
    root.set("count", str(len(rows)))
    for row in rows:
        item = ET.SubElement(root, doctype.replace(" ", ""))
        for key, value in row.items():
            ET.SubElement(item, key).text = _clean(value)

    xml_str = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
    return {"xml_content": xml_str, "count": len(rows), "truncated": truncated}


def _parse(xml_content: str):
    """Parse untrusted XML; DTDs and entities are refused outright."""
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", xml_content or "", re.IGNORECASE):
        frappe.throw(_("XML không được chứa khai báo DOCTYPE/ENTITY"))
    try:
        return ET.fromstring(xml_content)
    except ET.ParseError as e:
        frappe.throw(_("XML không hợp lệ: {0}").format(e))


@frappe.whitelist(methods=["POST"])
def import_xml(xml_content, doctype, update_existing=False):
    """Import records from XML in the background, as the calling user.

    Returns: {status: "queued"}; the result arrives as a notification.
    """
    assert_roles(*EXCHANGE_ROLES)
    _check_doctype(doctype)
    _parse(xml_content)  # fail fast on malformed or hostile input
    frappe.enqueue(
        "document_manager.document_manager.services.xml_handler._import_xml_worker",
        xml_content=xml_content,
        doctype=doctype,
        update_existing=frappe.utils.cint(update_existing),
        queue="long",
        timeout=1800,
        enqueue_after_commit=True,
    )
    return {"status": "queued",
            "message": _("Đang nhập dữ liệu trong nền. Kết quả sẽ được gửi vào thông báo của bạn.")}


def _import_xml_worker(xml_content, doctype, update_existing=False):
    """Background worker. Runs as the user who enqueued it, so DocType permissions apply."""
    allowed = set(FIELDS[doctype])
    results = {"imported": 0, "updated": 0, "skipped": 0, "errors": []}

    root = ET.fromstring(xml_content)  # validated by import_xml
    for position, item in enumerate(root, start=1):
        try:
            data = {f.tag: f.text or "" for f in item if f.tag in allowed}
            name = (item.findtext("name") or "").strip()
            if name and frappe.db.exists(doctype, name):
                if update_existing:
                    doc = frappe.get_doc(doctype, name)
                    doc.update(data)
                    doc.save()
                    results["updated"] += 1
                else:
                    results["skipped"] += 1
            else:
                doc = frappe.new_doc(doctype)
                doc.update(data)
                doc.insert()
                results["imported"] += 1
        except Exception as e:
            frappe.db.rollback()
            results["errors"].append(f"#{position}: {str(e)[:200]}")
        if position % 100 == 0:
            frappe.db.commit()
    frappe.db.commit()

    summary = (
        f"{doctype}: thêm {results['imported']}, cập nhật {results['updated']}, "
        f"bỏ qua {results['skipped']}, lỗi {len(results['errors'])}"
    )
    try:
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"Nhập XML hoàn tất — {summary}",
            "email_content": "<br>".join(results["errors"][:50]) or summary,
            "for_user": frappe.session.user,
            "type": "Alert",
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        log_exception("XML Import", summary)
    return results
