# -*- coding: utf-8 -*-
"""The exchange format: which levels of the archive travel as XML, which fields of each, and the XSD describing it.

The data is a tree that follows the archive: Phông (Fonds) > Khối tài liệu (Record Group) > Mục lục (Catalog) >
Hồ sơ (Archival File) > Văn bản (Archive Document). Nodes are matched on import by their business key inside
their parent (the code or number, else the title), never by the generated record name, so a file can move
between systems. Files (the scanned documents themselves) are not part of it: only the description of them.

    <ArchiveExchange version="1.0" exported_at="..." source="..." level="Archival File">
      <Fonds ref="true">                       <- ancestors of the exported level carry only their key fields
        <fonds_name>...</fonds_name> <fonds_code>...</fonds_code> <archival_agency>...</archival_agency>
        <RecordGroup ref="true"> ... <Catalog ref="true"> ... <ArchivalFile> <file_title>...</file_title> ...
"""

from dataclasses import dataclass

import frappe
from lxml import etree

VERSION = "1.0"
ROOT = "ArchiveExchange"
TEXT_LIMIT = 140  # Frappe's length of a Data field


@dataclass(frozen=True)
class Level:
    doctype: str
    element: str
    label: str
    parent_field: str | None  # Link field of this level to its parent
    link_field: str | None  # field of every deeper level that holds the name of a record of this level
    title: str
    code: str
    fields: tuple
    required: tuple  # what a record needs to be created: also what a "ref" ancestor carries


LEVELS = (
    Level("Fonds", "Fonds", "Phông", None, "fonds", "fonds_name", "fonds_code",
          ("fonds_name", "fonds_code", "archival_agency", "status", "start_year", "end_year", "total_shelf_meters",
           "total_boxes", "document_type_category", "document_group", "classification_scheme", "description", "history"),
          ("fonds_name", "fonds_code", "archival_agency")),
    Level("Record Group", "RecordGroup", "Khối tài liệu", "fonds", "record_group", "group_title", "group_code",
          ("group_title", "group_code", "status", "start_year", "end_year", "description"),
          ("group_title", "group_code")),
    Level("Catalog", "Catalog", "Mục lục", "record_group", "catalog", "catalog_title", "catalog_number",
          ("catalog_title", "catalog_number", "start_year", "end_year", "description"),
          ("catalog_title", "catalog_number")),
    Level("Archival File", "ArchivalFile", "Hồ sơ", "catalog", "archival_file", "file_title", "file_number",
          ("file_title", "file_number", "status", "start_date", "end_date", "total_pages", "confidentiality_level",
           "document_type_category", "document_group", "classification_scheme", "storage_warehouse", "shelf_number",
           "box_number", "physical_location", "description", "retention_years", "disposal_status", "notes"),
          ("file_title", "file_number")),
    Level("Archive Document", "ArchiveDocument", "Văn bản", "archival_file", None, "document_title", "document_number",
          ("document_title", "document_number", "document_date", "author", "page_count", "description",
           "confidentiality_level"),
          ("document_title", "document_number")),
)
BY_DOCTYPE = {level.doctype: level for level in LEVELS}
BY_ELEMENT = {level.element: level for level in LEVELS}


def index_of(doctype: str) -> int:
    if doctype not in BY_DOCTYPE:
        frappe.throw(frappe._("Không hỗ trợ trao đổi XML cho {0}").format(doctype))
    return LEVELS.index(BY_DOCTYPE[doctype])


def identity_fields(level: Level) -> tuple:
    """The business key of a record: its code (when it has one) and its title."""
    return (level.title, level.code)


# --- field descriptions (read from the DocType, so labels and options never drift from the form) --------------------

def kind_of(df) -> str:
    return {"Int": "int", "Float": "float", "Date": "date", "Select": "select", "Link": "link", "Check": "check",
            "Small Text": "text", "Text": "text", "Text Editor": "text", "Long Text": "text"}.get(df.fieldtype, "string")


def field_specs(level: Level) -> list[dict]:
    meta = frappe.get_meta(level.doctype)
    out = []
    for name in level.fields:
        df = meta.get_field(name)
        options = [o for o in (df.options or "").split("\n")] if df.fieldtype == "Select" else (
            df.options if df.fieldtype == "Link" else None)
        out.append({"fieldname": name, "label": df.label or name, "kind": kind_of(df), "options": options,
                    "required": name in level.required, "key": name in identity_fields(level)})
    return out


