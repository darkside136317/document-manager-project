# -*- coding: utf-8 -*-
"""MongoDB Atlas GridFS integration for file storage.

Provides upload, download, and delete operations for archival documents
using MongoDB Atlas GridFS. Replaces S3/MinIO for file storage.

Usage:
    from document_manager.document_manager.services.mongodb_storage import MongoGridFSStorage

    storage = MongoGridFSStorage()
    file_id = storage.upload_file(file_content, filename, metadata)
    content = storage.download_file(file_id)
    storage.delete_file(file_id)
"""

import frappe
from frappe.utils import cint

# pymongo imports (deferred to avoid import errors during bench setup)
_mongo_clients = {}  # one client per connection URI (a bench serves several sites)


def _get_mongo_client():
    """Lazy-initialize the MongoDB client of the current site (site config or environment)."""
    import pymongo

    uri = (
        frappe.conf.get("mongodb_atlas_uri")
        or frappe.get_conf().get("mongodb_atlas_uri")
        or ""
    )
    if not uri:
        frappe.throw(
            "MongoDB Atlas URI chưa được cấu hình. "
            "Thêm 'mongodb_atlas_uri' vào site_config.json hoặc common_site_config.json."
        )

    if uri not in _mongo_clients:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")  # fail now, not on the first read
        _mongo_clients[uri] = client
    return _mongo_clients[uri]


def _get_database():
    """Get the GridFS database."""
    client = _get_mongo_client()
    db_name = (
        frappe.conf.get("mongodb_database")
        or frappe.get_conf().get("mongodb_database")
        or "docmanager_files"
    )
    return client[db_name]


class MongoGridFSStorage:
    """MongoDB Atlas GridFS storage backend for archival documents.

    Files are stored in two GridFS collections:
    - 'documents': original uploaded files (PDF, DOCX, XLSX, images)
    - 'previews': generated preview files (PDF previews, thumbnails)
    """

    def __init__(self, collection_name: str = "documents"):
        """Initialize GridFS storage.

        Args:
            collection_name: GridFS collection prefix ('documents' or 'previews')
        """
        import gridfs

        self.db = _get_database()
        self.fs = gridfs.GridFS(self.db, collection=collection_name)
        self.collection_name = collection_name

    def upload_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> str:
        """Upload a file to MongoDB Atlas GridFS.

        Args:
            file_content: Raw file bytes
            filename: Original filename
            content_type: MIME type
            metadata: Additional metadata dict (doc_name, fonds, checksum, etc.)

        Returns:
            str: GridFS file ObjectId as string
        """
        file_id = self.fs.put(
            file_content,
            filename=filename,
            content_type=content_type,
            metadata=metadata or {},
        )
        return str(file_id)

    def download_file(self, file_id: str) -> bytes:
        """Download a file from GridFS by its ObjectId.

        Args:
            file_id: GridFS ObjectId as string

        Returns:
            bytes: File content
        """
        from bson import ObjectId

        grid_out = self.fs.get(ObjectId(file_id))
        return grid_out.read()

    def get_file_info(self, file_id: str) -> dict:
        """Get file metadata without downloading content.

        Args:
            file_id: GridFS ObjectId as string

        Returns:
            dict: File info including filename, content_type, length, metadata
        """
        from bson import ObjectId

        grid_out = self.fs.get(ObjectId(file_id))
        return {
            "filename": grid_out.filename,
            "content_type": grid_out.content_type,
            "length": grid_out.length,
            "upload_date": grid_out.upload_date,
            "metadata": grid_out.metadata,
        }

    def delete_file(self, file_id: str) -> None:
        """Delete a file from GridFS.

        Args:
            file_id: GridFS ObjectId as string
        """
        from bson import ObjectId

        self.fs.delete(ObjectId(file_id))

    def file_exists(self, file_id: str) -> bool:
        """Check if a file exists in GridFS.

        Args:
            file_id: GridFS ObjectId as string

        Returns:
            bool: True if file exists
        """
        from bson import ObjectId

        return self.fs.exists(ObjectId(file_id))

    def list_files(self, query: dict | None = None, limit: int = 100) -> list[dict]:
        """List files in GridFS matching a query.

        Args:
            query: MongoDB query dict (applied to metadata)
            limit: Maximum number of results

        Returns:
            list[dict]: File info dicts
        """
        cursor = self.db[f"{self.collection_name}.files"].find(
            query or {}, limit=limit
        )
        return [
            {
                "file_id": str(doc["_id"]),
                "filename": doc.get("filename"),
                "content_type": doc.get("contentType"),
                "length": doc.get("length"),
                "upload_date": doc.get("uploadDate"),
                "metadata": doc.get("metadata", {}),
            }
            for doc in cursor
        ]


