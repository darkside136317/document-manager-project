# -*- coding: utf-8 -*-
"""Everything the staff SPA needs at start-up: who the user is and what the sidebar shows."""

import frappe

from document_manager.document_manager.constants import (
    ARCHIVE_SCREENS,
    GROUP_CATALOGUES,
    GROUP_CATALOGUING,
    GROUP_EXCHANGE,
    GROUP_READERS,
    GROUP_REPORTS,
    GROUP_SLIPS,
    INVENTORY_SCREENS,
    LEGACY_LINKS,
    MASTERS,
    READER_SCREENS,
    SETTINGS_SCREENS,
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


def _reader_nav() -> list:
    """Sidebar groups of the slip queues and the reader management screens the user may open."""
    from document_manager.document_manager.api import slips
    from document_manager.document_manager.services.registration import pending_count

    nav = []
    if _can_read("Usage Request"):
        badge = slips.waiting_counts()
        nav.append({"group": GROUP_SLIPS, "items": [
            {"label": "Phiếu yêu cầu sử dụng", "route": "/dashboard/doc-gia/phieu-su-dung", "icon": "clipboard-list", "badge": badge["usage"]},
            {"label": "Phiếu sao chụp", "route": "/dashboard/doc-gia/phieu-sao-chup", "icon": "copy", "badge": badge["copy"]},
            *([{"label": "Góp ý của độc giả", "route": "/dashboard/doc-gia/gop-y", "icon": "message-square", "badge": badge["feedback"]}]
              if _can_read("Reader Feedback") else []),
        ]})
    items = []
    if _can_read("Reader Registration"):
        items.append({"label": "Đăng ký độc giả", "route": "/dashboard/doc-gia/dang-ky", "icon": "user-plus", "badge": pending_count()})
    items += [{"label": e["label"], "route": f"/dashboard/doc-gia/{e['slug']}", "icon": e["icon"]}
              for e in [*READER_SCREENS, *SETTINGS_SCREENS] if _can_read(e["doctype"])]
    if items:
        nav.append({"group": GROUP_READERS, "items": items})
    return nav


def _reports_nav() -> list:
    """The report hub and the inventory of the fonds, for whoever may run at least one report."""
    from document_manager.document_manager.services import reports

    items = []
    if reports.visible():
        items.append({"label": "Báo cáo, thống kê", "route": "/dashboard/bao-cao", "icon": "chart-bar"})
    items += [{"label": e["label"], "route": f"/dashboard/{e['slug']}", "icon": e["icon"]}
              for e in INVENTORY_SCREENS if _can_read(e["doctype"])]
    return [{"group": GROUP_REPORTS, "items": items}] if items else []


def _exchange_nav() -> list:
    from document_manager.document_manager.services.exchange import can_exchange

    if not can_exchange():
        return []
    return [{"group": GROUP_EXCHANGE, "items": [
        {"label": "Xuất, nhập XML", "route": "/dashboard/trao-doi-du-lieu", "icon": "arrow-left-right"}]}]


def build_boot() -> dict:
    """Sidebar sections filtered by the user's permissions (the server still enforces every call)."""
    nav = [{"group": "Tổng quan", "items": [
        {"label": "Tổng quan", "route": "/dashboard", "icon": "layout-dashboard"}]}]

    if _can_read("Archival File"):
        nav.append({"group": GROUP_CATALOGUING, "items": [
            {"label": "Biên mục hồ sơ, văn bản", "route": "/dashboard/bien-muc", "icon": "folder-tree"},
            {"label": "Tìm kiếm", "route": "/dashboard/tim-kiem", "icon": "search"},
        ]})

    nav.extend(_reader_nav())
    nav.extend(_reports_nav())
    nav.extend(_exchange_nav())

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
        "readers": _with_permissions([e for e in READER_SCREENS if _can_read(e["doctype"])]),
        "settings": _with_permissions([e for e in SETTINGS_SCREENS if _can_read(e["doctype"])]),
        "archive": _with_permissions([e for e in ARCHIVE_SCREENS if _can_read(e["doctype"])]),
        "inventory": _with_permissions([e for e in INVENTORY_SCREENS if _can_read(e["doctype"])]),
        "upload": {"extensions": UPLOAD_EXTENSIONS, "max_mb": UPLOAD_MAX_MB},
    }


@frappe.whitelist()
def get_staff_boot():
    if not is_staff():
        frappe.throw("Bạn không có quyền truy cập", frappe.PermissionError)
    return build_boot()
