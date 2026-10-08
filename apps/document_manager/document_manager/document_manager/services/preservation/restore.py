# -*- coding: utf-8 -*-
"""Restore batches: bring documents' files back from a backup, and the controlled restore of the database.

Files: a batch lists the documents to restore (picked by hand or taken from the restorable findings of an integrity
check); each is looked up in the manifests (the chosen backup, else the newest backup holding it), the blob is
verified against its hash, the private file is rewritten where it is missing or differs, and the GridFS copy is
re-uploaded where MongoDB lacks it. Items make a run resumable and show what happened to each document.

Database: restoring the site's database from inside the running site is dangerous, so the default is a *verified
runbook* (`Cần thao tác thủ công`): the dump is checked (present, a valid gzip, same SHA-256 as when it was made) and the
exact command is given. A site that sets `dm_allow_db_restore` in its site config (and has the root password) may let
the job run the restore itself, but only when the administrator types the site's name to confirm.
"""

import gzip
import os
import subprocess

import frappe
from frappe import _
from frappe.utils import cint

from document_manager.document_manager.services.errors import log_exception
from document_manager.document_manager.services.preservation import filestore, runner, sources

JOB = "document_manager.document_manager.services.preservation.restore.run"
DOCTYPE = "Restore Batch"
ITEM = "Restore Batch Item"
MAX_DOCUMENTS = 20000


# --- creating -------------------------------------------------------------------------------------------------------

def create_files_restore(documents, source_backup=None, source_check=None, user=None, check_items: dict | None = None):
    """A restore batch for the files of `documents` (names); returns the batch (items are in place)."""
    documents = list(dict.fromkeys(d for d in documents if d))
    if not documents:
        frappe.throw(_("Chưa chọn tài liệu nào để phục hồi"))
    if len(documents) > MAX_DOCUMENTS:
        frappe.throw(_("Một đợt phục hồi tối đa {0} tài liệu").format(MAX_DOCUMENTS))
    missing = [d for d in documents if not frappe.db.exists("Archive Document", d)]
    if missing:
        frappe.throw(_("Không tìm thấy văn bản: {0}").format(", ".join(missing[:5])))
    if source_backup:
        backup = frappe.get_doc("Backup Batch", source_backup)
        if backup.status not in ("Thành công", "Một phần") or backup.backup_type == "Cơ sở dữ liệu":
            frappe.throw(_("Đợt sao lưu {0} không có tệp tài liệu để phục hồi").format(source_backup))
    batch = frappe.get_doc({"doctype": DOCTYPE, "restore_type": "Tệp tài liệu", "source_backup": source_backup or None,
                            "source_check": source_check or None, "total": len(documents),
                            "initiated_by": frappe.session.user if user is None else (user or None)})
    batch.insert(ignore_permissions=True)
    for name in documents:
        frappe.get_doc({"doctype": ITEM, "restore": batch.name, "document": name, "source_backup": source_backup or None,
                        "check_item": (check_items or {}).get(name)}).insert(ignore_permissions=True)
    return batch


def create_from_check(check: str, source_backup: str | None = None):
    """The "go to restore" step of an integrity check: a batch for every document whose problem a backup can fix."""
    rows = frappe.get_all("Integrity Check Item", filters={"check": check, "restorable": 1, "status": "Chưa xử lý",
                                                             "document": ["is", "set"]},
                          fields=["name", "document"], page_length=MAX_DOCUMENTS + 1)
    if not rows:
        frappe.throw(_("Đợt kiểm tra này không có lỗi nào có thể phục hồi từ bản sao lưu"))
    items = {}
    for row in rows:
        items.setdefault(row.document, row.name)
    return create_files_restore(list(items), source_backup, check, check_items=items)


def create_db_restore(source_backup: str):
    backup = frappe.get_doc("Backup Batch", source_backup)
    if backup.status not in ("Thành công", "Một phần") or not backup.backup_path:
        frappe.throw(_("Đợt sao lưu {0} không có tệp sao lưu cơ sở dữ liệu").format(source_backup))
    batch = frappe.get_doc({"doctype": DOCTYPE, "restore_type": "Cơ sở dữ liệu", "source_backup": source_backup,
                            "status": "Chưa chạy", "initiated_by": frappe.session.user})  # prepared, not queued: it runs when asked
    batch.insert(ignore_permissions=True)
    return batch