def describe() -> list[dict]:
    """What the screens need to offer the choice of fields: levels top-down, each with its fields."""
    return [{"doctype": level.doctype, "element": level.element, "label": level.label,
             "fields": field_specs(level)} for level in LEVELS]


# --- XSD ------------------------------------------------------------------------------------------------------------

XS = "http://www.w3.org/2001/XMLSchema"


def _xs(tag: str, **attrs) -> etree._Element:
    return etree.Element(f"{{{XS}}}{tag}", **{k: str(v) for k, v in attrs.items()})


def _pattern(name: str, regex: str) -> etree._Element:
    simple = _xs("simpleType", name=name)
    restriction = etree.SubElement(simple, f"{{{XS}}}restriction", base="xs:string")
    etree.SubElement(restriction, f"{{{XS}}}pattern", value=regex)
    return simple


def _field_type(spec: dict) -> tuple[str, etree._Element | None]:
    """(type name, inline simple type when the field needs its own) of a field element."""
    kind = spec["kind"]
    if kind == "int":
        return "OptionalInt", None
    if kind == "float":
        return "OptionalFloat", None
    if kind == "date":
        return "OptionalDate", None
    if kind == "text":
        return "LongText", None
    if kind == "select":
        simple = _xs("simpleType")
        restriction = etree.SubElement(simple, f"{{{XS}}}restriction", base="xs:string")
        for option in dict.fromkeys(["", *(spec["options"] or [])]):  # an empty element means "no value"
            etree.SubElement(restriction, f"{{{XS}}}enumeration", value=option)
        return "", simple
    return "ShortText", None


def build_xsd() -> bytes:
    """The XSD of the exchange file, generated from the field lists above (same one the importer validates with)."""
    schema = etree.Element(f"{{{XS}}}schema", nsmap={"xs": XS}, elementFormDefault="unqualified")
    short = _xs("simpleType", name="ShortText")
    restriction = etree.SubElement(short, f"{{{XS}}}restriction", base="xs:string")
    etree.SubElement(restriction, f"{{{XS}}}maxLength", value=str(TEXT_LIMIT))
    schema.append(short)
    long = _xs("simpleType", name="LongText")
    etree.SubElement(long, f"{{{XS}}}restriction", base="xs:string")
    schema.append(long)
    schema.append(_pattern("OptionalInt", r"(-?[0-9]{1,10})?"))
    schema.append(_pattern("OptionalFloat", r"(-?[0-9]+(\.[0-9]+)?)?"))
    schema.append(_pattern("OptionalDate", r"([0-9]{4}-[0-9]{2}-[0-9]{2})?"))

    for index, level in enumerate(LEVELS):
        complex_type = _xs("complexType", name=f"{level.element}Type")
        sequence = etree.SubElement(complex_type, f"{{{XS}}}sequence")
        for spec in field_specs(level):
            type_name, inline = _field_type(spec)
            element = etree.SubElement(sequence, f"{{{XS}}}element", name=spec["fieldname"], minOccurs="0")
            if inline is not None:
                element.append(inline)
            else:
                element.set("type", type_name)
        if index + 1 < len(LEVELS):
            child = LEVELS[index + 1]
            etree.SubElement(sequence, f"{{{XS}}}element", name=child.element, type=f"{child.element}Type",
                             minOccurs="0", maxOccurs="unbounded")
        etree.SubElement(complex_type, f"{{{XS}}}attribute", name="ref", type="xs:boolean")
        schema.append(complex_type)

    root = etree.SubElement(schema, f"{{{XS}}}element", name=ROOT)
    complex_type = etree.SubElement(root, f"{{{XS}}}complexType")
    sequence = etree.SubElement(complex_type, f"{{{XS}}}sequence")
    etree.SubElement(sequence, f"{{{XS}}}element", name=LEVELS[0].element, type=f"{LEVELS[0].element}Type",
                     minOccurs="0", maxOccurs="unbounded")
    etree.SubElement(complex_type, f"{{{XS}}}attribute", name="version", type="xs:string", use="required")
    for name in ("exported_at", "source", "level"):
        etree.SubElement(complex_type, f"{{{XS}}}attribute", name=name, type="xs:string")
    return etree.tostring(schema, xml_declaration=True, encoding="UTF-8", pretty_print=True)


_compiled = {}


def validator() -> etree.XMLSchema:
    """The compiled schema (rebuilt when the select options of a DocType change, i.e. per process and site)."""
    key = frappe.local.site
    if key not in _compiled:
        _compiled[key] = etree.XMLSchema(etree.fromstring(build_xsd()))
    return _compiled[key]
