# -*- coding: utf-8 -*-
"""Actions on an Inventory Check (tổng kiểm kê phông): build the lines, complete the check, reopen it."""

import frappe
from frappe import _

from document_manager.document_manager.permissions import assert_roles
from document_manager.document_manager.services.audit import log_activity

DOCTYPE = "Inventory Check"
CHECKERS = ("Document Admin", "Cataloger")


def _load(name: str, *roles: str):
    assert_roles(*roles)
    doc = frappe.get_doc(DOCTYPE, name)
    doc.check_permission("write")
    return doc


def _answer(doc) -> dict:
    return {"name": doc.name, "status": doc.status, "completed_on": doc.completed_on,
            "total_difference": doc.total_difference, "modified": doc.modified}


@frappe.whitelist(methods=["POST"])
def populate(name):
    """Take the lines from the figures the system holds now (counts already typed for a listed fonds are kept)."""
    doc = _load(name, *CHECKERS)
    doc.populate()
    log_activity("Cập nhật", DOCTYPE, doc.name, "Lập danh sách phông kiểm kê")
    return _answer(doc)


@frappe.whitelist(methods=["POST"])
def complete(name):
    """Close the check: every fonds must be marked counted; the figures are then locked."""
    doc = _load(name, *CHECKERS)
    doc.complete()
    log_activity("Cập nhật", DOCTYPE, doc.name, f"Hoàn thành kiểm kê, {doc.total_difference} phông chênh lệch")
    return _answer(doc)


@frappe.whitelist(methods=["POST"])
def reopen(name):
    """Unlock a completed check (administrators only)."""
    doc = _load(name, "Document Admin")
    doc.reopen()
    log_activity("Cập nhật", DOCTYPE, doc.name, _("Mở lại đợt kiểm kê"))
    return _answer(doc)
