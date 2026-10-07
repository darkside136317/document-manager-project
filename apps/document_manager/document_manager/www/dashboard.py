# -*- coding: utf-8 -*-
"""Host page of the staff single-page application (/dashboard and every /dashboard/... route).

The SPA is built by Vite into `public/staff` (see frontend/). This page only
  * keeps non-staff out (readers go to /portal, guests to the login page),
  * hands the SPA its boot data (user, sidebar, CSRF token) as inline JSON,
  * links the hashed JS/CSS files listed in Vite's manifest.
"""

import json
import os

import frappe

from document_manager.document_manager.api.boot import build_boot
from document_manager.document_manager.permissions import require_staff
from document_manager.document_manager.services.web import inline_json

STAFF_BUILD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "staff")
ASSET_BASE = "/assets/document_manager/staff/"


def _entry_assets() -> tuple[list[str], list[str]]:
    """(js, css) URLs of the SPA entry from Vite's manifest; ([], []) when it has not been built."""
    try:
        with open(os.path.join(STAFF_BUILD, ".vite", "manifest.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError):
        return [], []
    entry = next((chunk for chunk in manifest.values() if chunk.get("isEntry")), None)
    if not entry:
        return [], []
    return [ASSET_BASE + entry["file"]], [ASSET_BASE + css for css in entry.get("css", [])]


def get_context(context):
    context.no_cache = 1
    require_staff(frappe.local.request.path if getattr(frappe.local, "request", None) else "/dashboard")

    boot = build_boot()
    boot["csrf_token"] = frappe.sessions.get_csrf_token()
    context.boot_json = inline_json(boot)
    context.dm_js, context.dm_css = _entry_assets()
    context.title = f"{boot['org']} — Quản lý tài liệu lưu trữ"
    return context
