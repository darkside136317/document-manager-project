# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document

from document_manager.document_manager.constants import ADMIN_ONLY_CAPABILITIES, ADMIN_ROLE, CAPABILITY_CODES

# The slip workflows name the roles that may move a slip: they follow these capabilities.
WORKFLOW_CAPABILITIES = frozenset({"slips.receive", "slips.leader_approve"})
# Frappe's own roles never become permission groups of the application.
RESERVED_ROLES = frozenset({"Administrator", "System Manager", "Guest", "All", "Desk User", "Reader"})


class StaffRoleProfile(Document):
    """Nhóm quyền cán bộ: a Frappe Role described for the staff app, with the functions it grants.

    What the group may do with data (read / create / write / delete ...) is the role's DocPerm, which Frappe enforces
    everywhere; the functions that are not a DocType (approve a slip as a leader, run a backup, ...) are the
    `capabilities` rows, checked by `policy.has_capability`. The administrators' group holds every capability
    implicitly and cannot be changed.
    """

    def validate(self):
        if self.role in RESERVED_ROLES:
            frappe.throw(_("Vai trò {0} không thể làm nhóm quyền của ứng dụng").format(self.role))
        self.label = (self.label or "").strip()
        self.is_admin = int(self.role == ADMIN_ROLE)
        if self.is_admin:
            self.set("capabilities", [])  # an administrator holds every capability: nothing to list
            return
        seen = set()
        for row in self.get("capabilities") or []:
            code = (row.capability or "").strip()
            if code in ADMIN_ONLY_CAPABILITIES:
                frappe.throw(_("Chức năng {0} chỉ dành cho quản trị viên").format(code))
            if code not in CAPABILITY_CODES:
                frappe.throw(_("Chức năng {0} không tồn tại").format(code))
            if code in seen:
                frappe.throw(_("Chức năng {0} xuất hiện hai lần").format(code))
            seen.add(code)
            row.capability = code

    def on_update(self):
        from document_manager.document_manager.policy import clear_cache

        clear_cache()
        before = self.get_doc_before_save()
        old = {r.capability for r in before.get("capabilities") or []} if before else set()
        new = {r.capability for r in self.get("capabilities") or []}
        if (old ^ new) & WORKFLOW_CAPABILITIES:
            sync_workflows()

    def on_trash(self):
        if self.is_builtin and not frappe.flags.in_uninstall:
            frappe.throw(_("Không xóa được nhóm quyền có sẵn"))
        from document_manager.document_manager.policy import clear_cache

        clear_cache()


def sync_workflows() -> None:
    from document_manager.document_manager.setup_workflows import setup_all

    setup_all()
