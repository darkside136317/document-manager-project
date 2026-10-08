# -*- coding: utf-8 -*-
"""Reader reports of module 6: the readers, the slips they sent, the slips overdue and what is asked for most."""

import frappe
from frappe import _
from frappe.utils import cint, nowdate

from document_manager.document_manager.services import lifecycle as lc
from document_manager.document_manager.services.reports.base import (
    UNKNOWN,
    Report,
    Where,
    bar_chart,
    check,
    col,
    data,
    date,
    grouped,
    link,
    page_args,
    register,
    rows,
    scalar,
    select,
)

GROUP = "Độc giả và khai thác"
BOTH, USAGE_ONLY, COPY_ONLY = "Cả hai loại phiếu", "Phiếu yêu cầu sử dụng", "Phiếu sao chụp"
KINDS = [BOTH, USAGE_ONLY, COPY_ONLY]
ACTIVE, LOCKED = "Đang hoạt động", "Ngừng hoạt động"
# a slip that was sent (not a basket, not cancelled): the ones the statistics count
SENT = "docstatus < 2 AND workflow_state NOT IN ('Nháp', 'Đã hủy')"
GRANTED = (lc.STATE_APPROVED, lc.STATE_IN_USE, lc.STATE_RETURNED, lc.STATE_COMPLETED)


# --- Báo cáo độc giả -----------------------------------------------------------------------------------------------

def run_readers(filters, page, page_size):
    page, page_size = page_args(page, page_size)
    where = Where().equal("r.reader_group", filters, "reader_group")
    where.like(["r.full_name", "r.email", "r.phone", "r.organization"], filters, "q")
    where.between("r.registration_date", filters, "registered_from", "registered_to")
    if "state" in filters:
        where.add("r.is_active = %(active)s", active=1 if filters["state"] == ACTIVE else 0)
    total = scalar(f"SELECT COUNT(*) FROM `tabReader` r WHERE {where.sql}", where.params)
    readers = rows(
        f"""SELECT r.name, r.full_name, r.email, r.phone, r.organization, r.reader_group, r.registration_date, r.is_active
            FROM `tabReader` r WHERE {where.sql} ORDER BY r.full_name, r.name LIMIT %(limit)s OFFSET %(offset)s""",
        {**where.params, "limit": page_size, "offset": (page - 1) * page_size})
    names = [r.name for r in readers]
    usage = grouped("Usage Request", "reader", names, ", MAX(request_date) AS last", SENT)
    copies = grouped("Copy Request", "reader", names, ", MAX(request_date) AS last", SENT)
    overdue = grouped("Usage Request", "reader", names, "", f"is_overdue = 1 AND workflow_state = '{lc.STATE_IN_USE}'")
    out = []
    for r in readers:
        u, c = usage.get(r.name), copies.get(r.name)
        lasts = [x.last for x in (u, c) if x and x.last]
        out.append({
            "name": r.name, "full_name": r.full_name, "email": r.email or "", "phone": r.phone or "",
            "organization": r.organization or "", "reader_group": r.reader_group or "",
            "registration_date": r.registration_date, "usage_slips": cint(u.n) if u else 0,
            "copy_slips": cint(c.n) if c else 0, "overdue": cint(overdue[r.name].n) if r.name in overdue else 0,
            "last_request": max(lasts) if lasts else None, "state": ACTIVE if r.is_active else LOCKED,
        })
    summary = {
        "full_name": _("Tổng cộng"),
        "usage_slips": scalar(f"SELECT COUNT(*) FROM `tabUsage Request` WHERE {SENT} AND reader IN "
                              f"(SELECT r.name FROM `tabReader` r WHERE {where.sql})", where.params),
        "copy_slips": scalar(f"SELECT COUNT(*) FROM `tabCopy Request` WHERE {SENT} AND reader IN "
                             f"(SELECT r.name FROM `tabReader` r WHERE {where.sql})", where.params),
        "overdue": scalar(f"SELECT COUNT(*) FROM `tabUsage Request` WHERE is_overdue = 1 AND workflow_state = "
                          f"'{lc.STATE_IN_USE}' AND reader IN (SELECT r.name FROM `tabReader` r WHERE {where.sql})",
                          where.params),
    }
    return {"rows": out, "total": total, "summary": summary}


