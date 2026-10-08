# -*- coding: utf-8 -*-
"""Data Exchange Job plumbing: creating a job, its progress, its files, its end, and the queue entry point."""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from document_manager.document_manager.services.audit import log_activity
from document_manager.document_manager.services.errors import log_exception

DOCTYPE = "Data Exchange Job"
EXPORT, IMPORT = "Xuất", "Nhập"
UPLOADED, QUEUED, RUNNING, DONE, DONE_WITH_ERRORS, FAILED, CANCELLED = (
    "Đã tải lên", "Chờ xử lý", "Đang xử lý", "Hoàn thành", "Hoàn thành có lỗi", "Thất bại", "Đã hủy")
BUSY = (QUEUED, RUNNING)
MAX_LOG_ROWS = 500
PROGRESS_TTL = 3600


class Cancelled(Exception):
    """Raised inside a run when the user asked to stop it."""


def new_job(direction: str, **values) -> "frappe.model.document.Document":
    doc = frappe.get_doc({"doctype": DOCTYPE, "direction": direction, **values})
    doc.insert(ignore_permissions=True)  # the caller has been checked by api/exchange.py
    return doc


def get(name: str):
    if not frappe.db.exists(DOCTYPE, name):
        frappe.throw(_("Không tìm thấy lượt trao đổi {0}").format(name), frappe.DoesNotExistError)
    return frappe.get_doc(DOCTYPE, name)


def options_of(job) -> dict:
    return json.loads(job.options_json) if job.options_json else {}


# --- progress (kept in the cache while a run is going, so a dry run that rolls back still reports) -------------------

def _key(name: str, suffix: str = "progress") -> str:
    return f"dm_exchange:{name}:{suffix}"


def set_progress(name: str, **values) -> None:
    current = get_progress(name) or {}
    current.update(values)
    frappe.cache.set_value(_key(name), current, expires_in_sec=PROGRESS_TTL)


def get_progress(name: str) -> dict | None:
    return frappe.cache.get_value(_key(name))


def clear_progress(name: str) -> None:
    frappe.cache.delete_value(_key(name))
    frappe.cache.delete_value(_key(name, "cancel"))


def request_cancel(name: str) -> None:
    frappe.cache.set_value(_key(name, "cancel"), 1, expires_in_sec=PROGRESS_TTL)


def check_cancel(name: str) -> None:
    if frappe.cache.get_value(_key(name, "cancel")):
        raise Cancelled()


# --- files ------------------------------------------------------------------------------------------------------------

def save_result_file(job, path: str, file_name: str) -> dict:
    """Attach the written export to the job as a private file; returns {file_url, size_kb, checksum}."""
    from frappe.utils.file_manager import save_file

    with open(path, "rb") as handle:
        content = handle.read()
    saved = save_file(file_name, content, DOCTYPE, job.name, is_private=1)
    return {"file_url": saved.file_url, "size_kb": round(len(content) / 1024, 2),
            "checksum": hashlib.sha256(content).hexdigest()}


def read_source(job) -> bytes:
    """The bytes of the uploaded file of an import job."""
    name = frappe.db.get_value("File", {"file_url": job.source_file}, "name")
    if not name:
        frappe.throw(_("Không còn tệp XML đã tải lên, hãy tải lại"))
    content = frappe.get_doc("File", name).get_content() or b""
    return content.encode("utf-8") if isinstance(content, str) else content


# --- the end of a run -------------------------------------------------------------------------------------------------

def finish(job, status: str, summary: str, result: dict | None = None, rows: list | None = None, **counts) -> None:
    """Record how a run ended (counts, per-level result, the first log rows) and tell the user."""
    values = {"status": status, "summary": summary[:2000], "finished_on": now_datetime(), "processed": cint(counts.get("processed")),
              "total": cint(counts.get("total")), "created": cint(counts.get("created")), "updated": cint(counts.get("updated")),
              "skipped": cint(counts.get("skipped")), "failed": cint(counts.get("failed")),
              "result_json": json.dumps(result or {}, ensure_ascii=False)}
    job.reload()
    job.update(values)
    job.set("rows", [])
    for row in (rows or [])[:MAX_LOG_ROWS]:
        job.append("rows", row)
    job.save(ignore_permissions=True)
    clear_progress(job.name)
    notify(job)


def notify(job) -> None:
    try:
        frappe.get_doc({
            "doctype": "Notification Log", "type": "Alert", "for_user": job.owner, "from_user": job.owner,
            "subject": f"{job.direction} XML: {job.status} — {job.summary}"[:140],
            "document_type": DOCTYPE, "document_name": job.name,
        }).insert(ignore_permissions=True)
    except Exception:
        log_exception("Data Exchange", f"Could not notify the owner of {job.name}")
    log_activity("Xuất XML" if job.direction == EXPORT else "Nhập XML", DOCTYPE, job.name,
                 f"{job.status}: {job.summary}"[:500], user=job.owner)


def fail(job, error: Exception) -> None:
    log_exception("Data Exchange", f"{job.name}: {error}")
    frappe.db.rollback()
    finish(job, FAILED, _("Không hoàn thành: {0}").format(str(error)[:300]))


# --- queue entry point ------------------------------------------------------------------------------------------------

def enqueue(job) -> None:
    job.db_set({"status": QUEUED, "started_on": None, "finished_on": None}, update_modified=False)
    frappe.enqueue("document_manager.document_manager.services.exchange.jobs.run", job=job.name, queue="long",
                   timeout=3600, enqueue_after_commit=True)


def run(job: str) -> None:
    """Worker: run an export or an import as the user who asked for it (their permissions apply)."""
    from document_manager.document_manager.services.exchange import exporter, importer

    doc = get(job)
    if doc.status != QUEUED:
        return  # run twice or cancelled meanwhile
    doc.db_set({"status": RUNNING, "started_on": now_datetime()}, update_modified=False)
    frappe.db.commit()
    try:
        (exporter.run_export if doc.direction == EXPORT else importer.run_import)(doc)
    except Cancelled:
        frappe.db.rollback()
        finish(get(job), CANCELLED, _("Đã dừng theo yêu cầu"))
    except Exception as e:
        fail(get(job), e)
    frappe.db.commit()
