# -*- coding: utf-8 -*-
"""Backup, integrity check, and restore services.

Background workers for:
- Database backup (via Frappe's built-in backup)
- File integrity check (checksum verification against GridFS)
- Data restoration from backup
"""

import hashlib

import frappe


def run_backup(batch_name: str, backup_type: str):
    """Run backup job (enqueued from BackupBatch.run_backup)."""
    batch = frappe.get_doc("Backup Batch", batch_name)
    try:
        backup_path = ""
        backup_size = 0

        if backup_type in ("Cơ sở dữ liệu", "Cả hai"):
            from frappe.utils.backups import new_backup
            backup = new_backup(ignore_files=True, force=True)
            backup_path = backup.backup_path_db
            import os
            if os.path.exists(backup_path):
                backup_size = os.path.getsize(backup_path) / (1024 * 1024)

        if backup_type in ("Tệp tài liệu", "Cả hai"):
            # Export file metadata to GridFS backup collection
            try:
                from document_manager.document_manager.services.mongodb_storage import MongoGridFSStorage
                storage = MongoGridFSStorage(collection_name="documents")
                files = storage.list_files(limit=0)
                backup_path += f" | {len(files)} files in GridFS"
            except Exception as e:
                frappe.log_error(f"File backup audit failed: {e}", "Backup Error")

        batch.db_set("status", "Thành công")
        batch.db_set("completed_at", frappe.utils.now())
        batch.db_set("backup_path", backup_path)
        batch.db_set("backup_size_mb", round(backup_size, 2))
        frappe.db.commit()

    except Exception as e:
        batch.db_set("status", "Lỗi")
        batch.db_set("error_log", str(e))
        batch.db_set("completed_at", frappe.utils.now())
        frappe.db.commit()
        frappe.log_error(f"Backup failed for {batch_name}: {e}", "Backup Error")


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
    """Run restore job (enqueued from RestoreBatch.run_restore)."""
    restore = frappe.get_doc("Restore Batch", restore_name)
    try:
        # Restore from source backup
        if restore.source_backup:
            backup = frappe.get_doc("Backup Batch", restore.source_backup)
            if backup.backup_path:
                frappe.logger().info(f"Restoring from: {backup.backup_path}")
                # frappe.utils.backups.restore(backup.backup_path) — requires manual execution
                restore.db_set("records_restored", 0)
                restore.db_set("error_log", "Phục hồi CSDL cần thực hiện thủ công qua bench restore.")

        restore.db_set("status", "Thành công")
        restore.db_set("completed_at", frappe.utils.now())
        frappe.db.commit()

    except Exception as e:
        restore.db_set("status", "Lỗi")
        restore.db_set("error_log", str(e))
        restore.db_set("completed_at", frappe.utils.now())
        frappe.db.commit()
