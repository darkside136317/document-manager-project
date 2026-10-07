# -*- coding: utf-8 -*-
"""Whitelisted API for reader registration.

Guest endpoints (register, forgot password) are POST-only, rate limited per IP and carry a honeypot
field; every other endpoint is for the officers who approve registrations. All rules live in
`services/registration.py`.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from document_manager.document_manager.permissions import assert_roles
from document_manager.document_manager.services import registration
from document_manager.document_manager.services.audit import log_activity

OFFICERS = ("Reading Room Officer", "Document Admin")


def _ip():
    return getattr(frappe.local, "request_ip", None)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def register_reader(full_name, email, phone=None, id_number=None, organization=None, position=None,
                    address=None, purpose=None, website=None):
    """Public sign-up form. `website` is a honeypot: people leave it empty, bots fill it."""
    if website:
        return {"status": "pending", "message": registration.ACCEPTED_MESSAGE}
    return registration.submit_registration(
        {"full_name": full_name, "email": email, "phone": phone, "id_number": id_number,
         "organization": organization, "position": position, "address": address, "purpose": purpose},
        ip=_ip())


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=60 * 60)
def request_password_reset(email, website=None):
    """Public "forgot password" form: the officers are asked to issue a new link."""
    if website:
        return {"status": "pending", "message": registration.ACCEPTED_MESSAGE}
    return registration.submit_password_help(email, ip=_ip())


@frappe.whitelist()
def list_registrations(status=None, request_type=None, search=None, start=0, page_length=20):
    assert_roles(*OFFICERS)
    return registration.queue(status, request_type, search, start, page_length)


@frappe.whitelist()
def reader_groups():
    """Active reader groups an officer may put a new reader in (the default one first)."""
    assert_roles(*OFFICERS)
    return frappe.get_all("Reader Group", filters={"is_active": 1}, fields=["name", "is_default"],
                          order_by="is_default desc, name asc", limit_page_length=0)


@frappe.whitelist()
def pending_registrations():
    assert_roles(*OFFICERS)
    return registration.pending_count()


@frappe.whitelist(methods=["POST"])
def approve_registration(name, reader_group=None):
    """Create the account (registration) or choose a new password link (forgot password).

    The response holds the one-time `set_password_path`: give it to the person, it is not stored."""
    assert_roles(*OFFICERS)
    return registration.approve(name, reader_group or None)


@frappe.whitelist(methods=["POST"])
def reject_registration(name, reason):
    assert_roles(*OFFICERS)
    return registration.reject(name, reason)


@frappe.whitelist(methods=["POST"])
def reissue_link(name):
    """A new one-time link for an approved request (the first one was lost or has expired)."""
    assert_roles(*OFFICERS)
    doc = frappe.get_doc("Reader Registration", name)
    if doc.status != "Đã duyệt" or not doc.user:
        frappe.throw(_("Chỉ cấp lại liên kết cho yêu cầu đã duyệt"))
    path = registration.issue_password_link(doc.user)
    log_activity(registration.ACTIVITY, "Reader Registration", doc.name, f"Cấp lại liên kết đặt mật khẩu cho {doc.user}")
    return {"name": doc.name, "user": doc.user, "set_password_path": path}