register(Report(
    slug="doc-gia", title="Báo cáo độc giả", group=GROUP, icon="users", paged=True,
    description="Danh sách độc giả kèm nhóm quyền, số phiếu đã gửi, số phiếu đang quá hạn và lần yêu cầu gần nhất.",
    needs=("Reader",), run=run_readers,
    filters=[link("reader_group", "Nhóm độc giả", "Reader Group"), select("state", "Tình trạng", [ACTIVE, LOCKED]),
             date("registered_from", "Đăng ký từ ngày"), date("registered_to", "Đăng ký đến ngày"),
             data("q", "Tên, email, điện thoại hoặc đơn vị")],
    columns=[col("full_name", "Họ và tên"), col("organization", "Cơ quan, đơn vị"), col("email", "Email"),
             col("phone", "Điện thoại"), col("reader_group", "Nhóm độc giả"), col("registration_date", "Ngày đăng ký", "Date"),
             col("usage_slips", "Phiếu sử dụng", "Int"), col("copy_slips", "Phiếu sao chụp", "Int"),
             col("overdue", "Quá hạn", "Int"), col("last_request", "Yêu cầu gần nhất", "Date"), col("state", "Tình trạng")],
))


# --- Thống kê phiếu yêu cầu ----------------------------------------------------------------------------------------

BY_STATE, BY_MONTH, BY_GROUP, BY_READER = "Trạng thái", "Tháng", "Nhóm độc giả", "Độc giả"
SLIP_DIMENSIONS = {
    BY_STATE: "s.workflow_state", BY_MONTH: "DATE_FORMAT(s.request_date, '%%Y-%%m')",
    BY_GROUP: "r.reader_group", BY_READER: "COALESCE(r.full_name, s.reader)",
}
MAX_SLIP_ROWS = 500


def _slip_sent(alias: str) -> str:
    return f"{alias}.docstatus < 2 AND {alias}.workflow_state NOT IN ('Nháp', 'Đã hủy')"


def run_slip_stats(filters, page, page_size):
    dimension = filters.get("group_by", BY_STATE)
    parts = []
    if filters.get("kind", BOTH) in (BOTH, USAGE_ONLY):
        parts.append(f"""SELECT u.name, u.reader, u.request_date, u.workflow_state, u.is_overdue,
                                (SELECT COUNT(*) FROM `tabUsage Request Item` i WHERE i.parent = u.name) AS items
                         FROM `tabUsage Request` u WHERE {_slip_sent('u')}""")
    if filters.get("kind", BOTH) in (BOTH, COPY_ONLY):
        parts.append(f"""SELECT c.name, c.reader, c.request_date, c.workflow_state, 0 AS is_overdue,
                                (SELECT COUNT(*) FROM `tabCopy Request Item` i WHERE i.parent = c.name) AS items
                         FROM `tabCopy Request` c WHERE {_slip_sent('c')}""")
    where = Where().equal("r.reader_group", filters, "reader_group").between("s.request_date", filters, "date_from", "date_to")
    granted = ", ".join(f"'{state}'" for state in GRANTED)
    found = rows(
        f"""SELECT {SLIP_DIMENSIONS[dimension]} AS k, COUNT(*) AS slips, COALESCE(SUM(s.items), 0) AS items,
                   SUM(s.workflow_state IN ({granted})) AS granted,
                   SUM(s.workflow_state = '{lc.STATE_REJECTED}') AS rejected,
                   SUM(s.workflow_state IN ('{lc.STATE_PENDING}', '{lc.STATE_LEADER}')) AS waiting,
                   SUM(s.is_overdue = 1 AND s.workflow_state = '{lc.STATE_IN_USE}') AS overdue
            FROM ({' UNION ALL '.join(parts)}) s
            LEFT JOIN `tabReader` r ON r.name = s.reader
            WHERE {where.sql} GROUP BY k ORDER BY {'k ASC' if dimension == BY_MONTH else 'slips DESC'}""", where.params)
    out = [{"label": str(r.k) if r.k not in (None, "") else UNKNOWN, "slips": cint(r.slips), "items": cint(r["items"]),
            "granted": cint(r.granted), "rejected": cint(r.rejected), "waiting": cint(r.waiting),
            "overdue": cint(r.overdue)} for r in found]
    summary = {"label": _("Tổng cộng"), **{k: sum(r[k] for r in out) for k in
                                           ("slips", "items", "granted", "rejected", "waiting", "overdue")}}
    top = out[:15]
    chart = bar_chart(_("Số phiếu theo {0}").format(dimension.lower()), [r["label"] for r in top],
                      [r["slips"] for r in top], _("Phiếu"))
    return {"rows": out[:MAX_SLIP_ROWS], "total": len(out), "summary": summary, "chart": chart,
            "columns": _slip_stat_columns(dimension)}


