# -*- coding: utf-8 -*-
"""Preservation of the electronic archive (module 7): backups, integrity checks and restores.

* `filestore`  — a content-addressed copy of the document files (one blob per distinct content, shared by batches);
* `backup`     — database dumps and the file backup of a batch, retention and the schedule;
* `integrity`  — checks of the database, of every document's file and of its description;
* `restore`    — restoring documents' files from a backup, and the controlled restore of the database;
* `runner`     — the Backup / Integrity / Restore jobs: status, progress, cancel, the queue entry points.

Who may use any of it: Document Admin, Preservation Officer and System Manager (`require_preservation`).
"""

import os

import frappe

from document_manager.document_manager.permissions import assert_roles

ROLES = ("Document Admin", "Preservation Officer", "System Manager")


def require_preservation() -> None:
    assert_roles(*ROLES)


def can_preserve(user: str | None = None) -> bool:
    user = user or frappe.session.user
    return user == "Administrator" or bool(set(ROLES) & set(frappe.get_roles(user)))


def backups_dir() -> str:
    """Where Frappe keeps the database dumps of this site (and where the file store lives)."""
    return frappe.get_site_path("private", "backups")


def store_dir() -> str:
    """The file store of the backups. It is NOT inside Frappe's backup folder: Frappe's own backup code scans that folder
    for dump files and trips over anything else in it."""
    return frappe.get_site_path("private", "dm-backup-store")
