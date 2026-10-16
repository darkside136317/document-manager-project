"""Idempotently import existing private Frappe files into MinIO on production start.

An old GridFS-only file cannot be imported without MongoDB; fail visibly before
serving the site so its last copy is not silently lost during a cutover.
"""

import hashlib
import os

import frappe

from document_manager.document_manager.services.object_storage import upload_document_file
from document_manager.document_manager.services.preservation.sources import disk_path, read_disk

PAGE = 100
_legacy_client = None


def _read_legacy(file_id):
    """Read a GridFS-only file during cutover if the old URI is still supplied."""
    global _legacy_client
    uri = os.environ.get("LEGACY_MONGODB_ATLAS_URI", "")
    if not uri or not file_id or file_id.startswith("minio:"):
        return None
    import gridfs
    import pymongo
    from bson import ObjectId

    if _legacy_client is None:
        _legacy_client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
    database = os.environ.get("LEGACY_MONGODB_DATABASE", "docmanager_files")
    return gridfs.GridFS(_legacy_client[database], collection="documents").get(ObjectId(file_id)).read()


def _restore_local(row, blob):
    path = disk_path(row.file_attachment) if row.file_attachment else None
    if not path:
        from frappe.utils.file_manager import save_file

        saved = save_file(row.name, blob, "Archive Document", row.name, is_private=1)
        frappe.db.set_value("Archive Document", row.name, "file_attachment", saved.file_url, update_modified=False)
        row.file_attachment = saved.file_url
        path = saved.get_full_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.minio-import.tmp"
    with open(temporary, "wb") as handle:
        handle.write(blob)
    os.replace(temporary, path)


def run():
    cursor = ""
    imported = 0
    missing = []
    while True:
        rows = frappe.db.sql(
            """SELECT name, file_attachment, gridfs_file_id, checksum FROM `tabArchive Document`
               WHERE name > %s
                 AND (gridfs_file_id IS NULL OR gridfs_file_id NOT LIKE 'minio:%%')
                 AND (COALESCE(file_attachment, '') != '' OR COALESCE(gridfs_file_id, '') != '')
               ORDER BY name LIMIT %s""",
            (cursor, PAGE), as_dict=True,
        )
        if not rows:
            break
        for row in rows:
            cursor = row.name
            blob = read_disk(row.file_attachment) if row.file_attachment else None
            if blob is not None and row.checksum and hashlib.sha256(blob).hexdigest() != row.checksum:
                blob = None
            if blob is None and row.gridfs_file_id:
                try:
                    blob = _read_legacy(row.gridfs_file_id)
                except Exception:
                    blob = None
                if blob is not None and row.checksum and hashlib.sha256(blob).hexdigest() != row.checksum:
                    blob = None
                if blob is not None:
                    _restore_local(row, blob)
            if blob is None:
                missing.append(row.name)
                continue
            filename = frappe.db.get_value("File", {"file_url": row.file_attachment}, "file_name")
            filename = filename or row.file_attachment.rsplit("/", 1)[-1]
            upload_document_file(row.name, blob, filename)
            frappe.db.commit()
            imported += 1
        print(f"MinIO backfill: {imported} imported; {len(missing)} missing local files")
    if missing:
        raise RuntimeError(
            f"MinIO backfill stopped: {len(missing)} files cannot be read from the site volume or legacy GridFS; "
            f"first documents: {', '.join(missing[:10])}. Restore these files before removing MongoDB."
        )
    return {"imported": imported, "missing": 0}
