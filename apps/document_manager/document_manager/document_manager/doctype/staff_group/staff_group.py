# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document

from document_manager.document_manager.constants import STAFF_ASSIGNABLE_ROLES


class StaffGroup(Document):
    """Nhóm cán bộ: gom người dùng và cấp vai trò đồng loạt.

    Saving the group gives its roles to every member (additively: leaving a group never takes a role away, that is
    done on the user). Only the staff roles of the app can be put in a group, and only staff accounts can be members;
    accounts with administrator rights of the whole system are never managed from here.
    """

    def validate(self):
        self.group_name = (self.group_name or "").strip()
        self._unique("roles", "role", _("Vai trò"))
        self._unique("members", "user", _("Thành viên"))
        for row in self.get("roles") or []:
            if row.role not in STAFF_ASSIGNABLE_ROLES:
                frappe.throw(_("Vai trò {0} không được cấp qua nhóm cán bộ").format(row.role))
        for row in self.get("members") or []:
            info = frappe.db.get_value("User", row.user, ["user_type", "enabled"], as_dict=True)
            if not info or info.user_type != "System User":
                frappe.throw(_("{0} không phải tài khoản cán bộ").format(row.user))
            if row.user in ("Administrator", "Guest") or "System Manager" in frappe.get_roles(row.user):
                frappe.throw(_("Không quản lý tài khoản {0} ở nhóm cán bộ").format(row.user))

    def _unique(self, table: str, field: str, label: str) -> None:
        seen = set()
        for row in self.get(table) or []:
            value = row.get(field)
            if value in seen:
                frappe.throw(_("{0} {1} xuất hiện hai lần").format(label, value))
            seen.add(value)

    def on_update(self):
        roles = [row.role for row in self.get("roles") or []]
        if not roles:
            return
        for row in self.get("members") or []:
            user = frappe.get_doc("User", row.user)
            missing = [r for r in roles if r not in {h.role for h in user.roles}]
            if missing:
                user.flags.ignore_permissions = True
                user.add_roles(*missing)
