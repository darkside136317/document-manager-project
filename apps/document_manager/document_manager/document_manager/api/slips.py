# -*- coding: utf-8 -*-
"""Whitelisted API of the staff queue of reader slips (phiếu yêu cầu sử dụng, phiếu sao chụp).

For the reading room, the leaders and Document Admin; readers use `api.requests` / `api.basket`.
State changes of the workflow itself still go through `api.requests.apply_action`; this module adds
what the queue screens need around it: the lists with their counters, the full slip with its items,
the per-item decisions, the return with the condition of each item, renewals and the timeline.
"""

import json

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow, get_transitions
from frappe.utils import cint, format_date, getdate, nowdate

from document_manager.document_manager.api.archive import print_urls
from document_manager.document_manager.permissions import assert_roles
from document_manager.document_manager.policy import get_limits
from document_manager.document_manager.services import lifecycle as lc
from document_manager.document_manager.services.audit import log_activity
from document_manager.document_manager.services.notify import SLIP_KINDS, notify_user

KINDS = {"usage": lc.USAGE, "copy": lc.COPY}
STAFF = ("Reading Room Officer", "Archive Leader", "Document Admin")
OFFICERS = ("Reading Room Officer", "Document Admin")
LEADERS = ("Archive Leader", "Document Admin")
PAGE_SIZE = 20

# view -> (label, filters). Counters are computed for every view of a kind.
VIEWS = {
    "cho_tiep_nhan": ("Chờ tiếp nhận", {"workflow_state": lc.STATE_PENDING, "docstatus": 1}),
    "cho_lanh_dao": ("Chờ lãnh đạo duyệt", {"workflow_state": lc.STATE_LEADER, "docstatus": 1}),
    "cho_thuc_hien": ("Đã duyệt", {"workflow_state": lc.STATE_APPROVED, "docstatus": 1}),
    "dang_su_dung": ("Đang sử dụng", {"workflow_state": lc.STATE_IN_USE, "docstatus": 1}),
    "qua_han": ("Quá hạn", {"workflow_state": lc.STATE_IN_USE, "docstatus": 1, "is_overdue": 1}),
    "da_dong": ("Đã đóng", {"workflow_state": ["in", [lc.STATE_RETURNED, lc.STATE_COMPLETED, lc.STATE_REJECTED, lc.STATE_CANCELLED]],
                            "docstatus": 1}),
    "nhap": ("Nháp", {"docstatus": 0}),
    "tat_ca": ("Tất cả", {}),
}
# the copy slip has no "in use" stage
VIEWS_OF = {"usage": list(VIEWS), "copy": [v for v in VIEWS if v not in ("dang_su_dung", "qua_han")]}
LIST_FIELDS = ["name", "reader", "reader_name", "workflow_state", "docstatus", "request_date", "submitted_on", "purpose",
               "requires_leader", "modified"]
USAGE_FIELDS = ["due_date", "is_overdue", "renewal_count"]


def _doctype(kind: str) -> str:
    if kind not in KINDS:
        frappe.throw(_("Loại phiếu không hợp lệ"), frappe.PermissionError)
    return KINDS[kind]


def _roles() -> set:
    return set(frappe.get_roles())


def _has(*roles) -> bool:
    return "Administrator" == frappe.session.user or bool(_roles() & set(roles))


def default_view() -> str:
    """Where a user's queue opens: the leader on what waits for them, everybody else on the reception."""
    if "Archive Leader" in _roles() and not _roles() & {"Reading Room Officer", "Document Admin"}:
        return "cho_lanh_dao"
    return "cho_tiep_nhan"


def waiting_counts() -> dict:
    """What waits for the current user in each queue (sidebar badges): a leader sees the slips waiting for a
    leader; the reading room sees the slips waiting for reception, plus overdue ones and feedback not answered."""
    leader_only = "Archive Leader" in _roles() and not _roles() & {"Reading Room Officer", "Document Admin"}
    counts = {}
    for kind, doctype in KINDS.items():
        if leader_only:
            counts[kind] = frappe.db.count(doctype, VIEWS["cho_lanh_dao"][1])
        else:
            counts[kind] = frappe.db.count(doctype, VIEWS["cho_tiep_nhan"][1])
            if kind == "usage":
                counts[kind] += frappe.db.count(doctype, VIEWS["qua_han"][1])
    counts["feedback"] = 0 if leader_only else frappe.db.count("Reader Feedback", {"status": "Mới"})
    return counts


