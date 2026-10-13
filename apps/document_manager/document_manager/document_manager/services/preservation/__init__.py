# -*- coding: utf-8 -*-
"""Preservation of the electronic archive (module 7): backups, integrity checks and restores.

* `filestore`  — a content-addressed copy of the document files (one blob per distinct content, shared by batches);
* `backup`     — database dumps and the file backup of a batch, retention and the schedule;
* `integrity`  — checks of the database, of every document's file and of its description;
* `restore`    — restoring documents' files from a backup, and the controlled restore of the database;
* `runner`     — the Backup / Integrity / Restore jobs: status, progress, cancel, the queue entry points.

Who may use it: the preservation capabilities (`preservation.backup|check|restore|db_restore`), administrators always.
"""

import frappe

from document_manager.document_manager.permissions import assert_capability, has_capability

CAPABILITIES = ("preservation.backup", "preservation.check", "preservation.restore", "preservation.db_restore")
# the kind of job -> the capability that runs it
KIND_CAPABILITY = {"backup": "preservation.backup", "integrity": "preservation.check", "restore": "preservation.restore"}


def require_preservation(*capabilities: str) -> None:
    """Any preservation capability by default; the given one(s) when the action needs a particular one."""
    assert_capability(*(capabilities or CAPABILITIES))


def can_preserve(user: str | None = None) -> bool:
    return has_capability(*CAPABILITIES, user=user)


def backups_dir() -> str:
    """Where Frappe keeps the database dumps of this site (and where the file store lives)."""
    return frappe.get_site_path("private", "backups")


def store_dir() -> str:
    """The file store of the backups. It is NOT inside Frappe's backup folder: Frappe's own backup code scans that folder
    for dump files and trips over anything else in it."""
    return frappe.get_site_path("private", "dm-backup-store")
