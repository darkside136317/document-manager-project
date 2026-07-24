# -*- coding: utf-8 -*-
"""Permission Query Conditions for access_level filtering.

These functions are referenced in hooks.py via `permission_query_conditions`
and `has_permission` to enforce confidentiality-based access control.

Staff roles (Document Admin, Cataloger, Reading Room Officer, Preservation Officer)
can see all documents regardless of confidentiality level.

Reader role can only see documents with confidentiality levels they're authorized for,
based on the `max_confidentiality_priority` field in their Reader profile.
"""

import frappe


STAFF_ROLES = frozenset({
    "Document Admin", "Cataloger", "Reading Room Officer",
    "Preservation Officer", "System Manager", "Administrator",
})


def _is_staff_user() -> bool:
    """Check if current user has any staff role."""
    return bool(STAFF_ROLES.intersection(set(frappe.get_roles(frappe.session.user))))


def _get_reader_max_priority() -> int:
    """Get the maximum confidentiality priority the current Reader is allowed to view."""
    max_priority = frappe.db.get_value(
        "Reader", {"user": frappe.session.user}, "max_confidentiality_priority"
    )
    return int(max_priority) if max_priority else 1  # Default: Thường (priority=1)


def _get_allowed_levels_sql() -> str:
    """Return SQL IN clause for allowed confidentiality levels."""
    if _is_staff_user():
        return ""  # No restriction
    max_priority = _get_reader_max_priority()
    allowed = frappe.get_all(
        "Confidentiality Level",
        filters={"priority": ["<=", max_priority]},
        pluck="name",
    )
    if not allowed:
        allowed = ["Thường"]
    escaped = ", ".join([frappe.db.escape(l) for l in allowed])
    return escaped


# === Permission Query Conditions ===
# These return SQL WHERE clause snippets that are appended to all queries.

def archival_file_query(user):
    """Permission query for Archival File — filter by confidentiality_level."""
    if _is_staff_user():
        return ""
    allowed = _get_allowed_levels_sql()
    return f"`tabArchival File`.`confidentiality_level` IN ({allowed})"


def archive_document_query(user):
    """Permission query for Archive Document — filter by confidentiality_level."""
    if _is_staff_user():
        return ""
    allowed = _get_allowed_levels_sql()
    return f"`tabArchive Document`.`confidentiality_level` IN ({allowed})"


# === Has Permission ===
# These check if a specific user can access a specific document.

def has_archival_file_permission(doc, ptype="read", user=None):
    """Check if user has permission to access this Archival File."""
    if _is_staff_user():
        return True
    if not doc.confidentiality_level:
        return True
    max_priority = _get_reader_max_priority()
    level_priority = frappe.db.get_value(
        "Confidentiality Level", doc.confidentiality_level, "priority"
    )
    return int(level_priority or 1) <= max_priority


def has_archive_document_permission(doc, ptype="read", user=None):
    """Check if user has permission to access this Archive Document."""
    if _is_staff_user():
        return True
    if not doc.confidentiality_level:
        return True
    max_priority = _get_reader_max_priority()
    level_priority = frappe.db.get_value(
        "Confidentiality Level", doc.confidentiality_level, "priority"
    )
    return int(level_priority or 1) <= max_priority