@frappe.whitelist()
def queue_badges():
    """The sidebar counters, refreshed after an action: {route: count}."""
    assert_roles(*STAFF)
    counts = waiting_counts()
    out = {"/dashboard/doc-gia/phieu-su-dung": counts["usage"], "/dashboard/doc-gia/phieu-sao-chup": counts["copy"],
           "/dashboard/doc-gia/gop-y": counts["feedback"]}
    if frappe.has_permission("Reader Registration", "read"):
        from document_manager.document_manager.services.registration import pending_count
        out["/dashboard/doc-gia/dang-ky"] = pending_count()
    return out


@frappe.whitelist()
def queue_summary():
    """Counters of both queues, for the sidebar badges and the tabs."""
    assert_roles(*STAFF)
    out = {}
    for kind, doctype in KINDS.items():
        out[kind] = {view: frappe.db.count(doctype, VIEWS[view][1]) for view in VIEWS_OF[kind]}
    out["default_view"] = default_view()
    return out


@frappe.whitelist()
def list_slips(kind, view=None, search=None, page=1, page_size=PAGE_SIZE):
    assert_roles(*STAFF)
    doctype = _doctype(kind)
    view = view or default_view()
    if view not in VIEWS_OF[kind]:
        frappe.throw(_("Danh sách không hợp lệ"))
    filters = dict(VIEWS[view][1])
    or_filters = None
    search = (search or "").strip()
    if search:
        like = f"%{search}%"
        or_filters = [[doctype, f, "like", like] for f in ("name", "reader", "reader_name", "purpose")]
    page = max(1, cint(page) or 1)
    page_size = max(1, min(100, cint(page_size) or PAGE_SIZE))
    fields = LIST_FIELDS + (USAGE_FIELDS if kind == "usage" else [])
    order = "due_date asc, modified desc" if view in ("dang_su_dung", "qua_han") else "modified desc"
    rows = frappe.get_all(doctype, filters=filters, or_filters=or_filters, fields=fields, order_by=order,
                          start=(page - 1) * page_size, page_length=page_size)
    total = frappe.get_all(doctype, filters=filters, or_filters=or_filters, fields=[{"COUNT": "name", "as": "c"}])[0].c
    if rows:
        counts = {r.parent: r.c for r in frappe.get_all(
            f"{doctype} Item", filters={"parent": ["in", [r.name for r in rows]], "parenttype": doctype},
            fields=["parent", {"COUNT": "name", "as": "c"}], group_by="parent", parent_doctype=doctype)}
        for row in rows:
            row["item_count"] = counts.get(row.name, 0)
    return {"rows": rows, "total": total, "page": page, "page_size": page_size, "view": view,
            "views": [{"view": v, "label": VIEWS[v][0]} for v in VIEWS_OF[kind]]}


# --- one slip ------------------------------------------------------------------------------------------------------

def _storage(file_name):
    row = frappe.db.get_value("Archival File", file_name, ["storage_warehouse", "shelf_number", "box_number", "physical_location"],
                              as_dict=True) if file_name else None
    if not row:
        return ""
    parts = [row.storage_warehouse, f"Giá {row.shelf_number}" if row.shelf_number else "", f"Hộp {row.box_number}" if row.box_number else "",
             row.physical_location]
    return " · ".join(p for p in parts if p)


def _item(row) -> dict:
    is_doc = bool(row.archive_document)
    if is_doc:
        title, number, level = frappe.db.get_value("Archive Document", row.archive_document,
                                                   ["document_title", "document_number", "confidentiality_level"]) or ("", "", "")
        parent = frappe.db.get_value("Archival File", row.archival_file, "file_title") if row.archival_file else ""
    else:
        title, number, level = frappe.db.get_value("Archival File", row.archival_file,
                                                   ["file_title", "file_number", "confidentiality_level"]) or ("", "", "")
        parent = ""
    return {
        "row": row.name, "kind": "Văn bản" if is_doc else "Hồ sơ", "archival_file": row.archival_file,
        "archive_document": row.archive_document, "title": title or row.archive_document or row.archival_file,
        "number": number or "", "parent_title": parent or "", "level": level or "", "location": _storage(row.archival_file),
        "copy_count": cint(row.get("copy_count")) or 1, "notes": row.notes or "", "item_status": row.get("item_status") or lc.ITEM_PENDING,
        "decision_note": row.get("decision_note") or "", "issued_on": row.get("issued_on"), "returned_on": row.get("returned_on"),
        "return_condition": row.get("return_condition") or "",
    }


