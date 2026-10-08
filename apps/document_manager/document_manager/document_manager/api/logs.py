# -*- coding: utf-8 -*-
"""The system log (Business Activity Log) for the staff app: search, read, export and the guarded clean-up.

Only Document Admin and System Manager. Clean-up is deliberate on purpose: it always shows what would go first
(`preview_purge`), refuses to touch the most recent days, needs the number of rows typed back as confirmation, and
records itself in the log.
"""

import csv
import io

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, nowdate

from document_manager.document_manager.permissions import assert_roles
from document_manager.document_manager.services import audit

DOCTYPE = audit.LOG_DOCTYPE
ADMIN_ROLES = ("Document Admin", "System Manager")
MAX_PAGE = 200
MAX_EXPORT = 50_000
MIN_KEEP_DAYS = 7
LIST_FIELDS = ["name", "activity_type", "reference_doctype", "reference_name", "user", "ip_address", "timestamp", "description"]


def _require() -> None:
    assert_roles(*ADMIN_ROLES)


def _conditions(params: dict) -> tuple[list, list | None]:
    filters = []
    for key in ("activity_type", "user", "reference_doctype"):
        if params.get(key):
            filters.append([DOCTYPE, key, "=", params[key]])
    if params.get("reference_name"):
        filters.append([DOCTYPE, "reference_name", "like", f"%{params['reference_name']}%"])
    if params.get("date_from"):
        filters.append([DOCTYPE, "timestamp", ">=", f"{getdate(params['date_from'])} 00:00:00"])
    if params.get("date_to"):
        filters.append([DOCTYPE, "timestamp", "<=", f"{getdate(params['date_to'])} 23:59:59"])
    or_filters = None
    text = (params.get("search") or "").strip()
    if text:
        like = f"%{text}%"
        or_filters = [[DOCTYPE, f, "like", like] for f in ("description", "reference_name", "user")]
    return filters, or_filters


def _params(**kw) -> dict:
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in kw.items() if v not in (None, "")}


@frappe.whitelist()
def filter_options():
    """The values the filters offer: activity types, and who and what the log mentions."""
    _require()
    types = (frappe.get_meta(DOCTYPE).get_field("activity_type").options or "").split("\n")
    users = frappe.db.sql(f"select distinct user from `tab{DOCTYPE}` where user is not null and user <> '' order by user limit 300")
    doctypes = frappe.db.sql(f"select distinct reference_doctype from `tab{DOCTYPE}` where reference_doctype <> '' order by 1 limit 100")
    return {"activity_types": [t for t in types if t], "users": [u[0] for u in users], "doctypes": [d[0] for d in doctypes]}


@frappe.whitelist()
def list_logs(activity_type=None, user=None, reference_doctype=None, reference_name=None, search=None, date_from=None,
              date_to=None, page=1, page_size=50):
    _require()
    params = _params(activity_type=activity_type, user=user, reference_doctype=reference_doctype, reference_name=reference_name,
                     search=search, date_from=date_from, date_to=date_to)
    filters, or_filters = _conditions(params)
    page, size = max(1, cint(page) or 1), min(MAX_PAGE, max(1, cint(page_size) or 50))
    rows = frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, fields=LIST_FIELDS, order_by="timestamp desc, name desc",
                          start=(page - 1) * size, page_length=size)
    count = frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, fields=[{"COUNT": "name", "as": "c"}])
    return {"data": rows, "total": cint(count[0].c) if count else 0, "page": page, "page_size": size}


@frappe.whitelist()
def get_log(name):
    _require()
    return frappe.get_doc(DOCTYPE, name).as_dict()


@frappe.whitelist()
def download_logs(activity_type=None, user=None, reference_doctype=None, reference_name=None, search=None, date_from=None, date_to=None):
    """The filtered log as CSV (up to 50.000 rows); the download itself is logged."""
    _require()
    params = _params(activity_type=activity_type, user=user, reference_doctype=reference_doctype, reference_name=reference_name,
                     search=search, date_from=date_from, date_to=date_to)
    filters, or_filters = _conditions(params)
    rows = frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, fields=LIST_FIELDS, order_by="timestamp desc, name desc",
                          page_length=MAX_EXPORT + 1)
    if len(rows) > MAX_EXPORT:
        frappe.throw(_("Có hơn {0} dòng nhật ký, hãy thu hẹp bộ lọc rồi tải lại").format(MAX_EXPORT))
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Thời gian", "Loại", "Người dùng", "Đối tượng", "Mã đối tượng", "Địa chỉ IP", "Nội dung"])
    for r in rows:
        writer.writerow([r.timestamp, r.activity_type, r.user or "", r.reference_doctype or "", r.reference_name or "", r.ip_address or "",
                         r.description or ""])
    audit.log_activity("Tải xuống", DOCTYPE, "", f"Tải nhật ký hệ thống ({len(rows)} dòng)")
    frappe.local.response.update({"type": "download", "filename": f"nhat-ky-he-thong-{nowdate()}.csv",
                                  "filecontent": ("﻿" + out.getvalue()).encode("utf-8"), "content_type": "text/csv; charset=utf-8"})


# --- clean-up ---------------------------------------------------------------------------------------------------------

def _purge_conditions(before, activity_types) -> tuple[str, dict]:
    cutoff = getdate(before)
    if cutoff > getdate(add_days(nowdate(), -MIN_KEEP_DAYS)):
        frappe.throw(_("Chỉ được dọn nhật ký cũ hơn {0} ngày").format(MIN_KEEP_DAYS))
    types = frappe.parse_json(activity_types) if isinstance(activity_types, str) and activity_types else (activity_types or [])
    sql, params = "`timestamp` < %(before)s", {"before": f"{cutoff} 00:00:00"}
    if types:
        sql += " and activity_type in %(types)s"
        params["types"] = tuple(types)
    return sql, params


@frappe.whitelist()
def preview_purge(before, activity_types=None):
    """What a clean-up of everything before `before` would delete: the count, the oldest and newest row, per type."""
    _require()
    where, params = _purge_conditions(before, activity_types)
    total, oldest, newest = frappe.db.sql(f"select count(*), min(`timestamp`), max(`timestamp`) from `tab{DOCTYPE}` where {where}", params)[0]
    by_type = frappe.db.sql(f"select activity_type, count(*) from `tab{DOCTYPE}` where {where} group by activity_type order by 2 desc", params)
    return {"total": cint(total), "oldest": oldest, "newest": newest, "by_type": [{"activity_type": t, "count": c} for t, c in by_type],
            "min_keep_days": MIN_KEEP_DAYS, "before": str(getdate(before))}


@frappe.whitelist(methods=["POST"])
def purge(before, confirm_count, activity_types=None):
    """Delete the rows `preview_purge` counted. `confirm_count` must be that very number, so a stale preview cannot delete more."""
    _require()
    preview = preview_purge(before, activity_types)
    if not preview["total"]:
        frappe.throw(_("Không có dòng nhật ký nào để dọn"))
    if cint(confirm_count) != preview["total"]:
        frappe.throw(_("Số dòng xác nhận ({0}) không khớp với số dòng sẽ xóa ({1}). Hãy xem trước lại.").format(cint(confirm_count), preview["total"]))
    types = frappe.parse_json(activity_types) if isinstance(activity_types, str) and activity_types else (activity_types or [])
    deleted = audit.purge_logs(f"{getdate(before)} 00:00:00", types=types or None)
    return {"deleted": deleted, "expected": preview["total"]}
