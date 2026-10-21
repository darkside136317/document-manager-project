# -*- coding: utf-8 -*-
"""Whitelisted API of the reader's basket (the open draft Usage / Copy Request)."""

import frappe

from document_manager.document_manager.services import basket


@frappe.whitelist()
def get_basket():
    return basket.summary()


@frappe.whitelist(methods=["POST"])
def add_to_basket(kind, name, target="usage"):
    """kind: "file" | "document"; target: "usage" | "copy"."""
    return basket.add_item(kind, name, target)


@frappe.whitelist(methods=["POST"])
def remove_from_basket(doctype, name, row):
    return basket.remove_item(doctype, name, row)


@frappe.whitelist(methods=["POST"])
def discard_draft(doctype, name):
    return basket.discard_draft(doctype, name)


@frappe.whitelist(methods=["POST"])
def move_item(doctype, name, row, target):
    """Move a row of a draft to the reader's draft of the other kind ("usage" | "copy")."""
    return basket.move_item(doctype, name, row, target)


@frappe.whitelist(methods=["POST"])
def start_from(doctype, name, target):
    """A draft of `target` from the items of one of the reader's slips ("Lập lại phiếu", "Xin sao chụp")."""
    return basket.start_from(doctype, name, target)


@frappe.whitelist(methods=["POST"])
def renew_slip(name):
    """The reader extends their own slip in use, within the same rules as the reading room (renewal limit, access to
    the fonds), unless it is already overdue. The reading room is told."""
    from frappe import _
    from frappe.utils import format_date

    from document_manager.document_manager.policy import get_reader_profile
    from document_manager.document_manager.services import lifecycle as lc
    from document_manager.document_manager.services.audit import log_activity
    from document_manager.document_manager.services.notify import SLIP_KINDS, notify_capability

    profile = get_reader_profile()
    if not profile or not frappe.db.exists(lc.USAGE, name) or frappe.db.get_value(lc.USAGE, name, "reader") != profile:
        frappe.throw(_("Không tìm thấy phiếu"), frappe.PermissionError)
    doc = frappe.get_doc(lc.USAGE, name)
    allowed, reason = lc.can_self_renew(doc)
    if not allowed:
        frappe.throw(reason)
    doc.flags.ignore_permissions = True  # the reader may not edit a sent slip; this one change is checked above
    doc.flags.dm_self_renewal = True
    lc.renew(doc)
    due = format_date(doc.due_date, "dd/MM/yyyy")
    log_activity("Cập nhật", doc.doctype, doc.name, f"Độc giả tự gia hạn đến {due} (lần {doc.renewal_count})")
    label, _reader_route, staff_route = SLIP_KINDS[doc.doctype]
    notify_capability("slips.receive", f"{doc.reader_name or doc.reader} tự gia hạn {label.lower()} {doc.name} đến {due}",
                      f"{staff_route}/{doc.name}", doc.doctype, doc.name)
    return {"due_date": due, "renewal_count": doc.renewal_count}
