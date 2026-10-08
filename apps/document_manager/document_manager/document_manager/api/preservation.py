# -*- coding: utf-8 -*-
"""API of the preservation screens (module 7): backups, integrity checks and restores, with their progress and findings.

Every endpoint needs Document Admin, Preservation Officer or System Manager. The jobs run in the background; this
module creates them, reports on them and offers the actions (stop, continue, delete) that are valid for their state.
"""

import os

import frappe
from frappe import _
from frappe.utils import cint

from document_manager.document_manager.services.audit import log_activity
from document_manager.document_manager.services.preservation import (
    backup,
    backups_dir,
    filestore,
    integrity,
    require_preservation,
    restore,
    runner,
    store_dir,
)

# kind -> (DocType, its item DocType, the item's link to the job)
KINDS = {
    "backup": ("Backup Batch", "Backup Batch Item", "batch"),
    "integrity": ("Integrity Check", "Integrity Check Item", "check"),
    "restore": ("Restore Batch", "Restore Batch Item", "restore"),
}
JOB_PATHS = {"backup": backup.JOB, "integrity": integrity.JOB}
MAX_PAGE = 100
ITEMS_SHOWN = 200
MAX_DOWNLOAD_MB = 500


def _kind(kind: str) -> tuple[str, str, str]:
    if kind not in KINDS:
        frappe.throw(_("Loại {0} không hợp lệ").format(kind))
    return KINDS[kind]


def _percent(kind: str, doc) -> int:
    if kind == "backup":
        total, done = cint(doc.files_total), cint(doc.files_done) + cint(doc.files_failed)
    elif kind == "restore":
        total, done = cint(doc.total), cint(doc.records_restored) + cint(doc.failed)
    else:
        total = frappe.cache.get_value("dm_preserve:documents") or 0
        if not total:
            total = frappe.db.count("Archive Document")
            frappe.cache.set_value("dm_preserve:documents", total, expires_in_sec=300)
        done = cint(doc.total_checked)
    if doc.status in ("Thành công", "Hoàn thành", "Phát hiện lỗi", "Một phần"):
        return 100
    return min(99, round(done * 100 / total)) if total else 0


def _stale(doc) -> bool:
    """A job that says it waits or runs but has for hours: its worker is gone, so it counts as stopped."""
    return runner.is_stale(doc.status, doc.creation, doc.get("started_at"))


def _resumable(kind: str, doc) -> bool:
    if kind == "restore" and doc.restore_type == "Cơ sở dữ liệu":
        return False  # a database restore is run again on purpose, with the site name typed
    return doc.status in ("Lỗi", "Đã hủy") or _stale(doc)


def _job(kind: str, doc, detail: bool = False) -> dict:
    doctype, item, link = KINDS[kind]
    busy = doc.status in runner.BUSY and not _stale(doc)
    out = {"kind": kind, "name": doc.name, "status": doc.status, "busy": busy, "percent": _percent(kind, doc),
           "started_at": doc.started_at, "completed_at": doc.completed_at, "creation": doc.creation, "owner": doc.owner,
           "initiated_by": doc.get("initiated_by") or "", "trigger": doc.get("trigger") or "",
           "can_resume": _resumable(kind, doc),
           "can_cancel": busy, "can_delete": not busy}
    if kind == "backup":
        out.update(backup_type=doc.backup_type, fonds=doc.fonds or "", database={"file": os.path.basename(doc.backup_path or ""), "size_mb": doc.backup_size_mb,
                                                                                   "checksum": doc.db_checksum or ""},
                   files={"total": cint(doc.files_total), "done": cint(doc.files_done), "failed": cint(doc.files_failed),
                          "size_mb": doc.files_size_mb}, notes=doc.notes or "", log=doc.error_log or "", expires_on=doc.expires_on,
                   has_database=bool(doc.backup_path and os.path.isfile(doc.backup_path)), has_files=cint(doc.files_done) > 0)
    elif kind == "integrity":
        out.update(check_type=doc.check_type, fonds=doc.fonds or "", phase=doc.phase or "", total_checked=cint(doc.total_checked),
                   errors=cint(doc.errors_found), warnings=cint(doc.warnings_found), summary=doc.summary or "", log=doc.error_details or "",
                   restorable=frappe.db.count("Integrity Check Item", {"check": doc.name, "restorable": 1, "status": "Chưa xử lý"}) if detail else None)
    else:
        out.update(restore_type=doc.restore_type, source_backup=doc.source_backup or "", source_check=doc.source_check or "",
                   total=cint(doc.total), restored=cint(doc.records_restored), failed=cint(doc.failed), log=doc.error_log or "")
    if detail:
        rows = frappe.get_all(item, filters={link: doc.name}, order_by="creation asc", page_length=ITEMS_SHOWN,
                              fields=[f for f in frappe.get_meta(item).get_valid_columns() if f not in ("owner", "modified_by", "docstatus", "idx", "creation", "modified")])
        out["items"] = rows
        out["items_total"] = frappe.db.count(item, {link: doc.name})
    return out


