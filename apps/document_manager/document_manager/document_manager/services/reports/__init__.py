# -*- coding: utf-8 -*-
"""Staff reports: the registry (`base.REPORTS`) filled by the report modules, and who may run what."""

import frappe
from frappe import _

from document_manager.document_manager.permissions import is_staff
from document_manager.document_manager.services.reports import archive, readers  # noqa: F401  (register the reports)
from document_manager.document_manager.services.reports.base import REPORTS, Report, page_args, parse_filters

GROUP_ORDER = (archive.GROUP, archive.GROUP_STATS, readers.GROUP)


def can_run(report: Report) -> bool:
    return is_staff() and all(frappe.has_permission(doctype, "read") for doctype in report.needs)


def visible() -> list[Report]:
    """The reports the current user may run, in the order of the report hub."""
    mine = [r for r in REPORTS.values() if can_run(r)]
    return sorted(mine, key=lambda r: (GROUP_ORDER.index(r.group) if r.group in GROUP_ORDER else 99, r.title))


def get(slug: str) -> Report:
    report = REPORTS.get(slug)
    if not report:
        frappe.throw(_("Không có báo cáo {0}").format(slug), frappe.DoesNotExistError)
    if not can_run(report):
        frappe.throw(_("Bạn không có quyền xem báo cáo này"), frappe.PermissionError)
    return report


def run(slug: str, filters=None, page=1, page_size=None) -> dict:
    """Run a report: {slug, title, columns, rows, total, page, page_size, summary, chart, info, filters}."""
    report = get(slug)
    parsed = parse_filters(report, filters)
    page, size = page_args(page, page_size)
    result = report.run(parsed, page, size)
    return {"slug": report.slug, "title": report.title, "columns": result.get("columns") or report.columns,
            "rows": result["rows"], "total": result["total"], "page": page, "page_size": size,
            "summary": result.get("summary"), "chart": result.get("chart"), "info": result.get("info") or [],
            "filters": parsed, "paged": report.paged, "landscape": report.landscape}
