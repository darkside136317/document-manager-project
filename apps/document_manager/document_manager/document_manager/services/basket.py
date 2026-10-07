# -*- coding: utf-8 -*-
"""The reader's "basket": a draft Usage Request / Copy Request kept on the server.

Adding a hồ sơ or văn bản from the search results puts it in the reader's open draft slip (one per
kind, created on first use). Submitting the slip is the normal workflow action, so everything
the request rules check (feature flags, readability of every row) still happens on save. Every
function acts as the signed-in reader: Frappe's own permissions apply, nothing is bypassed except
deleting an emptied draft, which readers cannot do through DocPerm.
"""

import frappe
from frappe import _

from document_manager.document_manager.permissions import get_reader_profile

TARGETS = {
    "usage": {"doctype": "Usage Request", "feature": "can_request_usage", "route": "/portal/phieu",
              "label": "phiếu yêu cầu sử dụng"},
    "copy": {"doctype": "Copy Request", "feature": "can_request_copy", "route": "/portal/sao-chep",
             "label": "phiếu sao chụp"},
}
KINDS = {"file": "Archival File", "document": "Archive Document"}


def _target(target: str) -> dict:
    if target not in TARGETS:
        frappe.throw(_("Loại phiếu không hợp lệ"), frappe.PermissionError)
    return TARGETS[target]


def _profile() -> str:
    profile = get_reader_profile()
    if not profile:
        frappe.throw(_("Tài khoản chưa có hồ sơ độc giả"), frappe.PermissionError)
    return profile


def _draft_name(profile: str, doctype: str) -> str | None:
    """The reader's open draft (docstatus 0), newest first."""
    rows = frappe.get_all(doctype, filters={"reader": profile, "docstatus": 0}, pluck="name",
                          order_by="modified desc", limit_page_length=1)
    return rows[0] if rows else None


def summary(profile: str | None = None) -> dict:
    """{usage: {name, count}, copy: {name, count}} — what the header badge shows."""
    profile = profile or get_reader_profile()
    out = {key: {"name": None, "count": 0, "route": spec["route"]} for key, spec in TARGETS.items()}
    if not profile:
        return out
    for key, spec in TARGETS.items():
        name = _draft_name(profile, spec["doctype"])
        if name:
            out[key]["name"] = name
            out[key]["count"] = frappe.db.count(f"{spec['doctype']} Item", {"parent": name, "parenttype": spec["doctype"]})
    return out


def _lock_reader(profile: str):
    """Serialise two quick clicks of the same reader so they cannot both create a draft."""
    frappe.db.sql("select name from `tabReader` where name = %s for update", profile)


def add_item(kind: str, name: str, target: str) -> dict:
    spec = _target(target)
    if kind not in KINDS:
        frappe.throw(_("Loại tài liệu không hợp lệ"))
    from document_manager.document_manager.permissions import assert_feature
    assert_feature(spec["feature"])
    profile = _profile()

    doctype = KINDS[kind]
    # One answer for "missing" and "not allowed", so names cannot be probed.
    if not name or not frappe.db.exists(doctype, name) or not frappe.has_permission(doctype, "read", doc=name):
        frappe.throw(_("Không tìm thấy hồ sơ/văn bản hoặc bạn không có quyền khai thác"), frappe.PermissionError)
    if kind == "document":
        row = {"archive_document": name, "archival_file": frappe.db.get_value("Archive Document", name, "archival_file")}
    else:
        row = {"archival_file": name}

    _lock_reader(profile)
    draft = _draft_name(profile, spec["doctype"])
    if draft:
        doc = frappe.get_doc(spec["doctype"], draft)
        if any((r.archival_file or "") == (row.get("archival_file") or "")
               and (r.archive_document or "") == (row.get("archive_document") or "") for r in doc.items):
            return {"added": False, "request": doc.name, "target": target, "count": len(doc.items),
                    "route": f"{spec['route']}/{doc.name}", "message": _("Đã có trong {0}").format(spec["label"])}
        doc.append("items", row)
        doc.save()
    else:
        doc = frappe.get_doc({"doctype": spec["doctype"], "items": [row]})
        doc.insert()
    return {"added": True, "request": doc.name, "target": target, "count": len(doc.items),
            "route": f"{spec['route']}/{doc.name}", "message": _("Đã thêm vào {0}").format(spec["label"])}


def _own_draft(doctype: str, name: str):
    """The draft slip `name`, only when it is the signed-in reader's and still editable."""
    if doctype not in {spec["doctype"] for spec in TARGETS.values()}:
        frappe.throw(_("Loại phiếu không hợp lệ"), frappe.PermissionError)
    profile = _profile()
    doc = frappe.get_doc(doctype, name)
    if doc.reader != profile or doc.docstatus != 0:
        frappe.throw(_("Không tìm thấy phiếu nháp"), frappe.PermissionError)
    return doc


def remove_item(doctype: str, name: str, row: str) -> dict:
    """Take one row out of the draft; the draft itself goes when its last row does."""
    doc = _own_draft(doctype, name)
    doc.set("items", [r for r in doc.items if r.name != row])
    if not doc.items:
        frappe.delete_doc(doctype, name, ignore_permissions=True)
        return {"request": None, "count": 0}
    doc.save()
    return {"request": doc.name, "count": len(doc.items)}


def discard_draft(doctype: str, name: str) -> dict:
    _own_draft(doctype, name)
    frappe.delete_doc(doctype, name, ignore_permissions=True)
    return {"request": None}
