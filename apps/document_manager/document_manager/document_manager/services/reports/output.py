# -*- coding: utf-8 -*-
"""Report output: the whole result as CSV or XLSX, and the printable page (HTML, PDF) with the unit's header."""

import csv
import io
from datetime import date, datetime

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from document_manager.document_manager.services import reports
from document_manager.document_manager.services.reports.base import parse_filters

MAX_EXPORT_ROWS = 50_000
MAX_PRINT_ROWS = 2_000
CHUNK = 1000
TEMPLATE = "document_manager/templates/reports/report_print.html"


def collect(slug: str, filters, limit: int) -> dict:
    """Run the report page by page until every row is read; refuses a result larger than `limit` rows."""
    first = reports.run(slug, filters, 1, CHUNK)
    if first["total"] > limit:
        frappe.throw(_("Báo cáo có {0} dòng, vượt giới hạn {1} dòng. Hãy thu hẹp bộ lọc rồi thử lại.").format(
            f"{first['total']:,}".replace(",", "."), f"{limit:,}".replace(",", ".")))
    result, page = first, 1
    rows = list(first["rows"])
    while first["paged"] and len(rows) < first["total"]:
        page += 1
        more = reports.run(slug, filters, page, CHUNK)["rows"]
        if not more:
            break
        rows.extend(more)
    result["rows"] = rows
    return result


# --- values ---------------------------------------------------------------------------------------------------------

def vn_number(value, decimals=0) -> str:
    """1234567.8 -> '1.234.567,8' (the Vietnamese way)."""
    text = f"{flt(value):,.{decimals}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def display(column: dict, value) -> str:
    """The text of a cell in print and CSV."""
    if value in (None, ""):
        return ""
    kind = column["fieldtype"]
    if kind == "Date" or isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%d/%m/%Y") if hasattr(value, "strftime") else str(value)
    if kind == "Datetime" or isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M") if hasattr(value, "strftime") else str(value)
    if kind == "Int":
        return vn_number(value)
    if kind == "Float":
        return vn_number(value, 2)
    if kind == "Percent":
        return vn_number(value, 1) + "%"
    return str(value)


def filter_summary(report_slug: str, applied: dict) -> list[tuple[str, str]]:
    """[(label, text)] of the filters in use, for the header of a printout."""
    report = reports.get(report_slug)
    out = []
    for spec in report.filters:
        value = applied.get(spec["fieldname"])
        if value in (None, ""):
            continue
        if spec["fieldtype"] == "Check":
            value = _("Có")
        elif spec["fieldtype"] == "Date":
            value = value.strftime("%d/%m/%Y")
        elif spec["fieldtype"] == "Link":
            value = _title_of(spec["options"], value)
        out.append((spec["label"], str(value)))
    return out


def _title_of(doctype: str, name: str) -> str:
    title_field = frappe.get_meta(doctype).title_field
    return (frappe.db.get_value(doctype, name, title_field) if title_field else None) or name


def unit_header() -> dict:
    info = frappe.db.get_singles_dict("Organization Info") or {}
    return {"name": info.get("org_name") or "", "type": info.get("org_type") or "", "address": info.get("address") or "",
            "phone": info.get("phone") or ""}


# --- CSV and XLSX ---------------------------------------------------------------------------------------------------

def to_csv(result: dict) -> bytes:
    """UTF-8 with a BOM, the one Excel opens with Vietnamese letters intact."""
    out = io.StringIO()
    writer = csv.writer(out)
    columns = result["columns"]
    writer.writerow([c["label"] for c in columns])
    for row in result["rows"]:
        writer.writerow([display(c, row.get(c["fieldname"])) for c in columns])
    if result.get("summary"):
        writer.writerow([display(c, result["summary"].get(c["fieldname"])) for c in columns])
    return ("﻿" + out.getvalue()).encode("utf-8")


def to_xlsx(result: dict, applied: list[tuple[str, str]]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = (result["title"] or "Báo cáo")[:31]
    header = unit_header()
    ws.append([header["name"]])
    ws.append([result["title"]])
    for label, text in [*result.get("info", []), *applied]:
        ws.append([f"{label}: {text}"])
    ws.append([f"{_('Ngày lập')}: {now_datetime().strftime('%d/%m/%Y %H:%M')}"])
    ws.append([])
    ws["A1"].font = Font(bold=True, size=12)
    ws["A2"].font = Font(bold=True, size=14)

    columns = result["columns"]
    head_row = ws.max_row + 1
    ws.append([c["label"] for c in columns])
    for cell in ws[head_row]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E8EDF3")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for row in result["rows"]:
        ws.append([_cell(c, row.get(c["fieldname"])) for c in columns])
    if result.get("summary"):
        ws.append([_cell(c, result["summary"].get(c["fieldname"])) for c in columns])
        for cell in ws[ws.max_row]:
            cell.font = Font(bold=True)
    for index, column in enumerate(columns, start=1):
        ws.column_dimensions[get_column_letter(index)].width = min(48, max(12, len(column["label"]) + 4))
        if column["fieldtype"] in ("Int", "Float", "Percent"):
            for cell in ws[get_column_letter(index)][head_row:]:
                cell.number_format = "#,##0.00" if column["fieldtype"] in ("Float", "Percent") else "#,##0"
    ws.freeze_panes = ws.cell(row=head_row + 1, column=1)
    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()


def _cell(column: dict, value):
    if value in (None, ""):
        return None
    if column["fieldtype"] in ("Int",):
        return cint(value)
    if column["fieldtype"] in ("Float", "Percent"):
        return flt(value)
    if column["fieldtype"] in ("Date", "Datetime"):
        return display(column, value)
    return str(value)


# --- print ----------------------------------------------------------------------------------------------------------

def render_html(result: dict, applied: list[tuple[str, str]]) -> str:
    columns = result["columns"]
    return frappe.render_template(TEMPLATE, {
        "title": result["title"], "unit": unit_header(), "info": result.get("info", []), "filters": applied,
        "columns": columns, "landscape": result.get("landscape", True),
        "rows": [[display(c, row.get(c["fieldname"])) for c in columns] for row in result["rows"]],
        "summary": [display(c, result["summary"].get(c["fieldname"])) for c in columns] if result.get("summary") else None,
        "aligns": [c.get("align", "left") for c in columns], "printed_on": now_datetime().strftime("%d/%m/%Y"),
        "user": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
    })


def prepare(slug: str, filters, limit: int) -> tuple[dict, list]:
    result = collect(slug, filters, limit)
    applied = filter_summary(slug, parse_filters(reports.get(slug), filters))
    return result, applied
