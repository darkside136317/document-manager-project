# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document

from document_manager.document_manager.permissions import STAFF_ROLES


class Reader(Document):
    """Độc giả — người dùng bên ngoài khai thác tài liệu."""

    def validate(self):
        # 0 = "follow the group"; a positive number overrides the group's clearance for this reader.
        self.max_confidentiality_priority = max(0, int(self.max_confidentiality_priority or 0))
        if not self.reader_group:
            self.reader_group = frappe.db.get_value("Reader Group", {"is_default": 1}, "name")
        if self.user and not self.email:
            self.email = frappe.db.get_value("User", self.user, "email")

    def on_update(self):
        if self.user:
            _sync_user(self)


def _is_staff_account(user):
    return user == "Administrator" or bool(STAFF_ROLES.intersection(frappe.get_roles(user)))


def _sync_user(reader):
    """Keep the linked User consistent with the Reader profile.

    * every linked user gets the Reader role;
    * reader-only accounts are Website Users (no Desk) and are enabled/disabled with `is_active`;
    * accounts that also hold a staff role are never downgraded or disabled from here.
    """
    user_doc = frappe.get_doc("User", reader.user)
    if "Reader" not in [r.role for r in user_doc.roles]:
        user_doc.append("roles", {"role": "Reader"})
        user_doc.flags.ignore_permissions = True
        user_doc.save()

    if _is_staff_account(reader.user):
        return

    _ensure_website_user(reader.user)
    enabled = 1 if reader.is_active else 0
    if frappe.db.get_value("User", reader.user, "enabled") != enabled:
        frappe.db.set_value("User", reader.user, "enabled", enabled)
        if not enabled:
            from frappe.sessions import clear_sessions
            clear_sessions(reader.user, force=True)


def _ensure_website_user(user):
    """Reader-only users get Website User type (no Desk access); staff keep System User."""
    if _is_staff_account(user):
        return
    frappe.db.set_value("User", user, "user_type", "Website User")


@frappe.whitelist(methods=["POST"])
def set_reader_password(reader_name, new_password):
    """Create/link the login account of a reader and set its password (admins only)."""
    frappe.only_for(("Document Admin", "System Manager"))
    reader = frappe.get_doc("Reader", reader_name)

    if not reader.user:
        if not reader.email:
            frappe.throw(_("Vui lòng cập nhật Email cho Độc giả trước khi tạo tài khoản đăng nhập."))
        if frappe.db.exists("User", reader.email):
            target = reader.email
        else:
            user = frappe.get_doc({
                "doctype": "User",
                "email": reader.email,
                "first_name": reader.full_name,
                "send_welcome_email": 0,
                "user_type": "Website User",
                "roles": [{"role": "Reader"}],
            })
            user.flags.no_welcome_mail = True
            user.insert(ignore_permissions=True)
            target = user.name
    else:
        target = reader.user

    # Never let a reader profile be used to take over someone else's account.
    if _is_staff_account(target):
        frappe.throw(_("Không thể đặt mật khẩu cho tài khoản cán bộ từ hồ sơ độc giả."), frappe.PermissionError)
    other = frappe.db.get_value("Reader", {"user": target, "name": ["!=", reader.name]})
    if other:
        frappe.throw(_("Tài khoản {0} đã gắn với độc giả {1}").format(target, other))

    if not reader.user:
        reader.user = target
        reader.flags.ignore_permissions = True
        reader.save()  # on_update adds the Reader role and sets the user type

    # Saving through the User doctype applies the site's password policy.
    user = frappe.get_doc("User", target)
    user.new_password = new_password
    user.flags.ignore_permissions = True
    user.save()
    return {"message": _("Thành công"), "user": target}
