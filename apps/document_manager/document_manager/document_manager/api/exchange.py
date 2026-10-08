# -*- coding: utf-8 -*-
"""API of the XML exchange screen (module 5): search and export, upload and analyse, import (or dry run), history.

Only administrators (`services.exchange.EXCHANGE_ROLES`) may use any of it. Exports and imports run in the
background as the user who started them; this module only creates the Data Exchange Job and reports on it.
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import cint

from document_manager.document_manager.services.audit import log_activity
from document_manager.document_manager.services.exchange import exporter, importer, jobs, require_exchange, schema, xmlio

MAX_LIST_PAGE = 100
LOG_ROWS_SHOWN = 200


def _load(value):
    return json.loads(value) if value else None


def _job(doc, rows=False) -> dict:
    progress = jobs.get_progress(doc.name) if doc.status in jobs.BUSY else None
    processed = cint((progress or {}).get("processed", doc.processed))
    total = cint((progress or {}).get("total", doc.total))
    out = {
        "name": doc.name, "direction": doc.direction, "status": doc.status, "level": doc.level or "", "mode": doc.mode or "",
        "dry_run": cint(doc.dry_run), "create_masters": cint(doc.create_masters), "file_name": doc.file_name or "",
        "file_size_kb": doc.file_size_kb, "checksum": doc.checksum or "", "total": total, "processed": processed,
        "created": cint((progress or {}).get("created", doc.created)), "updated": cint((progress or {}).get("updated", doc.updated)),
        "skipped": doc.skipped, "failed": cint((progress or {}).get("failed", doc.failed)), "summary": doc.summary or "",
        "phase": (progress or {}).get("phase", ""), "percent": round(processed * 100 / total) if total else 0,
        "started_on": doc.started_on, "finished_on": doc.finished_on, "owner": doc.owner, "creation": doc.creation,
        "busy": doc.status in jobs.BUSY, "has_result": bool(doc.result_file),
        "analysis": _load(doc.analysis_json), "result": _load(doc.result_json), "options": jobs.options_of(doc),
    }
    if rows:
        out["rows"] = [{"severity": r.severity, "level": r.level, "path": r.path, "message": r.message}
                       for r in (doc.rows or [])[:LOG_ROWS_SHOWN]]
        out["rows_total"] = len(doc.rows or [])
    return out


@frappe.whitelist()
def capabilities():
    """The levels with their search filters and fields, the import modes and the limits, for the screen."""
    require_exchange()
    levels = schema.describe()
    for level in levels:
        level["filters"] = exporter.FILTERS[level["doctype"]]
    return {"levels": levels, "modes": list(importer.MODES), "max_nodes": xmlio.MAX_NODES,
            "max_mb": xmlio.MAX_BYTES // 1024 // 1024, "version": schema.VERSION,
            "masters": sorted(importer.SAFE_MASTERS)}


@frappe.whitelist()
def preview_export(level, filters=None, include_children=0):
    """How many records of each level the export would contain."""
    require_exchange()
    return exporter.plan(level, filters, bool(cint(include_children)))


@frappe.whitelist(methods=["POST"])
def start_export(level, filters=None, fields=None, include_children=0):
    require_exchange()
    options = exporter.validate_request(level, {"filters": filters, "fields": fields, "include_children": include_children})
    plan = exporter.plan(level, options["filters"], bool(options["include_children"]))
    if not plan["counts"][level]:
        frappe.throw(_("Không có bản ghi nào khớp tiêu chí tìm kiếm"))
    if plan["too_many"]:
        frappe.throw(_("Kết quả có {0} bản ghi, vượt giới hạn {1}. Hãy thu hẹp tiêu chí.").format(plan["total"], plan["limit"]))
    job = jobs.new_job(jobs.EXPORT, level=level, options_json=json.dumps(options, ensure_ascii=False), total=plan["total"],
                       file_name=f"xuat-{schema.BY_DOCTYPE[level].element.lower()}.xml")
    jobs.enqueue(job)
    return _job(jobs.get(job.name))


def _uploaded_file(file_url: str):
    name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not name:
        frappe.throw(_("Không tìm thấy tệp đã tải lên"), frappe.DoesNotExistError)
    file = frappe.get_doc("File", name)
    if not file.is_private or (file.owner != frappe.session.user and frappe.session.user != "Administrator"):
        frappe.throw(_("Chỉ nhập từ tệp riêng tư do chính bạn tải lên"), frappe.PermissionError)
    if not (file.file_name or "").lower().endswith(".xml"):
        frappe.throw(_("Chỉ nhận tệp có đuôi .xml"))
    return file


@frappe.whitelist(methods=["POST"])
def analyze_import(file_url):
    """Read an uploaded XML file without writing anything: its structure, counts and fields; a Data Exchange Job keeps it."""
    require_exchange()
    file = _uploaded_file(file_url)
    content = file.get_content()
    content = content.encode("utf-8") if isinstance(content, str) else (content or b"")
    root = xmlio.parse(content)
    problems = xmlio.validate(root)
    if problems:
        return {"valid": False, "errors": problems, "job": None}
    analysis = xmlio.analyze(root)
    job = jobs.new_job(jobs.IMPORT, status=jobs.UPLOADED, file_name=file.file_name, source_file=file.file_url,
                       file_size_kb=round(len(content) / 1024, 2), checksum=hashlib.sha256(content).hexdigest(),
                       total=analysis["total"], level=analysis["attributes"].get("level") or "",
                       analysis_json=json.dumps(analysis, ensure_ascii=False))
    file.db_set({"attached_to_doctype": jobs.DOCTYPE, "attached_to_name": job.name}, update_modified=False)
    log_activity("Nhập XML", jobs.DOCTYPE, job.name, f"Tải lên và phân tích tệp {file.file_name}")
    return {"valid": True, "errors": [], "job": _job(jobs.get(job.name))}


@frappe.whitelist(methods=["POST"])
def start_import(job, mode=None, fields=None, dry_run=0, create_masters=0):
    """Run an analysed upload: add (or add and update) the records, with the fields chosen; `dry_run` writes nothing."""
    require_exchange()
    doc = jobs.get(job)
    if doc.direction != jobs.IMPORT or not doc.analysis_json:
        frappe.throw(_("Lượt này không phải là một tệp nhập đã phân tích"))
    if doc.status in jobs.BUSY:
        frappe.throw(_("Lượt nhập này đang chạy"))
    mode = mode or importer.MODE_INSERT
    if mode not in importer.MODES:
        frappe.throw(_("Cách nhập không hợp lệ"))
    analysis = _load(doc.analysis_json)
    chosen = exporter.selected_fields_ok(fields) if fields else {d: list(f) for d, f in analysis["fields"].items()}
    dry = 1 if cint(dry_run) else 0
    if not dry and frappe.db.exists(jobs.DOCTYPE, {"direction": jobs.IMPORT, "status": ["in", list(jobs.BUSY)], "dry_run": 0,
                                                    "name": ["!=", doc.name]}):
        frappe.throw(_("Đang có một lượt nhập khác chạy, hãy đợi nó kết thúc"))
    options = {"mode": mode, "fields": chosen, "dry_run": dry, "create_masters": 1 if cint(create_masters) else 0}
    doc.update({"options_json": json.dumps(options, ensure_ascii=False), "mode": mode, "dry_run": dry,
                "create_masters": options["create_masters"], "summary": "", "processed": 0, "created": 0, "updated": 0,
                "skipped": 0, "failed": 0, "result_json": ""})
    doc.set("rows", [])
    doc.save(ignore_permissions=True)
    jobs.enqueue(doc)
    log_activity("Nhập XML", jobs.DOCTYPE, doc.name, ("Chạy thử " if dry else "Bắt đầu nhập ") + (doc.file_name or ""))
    return _job(jobs.get(doc.name))


@frappe.whitelist()
def get_job(job):
    require_exchange()
    return _job(jobs.get(job), rows=True)


@frappe.whitelist()
def list_jobs(direction=None, page=1, page_size=20):
    require_exchange()
    page, size = max(1, cint(page) or 1), min(MAX_LIST_PAGE, max(1, cint(page_size) or 20))
    filters = {"direction": direction} if direction in (jobs.EXPORT, jobs.IMPORT) else {}
    names = frappe.get_all(jobs.DOCTYPE, filters=filters, pluck="name", order_by="creation desc", start=(page - 1) * size, page_length=size)
    return {"data": [_job(jobs.get(n)) for n in names], "total": frappe.db.count(jobs.DOCTYPE, filters), "page": page,
            "page_size": size}


@frappe.whitelist(methods=["POST"])
def cancel_job(job):
    require_exchange()
    doc = jobs.get(job)
    if doc.status == jobs.QUEUED:
        doc.db_set({"status": jobs.CANCELLED, "summary": _("Đã hủy trước khi chạy"), "finished_on": frappe.utils.now_datetime()})
    elif doc.status == jobs.RUNNING:
        jobs.request_cancel(doc.name)
    else:
        frappe.throw(_("Lượt này không còn chạy"))
    return _job(jobs.get(job))


@frappe.whitelist(methods=["POST"])
def delete_job(job):
    require_exchange()
    doc = jobs.get(job)
    if doc.status in jobs.BUSY:
        frappe.throw(_("Không xóa được lượt đang chạy, hãy hủy trước"))
    frappe.delete_doc(jobs.DOCTYPE, doc.name, ignore_permissions=True)
    return {"name": job}


@frappe.whitelist()
def download(job):
    """The XML file an export produced."""
    require_exchange()
    doc = jobs.get(job)
    if doc.direction != jobs.EXPORT or not doc.result_file:
        frappe.throw(_("Lượt này không có tệp kết quả"), frappe.DoesNotExistError)
    name = frappe.db.get_value("File", {"file_url": doc.result_file}, "name")
    if not name:
        frappe.throw(_("Tệp kết quả không còn"), frappe.DoesNotExistError)
    content = frappe.get_doc("File", name).get_content()
    log_activity("Tải xuống", jobs.DOCTYPE, doc.name, f"Tải tệp xuất {doc.file_name}")
    frappe.local.response.update({"type": "download", "filename": f"{doc.name}.xml",
                                  "filecontent": content.encode("utf-8") if isinstance(content, str) else content,
                                  "content_type": "application/xml; charset=utf-8"})


@frappe.whitelist()
def download_schema():
    """The XSD of the exchange file."""
    require_exchange()
    frappe.local.response.update({"type": "download", "filename": "archive-exchange.xsd", "filecontent": schema.build_xsd(),
                                  "content_type": "application/xml; charset=utf-8"})
