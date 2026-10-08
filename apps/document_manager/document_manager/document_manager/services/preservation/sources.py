# -*- coding: utf-8 -*-
"""Where the bytes of a document live: the private file on disk (the working copy) and the GridFS copy in MongoDB.

Reading prefers the disk, then GridFS. Nothing here raises for a missing source: the callers decide what a
missing or unreadable file means (an error in a backup, a finding in a check).
"""

import hashlib
import time

import frappe

from document_manager.document_manager.services.errors import log_exception

PROBE_TTL = 60
_probe: dict = {"at": 0.0, "ok": False, "message": ""}


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def mongo_available() -> tuple[bool, str]:
    """(reachable, reason) of the GridFS server; remembered for a minute so a long run pings it once."""
    now = time.monotonic()
    if now - _probe["at"] < PROBE_TTL and _probe["at"]:
        return _probe["ok"], _probe["message"]
    try:
        from document_manager.document_manager.services.mongodb_storage import _get_database

        _get_database().client.admin.command("ping")
        _probe.update(at=now, ok=True, message="")
    except Exception as e:
        from document_manager.document_manager.services.health import _short

        _probe.update(at=now, ok=False, message=_short(e))
    return _probe["ok"], _probe["message"]


def forget_probe() -> None:
    _probe["at"] = 0.0


def has_file(row) -> bool:
    return bool(row.get("file_attachment") or row.get("gridfs_file_id"))


def disk_path(file_url: str) -> str | None:
    """Full path of the private file behind `file_url`, or None when there is no File record for it."""
    if not file_url:
        return None
    name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not name:
        return None
    try:
        return frappe.get_doc("File", name).get_full_path()
    except Exception:
        return None


def read_disk(file_url: str) -> bytes | None:
    path = disk_path(file_url)
    if not path:
        return None
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def read_gridfs(file_id: str) -> bytes | None:
    if not file_id or not mongo_available()[0]:
        return None
    try:
        from document_manager.document_manager.services.mongodb_storage import MongoGridFSStorage

        storage = MongoGridFSStorage(collection_name="documents")
        return storage.download_file(file_id) if storage.file_exists(file_id) else None
    except Exception:
        log_exception("Preservation", f"Could not read GridFS file {file_id}")
        return None


def gridfs_exists(file_id: str) -> bool | None:
    """True/False when MongoDB answers, None when it cannot be asked."""
    if not file_id or not mongo_available()[0]:
        return None
    try:
        from document_manager.document_manager.services.mongodb_storage import MongoGridFSStorage

        return bool(MongoGridFSStorage(collection_name="documents").file_exists(file_id))
    except Exception:
        return None


def read_document(row) -> tuple[bytes | None, str]:
    """(bytes, source) of a document's file: "disk" or "gridfs"; (None, "") when neither can be read."""
    content = read_disk(row.get("file_attachment"))
    if content is not None:
        return content, "disk"
    content = read_gridfs(row.get("gridfs_file_id"))
    return (content, "gridfs") if content is not None else (None, "")


def filename_of(row) -> str:
    url = row.get("file_attachment") or ""
    return url.rsplit("/", 1)[-1] if url else f"{row.get('name')}"


# the first bytes of the formats the archive accepts
MAGIC = {
    "PDF": (b"%PDF",), "DOCX": (b"PK\x03\x04",), "XLSX": (b"PK\x03\x04",), "JPG": (b"\xff\xd8\xff",),
    "PNG": (b"\x89PNG\r\n\x1a\n",), "TIFF": (b"II*\x00", b"MM\x00*"),
}


def matches_type(file_type: str, content: bytes) -> bool | None:
    """Do the first bytes fit the declared type? None for a type nothing is known about."""
    signatures = MAGIC.get((file_type or "").upper())
    if not signatures:
        return None
    return any(content.startswith(s) for s in signatures)