def _timeline(doctype: str, name: str) -> list:
    """Who moved the slip where and when, from the document's version history."""
    out = []
    for version in frappe.get_all("Version", filters={"ref_doctype": doctype, "docname": name},
                                  fields=["creation", "owner", "data"], order_by="creation asc", limit_page_length=200):
        try:
            changed = json.loads(version.data or "{}").get("changed") or []
        except ValueError:
            continue
        for field, old, new in changed:
            if field == "workflow_state":
                out.append({"when": version.creation, "who": frappe.utils.get_fullname(version.owner) or version.owner,
                            "text": f"{old or 'Mới'} → {new}"})
    return out


def _slip(doc) -> dict:
    kind = "usage" if doc.doctype == lc.USAGE else "copy"
    state = doc.workflow_state or lc.STATE_DRAFT
    actions = sorted({t.action for t in get_transitions(doc)}) if doc.docstatus != 2 else []
    reader = frappe.db.get_value("Reader", doc.reader, ["name", "full_name", "email", "phone", "organization", "position", "reader_group", "is_active"],
                                 as_dict=True) or frappe._dict(name=doc.reader)
    limits = get_limits(doc.reader)
    renewable, why_not = lc.can_renew(doc) if kind == "usage" else (False, "")
    review_role = LEADERS if state == lc.STATE_LEADER else OFFICERS
    out = {
        "kind": kind, "doctype": doc.doctype, "name": doc.name, "state": state, "docstatus": doc.docstatus,
        "reader": reader, "purpose": doc.purpose or "", "notes": doc.notes or "", "request_date": doc.request_date,
        "submitted_on": doc.get("submitted_on"), "approved_by": doc.approved_by, "approved_date": doc.approved_date,
        "rejection_reason": doc.rejection_reason or "", "requires_leader": cint(doc.requires_leader), "leader": doc.get("leader"),
        "items": [_item(row) for row in doc.items], "actions": actions, "timeline": _timeline(doc.doctype, doc.name),
        "can": {
            "edit_draft": doc.docstatus == 0 and bool(doc.has_permission("write")),
            "delete_draft": doc.docstatus == 0 and _has(*OFFICERS),
            "decide_items": state in lc.REVIEW_STATES and _has(*review_role),
            "receive_return": kind == "usage" and state == lc.STATE_IN_USE and _has(*OFFICERS),
            "renew": bool(renewable) and _has(*OFFICERS),
        },
        "renew_reason": why_not if kind == "usage" and not renewable else "",
        "print": print_urls(doc.doctype, doc.name),
    }
    if kind == "usage":
        out.update({"issued_on": doc.issued_on, "issued_by": doc.issued_by, "due_date": doc.due_date, "renewal_count": cint(doc.renewal_count),
                    "is_overdue": cint(doc.is_overdue) or int(bool(doc.due_date and state == lc.STATE_IN_USE and getdate(doc.due_date) < getdate(nowdate()))),
                    "returned_date": doc.returned_date, "received_by": doc.get("received_by"),
                    "max_renewals": limits.max_renewals, "renewal_days": limits.renewal_days})
    else:
        out["completed_date"] = doc.completed_date
    return out


@frappe.whitelist()
def get_slip(kind, name):
    assert_roles(*STAFF)
    doc = frappe.get_doc(_doctype(kind), name)
    doc.check_permission("read")
    return _slip(doc)


# --- decisions --------------------------------------------------------------------------------------------------------

def _load_for_staff(kind, name, roles):
    assert_roles(*roles)
    doc = frappe.get_doc(_doctype(kind), name)
    doc.check_permission("write")
    return doc


@frappe.whitelist(methods=["POST"])
def decide_items(kind, name, decisions):
    """Approve or turn down items of a slip waiting for a decision.

    `decisions` is a JSON list of {row, status, note}; status "Đã duyệt" | "Từ chối" | "Chờ duyệt".
    The officer decides while the slip is "Chờ duyệt", the leader while it is "Chờ lãnh đạo duyệt"; the
    slip itself is then approved or refused through the workflow (items nobody turned down are approved)."""
    assert_roles(*STAFF)  # before looking the slip up: whoever is not staff learns nothing about which slips exist
    doc = frappe.get_doc(_doctype(kind), name)
    doc.check_permission("write")
    state = doc.workflow_state
    if state not in lc.REVIEW_STATES:
        frappe.throw(_("Phiếu không ở bước duyệt hồ sơ, văn bản"))
    assert_roles(*(LEADERS if state == lc.STATE_LEADER else OFFICERS))
    decisions = frappe.parse_json(decisions) if isinstance(decisions, str) else decisions
    by_row = {row.name: row for row in doc.items}
    for decision in decisions or []:
        row = by_row.get(decision.get("row"))
        if not row:
            frappe.throw(_("Không tìm thấy dòng {0} trong phiếu").format(decision.get("row")))
        status = decision.get("status")
        if status not in (lc.ITEM_APPROVED, lc.ITEM_REJECTED, lc.ITEM_PENDING):
            frappe.throw(_("Trạng thái duyệt không hợp lệ"))
        note = (decision.get("note") or "").strip()
        if status == lc.ITEM_REJECTED and not note:
            frappe.throw(_("Phải nhập lý do khi từ chối dòng {0}").format(row.idx))
        row.item_status, row.decision_note = status, note
    doc.save()
    log_activity("Cập nhật", doc.doctype, doc.name, "Duyệt từng hồ sơ, văn bản trong phiếu")
    return _slip(frappe.get_doc(doc.doctype, doc.name))


