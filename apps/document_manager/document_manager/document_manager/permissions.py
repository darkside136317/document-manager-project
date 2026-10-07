# -*- coding: utf-8 -*-
"""Frappe permission hooks and page guards.

The rules themselves live in `policy.py` (`get_reader_scope`); this module adapts them to Frappe:
`permission_query_conditions` (SQL appended to every list query) and `has_permission`
(single-document checks) referenced from hooks.py, plus the guards used by www pages and APIs.

Staff roles see everything the DocPerms allow. A reader sees only what their group allows:
confidentiality up to the group's level, only the fonds of the group's scope, and never files
that are drafts ("Nháp") or disposed of ("Đã tiêu hủy") nor the documents inside them.
"""

import frappe
from frappe import _

from document_manager.document_manager.policy import (  # noqa: F401  (re-exported for callers)
    STAFF_ROLES,
    assert_feature,
    fonds_allowed,
    get_reader_profile,
    get_reader_scope,
    is_staff,
    scope_fonds_sql,
)


def _is_staff_user() -> bool:
    """Check if current user has any staff role."""
    return is_staff()


def assert_roles(*roles: str, user: str | None = None) -> None:
    """Raise PermissionError unless `user` (default: session user) holds one of `roles`.

    Unlike `frappe.only_for`, this is also enforced while tests run.
    """
    user = user or frappe.session.user
    if user == "Administrator":
        return
    if not set(roles) & set(frappe.get_roles(user)):
        frappe.throw(_("Bạn không có quyền thực hiện thao tác này"), frappe.PermissionError)


def dm_is_staff() -> bool:
    """Jinja helper (templates already have an `is_staff` context variable, so the name differs)."""
    return is_staff()


def dm_display_name() -> str:
    """Jinja helper: name for the navbar."""
    return display_name()


def assert_can_search():
    """Search/preview APIs: staff, or a reader whose group may search."""
    assert_feature("can_search")


def display_name(user: str | None = None) -> str:
    """Name shown in the navbar: Reader full name, else the User full name, else the login."""
    user = user or frappe.session.user
    profile = get_reader_profile(user)
    if profile:
        return frappe.db.get_value("Reader", profile, "full_name") or user
    return frappe.utils.get_fullname(user) or user


def _redirect(location: str):
    frappe.local.flags.redirect_location = location
    raise frappe.Redirect


def require_staff(route: str = "/dashboard"):
    """Gate for staff-only pages. Guest -> login (back to `route`), Reader -> /portal."""
    if frappe.session.user == "Guest":
        _redirect(f"/login?redirect-to={route}")
    if not _is_staff_user():
        _redirect("/portal")


def require_portal_user(route: str = "/portal"):
    """Gate for portal pages: any logged-in staff or Reader."""
    if frappe.session.user == "Guest":
        _redirect(f"/login?redirect-to={route}")
    if not (_is_staff_user() or "Reader" in frappe.get_roles(frappe.session.user)):
        frappe.throw("Bạn không có quyền truy cập cổng thông tin", frappe.PermissionError)


# === Published state of a file ===
# A draft or a disposed file is invisible to readers, and so are the documents inside it.
# NULLs are treated as "not published".

_PUBLISHED_FILE_SQL = (
    "IFNULL(`{t}`.`status`, 'Nháp') != 'Nháp' AND IFNULL(`{t}`.`disposal_status`, '') != 'Đã tiêu hủy'"
)


def is_file_published(status, disposal_status) -> bool:
    return (status or "Nháp") != "Nháp" and (disposal_status or "") != "Đã tiêu hủy"


def _levels_allowed_sql(scope) -> str:
    """Quoted, comma separated names of the confidentiality levels the scope may read."""
    allowed = frappe.get_all(
        "Confidentiality Level", filters={"priority": ["<=", scope.max_priority]}, pluck="name",
        limit_page_length=0,
    )
    return ", ".join(frappe.db.escape(level) for level in allowed) or frappe.db.escape("Thường")


def _level_priority(level) -> int | None:
    return frappe.db.get_value("Confidentiality Level", level, "priority") if level else None


def _and(*conditions: str) -> str:
    return " AND ".join(c for c in conditions if c)


# === Permission Query Conditions ===
# These return SQL WHERE clause snippets that are appended to all queries.

def archival_file_query(user):
    """Archival File: confidentiality level, fonds scope and published state."""
    scope = get_reader_scope(user)
    if scope.is_staff:
        return ""
    if not scope.allowed:
        return "1=0"
    return _and(
        f"`tabArchival File`.`confidentiality_level` IN ({_levels_allowed_sql(scope)})",
        scope_fonds_sql(scope, "`tabArchival File`.`fonds`"),
        _PUBLISHED_FILE_SQL.format(t="tabArchival File"),
    )


