# -*- coding: utf-8 -*-
"""System administration API (Document Admin / System Manager only)."""

import frappe

from document_manager.document_manager.permissions import assert_roles

ADMIN_ROLES = ("Document Admin", "System Manager")


@frappe.whitelist()
def get_service_health():
    """Status of MongoDB Atlas (file storage) and Meilisearch (search)."""
    assert_roles(*ADMIN_ROLES)
    from document_manager.document_manager.services.health import check_services

    return check_services()
