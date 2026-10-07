# -*- coding: utf-8 -*-
"""Small helpers shared by the server-rendered pages (the staff SPA host and the reader site)."""

import json

import frappe


def inline_json(data) -> str:
    """JSON that is safe inside a <script> element (no way to close the tag or open a comment)."""
    return (json.dumps(data, ensure_ascii=False, default=str)
            .replace("<", "\u003c").replace(">", "\u003e").replace("&", "\u0026")
            .replace("\u2028", "\u2028").replace("\u2029", "\u2029"))


def csrf_token() -> str:
    """The CSRF token of the session ("" for a guest, whose POSTs to public endpoints need none)."""
    return frappe.sessions.get_csrf_token() if frappe.session.user != "Guest" else ""


def current_route() -> str:
    """Path and query string of the page being rendered, to come back to after signing in."""
    request = getattr(frappe.local, "request", None)
    if not request:
        return "/"
    query = request.query_string.decode("utf-8", "ignore") if request.query_string else ""
    return request.path + (f"?{query}" if query else "")
