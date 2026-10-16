"""Private S3-compatible object storage for archive files (MinIO in production).

Frappe's private File remains the working copy. Object IDs are prefixed so an
old GridFS ObjectId is never accidentally interpreted as a MinIO object key.
"""

import hashlib
import os
import re
import uuid
from urllib.parse import quote, unquote

import frappe

PREFIX = "minio:"
_clients = {}


def configured() -> bool:
    return bool(os.environ.get("MINIO_ENDPOINT"))


def _settings():
    endpoint = os.environ.get("MINIO_ENDPOINT", "")
    access = os.environ.get("MINIO_APP_ACCESS_KEY", "")
    secret = os.environ.get("MINIO_APP_SECRET_KEY", "")
    bucket = os.environ.get("MINIO_BUCKET", "documents")
    if not (endpoint and access and secret and bucket):
        raise RuntimeError("MinIO endpoint, app access key, secret key and bucket are required")
    return endpoint, access, secret, bucket


def _client():
    import boto3
    from botocore.config import Config

    endpoint, access, secret, _ = _settings()
    cache_key = (endpoint, access, secret)
    if cache_key not in _clients:
        _clients[cache_key] = boto3.client(
            "s3", endpoint_url=endpoint, aws_access_key_id=access,
            aws_secret_access_key=secret, region_name="us-east-1",
            config=Config(
                s3={"addressing_style": "path"}, connect_timeout=3, read_timeout=30,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
    return _clients[cache_key]


def _site_prefix() -> str:
    return hashlib.sha256(frappe.local.site.encode()).hexdigest()[:16]


def _object_key(file_id: str, collection_name="documents") -> str:
    if not file_id or not file_id.startswith(PREFIX):
        raise ValueError("Object ID is not a MinIO key; migrate the legacy file first")
    key = file_id[len(PREFIX):]
    if not re.fullmatch(rf"{_site_prefix()}/{re.escape(collection_name)}/[0-9a-f]{{32}}", key):
        raise ValueError("Object ID does not belong to this site and collection")
    return key


class ObjectStorage:
    def __init__(self, collection_name="documents"):
        if collection_name not in ("documents", "previews"):
            raise ValueError("Unsupported object collection")
        self.collection_name = collection_name
        self.bucket = _settings()[3]
        self.client = _client()

    def upload_file(self, file_content, filename, content_type="application/octet-stream", metadata=None):
        site = _site_prefix()
        key = f"{site}/{self.collection_name}/{uuid.uuid4().hex}"
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=file_content, ContentType=content_type,
            Metadata={"filename": quote(filename, safe=""), "sha256": hashlib.sha256(file_content).hexdigest()},
        )
        return PREFIX + key

    def download_file(self, file_id):
        response = self.client.get_object(Bucket=self.bucket, Key=_object_key(file_id, self.collection_name))
        body = response["Body"]
        try:
            return body.read()
        finally:
            body.close()

    def get_file_info(self, file_id):
        info = self.client.head_object(Bucket=self.bucket, Key=_object_key(file_id, self.collection_name))
        return {
            "filename": unquote(info.get("Metadata", {}).get("filename", "")),
            "content_type": info.get("ContentType"),
            "length": info.get("ContentLength"),
            "metadata": info.get("Metadata", {}),
        }

    def delete_file(self, file_id):
        self.client.delete_object(Bucket=self.bucket, Key=_object_key(file_id, self.collection_name))

    def file_exists(self, file_id):
        from botocore.exceptions import ClientError

        try:
            self.get_file_info(file_id)
            return True
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            raise


def upload_document_file(doc_name, file_content, filename):
    """Store a private object and update its archive record."""
    import mimetypes

    storage = ObjectStorage()
    file_id = storage.upload_file(file_content, filename, mimetypes.guess_type(filename)[0] or "application/octet-stream")
    frappe.db.set_value("Archive Document", doc_name, {
        "gridfs_file_id": file_id,
        "checksum": hashlib.sha256(file_content).hexdigest(),
        "file_size_kb": round(len(file_content) / 1024, 2),
    }, update_modified=False)
    return file_id


def delete_object_files(file_ids, collection_name="documents"):
    from document_manager.document_manager.services.errors import log_exception

    ids = [i for i in file_ids or [] if i and i.startswith(PREFIX)]
    if not ids:
        return []
    try:
        storage = ObjectStorage(collection_name)
    except Exception:
        log_exception("MinIO Cleanup Error", f"Cannot connect to delete {len(ids)} file(s)")
        return ids
    failed = []
    for file_id in ids:
        try:
            storage.delete_file(file_id)
        except Exception:
            log_exception("MinIO Cleanup Error", f"Cannot delete object {file_id}")
            failed.append(file_id)
    return failed


def enqueue_delete_object_files(file_ids, collection_name="documents"):
    ids = [i for i in file_ids or [] if i and i.startswith(PREFIX)]
    if ids:
        frappe.enqueue(
            "document_manager.document_manager.services.object_storage.delete_object_files",
            file_ids=ids, collection_name=collection_name, queue="short", enqueue_after_commit=True,
        )
