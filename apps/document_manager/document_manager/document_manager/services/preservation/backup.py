# -*- coding: utf-8 -*-
"""Backup batches: the database dump, the document files, retention and the schedule.

* the database is dumped with Frappe's own backup (a `.sql.gz` in the site's backup folder), then checksummed;
* the files are copied into the content-addressed store (`filestore`) and listed in the batch's manifest, page by
  page and resumable (`cursor`); a source file whose hash disagrees with the one recorded when it was uploaded
  is reported and NOT copied, so a damaged file never replaces a good backup;
* retention deletes old batches (never below the newest `backup_keep_min` successful ones) and their blobs.
"""

import os

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, getdate, nowdate

from document_manager.document_manager.services.errors import log_exception
from document_manager.document_manager.services.preservation import backups_dir, filestore, runner, sources

JOB = "document_manager.document_manager.services.preservation.backup.run"
BATCH = "Backup Batch"
FREQUENCY_DAYS = {"Hàng ngày": 1, "Hàng tuần": 7}
OK_STATES = ("Thành công", "Một phần")


# --- creating and queueing -----------------------------------------------------------------------------------------

def create_batch(backup_type: str, fonds: str | None = None, trigger: str = "Thủ công", notes: str = "",
                 user: str | None = None):
    """A batch waiting to run. `user` defaults to the session user; "" means nobody (a scheduled batch)."""
    initiated = frappe.session.user if user is None else (user or None)
    batch = frappe.get_doc({"doctype": BATCH, "backup_type": backup_type, "fonds": fonds or None, "trigger": trigger,
                            "notes": notes, "initiated_by": initiated})
    batch.insert(ignore_permissions=True)
    return batch


def start(batch) -> None:
    batch.db_set({"status": "Đang chờ", "completed_at": None}, update_modified=False)
    runner.enqueue(JOB, batch.name, timeout=4 * 3600)


# --- the job --------------------------------------------------------------------------------------------------------

def run(name: str) -> None:
    """Worker: back up what the batch asks for. Safe to run again on a batch that stopped half way."""
    batch = frappe.get_doc(BATCH, name)
    if batch.status not in ("Đang chờ", "Đang chạy", "Lỗi", "Đã hủy"):
        return
    runner.mark_running(batch)
    frappe.db.commit()
    wants_db = batch.backup_type in ("Cơ sở dữ liệu", "Cả hai") and not batch.backup_path
    wants_files = batch.backup_type in ("Tệp tài liệu", "Cả hai")
    notes, db_ok, files_ok = [], not wants_db, not wants_files
    try:
        if wants_db:
            db_ok = run_db_backup(batch, notes)
        if wants_files:
            files_ok = run_files_backup(batch, notes)
        batch.reload()
        if batch.backup_type == "Cả hai" and not (db_ok and files_ok):
            status = "Một phần" if (db_ok or batch.files_done) else "Lỗi"
        elif not db_ok or not files_ok:
            status = "Lỗi"
        elif cint(batch.files_failed):
            status = "Một phần"
        else:
            status = "Thành công"
        retention = runner.settings().backup_retention_days
        runner.finish(batch, status, error_log="\n".join(notes)[:60000], expires_on=add_days(nowdate(), retention))
    except runner.Cancelled:
        frappe.db.rollback()
        runner.finish(batch, "Đã hủy", error_log="Đã dừng theo yêu cầu. Có thể chạy tiếp từ chỗ đã dừng.")
    except Exception as e:
        frappe.db.rollback()
        log_exception("Backup Error", f"Backup {name} failed")
        runner.finish(batch, "Lỗi", error_log=runner.explain(e))
    frappe.db.commit()
    batch.reload()
    runner.notify(batch, _("Sao lưu {0}: {1}").format(batch.name, batch.status))