# --- Convenience functions for use in hooks and workers ---


def upload_document_file(doc_name: str, file_content: bytes, filename: str) -> str:
    """Upload a document file and update the Archive Document record.

    Args:
        doc_name: Archive Document name
        file_content: Raw file bytes
        filename: Original filename

    Returns:
        str: GridFS file ID
    """
    import hashlib

    storage = MongoGridFSStorage(collection_name="documents")

    # Compute checksum
    checksum = hashlib.sha256(file_content).hexdigest()

    # Detect content type
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    content_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "tiff": "image/tiff",
        "tif": "image/tiff",
    }
    content_type = content_types.get(ext, "application/octet-stream")

    # Get parent hierarchy for metadata
    doc = frappe.get_doc("Archive Document", doc_name)
    metadata = {
        "doc_name": doc_name,
        "archival_file": doc.archival_file,
        "fonds": doc.fonds,
        "checksum": checksum,
    }

    file_id = storage.upload_file(file_content, filename, content_type, metadata)

    # Update the document record
    frappe.db.set_value("Archive Document", doc_name, {
        "gridfs_file_id": file_id,
        "checksum": checksum,
        "file_size_kb": round(len(file_content) / 1024, 2),
    }, update_modified=False)

    return file_id


def upload_preview_file(doc_name: str, preview_content: bytes, filename: str) -> str:
    """Upload a preview file (PDF/thumbnail) for an Archive Document.

    Args:
        doc_name: Archive Document name
        preview_content: Preview file bytes
        filename: Preview filename

    Returns:
        str: GridFS preview file ID
    """
    storage = MongoGridFSStorage(collection_name="previews")

    file_id = storage.upload_file(
        preview_content,
        filename,
        content_type="application/pdf",
        metadata={"doc_name": doc_name},
    )

    frappe.db.set_value(
        "Archive Document", doc_name, "gridfs_preview_id", file_id,
        update_modified=False,
    )

    return file_id


def download_document_file(doc_name: str) -> tuple[bytes, str]:
    """Download the original file for an Archive Document.

    Args:
        doc_name: Archive Document name

    Returns:
        tuple: (file_content, filename)
    """
    doc = frappe.get_doc("Archive Document", doc_name)
    if not doc.gridfs_file_id:
        frappe.throw(f"Văn bản {doc_name} chưa có file trong GridFS")

    storage = MongoGridFSStorage(collection_name="documents")
    info = storage.get_file_info(doc.gridfs_file_id)
    content = storage.download_file(doc.gridfs_file_id)

    # Update last_accessed
    frappe.db.set_value(
        "Archive Document", doc_name, "last_accessed", frappe.utils.now(),
        update_modified=False,
    )

    return content, info["filename"]


# --- Cleanup (a deleted/replaced document must not leave its bytes behind) ---

def delete_gridfs_files(file_ids, collection_name: str = "documents") -> list[str]:
    """Delete files from GridFS; returns the ids that could not be deleted.

    Failures are logged with a traceback instead of being swallowed, so the orphans can be
    found (and retried by the integrity check) later.
    """
    from document_manager.document_manager.services.errors import log_exception

    ids = [i for i in (file_ids or []) if i]
    if not ids:
        return []
    try:
        storage = MongoGridFSStorage(collection_name=collection_name)
    except Exception:
        log_exception("GridFS Cleanup Error", f"Cannot connect to delete {len(ids)} file(s)")
        return ids

    failed = []
    for file_id in ids:
        try:
            storage.delete_file(file_id)
        except Exception:
            log_exception("GridFS Cleanup Error", f"Cannot delete {collection_name}/{file_id}")
            failed.append(file_id)
    return failed


def enqueue_delete_gridfs_files(file_ids, collection_name: str = "documents"):
    """Delete GridFS files in the background once the surrounding transaction has committed."""
    ids = [i for i in (file_ids or []) if i]
    if not ids:
        return
    frappe.enqueue(
        "document_manager.document_manager.services.mongodb_storage.delete_gridfs_files",
        file_ids=ids,
        collection_name=collection_name,
        queue="short",
        enqueue_after_commit=True,
    )

