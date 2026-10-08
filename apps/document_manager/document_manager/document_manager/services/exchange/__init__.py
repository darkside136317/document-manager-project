# -*- coding: utf-8 -*-
"""Exchange of archival data as XML (module 5): who may use it."""

import frappe

from document_manager.document_manager.permissions import assert_roles

EXCHANGE_ROLES = ("Document Admin", "System Manager")


def can_exchange(user: str | None = None) -> bool:
    user = user or frappe.session.user
    return user == "Administrator" or bool(set(EXCHANGE_ROLES) & set(frappe.get_roles(user)))


def require_exchange() -> None:
    assert_roles(*EXCHANGE_ROLES)