def run_db_backup(batch, notes: list) -> bool:
    """Dump the database; records the file, its size and SHA-256. Returns whether it worked."""
    try:
        from frappe.utils.backups import new_backup

        generated = new_backup(ignore_files=True, force=True)
        path = generated.backup_path_db
        if not path or not os.path.isfile(path):
            notes.append("Không tạo được tệp sao lưu cơ sở dữ liệu.")
            return False
        with open(path, "rb") as handle:
            digest = sources.sha256(handle.read())
        batch.db_set({"backup_path": path, "backup_size_mb": round(os.path.getsize(path) / (1024 * 1024), 2),
                      "db_checksum": digest}, update_modified=False)
        frappe.db.commit()
        return True
    except Exception as e:
        log_exception("Backup Error", f"Database backup of {batch.name} failed")
        notes.append(f"Sao lưu cơ sở dữ liệu lỗi: {runner.explain(e)}")
        return False


def _file_filters(batch) -> tuple[list, list]:
    filters = [["fonds", "=", batch.fonds]] if batch.fonds else []
    or_filters = [["file_attachment", "!=", ""], ["gridfs_file_id", "!=", ""]]
    return filters, or_filters


def run_files_backup(batch, notes: list) -> bool:
    """Copy every document's file into the store and list it in the manifest; resumes from the batch's cursor."""
    filters, or_filters = _file_filters(batch)
    total = _count(filters, or_filters)
    batch.db_set("files_total", total, update_modified=False)
    findings = runner.Findings("Backup Batch Item", "batch", batch.name)
    cursor = batch.cursor or ""
    done, failed, size = cint(batch.files_done), cint(batch.files_failed), float(batch.files_size_mb or 0)
    manifest = filestore.manifest_path(batch.name)
    batch.db_set("manifest_path", os.path.relpath(manifest, frappe.get_site_path()), update_modified=False)
    while True:
        rows = frappe.get_all("Archive Document", filters=[*filters, ["name", ">", cursor]] if cursor else filters,
                              or_filters=or_filters, order_by="name asc", page_length=runner.PAGE,
                              fields=["name", "document_title", "file_attachment", "gridfs_file_id", "checksum", "fonds"])
        if not rows:
            break
        entries = []
        for row in rows:
            content, source = sources.read_document(row)
            if content is None:
                failed += 1
                findings.add("Lỗi", _("Không đọc được tệp của văn bản (đường dẫn {0})").format(row.file_attachment or "—"), row.name)
                continue
            digest = sources.sha256(content)
            if row.checksum and row.checksum != digest:
                failed += 1
                findings.add("Lỗi", _("Tệp nguồn không khớp mã kiểm đã ghi khi tải lên (có thể đã hỏng): không sao lưu"), row.name)
                continue
            filestore.put(content)
            entries.append({"document": row.name, "file_url": row.file_attachment or "", "filename": sources.filename_of(row),
                            "sha256": digest, "size": len(content), "source": source, "fonds": row.fonds or ""})
            done += 1
            size += len(content) / (1024 * 1024)
        filestore.append_manifest(batch.name, entries)
        cursor = rows[-1].name
        batch.db_set({"cursor": cursor, "files_done": done, "files_failed": failed, "files_size_mb": round(size, 2)},
                     update_modified=False)
        frappe.db.commit()
        runner.check_cancel(BATCH, batch.name)
    if findings.truncated:
        notes.append(f"Chỉ ghi {runner.MAX_ITEMS} dòng lỗi đầu tiên (tổng {failed}).")
    if failed:
        notes.append(f"{failed} tệp không sao lưu được (xem các dòng lỗi của đợt).")
    return done > 0 or (total == 0)


def _count(filters, or_filters) -> int:
    rows = frappe.get_all("Archive Document", filters=filters, or_filters=or_filters, fields=[{"COUNT": "name", "as": "c"}])
    return cint(rows[0].c) if rows else 0


# --- deleting, retention, the schedule ------------------------------------------------------------------------------

