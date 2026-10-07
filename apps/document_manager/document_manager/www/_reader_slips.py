# -*- coding: utf-8 -*-
"""Page logic of the reader's slips (phiếu yêu cầu sử dụng, phiếu sao chụp): list and detail.

Both kinds share a template (`templates/reader/slip.html`); this module only differs by `CONFIG`.
What a reader may see is decided by the Usage/Copy Request permission hooks; editing goes through
`api.requests` / `api.basket`, which enforce the workflow.
"""

import frappe
from frappe.utils import cint, format_date, format_datetime, getdate, nowdate

from document_manager.document_manager.api.requests import get_actions
from document_manager.document_manager.policy import get_reader_scope
from document_manager.document_manager.services import templates
from document_manager.document_manager.services.web import inline_json
from document_manager.www._reader_ui import page_context, require_reader

PAGE_SIZE = 15

CONFIG = {
    "usage": {
        "doctype": "Usage Request", "item_doctype": "Usage Request Item", "base": "/portal/phieu", "active": "phieu",
        "title": "Phiếu yêu cầu sử dụng", "noun": "phiếu yêu cầu sử dụng", "icon": "file-text",
        "intro": "Yêu cầu đọc hồ sơ, văn bản tại phòng đọc.", "purpose_label": "Mục đích sử dụng",
        "states": ["Nháp", "Chờ duyệt", "Chờ lãnh đạo duyệt", "Đã duyệt", "Đang sử dụng", "Đã trả", "Từ chối", "Đã hủy"],
        "final": "Đã trả", "in_use": True,
        "date_field": "returned_date", "date_label": "Ngày trả tài liệu", "copies": False,
    },
    "copy": {
        "doctype": "Copy Request", "item_doctype": "Copy Request Item", "base": "/portal/sao-chep", "active": "sao-chep",
        "title": "Phiếu sao chụp", "noun": "phiếu sao chụp", "icon": "copy",
        "intro": "Yêu cầu sao chụp hồ sơ, văn bản.", "purpose_label": "Mục đích sao chụp",
        "states": ["Nháp", "Chờ duyệt", "Chờ lãnh đạo duyệt", "Đã duyệt", "Đã hoàn thành", "Từ chối", "Đã hủy"],
        "final": "Đã hoàn thành", "in_use": False,
        "date_field": "completed_date", "date_label": "Ngày hoàn thành", "copies": True,
    },
}


def _steps(cfg: dict, state: str, requires_leader: bool) -> list[dict]:
    """The progress line of a slip: done / current / todo steps, or a red end when it was refused or withdrawn.
    The leader's step is drawn only for a slip that needs one."""
    path = ["Nháp", "Chờ duyệt"]
    if requires_leader or state == "Chờ lãnh đạo duyệt":
        path.append("Chờ lãnh đạo duyệt")
    path.append("Đã duyệt")
    if cfg["in_use"]:
        path.append("Đang sử dụng")
    path.append(cfg["final"])
    if state in ("Từ chối", "Đã hủy"):
        reached = path[:path.index("Chờ duyệt") + 1]
        return [{"label": s, "status": "done"} for s in reached] + [{"label": state, "status": "bad"}]
    at = path.index(state) if state in path else 0
    return [{"label": s, "status": "done" if i < at or (state == cfg["final"] and i == at) else "current" if i == at else "todo"}
            for i, s in enumerate(path)]


def _title(doctype: str, name: str, field: str) -> str:
    if not name:
        return ""
    if not frappe.has_permission(doctype, "read", doc=name):
        return "Tài liệu này không còn trong phạm vi khai thác của bạn"
    return frappe.db.get_value(doctype, name, field) or name


def _item_rows(doc) -> list[dict]:
    rows = []
    for row in doc.items:
        is_doc = bool(row.archive_document)
        rows.append({
            "row": row.name, "archival_file": row.archival_file, "archive_document": row.archive_document,
            "kind": "Văn bản" if is_doc else "Hồ sơ", "item_status": row.get("item_status") or "",
            "decision_note": row.get("decision_note") or "",
            "title": _title("Archive Document", row.archive_document, "document_title") if is_doc
            else _title("Archival File", row.archival_file, "file_title"),
            "parent_title": _title("Archival File", row.archival_file, "file_title") if is_doc else "",
            "href": f"/portal/van-ban/{row.archive_document}" if is_doc else f"/portal/ho-so/{row.archival_file}",
            "copy_count": cint(row.get("copy_count")) or 1, "notes": row.notes or "",
        })
    return rows


