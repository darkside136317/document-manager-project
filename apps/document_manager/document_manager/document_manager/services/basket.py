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


def item_key(row) -> str:
    """"document:DOC-1" for a document, "file:AF-1" for a whole file: how the reader site tells what is in a draft."""
    return f"document:{row.get('archive_document')}" if row.get("archive_document") else f"file:{row.get('archival_file')}"


def summary(profile: str | None = None) -> dict:
    """{usage: {name, count, keys}, copy: {name, count, keys}}: the header badge, and which results are already in a draft."""
    profile = profile or get_reader_profile()
    out = {key: {"name": None, "count": 0, "keys": [], "route": spec["route"]} for key, spec in TARGETS.items()}
    if not profile:
        return out
    for key, spec in TARGETS.items():
        name = _draft_name(profile, spec["doctype"])
        if name:
            rows = frappe.get_all(f"{spec['doctype']} Item", filters={"parent": name, "parenttype": spec["doctype"]},
                                  fields=["archival_file", "archive_document"], parent_doctype=spec["doctype"])
            out[key].update(name=name, count=len(rows), keys=[item_key(r) for r in rows])
    return out


def _lock_reader(profile: str):
    """Serialise two quick clicks of the same reader so they cannot both create a draft."""
    frappe.db.sql("select name from `tabReader` where name = %s for update", profile)


def _result(doc, spec: dict, target: str, added: bool, message: str) -> dict:
    return {"added": added, "request": doc.name, "target": target, "count": len(doc.items),
            "keys": [item_key(r) for r in doc.items], "route": f"{spec['route']}/{doc.name}", "message": message}


def _row_for(kind: str, name: str) -> dict:
    """The slip row of a hồ sơ / văn bản the signed-in reader may read (one answer for missing and not allowed)."""
    if kind not in KINDS:
        frappe.throw(_("Loại tài liệu không hợp lệ"))
    doctype = KINDS[kind]
    if not name or not frappe.db.exists(doctype, name) or not frappe.has_permission(doctype, "read", doc=name):
        frappe.throw(_("Không tìm thấy hồ sơ/văn bản hoặc bạn không có quyền khai thác"), frappe.PermissionError)
    if kind == "document":
        return {"archive_document": name, "archival_file": frappe.db.get_value("Archive Document", name, "archival_file")}
    return {"archival_file": name}


def _add(profile: str, target: str, row: dict) -> dict:
    """Put `row` in the reader's draft of `target`, creating the draft when there is none.

    A document whose whole file is already in the draft is not added again; a whole file replaces the documents of it
    already chosen. The slip's own rules (the reader's rights, copies allowed) run when the draft is saved."""
    spec = _target(target)
    _lock_reader(profile)
    draft = _draft_name(profile, spec["doctype"])
    if not draft:
        doc = frappe.get_doc({"doctype": spec["doctype"], "items": [row]})
        doc.insert()
        return _result(doc, spec, target, True, _("Đã thêm vào {0}").format(spec["label"]))
    doc = frappe.get_doc(spec["doctype"], draft)
    file, document = row.get("archival_file") or "", row.get("archive_document") or ""
    for r in doc.items:
        if (r.archival_file or "") == file and (r.archive_document or "") == document:
            return _result(doc, spec, target, False, _("Đã có trong {0}").format(spec["label"]))
        if document and (r.archival_file or "") == file and not r.archive_document:
            return _result(doc, spec, target, False, _("Cả hồ sơ chứa văn bản này đã có trong {0}").format(spec["label"]))
    message = _("Đã thêm vào {0}").format(spec["label"])
    if not document:
        covered = [r for r in doc.items if r.archive_document and (r.archival_file or "") == file]
        if covered:
            doc.set("items", [r for r in doc.items if r not in covered])
            message = _("Đã thêm cả hồ sơ vào {0}, thay cho {1} văn bản đã chọn từ hồ sơ này").format(spec["label"], len(covered))
    doc.append("items", row)
    doc.save()
    return _result(doc, spec, target, True, message)


def add_item(kind: str, name: str, target: str) -> dict:
    spec = _target(target)
    from document_manager.document_manager.permissions import assert_feature
    assert_feature(spec["feature"])
    return _add(_profile(), target, _row_for(kind, name))


