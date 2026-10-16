"""Administrative field configuration and mode metadata for the digitization UI."""

import frappe
from frappe.utils import cint

from document_manager.document_manager.services import digitization_fields


@frappe.whitelist()
def configuration():
    return {"enabled": bool(cint(frappe.db.get_single_value("Document Manager Settings", "digitization_enabled"))),
            "fields": digitization_fields.list_config()}


@frappe.whitelist(methods=["POST"])
def save_field(doctype, fieldname, values):
    return digitization_fields.save_field_config(doctype, fieldname, frappe.parse_json(values))


@frappe.whitelist(methods=["POST"])
def add_field(doctype, fieldname, label, fieldtype="Data"):
    return digitization_fields.add_custom_field(doctype, fieldname, label, fieldtype)


@frappe.whitelist(methods=["POST"])
def remove_field(doctype, fieldname):
    return digitization_fields.remove_custom_field(doctype, fieldname)
