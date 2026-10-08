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
    ("Archive Leader", 1),
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
    set_upload_limit()
    set_password_link_expiry()
    seed_all()


def after_migrate():
    seed_all()


def seed_all():
    ensure_roles()
    ensure_confidentiality_levels()
    ensure_reader_settings_defaults()
    ensure_settings_defaults()
    from document_manager.document_manager.services.templates import ensure_default_templates
    ensure_default_templates()
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
                            "priority": priority, "description": description,
                            "requires_leader_approval": 1 if priority >= 2 else 0}
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


def set_upload_limit() -> bool:
    """Scanned records are big: raise Frappe's per-file limit to what the cataloguing screen accepts.

    A larger value chosen by an administrator is kept. Returns True when it changed.
    """
    from document_manager.document_manager.constants import UPLOAD_MAX_MB

    if frappe.utils.cint(frappe.db.get_single_value("System Settings", "max_file_size")) >= UPLOAD_MAX_MB:
        return False
    frappe.db.set_single_value("System Settings", "max_file_size", UPLOAD_MAX_MB)
    frappe.clear_cache()
    return True


PASSWORD_LINK_EXPIRY_SECONDS = 72 * 3600
FRAPPE_DEFAULT_LINK_EXPIRY = 1200  # 20 minutes: too short for a link an officer passes on to the reader


def set_password_link_expiry() -> bool:
    """One-time "set your password" links of new readers stay valid for 72 hours.

    Only a site still on Frappe's factory value (20 minutes) or on 0 ("never expires") is changed,
    and only when this runs (install, one patch): a value an administrator chose is kept.
    Returns True when it changed.
    """
    current = frappe.utils.cint(frappe.db.get_single_value("System Settings", "reset_password_link_expiry_duration"))
    if current not in (0, FRAPPE_DEFAULT_LINK_EXPIRY):
        return False
    frappe.db.set_single_value("System Settings", "reset_password_link_expiry_duration", PASSWORD_LINK_EXPIRY_SECONDS)
    frappe.clear_cache()
    return True


# Values a site that predates a Reader Settings field gets, once. A single DocType stores nothing for a
# field nobody saved, which reads as 0 ("no limit"): without this a new limit would silently be off.
READER_SETTINGS_DEFAULTS = {
    "max_items_per_request": 20, "max_open_requests": 5, "max_renewals": 2, "renewal_days": 7,
    "reminder_days_before": 1, "block_when_overdue": 1,
}


def ensure_reader_settings_defaults() -> int:
    """Store the default of every Reader Settings field that has no stored value. Returns how many."""
    stored = {row[0] for row in frappe.db.sql(
        "select field from tabSingles where doctype = %s", "Reader Settings")}
    missing = {field: value for field, value in READER_SETTINGS_DEFAULTS.items() if field not in stored}
    for field, value in missing.items():
        frappe.db.set_single_value("Reader Settings", field, value)
    if missing:
        frappe.clear_document_cache("Reader Settings", "Reader Settings")
    return len(missing)


def ensure_single_defaults(doctype: str, overrides: dict | None = None) -> int:
    """Store the default of every field of a Single that has no stored value yet (fields added to a settings page that
    already exists read as empty or 0 until then: a first save would fail validation or switch a check off)."""
    stored = {row[0] for row in frappe.db.sql("select field from tabSingles where doctype = %s", doctype)}
    overrides = overrides or {}
    missing = {}
    for field in frappe.get_meta(doctype).fields:
        if field.fieldname in stored:
            continue
        value = overrides.get(field.fieldname, field.default)
        if value not in (None, "") and not str(value).startswith(":") and str(value) not in ("Today", "Now"):
            missing[field.fieldname] = value
    for field, value in missing.items():
        frappe.db.set_single_value(doctype, field, value)
    if missing:
        frappe.clear_document_cache(doctype, doctype)
    return len(missing)


def ensure_settings_defaults() -> int:
    """Document Manager Settings: new fields start from their default; the account-security ones from what Frappe's
    System Settings holds now, so that the form shows what is in force (and a first save changes nothing)."""
    from document_manager.document_manager.doctype.document_manager_settings.document_manager_settings import SYSTEM_SETTINGS

    current = {}
    for field, target in SYSTEM_SETTINGS.items():
        value = frappe.db.get_single_value("System Settings", target)
        if frappe.utils.cint(value):
            current[field] = value
    # a zero the form once saved for an empty number is not a choice (every one of these needs 1 or more): put the default back
    from document_manager.document_manager.doctype.document_manager_settings.document_manager_settings import RANGES

    zeros = [field for field, _low, _high in RANGES if frappe.db.get_single_value("Document Manager Settings", field) in (0, "0", "")]
    for field in zeros:
        frappe.db.sql("delete from tabSingles where doctype = 'Document Manager Settings' and field = %s", field)
    if zeros:
        frappe.clear_document_cache("Document Manager Settings", "Document Manager Settings")
    return ensure_single_defaults("Document Manager Settings", current)


def flag_levels_needing_leader() -> int:
    """Existing sites: the levels above "Thường" need a leader's approval (the new flag starts at 0)."""
    names = frappe.get_all("Confidentiality Level", filters={"priority": [">=", 2], "requires_leader_approval": 0},
                           pluck="name")
    for name in names:
        frappe.db.set_value("Confidentiality Level", name, "requires_leader_approval", 1)
    return len(names)
