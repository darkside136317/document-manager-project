# -*- coding: utf-8 -*-
"""Everything the staff SPA needs at start-up: who the user is and what the sidebar shows."""

import frappe

from document_manager.document_manager.constants import (
    ARCHIVE_SCREENS,
    GROUP_CATALOGUES,
    GROUP_CATALOGUING,
    LEGACY_LINKS,
    MASTERS,
    UPLOAD_EXTENSIONS,
    UPLOAD_MAX_MB,
)
from document_manager.document_manager.permissions import display_name, is_staff


def _can_read(doctype) -> bool:
    try:
        return bool(frappe.has_permission(doctype, "read"))
    except Exception:  # a DocType missing on this site must not break the whole shell
        return False


def _with_permissions(entries) -> list:
    return [{**e, "permissions": {p: bool(frappe.has_permission(e["doctype"], p))
                                  for p in ("create", "write", "delete")}} for e in entries]


def build_boot() -> dict:
    """Sidebar sections filtered by the user's permissions (the server still enforces every call)."""
    nav = [{"group": "Tổng quan", "items": [
        {"label": "Tổng quan", "route": "/dashboard", "icon": "layout-dashboard"}]}]

    if _can_read("Archival File"):
        nav.append({"group": GROUP_CATALOGUING, "items": [
            {"label": "Biên mục hồ sơ, văn bản", "route": "/dashboard/bien-muc", "icon": "folder-tree"},
            {"label": "Tìm kiếm", "route": "/dashboard/tim-kiem", "icon": "search"},
        ]})

    masters = [m for m in MASTERS if _can_read(m["doctype"])]
    if masters:
        nav.append({"group": GROUP_CATALOGUES, "items": [
            {"label": m["label"], "route": f"/dashboard/danh-muc/{m['slug']}", "icon": m["icon"]} for m in masters]})

    legacy = {}
    for label, href, doctype, group in LEGACY_LINKS:
        if _can_read(doctype):
            legacy.setdefault(group, []).append({"label": label, "href": href})
    user = frappe.session.user
    return {
        "user": {"name": user, "full_name": display_name(user), "roles": frappe.get_roles(user)},
        "org": frappe.db.get_single_value("Organization Info", "org_name") or "Document Manager",
        "nav": nav,
        "legacy": [{"group": g, "items": items} for g, items in legacy.items()],
        "masters": _with_permissions(masters),
        "archive": _with_permissions([e for e in ARCHIVE_SCREENS if _can_read(e["doctype"])]),
        "upload": {"extensions": UPLOAD_EXTENSIONS, "max_mb": UPLOAD_MAX_MB},
    }


@frappe.whitelist()
def get_staff_boot():
    if not is_staff():
        frappe.throw("Bạn không có quyền truy cập", frappe.PermissionError)
    return build_boot()