@frappe.whitelist()
def overview():
    """What the preservation screens and the monitor start from: last backups, running jobs, the store, the disk."""
    require_preservation()
    import shutil

    good = backup.last_good()
    last_check = frappe.db.get_value("Integrity Check", {"status": ["in", ["Hoàn thành", "Phát hiện lỗi"]]},
                                     ["name", "status", "completed_at", "errors_found", "warnings_found"], order_by="completed_at desc", as_dict=True)
    running = [{"kind": k, "name": n} for k, (dt, _i, _l) in KINDS.items()
               for n in frappe.get_all(dt, filters={"status": ["in", list(runner.BUSY)]}, pluck="name")
               if not _stale(frappe.get_doc(dt, n))]
    try:
        usage = shutil.disk_usage(backups_dir() if os.path.isdir(backups_dir()) else frappe.get_site_path())
        disk = {"free_gb": round(usage.free / 1024 ** 3, 1), "total_gb": round(usage.total / 1024 ** 3, 1)}
    except OSError:
        disk = None
    config = runner.settings()
    return {"last_backup": good, "last_check": last_check, "running": running, "store": filestore.usage(), "disk": disk,
            "settings": {"auto_backup_enabled": config.auto_backup_enabled, "backup_frequency": config.backup_frequency,
                         "backup_retention_days": config.backup_retention_days, "auto_integrity_check": config.auto_integrity_check},
            "db_restore_enabled": restore.db_restore_enabled(), "site": frappe.local.site}


@frappe.whitelist()
def list_jobs(kind, status=None, page=1, page_size=20):
    require_preservation()
    doctype, _item, _link = _kind(kind)
    page, size = max(1, cint(page) or 1), min(MAX_PAGE, max(1, cint(page_size) or 20))
    filters = {"status": status} if status else {}
    names = frappe.get_all(doctype, filters=filters, pluck="name", order_by="creation desc", start=(page - 1) * size, page_length=size)
    return {"data": [_job(kind, frappe.get_doc(doctype, n)) for n in names], "total": frappe.db.count(doctype, filters), "page": page, "page_size": size}


@frappe.whitelist()
def get_job(kind, name):
    require_preservation()
    doctype, _item, _link = _kind(kind)
    return _job(kind, frappe.get_doc(doctype, name), detail=True)


@frappe.whitelist(methods=["POST"])
def start_backup(backup_type="Cả hai", fonds=None, notes=""):
    require_preservation()
    if backup_type not in ("Cơ sở dữ liệu", "Tệp tài liệu", "Cả hai"):
        frappe.throw(_("Loại sao lưu không hợp lệ"))
    if runner.is_active("Backup Batch"):
        frappe.throw(_("Đang có một đợt sao lưu chạy, hãy đợi nó kết thúc"))
    batch = backup.create_batch(backup_type, fonds, notes=notes)
    backup.start(batch)
    log_activity("Sao lưu", "Backup Batch", batch.name, f"Bắt đầu sao lưu ({backup_type})")
    return _job("backup", frappe.get_doc("Backup Batch", batch.name))


