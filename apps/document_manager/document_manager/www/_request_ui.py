# -*- coding: utf-8 -*-
"""Shared page logic for the reader request pages (usage_requests, copy_requests, reader_feedbacks).

Files starting with `_` are not routed by Frappe, so this module is only imported by the pages.
Record visibility is enforced by DocPerm + permission_query_conditions (see permissions.py);
state changes go through the Workflow via api.requests.
"""

from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.html_utils import clean_html

from document_manager.document_manager.api.requests import get_actions
from document_manager.document_manager.permissions import (
    get_reader_profile,
    is_staff,
    require_portal_user,
)

PAGE_LENGTH = 20

STATE_CLASS = {
    "Nháp": "",
    "Chờ duyệt": "warning",
    "Đã duyệt": "success",
    "Từ chối": "danger",
    "Đã trả": "",
    "Đã hoàn thành": "",
    "Đã hủy": "",
    "Mới": "warning",
    "Đã xem": "",
    "Đã phản hồi": "success",
}

CONFIGS = {
    "usage_requests": {
        "doctype": "Usage Request",
        "route": "/usage_requests",
        "state_field": "workflow_state",
        "states": ["Nháp", "Chờ duyệt", "Đã duyệt", "Từ chối", "Đã trả", "Đã hủy"],
        "list_title": "Danh sách Yêu cầu Khai thác",
        "form_title": "Phiếu Yêu cầu Khai thác",
        "new_title": "Tạo Phiếu Y/C Khai thác mới",
        "new_label": "Tạo Yêu cầu mới",
        "icon": "fa-check-square-o",
        "purpose_label": "Mục đích sử dụng",
        "items_title": "Danh sách Hồ sơ / Văn bản yêu cầu",
        "copy_count": False,
    },
    "copy_requests": {
        "doctype": "Copy Request",
        "route": "/copy_requests",
        "state_field": "workflow_state",
        "states": ["Nháp", "Chờ duyệt", "Đã duyệt", "Từ chối", "Đã hoàn thành", "Đã hủy"],
        "list_title": "Danh sách Yêu cầu Sao chụp",
        "form_title": "Phiếu Sao chụp Tài liệu",
        "new_title": "Tạo Phiếu Sao chụp mới",
        "new_label": "Tạo Phiếu sao chụp",
        "icon": "fa-copy",
        "purpose_label": "Mục đích sao chụp",
        "items_title": "Danh sách Tài liệu cần Sao chụp",
        "copy_count": True,
    },
    "reader_feedbacks": {
        "doctype": "Reader Feedback",
        "route": "/reader_feedbacks",
        "state_field": "status",
        "states": ["Mới", "Đã xem", "Đã phản hồi"],
        "list_title": "Góp ý của Độc giả",
        "form_title": "Chi tiết Góp ý",
        "new_title": "Gửi Góp ý",
        "new_label": "Gửi góp ý mới",
        "icon": "fa-comments",
    },
}


# Readers work in the reader site now; these pages stay for staff until their queue moves to the staff app.
PORTAL_PAGES = {"usage_requests": "/portal/phieu", "copy_requests": "/portal/sao-chep", "reader_feedbacks": "/portal/gop-y"}


def readers_to_portal(key):
    """Guests sign in first; readers are sent to the same record in the reader site; staff stay here."""
    require_portal_user(PORTAL_PAGES[key])
    if is_staff():
        return
    name = frappe.form_dict.get("name")
    frappe.local.flags.redirect_location = PORTAL_PAGES[key] + (f"/{quote(name)}" if name else "")
    raise frappe.Redirect(302)  # depends on the session: never a cacheable 301


def _can_create(key):
    """Show the 'new' button only to users who can actually file this kind of record."""
    cfg = CONFIGS[key]
    if not frappe.has_permission(cfg["doctype"], "create"):
        return False
    if key == "reader_feedbacks":
        return bool(get_reader_profile())  # feedback is always filed as the user's own profile
    return is_staff() or bool(get_reader_profile())  # staff may file on behalf of a reader


def _base(context):
    staff = is_staff()
    context.base_template = "templates/dm_dashboard_base.html" if staff else "templates/dm_portal_base.html"
    context.is_staff = staff
    context.state_class = STATE_CLASS


