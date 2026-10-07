# -*- coding: utf-8 -*-
"""Search portal page — public search interface for Readers."""
import frappe

from document_manager.document_manager.permissions import require_portal_user
from document_manager.document_manager.policy import get_reader_scope


def get_context(context):
    context.no_cache = 1
    require_portal_user()
    scope = get_reader_scope()
    context.title = "Tìm kiếm Tài liệu"
    # get_list applies the reader's fonds scope; levels are limited to the reader's clearance.
    context.fonds_list = frappe.get_list("Fonds", fields=["name", "fonds_name"], order_by="fonds_name")
    level_filters = {} if scope.is_staff else {"priority": ["<=", scope.max_priority or 1]}
    context.confidentiality_levels = frappe.get_all(
        "Confidentiality Level", filters=level_filters, fields=["name", "priority"], order_by="priority"
    )
    context.has_profile = bool(scope.profile)
    context.can_search = scope.can_search
    # Quick-action buttons: only what this user's group is actually allowed to file.
    context.can_request = frappe.has_permission("Usage Request", "create") and (
        scope.is_staff or (scope.allowed and scope.can_request_usage))
    context.can_copy = frappe.has_permission("Copy Request", "create") and (
        scope.is_staff or (scope.allowed and scope.can_request_copy))
    context.can_feedback = frappe.has_permission("Reader Feedback", "create") and bool(scope.profile) and (
        scope.is_staff or (scope.allowed and scope.can_feedback))
    context.breadcrumbs = [
        {'label': 'Tìm kiếm tài liệu'}
    ]