def move_item(doctype: str, name: str, row: str, target: str) -> dict:
    """Move one row of a draft to the reader's draft of the other kind (usage <-> copy), keeping its notes.
    Nothing moves when the other kind refuses it (copies not allowed, the function not granted)."""
    spec = _target(target)
    from document_manager.document_manager.permissions import assert_feature
    assert_feature(spec["feature"])
    source = _own_draft(doctype, name)
    if spec["doctype"] == doctype:
        frappe.throw(_("Hồ sơ, văn bản đã ở trong phiếu này"))
    moving = next((r for r in source.items if r.name == row), None)
    if not moving:
        frappe.throw(_("Không tìm thấy dòng trong phiếu nháp"))
    result = _add(source.reader, target, {"archival_file": moving.archival_file, "archive_document": moving.archive_document,
                                          "notes": moving.notes})
    left = remove_item(doctype, name, row)
    origin = next(key for key, value in TARGETS.items() if value["doctype"] == doctype)
    return {**result, "message": _("Đã chuyển sang {0}").format(spec["label"]),
            "source": {"target": origin, "request": left["request"], "count": left["count"], "keys": left["keys"]}}


# items of a sent slip that a new slip may start from
REUSABLE_ITEMS = ("Đã duyệt", "Đã giao", "Đã trả", "Đã hoàn thành")


def start_from(doctype: str, name: str, target: str) -> dict:
    """Put the items of one of the reader's slips into their draft of `target`: "Lập lại phiếu" (same kind) or
    "Xin sao chụp" (copies of what a usage slip gave). Items this reader may no longer use, or that cannot be copied,
    are left out and listed with the reason."""
    spec = _target(target)
    from document_manager.document_manager.permissions import assert_feature
    assert_feature(spec["feature"])
    if doctype not in {value["doctype"] for value in TARGETS.values()}:
        frappe.throw(_("Loại phiếu không hợp lệ"), frappe.PermissionError)
    profile = _profile()
    if not frappe.db.exists(doctype, name) or frappe.db.get_value(doctype, name, "reader") != profile:
        frappe.throw(_("Không tìm thấy phiếu"), frappe.PermissionError)
    source = frappe.get_doc(doctype, name)
    rows = source.items
    if spec["doctype"] != doctype and source.docstatus == 1:  # copies of what was granted, not of what was refused
        rows = [r for r in rows if r.get("item_status") in REUSABLE_ITEMS] or rows
    added, already, skipped, result = 0, 0, [], None
    for r in rows:
        title = r.get("document_title") or r.archive_document or r.archival_file
        frappe.db.savepoint("dm_start_from")
        try:
            kind = "document" if r.archive_document else "file"
            result = _add(profile, target, _row_for(kind, r.archive_document or r.archival_file))
            added += int(result["added"])
            already += int(not result["added"])
        except (frappe.ValidationError, frappe.PermissionError) as error:
            frappe.db.rollback(save_point="dm_start_from")
            frappe.clear_last_message()
            skipped.append({"title": title, "reason": _clean(error)})
    if result is None:
        draft = _draft_name(profile, spec["doctype"])
        result = _result(frappe.get_doc(spec["doctype"], draft), spec, target, False, "") if draft else \
            {"request": None, "count": 0, "keys": [], "route": spec["route"], "target": target}
    if added:
        message = _("Đã đưa {0} hồ sơ, văn bản vào {1}").format(added, spec["label"])
        if already:
            message += _("; {0} mục đã có sẵn trong phiếu").format(already)
    elif already:
        message = _("Các hồ sơ, văn bản này đã có sẵn trong {0}").format(spec["label"])
    else:
        message = _("Không có hồ sơ, văn bản nào đưa được vào {0}").format(spec["label"])
    return {**result, "added": added, "already": already, "skipped": skipped, "message": message}


def _clean(error) -> str:
    """A refusal as one line of plain text (server messages may carry HTML and line breaks)."""
    import re

    text = re.sub(r"<[^>]+>", "", str(error) or "").strip()
    return " ".join(text.split())[:200] or _("Không đưa được vào phiếu")


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
        return {"request": None, "count": 0, "keys": []}
    doc.save()
    return {"request": doc.name, "count": len(doc.items), "keys": [item_key(r) for r in doc.items]}


def discard_draft(doctype: str, name: str) -> dict:
    _own_draft(doctype, name)
    frappe.delete_doc(doctype, name, ignore_permissions=True)
    return {"request": None, "count": 0, "keys": []}