def _slip_stat_columns(label: str) -> list:
    return [col("label", label), col("slips", "Số phiếu", "Int"), col("items", "Số hồ sơ, văn bản", "Int"),
            col("granted", "Được duyệt", "Int"), col("rejected", "Từ chối", "Int"), col("waiting", "Chờ xử lý", "Int"),
            col("overdue", "Quá hạn", "Int")]


register(Report(
    slug="thong-ke-phieu", title="Thống kê phiếu yêu cầu của độc giả", group=GROUP, icon="chart-bar", landscape=False,
    description="Số phiếu sử dụng và sao chụp đã gửi theo trạng thái, tháng, nhóm độc giả hoặc từng độc giả.",
    needs=("Usage Request",), run=run_slip_stats,
    filters=[select("group_by", "Thống kê theo", list(SLIP_DIMENSIONS), BY_STATE), select("kind", "Loại phiếu", KINDS, BOTH),
             link("reader_group", "Nhóm độc giả", "Reader Group"), date("date_from", "Từ ngày"), date("date_to", "Đến ngày")],
    columns=_slip_stat_columns(BY_STATE),
))


# --- Phiếu đang sử dụng và quá hạn ---------------------------------------------------------------------------------

def run_overdue(filters, page, page_size):
    page, page_size = page_args(page, page_size)
    where = Where().add("u.docstatus = 1").add("u.workflow_state = %(state)s", state=lc.STATE_IN_USE)
    if not filters.get("include_not_due"):
        where.add("u.is_overdue = 1")
    where.equal("r.reader_group", filters, "reader_group")
    base = "FROM `tabUsage Request` u LEFT JOIN `tabReader` r ON r.name = u.reader"
    total = scalar(f"SELECT COUNT(*) {base} WHERE {where.sql}", where.params)
    slips = rows(
        f"""SELECT u.name, u.reader, u.reader_name, u.purpose, u.issued_on, u.due_date, u.renewal_count, u.is_overdue,
                   r.reader_group, r.phone, r.email, DATEDIFF(%(today)s, u.due_date) AS days_late,
                   (SELECT COUNT(*) FROM `tabUsage Request Item` i WHERE i.parent = u.name) AS items
            {base} WHERE {where.sql} ORDER BY u.due_date ASC, u.name LIMIT %(limit)s OFFSET %(offset)s""",
        {**where.params, "today": nowdate(), "limit": page_size, "offset": (page - 1) * page_size})
    out = [{
        "name": s.name, "reader_name": s.reader_name or s.reader, "reader_group": s.reader_group or "",
        "contact": " · ".join(x for x in (s.phone, s.email) if x), "purpose": (s.purpose or "")[:140],
        "issued_on": s.issued_on, "due_date": s.due_date, "days_late": max(0, cint(s.days_late)) if s.is_overdue else 0,
        "renewal_count": cint(s.renewal_count), "items": cint(s["items"]),
    } for s in slips]
    items = scalar(f"SELECT COUNT(*) FROM `tabUsage Request Item` WHERE parent IN (SELECT u.name {base} WHERE {where.sql})",
                   where.params)
    return {"rows": out, "total": total, "summary": {"reader_name": _("Tổng cộng"), "items": items}}


register(Report(
    slug="phieu-qua-han", title="Phiếu đang sử dụng và quá hạn", group=GROUP, icon="clock", paged=True,
    description="Các phiếu đã giao tài liệu mà độc giả chưa trả: hạn trả, số ngày quá hạn và cách liên hệ.",
    needs=("Usage Request",), run=run_overdue,
    filters=[check("include_not_due", "Cả phiếu chưa đến hạn trả"), link("reader_group", "Nhóm độc giả", "Reader Group")],
    columns=[col("name", "Số phiếu", link="/doc-gia/phieu-su-dung/{name}"), col("reader_name", "Độc giả"),
             col("reader_group", "Nhóm độc giả"), col("contact", "Liên hệ"), col("purpose", "Mục đích"),
             col("issued_on", "Ngày giao", "Datetime"), col("due_date", "Hạn trả", "Date"),
             col("days_late", "Quá hạn (ngày)", "Int"), col("renewal_count", "Lần gia hạn", "Int"),
             col("items", "Số mục", "Int")],
))


