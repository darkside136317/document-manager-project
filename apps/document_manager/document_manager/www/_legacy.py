# -*- coding: utf-8 -*-
"""Old addresses of the screens that moved: each one forwards to the new place for who is asking.

The reader pages and the reading room's queues now live in the reader site (/portal/...) and in the staff
app (/dashboard/doc-gia/...); the old www pages are empty shells whose controller sends the visitor on.
Guests sign in first and come back; readers go to their own page (or /portal when the old page was for staff only).
"""

from urllib.parse import quote

import frappe

from document_manager.document_manager.permissions import is_staff, login_redirect
from document_manager.document_manager.services.web import current_route
from document_manager.www._reader_ui import redirect_to

# old route -> (page of the reader site, page of the staff app); None: the old page was staff only
MOVED = {
    "usage_requests": ("/portal/phieu", "/dashboard/doc-gia/phieu-su-dung"),
    "copy_requests": ("/portal/sao-chep", "/dashboard/doc-gia/phieu-sao-chup"),
    "reader_feedbacks": ("/portal/gop-y", "/dashboard/doc-gia/gop-y"),
    "readers": (None, "/dashboard/doc-gia/doc-gia"),
    "reader_settings": (None, "/dashboard/doc-gia/thiet-lap-doc-gia"),
}
# these pages opened one record by ?name=: the new pages do too (not the reader management list)
RECORD_PAGES = {"usage_requests", "copy_requests", "reader_feedbacks"}


def moved(key: str):
    """Forward the visitor of the old page `key` to its new home (always a temporary redirect: it depends on who asks)."""
    reader_route, staff_route = MOVED[key]
    if frappe.session.user == "Guest":
        login_redirect(current_route())
    target = staff_route if is_staff() else (reader_route or "/portal")
    name = frappe.form_dict.get("name")
    if name and key in RECORD_PAGES:
        target += f"/{quote(name)}"
    redirect_to(target)