def delete_batch(name: str) -> dict:
    """Delete a batch with its dump, manifest and items; blobs nothing else refers to go too."""
    batch = frappe.get_doc(BATCH, name)
    if batch.status in runner.BUSY and not runner.is_stale(batch.status, batch.creation, batch.started_at):
        frappe.throw(_("Không xóa được đợt sao lưu đang chạy, hãy dừng trước"))
    if frappe.db.exists("Restore Batch", {"source_backup": name, "status": ["in", list(runner.BUSY)]}) and runner.is_active("Restore Batch"):
        frappe.throw(_("Có đợt phục hồi đang dùng bản sao lưu này"))
    path = batch.backup_path
    for item in frappe.get_all("Backup Batch Item", filters={"batch": name}, pluck="name"):
        frappe.delete_doc("Backup Batch Item", item, force=True, ignore_permissions=True)
    frappe.delete_doc(BATCH, name, force=True, ignore_permissions=True)
    filestore.remove_manifest(name)
    removed_files = False
    if path and os.path.isfile(path) and os.path.abspath(path).startswith(os.path.abspath(backups_dir())):
        sibling = path.replace("-database.sql.gz", "-site_config_backup.json")
        for target in (path, sibling):
            try:
                os.unlink(target)
                removed_files = removed_files or target == path
            except OSError:
                pass
    kept = frappe.get_all(BATCH, pluck="name")
    blobs, freed = filestore.collect_garbage(kept)
    return {"name": name, "database_file_removed": removed_files, "blobs_removed": blobs, "freed_bytes": freed}


def apply_retention() -> list[str]:
    """Delete the batches older than the retention period, keeping at least the newest successful ones."""
    config = runner.settings()
    cutoff = add_days(nowdate(), -config.backup_retention_days)
    good = frappe.get_all(BATCH, filters={"status": ["in", list(OK_STATES)]}, pluck="name", order_by="creation desc")
    protected = set(good[: config.backup_keep_min])
    removed = []
    for batch in frappe.get_all(BATCH, fields=["name", "creation", "status", "started_at"]):
        if batch.status in runner.BUSY and not runner.is_stale(batch.status, batch.creation, batch.started_at):
            continue
        if batch.name in protected or getdate(batch.creation) > getdate(cutoff):
            continue
        try:
            delete_batch(batch.name)
            removed.append(batch.name)
        except Exception:
            log_exception("Backup Retention", f"Could not delete {batch.name}")
    return removed


def is_due(last_completed, frequency: str, today=None) -> bool:
    """Is a scheduled backup due, given when the last good one finished?"""
    if not last_completed:
        return True
    today, last = getdate(today or nowdate()), getdate(last_completed)
    if frequency == "Hàng tháng":
        return today >= getdate(add_months(last, 1))
    return (today - last).days >= FREQUENCY_DAYS.get(frequency, 7)


def run_scheduled() -> str | None:
    """Daily job: a scheduled backup when one is due, then retention. Returns the name of the batch started."""
    config = runner.settings()
    started = None
    if config.auto_backup_enabled and not runner.is_active(BATCH):
        last = frappe.db.get_value(BATCH, {"status": ["in", list(OK_STATES)], "trigger": "Theo lịch"}, "completed_at",
                                   order_by="completed_at desc")
        if is_due(last, config.backup_frequency):
            kind = "Cả hai" if config.backup_include_files else "Cơ sở dữ liệu"
            batch = create_batch(kind, trigger="Theo lịch", notes="Sao lưu theo lịch", user="")
            start(batch)
            started = batch.name
    apply_retention()
    return started


def last_good() -> dict | None:
    """The newest finished batch (any trigger) for the overview: {name, status, completed_at, age_days}."""
    row = frappe.db.get_value(BATCH, {"status": ["in", list(OK_STATES)]}, ["name", "status", "completed_at", "backup_type"],
                              order_by="completed_at desc", as_dict=True)
    if not row:
        return None
    row["age_days"] = max(0, (getdate(nowdate()) - getdate(row.completed_at)).days) if row.completed_at else None
    return row