@frappe.whitelist(methods=["POST"])
def receive_return(name, conditions=None):
    """Take the documents back: `conditions` is a JSON object {row: condition} for the state of each one."""
    doc = _load_for_staff("usage", name, OFFICERS)
    if doc.workflow_state != lc.STATE_IN_USE:
        frappe.throw(_("Chỉ nhận trả phiếu đang sử dụng"))
    conditions = frappe.parse_json(conditions) if isinstance(conditions, str) and conditions else (conditions or {})
    by_row = {row.name: row for row in doc.items}
    for row_name, condition in conditions.items():
        if row_name not in by_row or condition not in lc.CONDITIONS:
            frappe.throw(_("Tình trạng tài liệu không hợp lệ"))
        by_row[row_name].return_condition = condition
    frappe.db.savepoint("receive_return")
    try:
        if conditions:
            doc.save()
        doc = apply_workflow(doc, "Nhận trả")
    except Exception:
        frappe.db.rollback(save_point="receive_return")
        raise
    return _slip(frappe.get_doc(doc.doctype, doc.name))


@frappe.whitelist(methods=["POST"])
def renew(name):
    """Extend the due date of a slip in use by the renewal period, within the reader's renewal limit."""
    doc = _load_for_staff("usage", name, OFFICERS)
    allowed, reason = lc.can_renew(doc)
    if not allowed:
        frappe.throw(reason)
    doc.due_date = lc.next_due_date(doc)
    doc.renewal_count = cint(doc.renewal_count) + 1
    doc.is_overdue = 0
    doc.save()
    log_activity("Cập nhật", doc.doctype, doc.name, f"Gia hạn đến {format_date(doc.due_date, 'dd/MM/yyyy')} (lần {doc.renewal_count})")
    user = frappe.db.get_value("Reader", doc.reader, "user")
    label, reader_route, _staff = SLIP_KINDS[doc.doctype]
    notify_user(user, f"{label} {doc.name} được gia hạn đến {format_date(doc.due_date, 'dd/MM/yyyy')}", f"{reader_route}/{doc.name}", doc.doctype, doc.name)
    return _slip(frappe.get_doc(doc.doctype, doc.name))


@frappe.whitelist(methods=["POST"])
def delete_draft(kind, name):
    """Staff delete a draft slip (a slip that was sent is withdrawn or refused, never deleted)."""
    assert_roles(*OFFICERS)
    doctype = _doctype(kind)
    if frappe.db.get_value(doctype, name, "docstatus") != 0:
        frappe.throw(_("Chỉ xóa được phiếu nháp"))
    frappe.delete_doc(doctype, name, ignore_permissions=True)
    return {"name": name}


@frappe.whitelist()
def reader_slips(reader, limit=10):
    """What the reader's page in the staff app shows besides the profile: recent slips of both kinds, how many
    are open or overdue, and the links to print the reader card."""
    assert_roles(*STAFF)
    recent = []
    for kind, doctype in KINDS.items():
        for row in frappe.get_all(doctype, filters={"reader": reader, "docstatus": ["<", 2]},
                                  fields=["name", "workflow_state", "request_date", "purpose"], order_by="modified desc",
                                  page_length=max(1, min(50, cint(limit) or 10))):
            recent.append({**row, "kind": kind})
    recent.sort(key=lambda r: str(r.get("request_date") or ""), reverse=True)
    return {
        "slips": recent,
        "open": sum(frappe.db.count(dt, {"reader": reader, "docstatus": 1, "workflow_state": ["in", list(lc.OPEN_STATES)]}) for dt in KINDS.values()),
        "overdue": lc.overdue_count(reader),
        "print": print_urls("Reader", reader),
    }
