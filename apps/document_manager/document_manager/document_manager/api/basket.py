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
