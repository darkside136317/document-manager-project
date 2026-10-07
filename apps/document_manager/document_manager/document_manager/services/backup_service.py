# -*- coding: utf-8 -*-
"""Backup, integrity check, and restore services.

Background workers for:
- Database backup (via Frappe's built-in backup)
- File integrity check (checksum verification against GridFS)
- Data restoration from backup
"""

import hashlib

import frappe

from document_manager.document_manager.services.errors import log_exception


def schedule_integrity_check():
    """Create and queue the configured weekly integrity check."""
    settings = frappe.get_single("Document Manager Settings")
    if not settings.auto_integrity_check:
        return

    check = frappe.get_doc(
        {
            "doctype": "Integrity Check",
            "check_type": "Toàn bộ",
        }
    ).insert(ignore_permissions=True)
    check.run_check()


FILE_BACKUP_NOTE = (
    "Sao lưu tệp tài liệu (GridFS) chưa được hỗ trợ: hệ thống chưa tạo bản sao nào của các tệp. "
    "Hãy sao lưu cụm MongoDB Atlas bằng công cụ của Atlas."
)


def run_backup(batch_name: str, backup_type: str):
    """Run backup job (enqueued from BackupBatch.run_backup).

    Only the database dump is real. A request that includes the document files is reported as
    "Một phần" (database done) or "Chưa hỗ trợ" (files only) — never as a success.
    """
    batch = frappe.get_doc("Backup Batch", batch_name)
    try:
        backup_path = ""
        backup_size = 0
        wants_db = backup_type in ("Cơ sở dữ liệu", "Cả hai")
        wants_files = backup_type in ("Tệp tài liệu", "Cả hai")

        if wants_db:
            import os

            from frappe.utils.backups import new_backup
            backup = new_backup(ignore_files=True, force=True)
            backup_path = backup.backup_path_db
            if os.path.exists(backup_path):
                backup_size = os.path.getsize(backup_path) / (1024 * 1024)

        if wants_files:
            status = "Một phần" if wants_db else "Chưa hỗ trợ"
            batch.db_set("error_log", FILE_BACKUP_NOTE)
        else:
            status = "Thành công"

        batch.db_set("status", status)
        batch.db_set("completed_at", frappe.utils.now())
        batch.db_set("backup_path", backup_path)
        batch.db_set("backup_size_mb", round(backup_size, 2))
        frappe.db.commit()

    except Exception as e:
        batch.db_set("status", "Lỗi")
        batch.db_set("error_log", str(e))
        batch.db_set("completed_at", frappe.utils.now())
        frappe.db.commit()
        log_exception("Backup Error", f"Backup failed for {batch_name}")


def run_integrity_check(check_name: str, check_type: str):
    """Run integrity check (enqueued from IntegrityCheck.run_check)."""
    check = frappe.get_doc("Integrity Check", check_name)
    errors = []
    total_checked = 0

    try:
        docs = frappe.get_all(
            "Archive Document",
            filters={"gridfs_file_id": ["is", "set"]},
            fields=["name", "gridfs_file_id", "checksum", "file_attachment"],
        )

        for doc in docs:
            total_checked += 1
            try:
                if check_type in ("Checksum", "Toàn bộ"):
                    # Verify checksum matches stored file
                    from document_manager.document_manager.services.mongodb_storage import MongoGridFSStorage
                    storage = MongoGridFSStorage(collection_name="documents")
                    if not storage.file_exists(doc["gridfs_file_id"]):
                        errors.append(f"{doc['name']}: File not found in GridFS (ID: {doc['gridfs_file_id']})")
                        continue
                    content = storage.download_file(doc["gridfs_file_id"])
                    computed_checksum = hashlib.sha256(content).hexdigest()
                    if doc["checksum"] and computed_checksum != doc["checksum"]:
                        errors.append(f"{doc['name']}: Checksum mismatch (expected: {doc['checksum'][:16]}..., got: {computed_checksum[:16]}...)")

                elif check_type == "File bị thiếu":
                    from document_manager.document_manager.services.mongodb_storage import MongoGridFSStorage
                    storage = MongoGridFSStorage(collection_name="documents")
                    if not storage.file_exists(doc["gridfs_file_id"]):
                        errors.append(f"{doc['name']}: File missing in GridFS")

                elif check_type == "Liên kết file-metadata":
                    if doc["file_attachment"] and not doc["gridfs_file_id"]:
                        errors.append(f"{doc['name']}: Has attachment but no GridFS ID")

            except Exception as e:
                errors.append(f"{doc['name']}: Error - {str(e)[:200]}")

        status = "Phát hiện lỗi" if errors else "Hoàn thành"
        check.db_set("status", status)
        check.db_set("total_checked", total_checked)
        check.db_set("errors_found", len(errors))
        check.db_set("error_details", "\n".join(errors) if errors else "Không phát hiện lỗi")
        check.db_set("completed_at", frappe.utils.now())
        frappe.db.commit()

    except Exception as e:
        check.db_set("status", "Phát hiện lỗi")
        check.db_set("error_details", str(e))
        check.db_set("completed_at", frappe.utils.now())
        frappe.db.commit()


def run_restore(restore_name: str):
    """Run restore job (enqueued from RestoreBatch.run_restore).

    Restoring a site from inside the running site is not safe, so nothing is overwritten here.
    The batch ends as "Cần thao tác thủ công" with the exact command, instead of claiming success.
    """
    restore = frappe.get_doc("Restore Batch", restore_name)
    try:
        if not restore.source_backup:
            status, note = "Lỗi", "Chưa chọn đợt sao lưu nguồn."
        else:
            backup = frappe.get_doc("Backup Batch", restore.source_backup)
            if not backup.backup_path:
                status, note = "Lỗi", f"Đợt sao lưu {backup.name} không có tệp sao lưu CSDL."
            else:
                site = frappe.local.site
                status = "Cần thao tác thủ công"
                note = (
                    "Hệ thống chưa tự động khôi phục dữ liệu. Thực hiện thủ công trên máy chủ:\n"
                    f"  bench --site {site} --force restore \"{backup.backup_path}\" "
                    "--db-root-password <mật khẩu root MariaDB>\n"
                    "Nên bật chế độ bảo trì trước khi chạy và kiểm tra lại sau khi hoàn tất."
                )
        restore.db_set("records_restored", 0)
        restore.db_set("status", status)
        restore.db_set("error_log", note)
        restore.db_set("completed_at", frappe.utils.now())
        frappe.db.commit()

    except Exception as e:
        restore.db_set("status", "Lỗi")
        restore.db_set("error_log", str(e))
        restore.db_set("completed_at", frappe.utils.now())
        frappe.db.commit()
        log_exception("Restore Error", f"Restore failed for {restore_name}")
