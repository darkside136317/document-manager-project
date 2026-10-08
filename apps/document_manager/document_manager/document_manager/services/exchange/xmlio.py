# -*- coding: utf-8 -*-
"""Reading untrusted exchange files safely, validating them against the XSD, and writing them as a stream."""

import re

import frappe
from frappe import _
from lxml import etree

from document_manager.document_manager.services.exchange import schema

MAX_BYTES = 50 * 1024 * 1024
MAX_NODES = 100_000
MAX_ERRORS = 50
_DTD = re.compile(rb"<!\s*(DOCTYPE|ENTITY|ELEMENT|ATTLIST)", re.IGNORECASE)
_ENCODING = re.compile(rb"^\s*<\?xml[^>]*encoding\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")


# --- reading --------------------------------------------------------------------------------------------------------

def parse(content: bytes) -> etree._Element:
    """Parse an uploaded file. Refuses what is not our own UTF-8 XML without any DTD: no entity can be declared,
    so there is nothing to expand (entity bombs, external entities) and nothing is ever fetched from the network."""
    if not content or not content.strip():
        frappe.throw(_("Tệp XML trống"))
    if len(content) > MAX_BYTES:
        frappe.throw(_("Tệp XML lớn hơn {0} MB").format(MAX_BYTES // 1024 // 1024))
    if content.startswith((b"\xff\xfe", b"\xfe\xff", b"\x00<", b"<\x00")):
        frappe.throw(_("Chỉ nhận tệp XML mã hóa UTF-8"))
    declared = _ENCODING.match(content[:300])
    if declared and declared.group(1).decode("ascii", "ignore").lower().replace("_", "-") not in ("utf-8", "utf8"):
        frappe.throw(_("Chỉ nhận tệp XML mã hóa UTF-8"))
    if _DTD.search(content):
        frappe.throw(_("XML không được chứa khai báo DOCTYPE, ENTITY"))
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, dtd_validation=False,
                             huge_tree=False, remove_comments=True, remove_pis=True)
    try:
        root = etree.fromstring(content, parser)
    except etree.XMLSyntaxError as e:
        frappe.throw(_("XML không hợp lệ: {0}").format(str(e)[:200]))
    docinfo = root.getroottree().docinfo
    if docinfo.doctype or docinfo.internalDTD is not None or docinfo.externalDTD is not None:
        frappe.throw(_("XML không được chứa khai báo DOCTYPE, ENTITY"))
    if root.tag != schema.ROOT:
        frappe.throw(_("Không phải tệp trao đổi dữ liệu lưu trữ (phần tử gốc phải là {0})").format(schema.ROOT))
    return root


def validate(root: etree._Element) -> list[str]:
    """Violations of the XSD, with line numbers (first 50); empty when the file is valid."""
    xsd = schema.validator()
    if xsd.validate(root):
        return []
    return [f"Dòng {e.line}: {e.message}" for e in list(xsd.error_log)[:MAX_ERRORS]]


def values_of(element: etree._Element, level: schema.Level) -> dict:
    """{field: text} of the field elements the node carries (an empty element is an empty value)."""
    out = {}
    for child in element:
        if child.tag in level.fields:
            out[child.tag] = (child.text or "").strip()
    return out


def children_of(element: etree._Element, index: int) -> list:
    if index + 1 >= len(schema.LEVELS):
        return []
    tag = schema.LEVELS[index + 1].element
    return [child for child in element if child.tag == tag]


def is_ref(element: etree._Element) -> bool:
    return (element.get("ref") or "").lower() in ("true", "1")


def key_of(level: schema.Level, values: dict) -> str:
    return values.get(level.code) or values.get(level.title) or ""


def walk(root: etree._Element):
    """Yield (level index, element, node id, parent id) depth-first in document order (ids are running numbers)."""
    stack = [(0, child, 0) for child in reversed(list(root)) if child.tag == schema.LEVELS[0].element]
    counter = 0
    while stack:
        index, element, parent_id = stack.pop()
        counter += 1
        yield index, element, counter, parent_id
        stack.extend((index + 1, child, counter) for child in reversed(children_of(element, index)))


def analyze(root: etree._Element) -> dict:
    """What the file contains, for the user to look at before importing."""
    counts = {level.doctype: {"nodes": 0, "ref": 0} for level in schema.LEVELS}
    found = {level.doctype: {} for level in schema.LEVELS}
    warnings, total = [], 0
    seen = {}
    for index, element, _node, parent_id in walk(root):
        level = schema.LEVELS[index]
        total += 1
        if total > MAX_NODES:
            frappe.throw(_("Tệp có hơn {0} bản ghi, hãy tách thành nhiều tệp").format(f"{MAX_NODES:,}".replace(",", ".")))
        counts[level.doctype]["nodes"] += 1
        if is_ref(element):
            counts[level.doctype]["ref"] += 1
        values = values_of(element, level)
        for name in values:
            found[level.doctype][name] = found[level.doctype].get(name, 0) + 1
        if not values.get(level.title):
            if len(warnings) < MAX_ERRORS:
                warnings.append(f"{level.label}: có bản ghi không có {level.title}")
            continue
        if not is_ref(element):
            twin = (parent_id, level.doctype, key_of(level, values))
            if twin in seen and len(warnings) < MAX_ERRORS:
                warnings.append(f"{level.label} “{key_of(level, values)}” xuất hiện nhiều lần trong cùng một cấp cha")
            seen[twin] = True
    return {"counts": counts, "fields": found, "total": total, "warnings": warnings,
            "attributes": {k: root.get(k) or "" for k in ("version", "exported_at", "source", "level")}}


# --- writing --------------------------------------------------------------------------------------------------------

def clean(value) -> str:
    return _ILLEGAL.sub("", "" if value is None else str(value))


def write(path: str, attributes: dict, roots: list) -> None:
    """Stream the tree of nodes ({ref, values, children}) to `path`; memory stays bounded by one node's text."""
    with open(path, "wb") as handle, etree.xmlfile(handle, encoding="utf-8") as xf:
        xf.write_declaration()
        with xf.element(schema.ROOT, attrib={k: clean(v) for k, v in attributes.items() if v not in (None, "")}):
            for node in roots:
                _emit(xf, 0, node, 1)
            xf.write("\n")


def _emit(xf, index: int, node: dict, depth: int) -> None:
    level = schema.LEVELS[index]
    pad = "\n" + "  " * depth
    xf.write(pad)
    with xf.element(level.element, attrib={"ref": "true"} if node.get("ref") else {}):
        for name in level.fields:
            if name in node["values"]:
                xf.write(pad + "  ")
                element = etree.Element(name)
                element.text = clean(node["values"][name])
                xf.write(element)
        for child in node.get("children", ()):
            _emit(xf, index + 1, child, depth + 1)
        xf.write(pad)