def slip_context(context, key: str):
    cfg = CONFIG[key]
    require_reader()
    scope = get_reader_scope()
    name = frappe.form_dict.get("name")
    page_context(context, cfg["title"], active=cfg["active"])
    context.update({"cfg": cfg, "key": key, "doc": None})

    if name:
        # One answer for "missing" and "not yours", so names cannot be probed.
        if not frappe.db.exists(cfg["doctype"], name) or not frappe.has_permission(cfg["doctype"], "read", doc=name):
            raise frappe.DoesNotExistError
        doc = frappe.get_doc(cfg["doctype"], name)
        state = doc.workflow_state or "Nháp"
        editable = doc.docstatus == 0 and doc.has_permission("write")
        actions = {a["action"] for a in get_actions(cfg["doctype"], name)}
        options = templates.slip_options_for(cfg["doctype"])
        items = _item_rows(doc)
        context.update({
            "doc": doc, "state": state, "steps": _steps(cfg, state, bool(cint(doc.requires_leader))), "editable": editable, "items": items,
            "reader_name": doc.reader_name or frappe.db.get_value("Reader", doc.reader, "full_name") or doc.reader,
            "due_date": format_date(doc.get("due_date"), "dd/MM/yyyy") if doc.get("due_date") else "",
            "overdue": bool(doc.get("due_date") and state == "Đang sử dụng" and getdate(doc.due_date) < getdate(nowdate())),
            "renewals": cint(doc.get("renewal_count")),
            "can_cancel": "Hủy phiếu" in actions,
            "dates": [(label, text) for label, text in (
                ("Ngày lập phiếu", format_datetime(doc.request_date, "dd/MM/yyyy") if doc.request_date else ""),
                ("Ngày duyệt", format_datetime(doc.approved_date, "dd/MM/yyyy HH:mm") if doc.approved_date else ""),
                (cfg["date_label"], format_datetime(doc.get(cfg["date_field"]), "dd/MM/yyyy HH:mm") if doc.get(cfg["date_field"]) else ""),
            ) if text],
            "options": options,
            "editor_config": inline_json({
                "doctype": cfg["doctype"], "name": doc.name, "purpose": doc.purpose or "", "notes": doc.notes or "",
                "items": items, "listUrl": cfg["base"], "target": key, "requirePurpose": options.require_purpose,
            }),
            "title": f"{cfg['title']} {doc.name}",
        })
        return context

    page = max(1, cint(frappe.form_dict.get("page")) or 1)
    status = frappe.form_dict.get("status") or ""
    filters = {"workflow_state": status} if status in cfg["states"] else {}
    total = frappe.get_list(cfg["doctype"], filters=filters, fields=[{"COUNT": "name", "as": "c"}])[0].c
    rows = frappe.get_list(cfg["doctype"], filters=filters, fields=["name", "workflow_state", "request_date", "purpose", "docstatus"],
                           order_by="modified desc", start=(page - 1) * PAGE_SIZE, page_length=PAGE_SIZE)
    counts = {}
    if rows:
        counts = {r.parent: r.c for r in frappe.get_all(
            cfg["item_doctype"], filters={"parent": ["in", [r.name for r in rows]], "parenttype": cfg["doctype"]},
            fields=["parent", {"COUNT": "name", "as": "c"}], group_by="parent", parent_doctype=cfg["doctype"])}
    context.update({
        "rows": rows, "counts": counts, "status": status, "page": page, "pages": max(1, -(-total // PAGE_SIZE)),
        "total": total, "can_create": bool(scope.profile and scope.get("can_request_usage" if key == "usage" else "can_request_copy")),
        "base_query": f"{cfg['base']}?" + (f"status={status}&" if status else ""),
    })
    return context
