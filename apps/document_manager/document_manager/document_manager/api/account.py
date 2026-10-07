# -*- coding: utf-8 -*-
"""Whitelisted API of the signed-in reader's own account: profile, password and notifications.

Only the reader's own record is ever touched. The profile is edited through a short allow-list of
contact fields: name, e-mail, ID number, group and clearance stay under the officers' control.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from document_manager.document_manager.permissions import get_reader_profile, get_reader_scope
from document_manager.document_manager.policy import FEATURE_LABELS, FEATURES
from document_manager.document_manager.services import notify

EDITABLE_FIELDS = ("phone", "address", "organization", "position")
PROFILE_FIELDS = ("full_name", "email", "phone", "id_number", "organization", "position", "address",
                  "registration_date", "reader_group")


def _own_reader():
    profile = get_reader_profile()
    if not profile:
        frappe.throw(_("Tài khoản chưa có hồ sơ độc giả"), frappe.PermissionError)
    return frappe.get_doc("Reader", profile)


@frappe.whitelist()
def get_account():
    """The reader's profile plus what their group allows, for the account page."""
    reader = _own_reader()
    scope = get_reader_scope()
    return {
        "profile": {field: reader.get(field) for field in PROFILE_FIELDS},
        "is_active": bool(reader.is_active),
        "group": scope.group,
        "features": [{"feature": f, "label": FEATURE_LABELS[f], "allowed": bool(scope.get(f))} for f in FEATURES],
    }


@frappe.whitelist(methods=["POST"])
def update_profile(phone=None, address=None, organization=None, position=None):
    reader = _own_reader()
    values = {"phone": phone, "address": address, "organization": organization, "position": position}
    for field in EDITABLE_FIELDS:
        value = values[field]
        if value is not None:
            reader.set(field, frappe.utils.strip_html(str(value)).strip()[:300])
    reader.flags.ignore_permissions = True  # only the allow-listed fields above were set
    reader.save()
    return {field: reader.get(field) for field in EDITABLE_FIELDS}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=15 * 60)
def change_password(old_password, new_password):
    """Frappe's own `update_password`: password policy and re-login included.

    The current password is checked here first: Frappe answers a wrong one with an
    AuthenticationError, and the framework ends the session of whoever raises that. A reader who mistyped
    the old password must stay signed in, so it becomes an ordinary validation message.
    """
    from frappe.core.doctype.user.user import update_password
    from frappe.utils.password import check_password

    if not old_password or not new_password:
        frappe.throw(_("Vui lòng nhập mật khẩu hiện tại và mật khẩu mới"))
    if old_password == new_password:
        frappe.throw(_("Mật khẩu mới phải khác mật khẩu hiện tại"))
    try:
        check_password(frappe.session.user, old_password)
    except frappe.AuthenticationError:
        frappe.throw(_("Mật khẩu hiện tại không đúng"))
    update_password(new_password, old_password=old_password)
    return {"message": _("Đã đổi mật khẩu")}


# --- notifications ------------------------------------------------------------------------------

@frappe.whitelist()
def get_notifications(start=0, page_length=20):
    return notify.list_for(frappe.session.user, start, page_length)


@frappe.whitelist()
def get_unread_count():
    return notify.unread_count()


@frappe.whitelist(methods=["POST"])
def mark_notifications_read(names=None):
    """Mark some (JSON list of names) or all of the caller's notifications as read. Returns the unread count."""
    names = frappe.parse_json(names) if isinstance(names, str) and names else names
    return notify.mark_read(frappe.session.user, names or None)
