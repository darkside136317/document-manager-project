# -*- coding: utf-8 -*-
"""Building blocks of the staff reports: the registry, filter handling and a few SQL helpers.

A report is a `Report` entry: its title and group, the filters its form offers, its default columns and a
`run(filters, page, page_size)` function returning

    {"rows": [...], "total": int, "summary": {...} | None, "chart": {...} | None,
     "columns": [...] (optional, when the columns depend on a filter), "info": [(label, value)] (optional)}

Rows are dicts keyed by the columns' `fieldname`. Everything is computed with parameterised SQL over the
indexed link columns (`fonds`, `catalog`, `archival_file`, ...) and totals come from one aggregate query,
never from loading rows. Who may run a report is decided by `needs`: the DocTypes the user must be able to
read (the staff role gate comes first).
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50
UNKNOWN = "(Chưa xác định)"

REPORTS: dict[str, "Report"] = {}


@dataclass
class Report:
    slug: str
    title: str
    group: str
    description: str
    icon: str
    run: Callable
    columns: list = field(default_factory=list)
    filters: list = field(default_factory=list)
    needs: tuple = ()
    paged: bool = False
    landscape: bool = True

    def describe(self) -> dict:
        return {"slug": self.slug, "title": self.title, "group": self.group, "description": self.description,
                "icon": self.icon, "columns": self.columns, "filters": self.filters, "paged": self.paged}


def register(report: Report) -> Report:
    REPORTS[report.slug] = report
    return report


# --- filter definitions --------------------------------------------------------------------------------------------

def link(fieldname, label, doctype, **extra) -> dict:
    return {"fieldname": fieldname, "label": label, "fieldtype": "Link", "options": doctype, **extra}


def select(fieldname, label, options, default="", **extra) -> dict:
    return {"fieldname": fieldname, "label": label, "fieldtype": "Select", "options": list(options), "default": default,
            **extra}


def data(fieldname, label, **extra) -> dict:
    return {"fieldname": fieldname, "label": label, "fieldtype": "Data", **extra}


def date(fieldname, label, **extra) -> dict:
    return {"fieldname": fieldname, "label": label, "fieldtype": "Date", **extra}


def integer(fieldname, label, **extra) -> dict:
    return {"fieldname": fieldname, "label": label, "fieldtype": "Int", **extra}


def check(fieldname, label, **extra) -> dict:
    return {"fieldname": fieldname, "label": label, "fieldtype": "Check", **extra}


def col(fieldname, label, fieldtype="Data", **extra) -> dict:
    """A column. `link` is a route template filled from the row ("/ho-so/{name}"), `align` "right" for numbers."""
    align = "right" if fieldtype in ("Int", "Float", "Percent") else "left"
    return {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, "align": align, **extra}


# --- reading the filters -------------------------------------------------------------------------------------------

def parse_filters(report: Report, raw) -> dict:
    """Keep only the filters the report declares, trimmed, typed and validated; empty values are dropped."""
    raw = frappe.parse_json(raw) if isinstance(raw, str) and raw else (raw or {})
    out = {}
    for spec in report.filters:
        name = spec["fieldname"]
        value = raw.get(name)
        if value in (None, "", False):
            if spec.get("default") not in (None, "") and name not in raw:
                value = spec["default"]
            else:
                continue
        kind = spec["fieldtype"]
        if kind == "Int":
            value = cint(value)
        elif kind == "Check":
            value = 1 if cint(value) else 0
        elif kind == "Date":
            try:
                value = getdate(value)
            except Exception:
                frappe.throw(_("Ngày không hợp lệ ở bộ lọc “{0}”").format(spec["label"]))
        elif kind == "Select":
            value = str(value)
            if value not in spec["options"]:
                frappe.throw(_("Giá trị không hợp lệ ở bộ lọc “{0}”").format(spec["label"]))
        else:
            value = str(value).strip()[:140]
        if value in ("", None):
            continue
        out[name] = value
    return out


def page_args(page, page_size, default=DEFAULT_PAGE_SIZE) -> tuple[int, int]:
    return max(1, cint(page) or 1), min(MAX_PAGE_SIZE, max(1, cint(page_size) or default))


# --- SQL helpers ---------------------------------------------------------------------------------------------------

class Where:
    """Accumulates AND-ed conditions with named parameters: `where.add("af.fonds = %(fonds)s", fonds=...)`."""

    def __init__(self):
        self.clauses: list[str] = []
        self.params: dict = {}

    def add(self, clause: str, **params) -> "Where":
        self.clauses.append(clause)
        self.params.update(params)
        return self

    def equal(self, column: str, filters: dict, key: str) -> "Where":
        if key in filters:
            self.add(f"{column} = %({key})s", **{key: filters[key]})
        return self

    def like(self, columns: list[str], filters: dict, key: str) -> "Where":
        if key in filters:
            text = "%" + str(filters[key]).replace("%", r"\%").replace("_", r"\_") + "%"
            self.add("(" + " OR ".join(f"{c} LIKE %({key})s" for c in columns) + ")", **{key: text})
        return self

    def between(self, column: str, filters: dict, start: str, end: str) -> "Where":
        if start in filters:
            self.add(f"{column} >= %({start})s", **{start: filters[start]})
        if end in filters:
            self.add(f"{column} <= %({end})s", **{end: filters[end]})
        return self

    @property
    def sql(self) -> str:
        return " AND ".join(self.clauses) or "1=1"


def rows(query: str, params: dict | None = None) -> list:
    return frappe.db.sql(query, params or {}, as_dict=True)


def scalar(query: str, params: dict | None = None) -> int:
    result = frappe.db.sql(query, params or {})
    return cint(result[0][0]) if result and result[0] else 0


def grouped(table: str, key: str, names: list, extra: str = "", where: str = "") -> dict:
    """{key: row} of `SELECT key, COUNT(*) AS n {extra} FROM table WHERE key IN names GROUP BY key`."""
    if not names:
        return {}
    suffix = f" AND {where}" if where else ""
    found = rows(f"SELECT {key} AS k, COUNT(*) AS n{extra} FROM `tab{table}` WHERE {key} IN %(names)s{suffix} GROUP BY {key}",
                 {"names": tuple(names)})
    return {r.k: r for r in found}


def period(start, end) -> str:
    """'1990 – 2005' / 'từ 1990' / 'đến 2005' / ''."""
    if start and end:
        return f"{start} – {end}" if start != end else str(start)
    if start:
        return f"từ {start}"
    if end:
        return f"đến {end}"
    return ""


def share(part, whole) -> float:
    return round(flt(part) * 100 / flt(whole), 1) if whole else 0.0


def mb(kilobytes) -> float:
    return round(flt(kilobytes) / 1024, 2)


def bar_chart(title: str, labels: list, values: list, series: str) -> dict | None:
    if not labels:
        return None
    return {"type": "bar", "title": title, "labels": labels, "datasets": [{"name": series, "values": values}]}