def archive_document_query(user):
    """Archive Document: confidentiality level, fonds scope and parent file published."""
    scope = get_reader_scope(user)
    if scope.is_staff:
        return ""
    if not scope.allowed:
        return "1=0"
    return _and(
        f"`tabArchive Document`.`confidentiality_level` IN ({_levels_allowed_sql(scope)})",
        scope_fonds_sql(scope, "`tabArchive Document`.`fonds`"),
        "`tabArchive Document`.`archival_file` IN (SELECT `pf`.`name` FROM `tabArchival File` `pf` WHERE "
        + _PUBLISHED_FILE_SQL.format(t="pf") + ")",
    )


def fonds_query(user):
    scope = get_reader_scope(user)
    if scope.is_staff:
        return ""
    if not scope.allowed:
        return "1=0"
    return scope_fonds_sql(scope, "`tabFonds`.`name`")


def record_group_query(user):
    scope = get_reader_scope(user)
    if scope.is_staff:
        return ""
    if not scope.allowed:
        return "1=0"
    return scope_fonds_sql(scope, "`tabRecord Group`.`fonds`")


def catalog_query(user):
    scope = get_reader_scope(user)
    if scope.is_staff:
        return ""
    if not scope.allowed:
        return "1=0"
    return scope_fonds_sql(scope, "`tabCatalog`.`fonds`")


# === Has Permission ===
# Frappe v16: a falsy hook result (including None) DENIES; return True to defer to DocPerm.

def _reader_scope_for(doc, user, ptype):
    """(decision, scope): decision is True/False when settled, None when the caller must still
    check the document itself against the scope."""
    user = user or frappe.session.user
    if user == "Guest":
        return False, None
    if ptype != "read":
        return True, None  # defer to standard Role Permissions
    scope = get_reader_scope(user)
    if scope.is_staff:
        return True, scope
    if not scope.allowed:
        return False, scope
    return None, scope


def has_archival_file_permission(doc, ptype="read", user=None):
    """Check if user has permission to access this Archival File."""
    decision, scope = _reader_scope_for(doc, user, ptype)
    if decision is not None:
        return decision
    if not doc.confidentiality_level:
        return False  # the query condition excludes NULL levels too
    if not is_file_published(doc.get("status"), doc.get("disposal_status")):
        return False
    if not fonds_allowed(scope, doc.get("fonds")):
        return False
    return int(_level_priority(doc.confidentiality_level) or 1) <= scope.max_priority


def has_archive_document_permission(doc, ptype="read", user=None):
    """Check if user has permission to access this Archive Document."""
    decision, scope = _reader_scope_for(doc, user, ptype)
    if decision is not None:
        return decision
    if not doc.confidentiality_level:
        return False  # the query condition excludes NULL levels too
    parent = frappe.db.get_value(
        "Archival File", doc.get("archival_file"), ["status", "disposal_status"], as_dict=True
    ) if doc.get("archival_file") else None
    if not parent or not is_file_published(parent.status, parent.disposal_status):
        return False
    if not fonds_allowed(scope, doc.get("fonds")):
        return False
    return int(_level_priority(doc.confidentiality_level) or 1) <= scope.max_priority


def has_fonds_permission(doc, ptype="read", user=None):
    decision, scope = _reader_scope_for(doc, user, ptype)
    return decision if decision is not None else fonds_allowed(scope, doc.name)


def has_record_group_permission(doc, ptype="read", user=None):
    decision, scope = _reader_scope_for(doc, user, ptype)
    return decision if decision is not None else fonds_allowed(scope, doc.get("fonds"))


def has_catalog_permission(doc, ptype="read", user=None):
    decision, scope = _reader_scope_for(doc, user, ptype)
    return decision if decision is not None else fonds_allowed(scope, doc.get("fonds"))


# === Reader-owned records (Usage Request, Copy Request, Reader Feedback, Reader) ===
# Staff are limited by DocPerm only; a Reader only ever sees records tied to their own profile.

def _reader_scope_query(doctype: str) -> str:
    if is_staff():
        return ""
    profile = get_reader_profile()
    if not profile:
        return "1=0"
    return f"`tab{doctype}`.`reader` = {frappe.db.escape(profile)}"


def _reader_scope_permission(doc, user, ptype="read") -> bool:
    user = user or frappe.session.user
    if user == "Guest":
        return False
    if is_staff(user):
        return True
    if ptype == "create" or doc.is_new():
        return True  # the controller binds `reader` to the session user before saving
    profile = get_reader_profile(user)
    if not profile or doc.get("reader") != profile:
        return False
    return True


def usage_request_query(user):
    return _reader_scope_query("Usage Request")


def copy_request_query(user):
    return _reader_scope_query("Copy Request")


def reader_feedback_query(user):
    return _reader_scope_query("Reader Feedback")


def reader_query(user):
    if is_staff():
        return ""
    return f"`tabReader`.`user` = {frappe.db.escape(frappe.session.user)}"


def has_usage_request_permission(doc, ptype="read", user=None):
    return _reader_scope_permission(doc, user, ptype)


def has_copy_request_permission(doc, ptype="read", user=None):
    return _reader_scope_permission(doc, user, ptype)


def has_reader_feedback_permission(doc, ptype="read", user=None):
    return _reader_scope_permission(doc, user, ptype)


def has_reader_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if user == "Guest":
        return False
    if is_staff(user):
        return True
    return doc.get("user") == user