def start(doc, confirm_site: str = "") -> None:
    doc.db_set({"status": "Đang chờ", "completed_at": None}, update_modified=False)
    frappe.enqueue(JOB, name=doc.name, confirm_site=confirm_site, queue="long", timeout=4 * 3600, enqueue_after_commit=True)


# --- files ----------------------------------------------------------------------------------------------------------

def manifest_entries(documents: set, source_backup: str | None) -> dict:
    """{document: entry} from the chosen backup's manifest, else from the newest backup that holds the document."""
    if source_backup:
        batches = [source_backup]
    else:
        batches = frappe.get_all("Backup Batch", filters={"status": ["in", ["Thành công", "Một phần"]],
                                                           "backup_type": ["in", ["Tệp tài liệu", "Cả hai"]]},
                                 pluck="name", order_by="completed_at desc")
    found = {}
    for batch in batches:
        for entry in filestore.read_manifest(batch):
            name = entry.get("document")
            if name in documents and name not in found:
                found[name] = {**entry, "backup": batch}
        if len(found) == len(documents):
            break
    return found


def restore_document(row, entry: dict, blob: bytes) -> list[str]:
    """Put `blob` back where the document's file should be. Returns what was done: ["đĩa", "GridFS", ...]."""
    done = []
    digest = entry["sha256"]
    name = row.name
    current = sources.read_disk(row.file_attachment) if row.file_attachment else None
    if current is None or sources.sha256(current) != digest:
        path = sources.disk_path(row.file_attachment) if row.file_attachment else None
        if not path:
            from frappe.utils.file_manager import save_file

            saved = save_file(entry.get("filename") or name, blob, "Archive Document", name, is_private=1)
            frappe.db.set_value("Archive Document", name, "file_attachment", saved.file_url, update_modified=False)
            row.file_attachment = saved.file_url
            path = saved.get_full_path()
            frappe.db.set_value("File", saved.name, {"file_size": len(blob), "content_hash": digest}, update_modified=False)
        # the exact bytes of the backup go to the disk (Frappe may rewrite a PDF it stores itself)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary = f"{path}.restore.tmp"
        with open(temporary, "wb") as handle:
            handle.write(blob)
        os.replace(temporary, path)
        check = sources.read_disk(row.file_attachment)
        if check is None or sources.sha256(check) != digest:
            frappe.throw(_("Đã ghi tệp nhưng đọc lại không khớp mã kiểm"))
        done.append("tệp trên máy chủ")
    updates = {}
    if not row.checksum or row.checksum != digest:
        updates.update(checksum=digest, file_size_kb=round(len(blob) / 1024, 2))
    if updates:
        frappe.db.set_value("Archive Document", name, updates, update_modified=False)
    if row.gridfs_file_id and sources.gridfs_exists(row.gridfs_file_id) is False:
        from document_manager.document_manager.services.mongodb_storage import upload_document_file

        upload_document_file(name, blob, entry.get("filename") or name)
        done.append("bản trên GridFS")
    return done


def run_files_restore(doc) -> None:
    documents = set(frappe.get_all(ITEM, filters={"restore": doc.name}, pluck="document"))
    entries = manifest_entries(documents, doc.source_backup)
    restored, failed = cint(doc.records_restored), cint(doc.failed)
    while True:
        items = frappe.get_all(ITEM, filters={"restore": doc.name, "status": "Chờ"}, fields=["name", "document", "check_item"],
                               order_by="creation asc", page_length=runner.PAGE)
        if not items:
            break
        for item in items:
            result = _restore_one(item, entries)
            frappe.db.set_value(ITEM, item.name, result, update_modified=False)
            if result["status"] == "Đã khôi phục":
                restored += 1
                if doc.source_check:  # whatever the check found wrong with this document's file is settled with it
                    frappe.db.sql("update `tabIntegrity Check Item` set status = 'Đã khôi phục' where `check` = %s and document = %s "
                                  "and status = 'Chưa xử lý'", (doc.source_check, item.document))
            else:
                failed += 1
        doc.db_set({"records_restored": restored, "failed": failed}, update_modified=False)
        frappe.db.commit()
        runner.check_cancel(DOCTYPE, doc.name)
    status = "Thành công" if not failed else ("Một phần" if restored else "Lỗi")
    runner.finish(doc, status, records_restored=restored, failed=failed)


