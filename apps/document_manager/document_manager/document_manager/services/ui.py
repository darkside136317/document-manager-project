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

from document_manager.document_manager.constants import REGISTRY
from document_manager.document_manager.permissions import is_staff

BREAKS = ("Section Break", "Column Break", "Tab Break")
# Field types the generic form can draw. Anything else (tables, attachments, ...) is left out
# until a dedicated screen needs it.
SUPPORTED = ("Data", "Int", "Float", "Check", "Select", "Date", "Datetime", "Small Text", "Text", "Long Text",
             "Text Editor", "Link", "Read Only", "Table")
# Column types of a child table the grid can edit.
CELL_TYPES = ("Data", "Int", "Float", "Check", "Select", "Link", "Date", "Small Text")
MAX_TABLE_ROWS = 200
# Never offered by the generic link search, whatever a registered form links to.
NEVER_SEARCHABLE = {"User", "Role", "DocType"}
HIDDEN_FIELDS = ("lft", "rgt", "old_parent")
MAX_LIST_COLUMNS = 6


def assert_staff() -> None:
    """The generic API belongs to the staff app: Frappe's own permissions would also let a reader read their record."""
    if not is_staff():
        frappe.throw(_("Chỉ cán bộ mới dùng được chức năng này"), frappe.PermissionError)


def assert_master(doctype: str) -> None:
    """Only registered DocTypes are reachable through the generic API, and only by the staff."""
    assert_staff()
    if doctype not in REGISTRY:
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
    targets = set(REGISTRY)
    for entry in REGISTRY.values():
        for df in frappe.get_meta(entry["doctype"]).fields:
            if df.fieldtype == "Link" and df.options:
                targets.add(df.options)
            elif df.fieldtype == "Table" and df.options:  # a Link inside a child table (the fonds of a reader group)
                targets.update(c.options for c in frappe.get_meta(df.options).fields if c.fieldtype == "Link" and c.options)
    return targets - NEVER_SEARCHABLE


def table_columns(child_doctype: str) -> list[dict]:
    """The editable columns of a child table, as the grid shows them."""
    columns = []
    for df in frappe.get_meta(child_doctype).fields:
        if df.fieldtype not in CELL_TYPES or df.hidden:
            continue
        columns.append({"fieldname": df.fieldname, "label": df.label or df.fieldname, "fieldtype": df.fieldtype,
                        "options": df.options or "", "reqd": bool(df.reqd), "read_only": bool(df.read_only) or bool(df.fetch_from),
                        "default": df.default, "description": df.description or ""})
    return columns


def _layout(fields) -> list:
    """Sections of columns of field names, from the Section / Column Break structure of the DocType."""
    sections, current = [], {"title": None, "collapsible": False, "depends_on": "", "columns": [[]]}

    def flush():
        if any(current["columns"]):
            sections.append({**current, "columns": [c for c in current["columns"] if c]})

    for df in fields:
        if df.fieldtype in ("Section Break", "Tab Break"):
            flush()
            current = {"title": df.label or None, "collapsible": bool(df.collapsible), "depends_on": df.depends_on or "",
                       "columns": [[]]}
        elif df.fieldtype == "Column Break":
            current["columns"].append([])
        elif df.fieldname:
            current["columns"][-1].append(df.fieldname)
    flush()
    return sections


def _suggestions(entry: dict) -> dict:
    """{field: dictionary type} for the fields whose registry entry names a quick-entry dictionary
    the user can read (the dictionary may not exist yet: then there is simply nothing to suggest)."""
    wanted = entry.get("suggest") or {}
    if not wanted or not frappe.has_permission("Quick Entry Dictionary", "read"):
        return {}
    return {field: kind for field, kind in wanted.items() if frappe.db.exists("Dictionary Type", kind)}


def describe(doctype: str) -> dict:
    assert_master(doctype)
    entry = REGISTRY[doctype]
    meta = frappe.get_meta(doctype)
    perms = permissions_of(doctype)
    if not perms["read"]:
        frappe.throw(_("Bạn không có quyền xem {0}").format(_(doctype)), frappe.PermissionError)

    read_levels = meta.get_permlevel_access("read") or [0]
    write_levels = meta.get_permlevel_access("write") or []
    hidden = set(entry.get("hide") or ())
    readonly = set(entry.get("readonly") or ())  # fields the screen shows but never edits (managed by an action)
    suggest = _suggestions(entry)
    kept, fields = [], []
    for df in meta.fields:
        if df.fieldtype in BREAKS:
            kept.append(df)
            continue
        if df.fieldtype not in SUPPORTED or df.hidden or df.fieldname in HIDDEN_FIELDS or df.fieldname in hidden:
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
            "read_only": bool(df.read_only) or cint(df.permlevel) not in write_levels or bool(df.fetch_from)
            or df.fieldname in readonly,
            "unique": bool(df.unique),
            "description": df.description or "",
            "default": df.default,
            "in_list_view": bool(df.in_list_view),
            "in_standard_filter": bool(df.in_standard_filter),
            "depends_on": df.depends_on or "",
            "suggest": suggest.get(df.fieldname, ""),
            **({"table": {"doctype": df.options, "columns": table_columns(df.options)}} if df.fieldtype == "Table" else {}),
        })

    by_name = {f["fieldname"]: f for f in fields}
    configured = [f for f in (entry.get("list_fields") or []) if f in valid_columns(meta)]
    list_fields = configured or [f["fieldname"] for f in fields if f["in_list_view"]][:MAX_LIST_COLUMNS]
    if not list_fields:
        list_fields = [f["fieldname"] for f in fields if f["fieldtype"] not in no_value_fields][:4]
    # Columns may include fields the form hides (size, index status): describe them from the raw meta.
    columns = []
    for name in list_fields:
        df = meta.get_field(name)
        columns.append({"fieldname": name, "label": (df.label if df else None) or name,
                        "fieldtype": df.fieldtype if df else "Data"})
    title_field = title_field_of(meta)
    search_fields = [f.strip() for f in (meta.search_fields or "").split(",") if f.strip() in valid_columns(meta)]
    if not search_fields and title_field in valid_columns(meta):
        search_fields = [title_field]

    return {
        "doctype": doctype,
        "label": entry["label"],
        "slug": entry["slug"],
        "title_field": title_field,
        "name_field": name_field_of(meta),
        "allow_rename": bool(meta.allow_rename),
        "is_tree": bool(meta.is_tree),
        "is_single": bool(meta.issingle),
        "parent_field": parent_field_of(meta),
        "search_fields": search_fields,
        "list_fields": list_fields,
        "columns": columns,
        "fields": fields,
        "layout": _layout(kept),
        "permissions": perms,
    }