@frappe.whitelist(methods=["POST"])
def start_check(check_type="Toàn bộ", fonds=None):
    require_preservation()
    if check_type not in integrity.PHASES:
        frappe.throw(_("Loại kiểm tra không hợp lệ"))
    if runner.is_active("Integrity Check"):
        frappe.throw(_("Đang có một đợt kiểm tra chạy, hãy đợi nó kết thúc"))
    check = integrity.create(check_type, fonds)
    integrity.start(check)
    log_activity("Kiểm tra", "Integrity Check", check.name, f"Bắt đầu kiểm tra ({check_type})")
    return _job("integrity", frappe.get_doc("Integrity Check", check.name))


@frappe.whitelist(methods=["POST"])
def start_restore(documents=None, source_backup=None, check=None):
    """Restore the files of documents (a list of names) or of every restorable finding of an integrity check."""
    require_preservation()
    if check:
        batch = restore.create_from_check(check, source_backup)
    else:
        batch = restore.create_files_restore(frappe.parse_json(documents) if isinstance(documents, str) else (documents or []), source_backup)
    restore.start(batch)
    log_activity("Phục hồi", "Restore Batch", batch.name, f"Bắt đầu phục hồi {batch.total} tài liệu")
    return _job("restore", frappe.get_doc("Restore Batch", batch.name))


@frappe.whitelist(methods=["POST"])
def prepare_db_restore(source_backup):
    """Check a database dump and make the restore batch for it (nothing runs yet): returns the verification and the runbook."""
    require_preservation()
    check = restore.verify_db_backup(source_backup)
    batch = restore.create_db_restore(source_backup) if check["ok"] else None
    return {"verification": check, "batch": _job("restore", frappe.get_doc("Restore Batch", batch.name)) if batch else None,
            "runbook": restore.runbook(check["path"]) if check["path"] else "", "can_run": restore.db_restore_enabled() and bool(restore.root_password()),
            "site": frappe.local.site}


@frappe.whitelist(methods=["POST"])
def run_restore(name, confirm_site=""):
    """Run a restore batch; a database restore needs `confirm_site` (the site's name) to run itself."""
    require_preservation()
    batch = frappe.get_doc("Restore Batch", name)
    if batch.status in runner.BUSY and not _stale(batch):
        frappe.throw(_("Đợt phục hồi này đang chạy"))
    restore.start(batch, confirm_site)
    log_activity("Phục hồi", "Restore Batch", batch.name, "Chạy đợt phục hồi")
    return _job("restore", frappe.get_doc("Restore Batch", name))


@frappe.whitelist(methods=["POST"])
def cancel(kind, name):
    require_preservation()
    doctype, _item, _link = _kind(kind)
    doc = frappe.get_doc(doctype, name)
    if doc.status not in runner.BUSY or _stale(doc):
        frappe.throw(_("Không có gì đang chạy để dừng"))
    runner.request_cancel(doctype, name)
    if doc.status == "Đang chờ":
        doc.db_set("status", "Đã hủy", update_modified=False)
    return _job(kind, frappe.get_doc(doctype, name))


@frappe.whitelist(methods=["POST"])
def resume(kind, name):
    """Continue a job from where it stopped (it keeps a cursor), or run it again from the start when it had not begun."""
    require_preservation()
    doctype, _item, _link = _kind(kind)
    doc = frappe.get_doc(doctype, name)
    if not _resumable(kind, doc):
        frappe.throw(_("Chỉ chạy tiếp được đợt đã dừng hoặc bị lỗi") if kind != "restore" or doc.restore_type != "Cơ sở dữ liệu"
                     else _("Đợt phục hồi cơ sở dữ liệu phải chạy lại bằng nút chạy, kèm xác nhận tên site"))
    if kind == "restore":
        restore.start(doc)
    else:
        runner.clear_cancel(doctype, name)
        doc.db_set({"status": "Đang chờ"}, update_modified=False)
        frappe.enqueue(JOB_PATHS[kind], name=name, queue="long", timeout=4 * 3600, enqueue_after_commit=True)
    return _job(kind, frappe.get_doc(doctype, name))