def _restore_one(item, entries: dict) -> dict:
    entry = entries.get(item.document)
    if not entry:
        return {"status": "Lỗi", "message": _("Không có bản sao lưu nào chứa tệp của văn bản này")}
    blob = filestore.get(entry["sha256"])
    if blob is None:
        return {"status": "Lỗi", "message": _("Bản sao lưu {0} của tệp bị thiếu hoặc hỏng").format(entry["backup"]),
                "source_backup": entry["backup"]}
    row = frappe.db.get_value("Archive Document", item.document, ["name", "file_attachment", "gridfs_file_id", "checksum"], as_dict=True)
    try:
        done = restore_document(row, entry, blob)
    except Exception as e:
        frappe.db.rollback()
        log_exception("Restore Error", f"Could not restore the file of {item.document}")
        return {"status": "Lỗi", "message": runner.explain(e), "source_backup": entry["backup"]}
    message = _("Đã khôi phục: {0}").format(", ".join(done)) if done else _("Tệp đã đúng, không cần ghi")
    return {"status": "Đã khôi phục", "message": message, "source_backup": entry["backup"]}


# --- the database ---------------------------------------------------------------------------------------------------

def verify_db_backup(batch_name: str) -> dict:
    """Is the dump of a backup batch fit to restore from? {ok, problems, path, size_mb, sha256}."""
    batch = frappe.get_doc("Backup Batch", batch_name)
    problems, digest, size = [], "", 0
    path = batch.backup_path
    if not path:
        problems.append(_("Đợt sao lưu không có tệp sao lưu cơ sở dữ liệu"))
    elif not os.path.isfile(path):
        problems.append(_("Không còn tệp {0} trên máy chủ").format(os.path.basename(path)))
    else:
        size = os.path.getsize(path)
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
            digest = sources.sha256(raw)
            if batch.db_checksum and batch.db_checksum != digest:
                problems.append(_("Mã SHA-256 của tệp khác với mã ghi lúc sao lưu: tệp đã bị thay đổi hoặc hỏng"))
            with gzip.open(path, "rb") as stream:
                head = stream.read(4096)
                while stream.read(1 << 20):
                    pass
            if b"CREATE TABLE" not in head and b"MariaDB dump" not in head and b"MySQL dump" not in head:
                problems.append(_("Nội dung tệp không giống một bản sao lưu cơ sở dữ liệu"))
        except (OSError, EOFError, gzip.BadGzipFile):
            problems.append(_("Tệp không đọc được hoặc không phải gzip hợp lệ"))
    return {"ok": not problems, "problems": problems, "path": path or "", "size_mb": round(size / (1024 * 1024), 2), "sha256": digest}


def db_restore_enabled() -> bool:
    return bool(cint(frappe.conf.get("dm_allow_db_restore")))


def root_password() -> str:
    return frappe.conf.get("dm_db_root_password") or os.environ.get("DB_ROOT_PASSWORD") or ""


def restore_command(path: str, site: str | None = None) -> str:
    return f'bench --site {site or frappe.local.site} --force restore "{path}" --db-root-password <mật khẩu root MariaDB>'


def runbook(path: str) -> str:
    site = frappe.local.site
    return (
        "Khôi phục cơ sở dữ liệu thay thế toàn bộ dữ liệu hiện tại bằng bản sao lưu, nên hệ thống không tự làm khi chưa được cho phép.\n"
        "Thực hiện trên máy chủ, theo thứ tự:\n"
        f"  1. bench --site {site} set-maintenance-mode on\n"
        f"  2. {restore_command(path)}\n"
        f"  3. bench --site {site} migrate\n"
        f"  4. bench --site {site} set-maintenance-mode off\n"
        "Sau đó đăng nhập, chạy một đợt kiểm tra toàn vẹn và kiểm tra lại dữ liệu.\n"
        "Muốn hệ thống tự chạy: đặt dm_allow_db_restore = 1 (và dm_db_root_password hoặc biến môi trường DB_ROOT_PASSWORD) trong site_config."
    )


