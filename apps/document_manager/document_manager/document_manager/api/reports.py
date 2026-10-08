# -*- coding: utf-8 -*-
"""API of the report screens of the staff app: the catalogue of reports, running one, and its CSV/XLSX/print output.

Whether a user may run a report is decided in `services/reports` (staff role, and read access to the DocTypes
the report is built from); every endpoint here goes through it.
"""

import frappe
from frappe import _
from frappe.utils import nowdate

from document_manager.document_manager.permissions import is_staff
from document_manager.document_manager.services import reports
from document_manager.document_manager.services.audit import log_activity
from document_manager.document_manager.services.reports import output

FORMATS = ("xlsx", "csv")


@frappe.whitelist()
def list_reports():
    """[{group, reports: [{slug, title, description, icon}]}] of the reports the user may run."""
    if not is_staff():
        frappe.throw(_("Bạn không có quyền xem báo cáo"), frappe.PermissionError)
    groups = {}
    for report in reports.visible():
        groups.setdefault(report.group, []).append(
            {"slug": report.slug, "title": report.title, "description": report.description, "icon": report.icon})
    return [{"group": group, "reports": items} for group, items in groups.items()]


@frappe.whitelist()
def get_report(slug):
    """The form of a report: its title, filters and default columns."""
    return reports.get(slug).describe()


@frappe.whitelist()
def run_report(slug, filters=None, page=1, page_size=None):
    return reports.run(slug, filters, page, page_size)


def _file_name(slug: str, extension: str) -> str:
    return f"bao-cao-{slug}-{nowdate()}.{extension}"


@frappe.whitelist()
def download_report(slug, filters=None, format="xlsx"):
    """The whole result (up to 50.000 rows) as an Excel or CSV file."""
    if format not in FORMATS:
        frappe.throw(_("Định dạng {0} không được hỗ trợ").format(format))
    result, applied = output.prepare(slug, filters, output.MAX_EXPORT_ROWS)
    if format == "csv":
        content, mime = output.to_csv(result), "text/csv; charset=utf-8"
    else:
        content, mime = output.to_xlsx(result, applied), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    log_activity("Tải xuống", "Report", slug, f"Xuất báo cáo “{result['title']}” ({format.upper()}, {len(result['rows'])} dòng)")
    frappe.local.response.update({"type": "download", "filename": _file_name(slug, format), "filecontent": content,
                                  "content_type": mime})


@frappe.whitelist()
def print_report(slug, filters=None, format="html"):
    """The printable report with the unit's header: a page to view (format html) or a PDF."""
    if format not in ("html", "pdf"):
        frappe.throw(_("Định dạng {0} không được hỗ trợ").format(format))
    result, applied = output.prepare(slug, filters, output.MAX_PRINT_ROWS)
    html = output.render_html(result, applied)
    log_activity("Tải xuống", "Report", slug, f"In báo cáo “{result['title']}” ({format.upper()})")
    if format == "pdf":
        from frappe.utils.pdf import get_pdf

        options = {"orientation": "Landscape" if result["landscape"] else "Portrait",
                   "load-error-handling": "ignore", "load-media-error-handling": "ignore"}
        frappe.local.response.update({"type": "pdf", "filename": _file_name(slug, "pdf"),
                                      "filecontent": get_pdf(html, options=options)})
        return
    frappe.local.response.update({"type": "download", "filename": _file_name(slug, "html"), "filecontent": html.encode("utf-8"),
                                  "content_type": "text/html; charset=utf-8", "display_content_as": "inline"})