# --- Tài liệu được khai thác nhiều ---------------------------------------------------------------------------------

LEVEL_BOTH, LEVEL_FILES, LEVEL_DOCS = "Hồ sơ và văn bản", "Chỉ hồ sơ", "Chỉ văn bản"
MAX_TOP_ROWS = 100


def run_top_items(filters, page, page_size):
    parts = []
    granted = ", ".join(f"'{state}'" for state in GRANTED)
    if filters.get("kind", BOTH) in (BOTH, USAGE_ONLY):
        parts.append(f"""SELECT i.archival_file, i.archive_document, p.reader, p.request_date
                         FROM `tabUsage Request Item` i JOIN `tabUsage Request` p ON p.name = i.parent
                         WHERE p.docstatus < 2 AND p.workflow_state IN ({granted}) AND i.item_status <> '{lc.ITEM_REJECTED}'""")
    if filters.get("kind", BOTH) in (BOTH, COPY_ONLY):
        parts.append(f"""SELECT i.archival_file, i.archive_document, p.reader, p.request_date
                         FROM `tabCopy Request Item` i JOIN `tabCopy Request` p ON p.name = i.parent
                         WHERE p.docstatus < 2 AND p.workflow_state IN ({granted}) AND i.item_status <> '{lc.ITEM_REJECTED}'""")
    where = Where().between("t.request_date", filters, "date_from", "date_to")
    level = filters.get("level", LEVEL_BOTH)
    if level == LEVEL_FILES:
        where.add("(t.archive_document IS NULL OR t.archive_document = '')")
    elif level == LEVEL_DOCS:
        where.add("(t.archive_document IS NOT NULL AND t.archive_document <> '')")
    found = rows(
        f"""SELECT t.archive_document, t.archival_file, COUNT(*) AS times, COUNT(DISTINCT t.reader) AS readers,
                   ad.document_title, ad.document_number, af.file_title, af.file_number, fo.fonds_name
            FROM ({' UNION ALL '.join(parts)}) t
            LEFT JOIN `tabArchive Document` ad ON ad.name = t.archive_document
            LEFT JOIN `tabArchival File` af ON af.name = t.archival_file
            LEFT JOIN `tabFonds` fo ON fo.name = COALESCE(ad.fonds, af.fonds)
            WHERE {where.sql}
            GROUP BY t.archive_document, t.archival_file ORDER BY times DESC, readers DESC LIMIT {MAX_TOP_ROWS}""", where.params)
    out = []
    for r in found:
        is_document = bool(r.archive_document)
        out.append({
            "name": r.archive_document or r.archival_file, "kind": _("Văn bản") if is_document else _("Hồ sơ"),
            "number": (r.document_number if is_document else r.file_number) or "",
            "title": (r.document_title if is_document else r.file_title) or "", "fonds_name": r.fonds_name or "",
            "times": cint(r.times), "readers": cint(r.readers),
            "route": f"/van-ban/{r.archive_document}" if is_document else f"/ho-so/{r.archival_file}",
        })
    top = out[:15]
    chart = bar_chart(_("Số lần được yêu cầu"), [(r["title"] or r["name"])[:40] for r in top],
                      [r["times"] for r in top], _("Lần"))
    return {"rows": out, "total": len(out), "summary": None, "chart": chart}


register(Report(
    slug="tai-lieu-duoc-khai-thac", title="Hồ sơ, văn bản được khai thác nhiều", group=GROUP, icon="trending-up",
    description="Các hồ sơ, văn bản được độc giả yêu cầu nhiều nhất trong những phiếu đã được duyệt (tối đa 100 dòng).",
    needs=("Usage Request",), run=run_top_items, landscape=False,
    filters=[select("kind", "Loại phiếu", KINDS, BOTH), select("level", "Đối tượng", [LEVEL_BOTH, LEVEL_FILES, LEVEL_DOCS], LEVEL_BOTH),
             date("date_from", "Từ ngày"), date("date_to", "Đến ngày")],
    columns=[col("kind", "Loại"), col("number", "Số"), col("title", "Tiêu đề", link="{route}"), col("fonds_name", "Phông"),
             col("times", "Số lần yêu cầu", "Int"), col("readers", "Số độc giả", "Int")],
))