def run_db_restore(doc, confirm_site: str) -> None:
    if not doc.source_backup:
        return runner.finish(doc, "Lỗi", error_log="Chưa chọn đợt sao lưu nguồn.")
    check = verify_db_backup(doc.source_backup)
    if not check["ok"]:
        return runner.finish(doc, "Lỗi", error_log="Bản sao lưu không dùng được:\n- " + "\n- ".join(check["problems"]))
    steps = runbook(check["path"])
    if not (db_restore_enabled() and root_password() and confirm_site == frappe.local.site):
        reason = ""
        if db_restore_enabled() and confirm_site != frappe.local.site:
            reason = "Chưa nhập đúng tên site để xác nhận nên hệ thống chưa tự chạy.\n"
        return runner.finish(doc, "Cần thao tác thủ công", error_log=f"Bản sao lưu đã được kiểm tra (SHA-256 {check['sha256'][:16]}…).\n{reason}{steps}")
    bench = frappe.utils.get_bench_path()
    site = frappe.local.site
    log = []
    try:
        for command in (["bench", "--site", site, "set-maintenance-mode", "on"],
                        ["bench", "--site", site, "--force", "restore", check["path"], "--db-root-password", root_password()],
                        ["bench", "--site", site, "migrate"]):
            result = subprocess.run(command, cwd=bench, capture_output=True, text=True, timeout=3 * 3600)
            log.append(f"$ {' '.join(command[:5])}\n{(result.stdout or '')[-800:]}{(result.stderr or '')[-800:]}")
            if result.returncode:
                raise RuntimeError(f"Lệnh {' '.join(command[:4])} lỗi (mã {result.returncode})")
        outcome = ("Thành công", "\n".join(log))
    except Exception as e:
        outcome = ("Lỗi", f"{runner.explain(e)}\n" + "\n".join(log))
    finally:
        subprocess.run(["bench", "--site", site, "set-maintenance-mode", "off"], cwd=bench, capture_output=True, text=True, timeout=300)
    # the restored database may not hold this batch any more: report where it can be seen
    try:
        frappe.db.rollback()
        if frappe.db.exists(DOCTYPE, doc.name):
            runner.finish(frappe.get_doc(DOCTYPE, doc.name), outcome[0], error_log=outcome[1][-60000:])
    except Exception:
        frappe.logger().warning("Restore batch %s ended %s: %s", doc.name, outcome[0], outcome[1][-500:])


# --- the job --------------------------------------------------------------------------------------------------------

def run(name: str, confirm_site: str = "") -> None:
    doc = frappe.get_doc(DOCTYPE, name)
    if doc.status not in ("Chưa chạy", "Đang chờ", "Đang chạy", "Lỗi", "Đã hủy"):
        return
    runner.mark_running(doc)
    frappe.db.commit()
    try:
        if doc.restore_type == "Cơ sở dữ liệu":
            run_db_restore(doc, confirm_site)
        else:
            run_files_restore(doc)
            if doc.restore_type == "Cả hai" and doc.source_backup:
                doc.reload()
                note = f"Phần cơ sở dữ liệu của đợt này làm riêng bằng một đợt phục hồi loại \"Cơ sở dữ liệu\".\n{runbook(frappe.db.get_value('Backup Batch', doc.source_backup, 'backup_path') or '')}"
                doc.db_set("error_log", note, update_modified=False)
    except runner.Cancelled:
        frappe.db.rollback()
        runner.finish(doc, "Đã hủy", error_log="Đã dừng theo yêu cầu. Các tài liệu đã phục hồi vẫn giữ nguyên.")
    except Exception as e:
        frappe.db.rollback()
        log_exception("Restore Error", f"Restore {name} failed")
        runner.finish(doc, "Lỗi", error_log=runner.explain(e))
    frappe.db.commit()
    if frappe.db.exists(DOCTYPE, name):
        runner.notify(frappe.get_doc(DOCTYPE, name), _("Phục hồi {0}: {1}").format(name, frappe.db.get_value(DOCTYPE, name, "status")))