@frappe.whitelist(methods=["POST"])
def delete_job(kind, name):
    require_preservation()
    doctype, item, link = _kind(kind)
    if kind == "backup":
        result = backup.delete_batch(name)
    else:
        doc = frappe.get_doc(doctype, name)
        if doc.status in runner.BUSY and not _stale(doc):
            frappe.throw(_("Không xóa được đợt đang chạy, hãy dừng trước"))
        for row in frappe.get_all(item, filters={link: name}, pluck="name"):
            frappe.delete_doc(item, row, force=True, ignore_permissions=True)
        frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        result = {"name": name}
    runner.clear_cancel(doctype, name)
    log_activity("Xóa", doctype, name, f"Xóa {doctype} {name}")
    return result


@frappe.whitelist()
def verify_backup(name):
    require_preservation()
    return restore.verify_db_backup(name)


@frappe.whitelist()
def download_backup(name, which="database"):
    """The database dump of a backup batch (a .sql.gz) or its manifest; the download is logged."""
    require_preservation()
    batch = frappe.get_doc("Backup Batch", name)
    if which == "manifest":
        path = filestore.manifest_path(name)
        mime, filename = "application/x-ndjson", f"{name}-manifest.jsonl"
    else:
        path = batch.backup_path or ""
        mime, filename = "application/gzip", f"{name}-database.sql.gz"
    roots = [os.path.abspath(backups_dir()) + os.sep, os.path.abspath(store_dir()) + os.sep]
    if not path or not os.path.isfile(path) or not os.path.abspath(path).startswith(tuple(roots)):
        frappe.throw(_("Không còn tệp để tải"), frappe.DoesNotExistError)
    if os.path.getsize(path) > MAX_DOWNLOAD_MB * 1024 * 1024:
        frappe.throw(_("Tệp lớn hơn {0} MB: hãy sao chép trực tiếp từ máy chủ ({1})").format(MAX_DOWNLOAD_MB, path))
    with open(path, "rb") as handle:
        content = handle.read()
    log_activity("Tải xuống", "Backup Batch", name, f"Tải {filename}")
    frappe.local.response.update({"type": "download", "filename": filename, "filecontent": content, "content_type": mime})


@frappe.whitelist(methods=["POST"])
def fix_counters():
    """Recompute the counters of files per fonds and documents per file (what the COUNTER_* findings are about)."""
    require_preservation()
    result = integrity.fix_counters()
    log_activity("Kiểm tra", "Integrity Check", "", f"Sửa bộ đếm: {result['fonds']} phông, {result['files']} hồ sơ")
    return result


@frappe.whitelist(methods=["POST"])
def set_finding_status(name, status):
    """Mark a finding handled ("Đã bỏ qua") or open again ("Chưa xử lý")."""
    require_preservation()
    if status not in ("Chưa xử lý", "Đã bỏ qua"):
        frappe.throw(_("Trạng thái không hợp lệ"))
    frappe.db.set_value("Integrity Check Item", name, "status", status)
    return {"name": name, "status": status}


@frappe.whitelist()
def list_findings(check, status=None, severity=None, code=None, page=1, page_size=50):
    require_preservation()
    page, size = max(1, cint(page) or 1), min(MAX_PAGE, max(1, cint(page_size) or 50))
    filters = {"check": check, **{k: v for k, v in (("status", status), ("severity", severity), ("code", code)) if v}}
    rows = frappe.get_all("Integrity Check Item", filters=filters, order_by="creation asc", start=(page - 1) * size, page_length=size,
                          fields=["name", "document", "code", "severity", "message", "restorable", "status"])
    return {"data": rows, "total": frappe.db.count("Integrity Check Item", filters), "page": page, "page_size": size}


@frappe.whitelist(methods=["POST"])
def run_retention():
    """Delete the backups older than the retention period now (the daily job does the same)."""
    require_preservation()
    removed = backup.apply_retention()
    log_activity("Xóa", "Backup Batch", "", f"Dọn bản sao lưu cũ: {len(removed)} đợt")
    return {"removed": removed}
