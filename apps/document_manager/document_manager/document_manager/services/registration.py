# -*- coding: utf-8 -*-
"""Reader registration and password help — the part of the reader site that serves people who are
not signed in yet.

Nobody here is trusted: input is validated and trimmed, answers never reveal whether an email
already has an account, and a request never touches an existing staff account. Approval creates
the User (Website User, role Reader) and the Reader profile in one transaction and hands back a
**one-time link** to set the password. The site sends no mail (no SMTP is required): the officer
passes the link to the person, or — when the site approves registrations automatically — the
registrant is shown the link straight away.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, validate_email_address

from document_manager.document_manager.doctype.reader.reader import _is_staff_account
from document_manager.document_manager.doctype.reader_registration.reader_registration import (
    REQUEST_REGISTER,
    REQUEST_RESET,
    STATUS_APPROVED,
    STATUS_NEW,
    STATUS_REJECTED,
)
from document_manager.document_manager.services.audit import log_activity

SET_PASSWORD_PATH = "/dat-mat-khau"
MAX_LENGTHS = {"full_name": 140, "email": 140, "phone": 20, "id_number": 20, "organization": 140,
               "position": 140, "address": 300, "purpose": 500}
PHONE_RE = re.compile(r"^[0-9+()\-. ]{6,20}$")

ACCEPTED_MESSAGE = "Yêu cầu đã được ghi nhận. Cán bộ sẽ xem xét và liên hệ với bạn qua email hoặc số điện thoại đã cung cấp."
ACTIVITY = "Quản lý người dùng"


def _clean(data: dict) -> dict:
    """Trimmed, tag-free, length-limited copy of the fields we accept."""
    out = {}
    for field, limit in MAX_LENGTHS.items():
        raw = data.get(field)
        value = frappe.utils.strip_html(str(raw)).strip() if raw else ""
        if field not in ("address", "purpose"):
            value = " ".join(value.split())
        if len(value) > limit:
            frappe.throw(_("Trường {0} quá dài (tối đa {1} ký tự)").format(field, limit))
        out[field] = value
    out["email"] = out["email"].lower()
    return out


def _check_new_registration(values: dict):
    if len(values["full_name"]) < 2:
        frappe.throw(_("Vui lòng nhập họ và tên"))
    if not validate_email_address(values["email"]):
        frappe.throw(_("Địa chỉ email không hợp lệ"))
    if values["phone"] and not PHONE_RE.match(values["phone"]):
        frappe.throw(_("Số điện thoại không hợp lệ"))


def registration_settings() -> frappe._dict:
    settings = frappe.get_cached_doc("Reader Settings")
    return frappe._dict(
        allow_self_registration=cint(settings.allow_self_registration),
        require_approval=cint(settings.require_approval),
    )


def _create_request(request_type: str, values: dict, ip: str | None, **extra) -> "frappe.model.document.Document":
    doc = frappe.get_doc({"doctype": "Reader Registration", "request_type": request_type, "status": STATUS_NEW,
                          "ip_address": ip, **values, **extra})
    doc.insert(ignore_permissions=True)
    return doc


def submit_registration(data: dict, ip: str | None = None) -> dict:
    """A visitor asks for a reader account. Returns {status: "pending" | "approved", ...}."""
    settings = registration_settings()
    if not settings.allow_self_registration:
        frappe.throw(_("Đơn vị hiện chưa mở đăng ký trực tuyến. Vui lòng liên hệ trực tiếp để được cấp tài khoản."))
    values = _clean(data)
    _check_new_registration(values)

    email = values["email"]
    taken = frappe.db.exists("User", email) or frappe.db.exists("Reader", {"email": email})
    waiting = frappe.db.exists("Reader Registration", {"email": email, "request_type": REQUEST_REGISTER,
                                                       "status": STATUS_NEW})
    if taken or waiting:
        # The same answer as a fresh request: nobody learns whether this email has an account.
        return {"status": "pending", "message": ACCEPTED_MESSAGE}

    doc = _create_request(REQUEST_REGISTER, values, ip)
    if settings.require_approval:
        return {"status": "pending", "message": ACCEPTED_MESSAGE}
    result = _approve(doc, actor="Administrator")
    return {"status": "approved", "set_password_path": result["set_password_path"],
            "message": _("Tài khoản đã được tạo. Hãy đặt mật khẩu để đăng nhập.")}


def submit_password_help(email: str, ip: str | None = None) -> dict:
    """A reader forgot the password: queue a request for the officers (same answer for every email)."""
    email = (email or "").strip().lower()
    if not validate_email_address(email):
        frappe.throw(_("Địa chỉ email không hợp lệ"))
    reader = frappe.db.get_value("Reader", {"email": email, "is_active": 1}, ["name", "user", "full_name"], as_dict=True)
    if reader and reader.user and frappe.db.get_value("User", reader.user, "enabled") and not _is_staff_account(reader.user):
        waiting = frappe.db.exists("Reader Registration", {"user": reader.user, "request_type": REQUEST_RESET,
                                                           "status": STATUS_NEW})
        if not waiting:
            _create_request(REQUEST_RESET, {"full_name": reader.full_name, "email": email}, ip,
                            reader=reader.name, user=reader.user)
    return {"status": "pending", "message": ACCEPTED_MESSAGE}


# --- staff side -----------------------------------------------------------------------------

def issue_password_link(user: str) -> str:
    """A new one-time path (`/dat-mat-khau?key=...`) that lets `user` choose a password.

    Replaces any earlier link. The key is stored hashed; the link expires after the System
    Settings "reset password link expiry". Staff accounts are refused: they keep the normal flow.
    """
    if _is_staff_account(user):
        frappe.throw(_("Không cấp liên kết đặt mật khẩu cho tài khoản cán bộ"), frappe.PermissionError)
    link = frappe.get_doc("User", user)._reset_password(send_email=False)
    return f"{SET_PASSWORD_PATH}?key={link.split('key=', 1)[1]}"


def check_link(key: str | None) -> tuple[str | None, str | None]:
    """(user, problem) of a set-password link: `user` when it still works, else why it does not."""
    from frappe.core.doctype.user.user import _get_user_for_update_password

    if not key or len(key) > 200:
        return None, "invalid"
    result = _get_user_for_update_password(key, None)
    if result.get("message"):
        return None, "expired" if "expired" in result["message"] else "invalid"
    return result["user"], None


def _approve(doc, actor: str, reader_group: str | None = None) -> dict:
    if doc.status != STATUS_NEW:
        frappe.throw(_("Yêu cầu này đã được xử lý"))
    if doc.request_type == REQUEST_REGISTER:
        user = _create_account(doc, reader_group)
    else:
        user = doc.user
        if not user or not frappe.db.exists("User", user):
            frappe.throw(_("Không tìm thấy tài khoản của độc giả"))
    path = issue_password_link(user)
    doc.db_set({"status": STATUS_APPROVED, "decided_by": actor, "decided_on": now_datetime(), "user": user},
               update_modified=True)
    log_activity(ACTIVITY, "Reader Registration", doc.name,
                 f"Duyệt {doc.request_type.lower()}: {doc.full_name} <{doc.email}>")
    return {"name": doc.name, "user": user, "reader": doc.reader, "set_password_path": path}


def _create_account(doc, reader_group: str | None) -> str:
    """User + Reader for an approved registration. Fails (and rolls back) if the email is now taken."""
    email = doc.email
    if frappe.db.exists("User", email) or frappe.db.exists("Reader", {"email": email}):
        frappe.throw(_("Email {0} đã có tài khoản").format(email))
    if reader_group and not frappe.db.exists("Reader Group", reader_group):
        frappe.throw(_("Nhóm độc giả {0} không tồn tại").format(reader_group))
    user = frappe.get_doc({
        "doctype": "User", "email": email, "first_name": doc.full_name, "enabled": 1,
        "send_welcome_email": 0, "user_type": "Website User", "roles": [{"role": "Reader"}],
    })
    user.flags.no_welcome_mail = True
    user.insert(ignore_permissions=True)
    reader = frappe.get_doc({
        "doctype": "Reader", "full_name": doc.full_name, "user": user.name, "email": email, "phone": doc.phone,
        "id_number": doc.id_number, "organization": doc.organization, "position": doc.position,
        "address": doc.address, "is_active": 1, "reader_group": reader_group,
        "notes": doc.purpose and _("Mục đích khai thác khi đăng ký: {0}").format(doc.purpose),
    })
    reader.insert(ignore_permissions=True)
    doc.db_set("reader", reader.name)
    doc.reader = reader.name
    return user.name


def approve(name: str, reader_group: str | None = None) -> dict:
    """Approve one request as the signed-in officer (savepoint: a half-created account never stays)."""
    doc = frappe.get_doc("Reader Registration", name)
    frappe.db.savepoint("approve_registration")
    try:
        return _approve(doc, actor=frappe.session.user, reader_group=reader_group)
    except Exception:
        frappe.db.rollback(save_point="approve_registration")
        raise


def reject(name: str, reason: str) -> dict:
    reason = (reason or "").strip()
    if not reason:
        frappe.throw(_("Phải nhập lý do từ chối"))
    doc = frappe.get_doc("Reader Registration", name)
    if doc.status != STATUS_NEW:
        frappe.throw(_("Yêu cầu này đã được xử lý"))
    doc.db_set({"status": STATUS_REJECTED, "decided_by": frappe.session.user, "decided_on": now_datetime(),
                "rejection_reason": reason})
    log_activity(ACTIVITY, "Reader Registration", doc.name, f"Từ chối: {doc.full_name} <{doc.email}>: {reason}")
    return {"name": doc.name, "status": STATUS_REJECTED}


QUEUE_FIELDS = ["name", "request_type", "status", "full_name", "email", "phone", "id_number", "organization",
                "position", "address", "purpose", "reader", "user", "decided_by", "decided_on",
                "rejection_reason", "creation"]


def queue(status: str | None = None, request_type: str | None = None, search: str | None = None,
          start: int = 0, page_length: int = 20) -> dict:
    filters = {}
    if status:
        filters["status"] = status
    if request_type:
        filters["request_type"] = request_type
    or_filters = None
    search = (search or "").strip()
    if search:
        like = f"%{search}%"
        or_filters = [["full_name", "like", like], ["email", "like", like], ["phone", "like", like],
                      ["organization", "like", like]]
    page_length = max(1, min(cint(page_length) or 20, 100))
    rows = frappe.get_all("Reader Registration", filters=filters, or_filters=or_filters, fields=QUEUE_FIELDS,
                          order_by="creation desc", start=max(0, cint(start)), page_length=page_length)
    total = frappe.get_all("Reader Registration", filters=filters, or_filters=or_filters,
                           fields=[{"COUNT": "name", "as": "c"}])[0].c
    return {"rows": rows, "total": total}


def pending_count() -> int:
    return frappe.db.count("Reader Registration", {"status": STATUS_NEW})
