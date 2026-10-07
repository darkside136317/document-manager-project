# -*- coding: utf-8 -*-
"""Back end of the generic staff screens: which DocTypes may be managed, and how to describe them.

`describe(doctype)` turns DocType metadata into what the SPA needs to draw a list, a form (layout
included) or a tree, already restricted to what the current user may read and write. Nothing here
bypasses permissions: it only reports them.
"""

import frappe
from frappe import _
from frappe.model import no_value_fields
from frappe.utils import cint

from document_manager.document_manager.constants import MASTER_BY_DOCTYPE, MASTERS

BREAKS = ("Section Break", "Column Break", "Tab Break")
# Field types the generic form can draw. Anything else (tables, attachments, ...) is left out
# until a dedicated screen needs it.
SUPPORTED = ("Data", "Int", "Float", "Check", "Select", "Date", "Datetime", "Small Text", "Text", "Long Text",
             "Text Editor", "Link", "Read Only")
HIDDEN_FIELDS = ("lft", "rgt", "old_parent")
MAX_LIST_COLUMNS = 6


def assert_master(doctype: str) -> None:
    """Only registered DocTypes are reachable through the generic API."""
    if doctype not in MASTER_BY_DOCTYPE:
        frappe.throw(_("Loại dữ liệu {0} không được quản lý ở màn hình này").format(doctype), frappe.PermissionError)


def permissions_of(doctype: str) -> dict:
    return {ptype: bool(frappe.has_permission(doctype, ptype)) for ptype in ("read", "create", "write", "delete")}


def parent_field_of(meta) -> str | None:
    if not meta.is_tree:
        return None
    return meta.get("nsm_parent_field") or f"parent_{frappe.scrub(meta.name)}"


def name_field_of(meta) -> str | None:
    """Field the record name is built from (`autoname = field:xxx`), if any."""
    autoname = meta.autoname or ""
    return autoname[len("field:"):] if autoname.startswith("field:") else None


def valid_columns(meta) -> set:
    return set(meta.get_valid_columns()) | {"name"}


def title_field_of(meta) -> str:
    return meta.title_field or name_field_of(meta) or "name"


def link_targets() -> set:
    """DocTypes a Link field of a registered screen points to (what `api.crud.link_search` may search)."""
    targets = set(MASTER_BY_DOCTYPE)
    for master in MASTERS:
        for df in frappe.get_meta(master["doctype"]).fields:
            if df.fieldtype == "Link" and df.options:
                targets.add(df.options)
    return targets


def _layout(fields) -> list:
    """Sections of columns of field names, from the Section / Column Break structure of the DocType."""
    sections, current = [], {"title": None, "collapsible": False, "columns": [[]]}

    def flush():
        if any(current["columns"]):
            sections.append({**current, "columns": [c for c in current["columns"] if c]})

    for df in fields:
        if df.fieldtype in ("Section Break", "Tab Break"):
            flush()
            current = {"title": df.label or None, "collapsible": bool(df.collapsible), "columns": [[]]}
        elif df.fieldtype == "Column Break":
            current["columns"].append([])
        elif df.fieldname:
            current["columns"][-1].append(df.fieldname)
    flush()
    return sections


def describe(doctype: str) -> dict:
    assert_master(doctype)
    meta = frappe.get_meta(doctype)
    perms = permissions_of(doctype)
    if not perms["read"]:
        frappe.throw(_("Bạn không có quyền xem {0}").format(_(doctype)), frappe.PermissionError)

    read_levels = meta.get_permlevel_access("read") or [0]
    write_levels = meta.get_permlevel_access("write") or []
    kept, fields = [], []
    for df in meta.fields:
        if df.fieldtype in BREAKS:
            kept.append(df)
            continue
        if df.fieldtype not in SUPPORTED or df.hidden or df.fieldname in HIDDEN_FIELDS:
            continue
        if cint(df.permlevel) not in read_levels:
            continue
        kept.append(df)
        fields.append({
            "fieldname": df.fieldname,
            "label": df.label or df.fieldname,
            "fieldtype": df.fieldtype,
            "options": df.options or "",
            "reqd": bool(df.reqd),
            "read_only": bool(df.read_only) or cint(df.permlevel) not in write_levels or bool(df.fetch_from),
            "unique": bool(df.unique),
            "description": df.description or "",
            "default": df.default,
            "in_list_view": bool(df.in_list_view),
            "in_standard_filter": bool(df.in_standard_filter),
            "depends_on": df.depends_on or "",
        })

    by_name = {f["fieldname"]: f for f in fields}
    list_fields = [f["fieldname"] for f in fields if f["in_list_view"]][:MAX_LIST_COLUMNS]
    if not list_fields:
        list_fields = [f["fieldname"] for f in fields if f["fieldtype"] not in no_value_fields][:4]
    title_field = title_field_of(meta)
    search_fields = [f.strip() for f in (meta.search_fields or "").split(",") if f.strip() in by_name]
    if not search_fields and title_field in by_name:
        search_fields = [title_field]

    master = MASTER_BY_DOCTYPE[doctype]
    return {
        "doctype": doctype,
        "label": master["label"],
        "slug": master["slug"],
        "title_field": title_field,
        "name_field": name_field_of(meta),
        "allow_rename": bool(meta.allow_rename),
        "is_tree": bool(meta.is_tree),
        "parent_field": parent_field_of(meta),
        "search_fields": search_fields,
        "list_fields": list_fields,
        "fields": fields,
        "layout": _layout(kept),
        "permissions": perms,
    }