def list_context(context, key):
    cfg = CONFIGS[key]
    require_portal_user(cfg["route"])
    _base(context)

    start = cint(frappe.form_dict.get("start", 0))
    search = (frappe.form_dict.get("search") or "").strip()
    status = frappe.form_dict.get("status") or frappe.form_dict.get("workflow_state") or ""
    if status not in cfg["states"]:
        status = ""

    filters = {}
    if search:
        filters["name"] = ["like", f"%{search}%"]
    if status:
        filters[cfg["state_field"]] = status

    fields = ["name", cfg["state_field"] + " as state", "reader_name", "docstatus"]
    fields += ["subject", "feedback_date"] if key == "reader_feedbacks" else ["request_date", "purpose"]
    rows = frappe.get_list(
        cfg["doctype"], filters=filters, fields=fields,
        start=start, page_length=PAGE_LENGTH, order_by="modified desc",
    )
    total = frappe.get_list(cfg["doctype"], filters=filters, fields=[{"COUNT": "name", "as": "c"}])[0].c

    context.update({
        "cfg": cfg,
        "can_create": _can_create(key),
        "page_title": cfg["list_title"],
        "page_icon": cfg["icon"],
        "breadcrumbs": [{"label": "Độc giả & Khai thác"}],
        "rows": rows,
        "search_term": search,
        "status_filter": status,
        "start": start,
        "limit": PAGE_LENGTH,
        "total_count": total,
        "has_more": start + PAGE_LENGTH < total,
        "query_base": f"search={quote(search)}&status={quote(status)}",
    })


def form_context(context, key):
    cfg = CONFIGS[key]
    require_portal_user(f"{cfg['route']}/form")
    _base(context)

    name = frappe.form_dict.get("name")
    doc, actions, can_edit = None, [], False
    if name:
        # One generic answer for "missing" and "not yours", so names cannot be probed.
        if not frappe.db.exists(cfg["doctype"], name) or not frappe.has_permission(cfg["doctype"], "read", doc=name):
            frappe.throw(_("Không tìm thấy phiếu hoặc bạn không có quyền xem"), frappe.PermissionError)
        doc = frappe.get_doc(cfg["doctype"], name)
        # "Gửi duyệt" is the draft's "Gửi yêu cầu" button, handled with the form fields.
        actions = [a for a in get_actions(cfg["doctype"], name) if a["action"] != "Gửi duyệt"]
        can_edit = key != "reader_feedbacks" and doc.docstatus == 0 and doc.has_permission("write")
        page_title = f"{cfg['form_title']}: {doc.name}"
    else:
        if not frappe.has_permission(cfg["doctype"], "create"):
            frappe.throw(_("Bạn không có quyền tạo phiếu mới"), frappe.PermissionError)
        can_edit = True
        page_title = cfg["new_title"]

    profile = get_reader_profile()
    staff = is_staff()
    # A reader files as their own profile; staff may pick another reader (own profile preselected).
    needs_profile = not profile and (not staff or key == "reader_feedbacks")
    if needs_profile and not doc:
        can_edit = False
    readers = []
    if staff and not doc and key != "reader_feedbacks":
        readers = frappe.get_list("Reader", filters={"is_active": 1}, fields=["name", "full_name"],
                                  order_by="full_name", limit_page_length=500)

    context.update({
        "cfg": cfg,
        "doc": doc,
        "docname": name,
        "state": doc.get(cfg["state_field"]) if doc else None,
        "actions": actions,
        "can_edit": can_edit,
        "readers": readers,
        "reader_profile": profile,
        "reader_name": frappe.db.get_value("Reader", profile, "full_name") if profile else None,
        "needs_profile": needs_profile and not doc,
        "items": doc.get("items") if doc and key != "reader_feedbacks" else [],
        "content_html": clean_html(doc.content or "") if doc and key == "reader_feedbacks" else "",
        "response_html": clean_html(doc.response or "") if doc and key == "reader_feedbacks" else "",
        "page_title": page_title,
        "page_icon": cfg["icon"],
        "breadcrumbs": [
            {"label": "Độc giả & Khai thác"},
            {"label": cfg["list_title"], "link": cfg["route"]},
        ],
    })
