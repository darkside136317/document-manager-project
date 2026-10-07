# -*- coding: utf-8 -*-
"""Generic list / get / save / delete / link search / tree API of the staff screens.

Thin on purpose: it only resolves the registered DocType, validates the request shape and hands
over to Frappe (`get_list`, `get_doc().save()`, `delete_doc`) so permissions, validation, naming,
nested-set maintenance and link checks are exactly Frappe's. Only DocTypes in `constants.MASTERS`
are reachable.
"""

import frappe
from frappe import _
from frappe.utils import cint

from document_manager.document_manager.services.ui import (
    assert_master,
    describe,
    link_targets,
    title_field_of,
    valid_columns,
)

MAX_PAGE_SIZE = 200
ALLOWED_OPS = {"=", "!=", "like", "not like", ">", "<", ">=", "<=", "in", "not in", "is"}
RECORD_KEYS = ("name", "modified", "creation", "owner", "modified_by")


def _parse(value, default):
    if value in (None, ""):
        return default
    return frappe.parse_json(value) if isinstance(value, str) else value


def _filters(meta, raw) -> list:
    """`{field: value}` or `{field: [op, value]}` -> Frappe filter triples, columns checked."""
    columns = valid_columns(meta)
    out = []
    for field, value in (_parse(raw, {}) or {}).items():
        if field not in columns:
            frappe.throw(_("Không lọc được theo trường {0}").format(field))
        if isinstance(value, (list, tuple)) and len(value) == 2:
            op = str(value[0]).lower()
            if op not in ALLOWED_OPS:
                frappe.throw(_("Phép so sánh {0} không hợp lệ").format(op))
            out.append([meta.name, field, op, value[1]])
        else:
            out.append([meta.name, field, "=", value])
    return out


def _order_by(meta, order_by) -> str:
    if not order_by:
        return "modified desc"
    field, _sep, direction = str(order_by).strip().partition(" ")
    direction = (direction or "asc").lower()
    if field not in valid_columns(meta) or direction not in ("asc", "desc"):
        frappe.throw(_("Cách sắp xếp không hợp lệ"))
    return f"{field} {direction}"


def _count(doctype, filters, or_filters=None) -> int:
    rows = frappe.get_list(doctype, filters=filters, or_filters=or_filters, fields=[{"COUNT": "name", "as": "c"}])
    return rows[0].c if rows else 0


@frappe.whitelist()
def get_list(doctype, search=None, filters=None, order_by=None, page=1, page_size=20):
    """One page of records: {data, total, page, page_size}."""
    info = describe(doctype)  # also checks the registry and read permission
    meta = frappe.get_meta(doctype)
    page = max(1, cint(page) or 1)
    page_size = min(MAX_PAGE_SIZE, max(1, cint(page_size) or 20))

    fields = ["name", "modified", *[f for f in info["list_fields"] if f != "name"]]
    if info["is_tree"]:
        fields += [f for f in (info["parent_field"], "is_group") if f and f not in fields and f in valid_columns(meta)]
    conditions = _filters(meta, filters)
    or_conditions = None
    search = (search or "").strip()
    if search:
        columns = ["name", *info["search_fields"]]
        or_conditions = [[doctype, c, "like", f"%{search}%"] for c in dict.fromkeys(columns)]

    data = frappe.get_list(
        doctype, fields=fields, filters=conditions, or_filters=or_conditions,
        order_by=_order_by(meta, order_by), start=(page - 1) * page_size, page_length=page_size,
    )
    return {"data": data, "total": _count(doctype, conditions, or_conditions), "page": page, "page_size": page_size}


def _record(doc, info) -> dict:
    doc.apply_fieldlevel_read_permissions()
    keys = [*RECORD_KEYS, *(f["fieldname"] for f in info["fields"])]
    return {k: doc.get(k) for k in dict.fromkeys(keys)}


@frappe.whitelist()
def get(doctype, name):
    info = describe(doctype)
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    return _record(doc, info)


@frappe.whitelist(methods=["POST"])
def save(doctype, values, name=None):
    """Create (no `name`) or update a record; only fields the user may write are applied.

    Send back the `modified` you loaded: a concurrent edit is then reported instead of overwritten.
    """
    info = describe(doctype)
    values = _parse(values, {})
    writable = {f["fieldname"] for f in info["fields"] if not f["read_only"]}
    if name:
        doc = frappe.get_doc(doctype, name)
        doc.check_permission("write")
        if values.get("modified"):
            doc.modified = values["modified"]  # Frappe compares it with the database value on save
        # the name of a record built from a field never changes by editing that field
        writable.discard(info["name_field"] or "")
    else:
        doc = frappe.new_doc(doctype)
        doc.check_permission("create")
    for field in writable:
        if field in values:
            doc.set(field, values[field])
    doc.save() if name else doc.insert()
    return _record(frappe.get_doc(doctype, doc.name), info)


@frappe.whitelist(methods=["POST"])
def delete(doctype, name):
    """Delete one record. Frappe refuses (with the list of links) while other records still use it."""
    assert_master(doctype)
    frappe.delete_doc(doctype, name)
    return {"name": name}


@frappe.whitelist()
def link_search(doctype, txt="", filters=None, limit=10):
    """Options of a Link field: [{value, label, description}]."""
    if doctype not in link_targets():
        frappe.throw(_("Không tìm kiếm được trong {0}").format(doctype), frappe.PermissionError)
    meta = frappe.get_meta(doctype)
    title = title_field_of(meta)
    fields = ["name"] + ([title] if title != "name" else [])
    txt = (txt or "").strip()
    or_filters = [[doctype, c, "like", f"%{txt}%"] for c in fields] if txt else None
    rows = frappe.get_list(
        doctype, fields=fields, filters=_filters(meta, filters), or_filters=or_filters,
        order_by=f"{title} asc", page_length=min(50, max(1, cint(limit) or 10)),
    )
    return [{"value": r.name, "label": r.get(title) or r.name,
             "description": r.name if (r.get(title) or r.name) != r.name else ""} for r in rows]


@frappe.whitelist()
def tree_children(doctype, parent=None, filters=None):
    """Children of `parent` (roots when empty) of a tree DocType, with their own child counts."""
    info = describe(doctype)
    if not info["is_tree"]:
        frappe.throw(_("{0} không phải danh mục dạng cây").format(doctype))
    meta = frappe.get_meta(doctype)
    parent_field = info["parent_field"]
    conditions = _filters(meta, filters)
    conditions.append([doctype, parent_field, "=", parent] if parent else [doctype, parent_field, "is", "not set"])

    fields = ["name", "modified", parent_field, *[f for f in info["list_fields"] if f != "name"]]
    if "is_group" in valid_columns(meta):
        fields.append("is_group")
    rows = frappe.get_list(doctype, fields=list(dict.fromkeys(fields)), filters=conditions,
                           order_by=f"{title_field_of(meta)} asc", page_length=1000)
    if rows:
        counts = frappe.get_list(
            doctype, fields=[parent_field, {"COUNT": "name", "as": "c"}],
            filters=[[doctype, parent_field, "in", [r.name for r in rows]]], group_by=parent_field,
        )
        by_parent = {c.get(parent_field): c.c for c in counts}
        for row in rows:
            row["child_count"] = by_parent.get(row.name, 0)
    return rows
