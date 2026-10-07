# -*- coding: utf-8 -*-
"""Whitelisted API for reader requests (Usage Request, Copy Request, Reader Feedback).

Every state change goes through `frappe.model.workflow.apply_workflow`, so the Workflow's
role/transition rules and DocType permissions are enforced by Frappe itself.
"""

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow, get_transitions

REQUEST_DOCTYPES = ("Usage Request", "Copy Request")
ALL_DOCTYPES = (*REQUEST_DOCTYPES, "Reader Feedback")

REQUEST_FIELDS = ("purpose", "notes")
ITEM_FIELDS = {
    "Usage Request": ("archival_file", "archive_document", "notes"),
    "Copy Request": ("archival_file", "archive_document", "notes", "copy_count"),
}


def _check_doctype(doctype, allowed=ALL_DOCTYPES):
    if doctype not in allowed:
        frappe.throw(_("Loại tài liệu không hợp lệ"), frappe.PermissionError)


def _plain_to_html(text: str) -> str:
    """Portal textareas are plain text: escape, keep line breaks."""
    return frappe.utils.escape_html(text or "").replace("\n", "<br>")


def _state_field(doctype):
    return "status" if doctype == "Reader Feedback" else "workflow_state"


@frappe.whitelist(methods=["POST"])
def apply_action(doctype, name, action, text=None, notes=None):
    """Run a workflow action. `text` is the rejection reason (Từ chối) or the reply (Phản hồi)."""
    _check_doctype(doctype)
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    extra = {}
    if text and action == "Từ chối":
        extra["rejection_reason"] = text
    elif text and action == "Phản hồi":
        extra["response"] = _plain_to_html(text)
    if notes and doctype in REQUEST_DOCTYPES:
        extra["notes"] = notes
    # apply_workflow reloads the doc from the DB, so extra fields must be saved first.
    frappe.db.savepoint("apply_action")
    try:
        if extra:
            doc.update(extra)
            doc.save()
        doc = apply_workflow(doc, action)
    except Exception:
        frappe.db.rollback(save_point="apply_action")
        raise
    return {"name": doc.name, "state": doc.get(_state_field(doctype))}


@frappe.whitelist()
def get_actions(doctype, name):
    """Workflow actions the current user may run on this document."""
    _check_doctype(doctype)
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    seen, actions = set(), []
    for t in get_transitions(doc):
        if t.action not in seen:
            seen.add(t.action)
            actions.append({"action": t.action, "next_state": t.next_state})
    return actions


@frappe.whitelist(methods=["POST"])
def save_request(doctype, payload, name=None, submit=0):
    """Create or update a draft request, optionally sending it for approval ("Gửi duyệt")."""
    _check_doctype(doctype, REQUEST_DOCTYPES)
    data = frappe.parse_json(payload) if isinstance(payload, str) else payload
    if name:
        doc = frappe.get_doc(doctype, name)
        doc.check_permission("write")
    else:
        doc = frappe.new_doc(doctype)
        doc.reader = data.get("reader")  # overwritten server-side for non-staff
    for field in REQUEST_FIELDS:
        if field in data:
            doc.set(field, data[field])
    if "items" in data:
        allowed = ITEM_FIELDS[doctype]
        doc.set("items", [{k: v for k, v in (row or {}).items() if k in allowed}
                          for row in data["items"]])
    doc.save() if name else doc.insert()
    if frappe.utils.cint(submit):
        doc = apply_workflow(doc, "Gửi duyệt")
    return {"name": doc.name, "state": doc.workflow_state}


@frappe.whitelist(methods=["POST"])
def submit_feedback(subject, content):
    doc = frappe.get_doc({"doctype": "Reader Feedback", "subject": subject,
                          "content": _plain_to_html(content)})
    doc.insert()
    return {"name": doc.name, "state": doc.status}


@frappe.whitelist()
def search_items(kind, txt=""):
    """Autocomplete for the request item picker. Uses get_list, so confidentiality hooks apply."""
    from document_manager.document_manager.permissions import assert_can_search
    assert_can_search()
    if kind == "document":
        doctype, title = "Archive Document", "document_title"
    elif kind == "file":
        doctype, title = "Archival File", "file_title"
    else:
        frappe.throw(_("Loại tìm kiếm không hợp lệ"))
    txt = (txt or "").strip()
    rows = frappe.get_list(
        doctype,
        fields=["name", title + " as title"],
        or_filters=[["name", "like", f"%{txt}%"], [title, "like", f"%{txt}%"]] if txt else None,
        order_by="modified desc",
        limit_page_length=10,
    )
    return [{"value": r.name, "label": f"{r.name} — {r.title or ''}"} for r in rows]
