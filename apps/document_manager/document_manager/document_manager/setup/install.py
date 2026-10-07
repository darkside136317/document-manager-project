# -*- coding: utf-8 -*-
"""Idempotent seed of everything a *fresh* site needs.

`after_install` runs on `bench install-app` (a new site); `after_migrate` runs on every
`bench migrate`. Both call `seed_all`, which only creates what is missing, so an existing site's
data is never overwritten.
"""

import frappe

from document_manager.document_manager.setup_workflows import setup_all

ROLES = (
    ("Document Admin", 1),
    ("Cataloger", 1),
    ("Reading Room Officer", 1),
    ("Preservation Officer", 1),
    ("Reader", 0),
)

# (name, code, priority, description) — priority 1 is what every reader sees by default.
CONFIDENTIALITY_LEVELS = (
    ("Thường", "TH", 1, "Tài liệu thường, được khai thác theo quy định chung"),
    ("Mật", "M", 2, "Tài liệu mật — chỉ độc giả được cấp quyền"),
    ("Tối mật", "TM", 3, "Tài liệu tối mật — chỉ độc giả được cấp quyền đặc biệt"),
    ("Tuyệt mật", "TUM", 4, "Tài liệu tuyệt mật — chỉ cán bộ"),
)


def after_install():
    set_vietnamese_defaults()
    seed_all()


def after_migrate():
    seed_all()


def seed_all():
    ensure_roles()
    ensure_confidentiality_levels()
    ensure_default_reader_group()
    setup_all()  # workflows + in-app notifications of the reader requests


def ensure_roles():
    for name, desk_access in ROLES:
        if not frappe.db.exists("Role", name):
            frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": desk_access,
                            "is_custom": 1}).insert(ignore_permissions=True)


def ensure_confidentiality_levels():
    """The default level ("Thường") is a Link default on Archival File: it must always exist."""
    for name, code, priority, description in CONFIDENTIALITY_LEVELS:
        if not frappe.db.exists("Confidentiality Level", name):
            frappe.get_doc({"doctype": "Confidentiality Level", "level_name": name, "level_code": code,
                            "priority": priority, "description": description}
                           ).insert(ignore_permissions=True)


DEFAULT_READER_GROUP = "Độc giả mặc định"


def ensure_default_reader_group() -> str:
    """The group of every reader who has none: public level, whole archive, every feature."""
    name = frappe.db.get_value("Reader Group", {"is_default": 1}, "name")
    if name:
        return name
    if frappe.db.exists("Reader Group", DEFAULT_READER_GROUP):
        frappe.db.set_value("Reader Group", DEFAULT_READER_GROUP, {"is_default": 1, "is_active": 1})
        return DEFAULT_READER_GROUP
    frappe.get_doc({"doctype": "Reader Group", "group_name": DEFAULT_READER_GROUP, "is_default": 1,
                    "is_active": 1, "max_confidentiality_priority": 1,
                    "description": "Nhóm áp dụng cho độc giả chưa được xếp nhóm"}).insert(ignore_permissions=True)
    return DEFAULT_READER_GROUP


def set_vietnamese_defaults() -> bool:
    """Frappe's own messages (link checks, validation, ...) should read Vietnamese on this app.

    Only a site still on the factory default (English) is switched, and only once: running it
    again never overrides a language an administrator chose later. Returns True when it changed.
    """
    if frappe.db.get_single_value("System Settings", "language") not in (None, "", "en"):
        return False
    if not frappe.db.exists("Language", "vi"):
        return False
    frappe.db.set_value("Language", "vi", "enabled", 1)
    frappe.db.set_single_value("System Settings", "language", "vi")
    frappe.clear_cache()
    return True
