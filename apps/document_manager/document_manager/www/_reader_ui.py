# -*- coding: utf-8 -*-
"""Shared page logic of the reader site (public pages and the /portal area).

Files starting with `_` are not routed by Frappe. Every reader page calls `page_context(context, ...)`
for the data the layout needs (unit profile, navigation, who is signed in, basket and bell counts)
and, for pages that need a session, `require_reader()` first.
"""

import os
from datetime import date

import frappe

from document_manager.document_manager.permissions import (
    display_name,
    get_reader_profile,
    is_staff,
)
from document_manager.document_manager.services import basket, notify, public_site
from document_manager.document_manager.services.web import csrf_token, current_route, inline_json

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public")
ASSET_FILES = ("css/dm-reader.css", "js/dm-reader.js", "js/vendor/alpine.min.js")

# (key, label, href, icon)
ABOUT_PAGES = (
    ("gioi-thieu", "Giới thiệu", "/gioi-thieu", "building-2"),
    ("lanh-dao", "Lãnh đạo", "/lanh-dao", "users"),
    ("co-cau", "Cơ cấu tổ chức", "/co-cau", "network"),
    ("lien-he", "Liên hệ", "/lien-he", "phone"),
    ("huong-dan", "Hướng dẫn", "/huong-dan", "book-open-text"),
)
READER_PAGES = (
    ("tra-cuu", "Tra cứu", "/portal", "search"),
    ("phieu", "Phiếu sử dụng", "/portal/phieu", "file-text"),
    ("sao-chep", "Phiếu sao chụp", "/portal/sao-chep", "copy"),
    ("gop-y", "Góp ý", "/portal/gop-y", "message-square"),
)


def asset_version() -> str:
    """Changes whenever a reader-site asset does, so browsers never keep a stale script or style."""
    stamp = 0
    for name in ASSET_FILES:
        try:
            stamp = max(stamp, int(os.path.getmtime(os.path.join(ASSETS, name))))
        except OSError:
            pass
    return str(stamp)


def _item(entry):
    key, label, href, icon = entry
    return {"key": key, "label": label, "href": href, "icon": icon}


def _about_nav(org: dict) -> list[dict]:
    hidden = set()
    if not org["show_leaders"]:
        hidden.add("lanh-dao")
    if not org["show_structure"]:
        hidden.add("co-cau")
    return [_item(entry) for entry in ABOUT_PAGES if entry[0] not in hidden]


def require_reader():
    """Pages of the reader area need a session: guests are sent to sign in, then back here."""
    from document_manager.document_manager.permissions import require_portal_user

    require_portal_user(current_route())


def page_context(context, title: str, active: str = "", description: str = "", public: bool = False):
    """Fill `context` with everything templates/reader/base.html needs."""
    user = frappe.session.user
    signed_in = user != "Guest"
    org = public_site.get_org_profile()
    about = _about_nav(org)
    profile = get_reader_profile(user) if signed_in else None
    nav = [_item(entry) for entry in READER_PAGES] + [n for n in about if n["key"] in ("gioi-thieu", "huong-dan")] \
        if signed_in else about
    slips = basket.summary(profile) if profile else {}
    unread = notify.unread_count(user)
    context.update({
        "no_cache": 1,
        "title": title, "description": description, "active": active, "public_page": public,
        "org": org, "nav": nav, "about_nav": about,
        "signed_in": signed_in, "is_staff": signed_in and is_staff(), "has_profile": bool(profile),
        "display_name": display_name(user) if signed_in else "", "user_email": user if signed_in else "",
        "year": date.today().year, "asset_v": asset_version(),
        "boot_json": inline_json({"csrf": csrf_token(), "signed_in": signed_in, "basket": slips, "unread": unread}),
    })
    return context


def redirect_to(location: str):
    frappe.local.flags.redirect_location = location
    raise frappe.Redirect(302)  # depends on the session: never a cacheable 301


def guest_only(default: str = "/portal"):
    """Sign-in and sign-up pages send people who are already in to their own home."""
    if frappe.session.user != "Guest":
        redirect_to("/dashboard" if is_staff() else default)

