# -*- coding: utf-8 -*-
"""System administration API (Document Admin / System Manager only): service health and the monitor of the whole system."""

import os
import shutil

import frappe
from frappe.utils import add_days, cint, now_datetime

from document_manager.document_manager.permissions import assert_roles
from document_manager.document_manager.services.errors import log_exception

ADMIN_ROLES = ("Document Admin", "System Manager")


@frappe.whitelist()
def get_service_health():
    """Status of MongoDB Atlas (file storage) and Meilisearch (search)."""
    assert_roles(*ADMIN_ROLES)
    from document_manager.document_manager.services.health import check_services

    return check_services(fresh=True)


def _queues() -> list[dict]:
    """Jobs waiting in each queue (empty when the queues cannot be read)."""
    try:
        from frappe.utils.background_jobs import get_queues

        return [{"name": q.name.split(":")[-1], "jobs": q.count} for q in get_queues()]
    except Exception:
        log_exception("Monitor", "Could not read the job queues")
        return []


def _workers() -> int | None:
    try:
        from frappe.utils.background_jobs import get_workers

        return len(get_workers())
    except Exception:
        return None


FILES_SIZE_KEY = "dm_private_files_bytes"


def measure_private_files() -> int:
    """Total size of the uploaded files. Walking a folder of a million files takes a while: this runs as a background job."""
    total = 0
    private = frappe.get_site_path("private", "files")
    if os.path.isdir(private):
        for entry in os.scandir(private):
            try:
                total += entry.stat().st_size if entry.is_file() else 0
            except OSError:
                pass
    frappe.cache.set_value(FILES_SIZE_KEY, total, expires_in_sec=6 * 3600)
    return total


def private_files_bytes() -> int | None:
    """The last measured size of the uploaded files; None while the first measurement is still running."""
    size = frappe.cache.get_value(FILES_SIZE_KEY)
    if size is None:
        frappe.enqueue("document_manager.document_manager.api.admin.measure_private_files", queue="short", timeout=600,
                       job_id="dm_measure_private_files", deduplicate=True, enqueue_after_commit=False)
    return size


@frappe.whitelist()
def monitor():
    """Everything the monitoring screen shows in one call: services, search index, jobs, storage, users, log, backups."""
    assert_roles(*ADMIN_ROLES)
    from document_manager.document_manager.services.health import check_services
    from document_manager.document_manager.services.preservation import backup, filestore

    day_ago = add_days(now_datetime(), -1)
    week_ago = add_days(now_datetime(), -7)
    documents = frappe.db.count("Archive Document")
    indexed = frappe.db.count("Archive Document", {"search_index_status": "Đã index"})
    index_errors = frappe.db.count("Archive Document", {"search_index_status": "Lỗi"})
    try:
        usage = shutil.disk_usage(frappe.get_site_path())
        disk = {"free_gb": round(usage.free / 1024 ** 3, 1), "total_gb": round(usage.total / 1024 ** 3, 1),
                "used_percent": round((usage.total - usage.free) * 100 / usage.total)}
    except OSError:
        disk = None
    files_size = private_files_bytes()
    last_check = frappe.db.get_value("Integrity Check", {"status": ["in", ["Hoàn thành", "Phát hiện lỗi"]]},
                                     ["name", "status", "completed_at", "errors_found", "warnings_found"], order_by="completed_at desc",
                                     as_dict=True)
    return {
        "services": check_services(),
        "documents": {"total": documents, "indexed": indexed, "errors": index_errors,
                      "percent": round(indexed * 100 / documents) if documents else 100},
        "jobs": {"queues": _queues(), "workers": _workers(),
                 "errors_24h": frappe.db.count("Error Log", {"creation": [">", day_ago]}),
                 "failed_7d": frappe.db.count("Scheduled Job Log", {"status": "Failed", "creation": [">", week_ago]})},
        "storage": {"disk": disk, "private_files_mb": None if files_size is None else round(files_size / (1024 * 1024), 1), "backup_store": filestore.usage()},
        "users": {"staff": frappe.db.count("User", {"user_type": "System User", "enabled": 1, "name": ["not in", ["Administrator", "Guest"]]}),
                  "readers": frappe.db.count("Reader", {"is_active": 1})},
        "log": {"rows": frappe.db.count("Business Activity Log"),
                "last_24h": frappe.db.count("Business Activity Log", {"timestamp": [">", day_ago]})},
        "backups": {"last": backup.last_good(), "last_check": last_check,
                    "running": cint(frappe.db.count("Backup Batch", {"status": "Đang chạy"}))},
        "site": frappe.local.site, "checked_at": str(now_datetime()),
    }
