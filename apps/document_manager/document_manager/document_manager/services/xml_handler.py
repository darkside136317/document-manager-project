# -*- coding: utf-8 -*-
"""XML Export/Import service for archival data.

Supports exporting/importing archival files and documents in XML format
following Vietnamese archival standards. Large datasets use batch processing
via Redis Queue to avoid request timeouts.
"""

import io
import xml.etree.ElementTree as ET
from xml.dom import minidom

import frappe
from frappe import _


@frappe.whitelist()
def export_xml(doctype, filters=None, fields=None):
    """Export documents as XML.

    Args:
        doctype: Doctype to export (Archival File, Archive Document, etc.)
        filters: JSON string of filters
        fields: JSON string of field names to include

    Returns:
        dict: {xml_content: str, count: int}
    """
    import json

    if isinstance(filters, str):
        filters = json.loads(filters) if filters else {}
    if isinstance(fields, str):
        fields = json.loads(fields) if fields else None

    if doctype not in ("Archival File", "Archive Document", "Fonds", "Record Group", "Catalog"):
        frappe.throw(f"Không hỗ trợ xuất XML cho {doctype}")

    all_fields = fields or _get_default_fields(doctype)
    data = frappe.get_all(doctype, filters=filters, fields=all_fields, limit_page_length=0)

    root = ET.Element("ArchivalData")
    root.set("doctype", doctype)
    root.set("exported_at", str(frappe.utils.now()))
    root.set("count", str(len(data)))

    for row in data:
        item = ET.SubElement(root, doctype.replace(" ", ""))
        for key, value in row.items():
            field_el = ET.SubElement(item, key)
            field_el.text = str(value) if value is not None else ""

    xml_str = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
    return {"xml_content": xml_str, "count": len(data)}


@frappe.whitelist()
def import_xml(xml_content, doctype, update_existing=False):
    """Import documents from XML.

    Args:
        xml_content: XML string
        doctype: Target Doctype
        update_existing: If True, update existing records; else skip duplicates

    Returns:
        dict: {imported: int, skipped: int, errors: list}
    """
    if doctype not in ("Archival File", "Archive Document", "Fonds", "Record Group", "Catalog"):
        frappe.throw(f"Không hỗ trợ nhập XML cho {doctype}")

    # Enqueue for large imports
    frappe.enqueue(
        "document_manager.document_manager.services.xml_handler._import_xml_worker",
        xml_content=xml_content,
        doctype=doctype,
        update_existing=update_existing,
        queue="long",
        timeout=600,
    )
    return {"status": "queued", "message": "Import đang được xử lý trong background. Kiểm tra log để xem kết quả."}


def _import_xml_worker(xml_content, doctype, update_existing=False):
    """Background worker for XML import."""
    results = {"imported": 0, "skipped": 0, "errors": []}

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        frappe.log_error(f"XML parse error: {e}", "XML Import Error")
        return

    for item in root:
        try:
            data = {}
            for field in item:
                data[field.tag] = field.text or ""

            name = data.pop("name", None)
            if name and frappe.db.exists(doctype, name):
                if update_existing:
                    doc = frappe.get_doc(doctype, name)
                    doc.update(data)
                    doc.save(ignore_permissions=True)
                    results["imported"] += 1
                else:
                    results["skipped"] += 1
            else:
                doc = frappe.new_doc(doctype)
                doc.update(data)
                doc.insert(ignore_permissions=True)
                results["imported"] += 1

        except Exception as e:
            results["errors"].append(str(e))

        if results["imported"] % 100 == 0:
            frappe.db.commit()

    frappe.db.commit()
    frappe.logger().info(
        f"XML Import complete: {results['imported']} imported, "
        f"{results['skipped']} skipped, {len(results['errors'])} errors"
    )


def _get_default_fields(doctype):
    """Get default export fields for a doctype."""
    defaults = {
        "Fonds": ["name", "fonds_name", "fonds_code", "archival_agency", "start_year", "end_year", "status"],
        "Record Group": ["name", "group_title", "group_code", "fonds", "start_year", "end_year"],
        "Catalog": ["name", "catalog_title", "catalog_number", "record_group", "fonds"],
        "Archival File": ["name", "file_title", "file_number", "catalog", "record_group", "fonds",
                          "confidentiality_level", "storage_warehouse", "status", "start_date", "end_date"],
        "Archive Document": ["name", "document_title", "document_number", "archival_file", "fonds",
                             "file_type", "document_date", "author", "confidentiality_level"],
    }
    return defaults.get(doctype, ["name"])
