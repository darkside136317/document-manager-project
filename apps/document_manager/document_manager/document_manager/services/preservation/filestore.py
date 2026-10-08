# -*- coding: utf-8 -*-
"""The file store of the backups: one blob per distinct content, named by its SHA-256, shared by every batch.

    <site>/private/backups/dm-files/objects/ab/ab12...            the bytes
    <site>/private/backups/dm-files/manifests/BK-20261008-001.jsonl  one line per document of a batch:
        {"document", "file_url", "filename", "sha256", "size", "source", "fonds"}

A backup therefore copies only what the store does not hold yet (incremental by nature), a restore finds the
bytes of any document by the hash in a batch's manifest, and deleting a batch only removes the blobs no
remaining batch refers to (`collect_garbage`).
"""

import json
import os
import time

from document_manager.document_manager.services.preservation import store_dir
from document_manager.document_manager.services.preservation.sources import sha256

GC_MIN_AGE = 24 * 3600  # a blob younger than this may belong to a backup that has not written its manifest yet


def objects_dir() -> str:
    return os.path.join(store_dir(), "objects")


def manifests_dir() -> str:
    return os.path.join(store_dir(), "manifests")


def blob_path(digest: str) -> str:
    return os.path.join(objects_dir(), digest[:2], digest)


def manifest_path(batch: str) -> str:
    return os.path.join(manifests_dir(), f"{batch}.jsonl")


def has(digest: str) -> bool:
    return bool(digest) and os.path.isfile(blob_path(digest))


def put(content: bytes) -> tuple[str, bool]:
    """Keep `content`; returns (its SHA-256, whether a new blob was written)."""
    digest = sha256(content)
    path = blob_path(digest)
    if os.path.isfile(path):
        return digest, False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.{os.getpid()}.tmp"
    with open(temporary, "wb") as handle:
        handle.write(content)
    os.replace(temporary, path)  # a reader never sees half a blob
    return digest, True


def get(digest: str) -> bytes | None:
    """The bytes of a blob, or None when it is missing or no longer matches its name (a damaged copy)."""
    try:
        with open(blob_path(digest), "rb") as handle:
            content = handle.read()
    except OSError:
        return None
    return content if sha256(content) == digest else None


def append_manifest(batch: str, entries: list[dict]) -> None:
    if not entries:
        return
    os.makedirs(manifests_dir(), exist_ok=True)
    with open(manifest_path(batch), "a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_manifest(batch: str):
    """The entries of a batch's manifest, one at a time."""
    try:
        handle = open(manifest_path(batch), encoding="utf-8")
    except OSError:
        return
    with handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def remove_manifest(batch: str) -> None:
    try:
        os.unlink(manifest_path(batch))
    except OSError:
        pass


def referenced(batches) -> set[str]:
    out = set()
    for batch in batches:
        out.update(entry["sha256"] for entry in read_manifest(batch) if entry.get("sha256"))
    return out


def collect_garbage(keep_batches, min_age: int | None = None) -> tuple[int, int]:
    """Delete the blobs that no kept batch refers to; returns (blobs removed, bytes freed)."""
    min_age = GC_MIN_AGE if min_age is None else min_age
    keep = referenced(keep_batches)
    removed = freed = 0
    now = time.time()
    root = objects_dir()
    if not os.path.isdir(root):
        return 0, 0
    for folder, _dirs, names in os.walk(root):
        for name in names:
            if name.endswith(".tmp") or name in keep:
                continue
            path = os.path.join(folder, name)
            try:
                if now - os.path.getmtime(path) < min_age:
                    continue
                size = os.path.getsize(path)
                os.unlink(path)
            except OSError:
                continue
            removed += 1
            freed += size
    return removed, freed


def usage() -> dict:
    """How much the store holds: {blobs, bytes, manifests}."""
    blobs = size = 0
    for folder, _dirs, names in os.walk(objects_dir()) if os.path.isdir(objects_dir()) else ():
        for name in names:
            if not name.endswith(".tmp"):
                blobs += 1
                try:
                    size += os.path.getsize(os.path.join(folder, name))
                except OSError:
                    pass
    manifests = len(os.listdir(manifests_dir())) if os.path.isdir(manifests_dir()) else 0
    return {"blobs": blobs, "bytes": size, "manifests": manifests}
