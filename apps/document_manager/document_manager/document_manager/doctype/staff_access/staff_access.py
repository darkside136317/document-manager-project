# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document

READ_ALL, READ_CHOSEN = "Tất cả phông", "Chỉ các phông được chọn"
WRITE_SAME, WRITE_CHOSEN = "Như phạm vi xem", "Chỉ các phông được chọn"


class StaffAccess(Document):
    """Phạm vi truy cập của một cán bộ: the fonds they may read, the fonds they may change, the highest level they read.

    A staff member with no Staff Access and in no staff group that sets a scope reads and changes every fonds, as before
    scopes existed; otherwise the scopes of their Staff Access and of their staff groups add up. Administrators always
    have every fonds; what they may do is never narrowed here.
    """

    def validate(self):
        info = frappe.db.get_value("User", self.user, ["user_type"], as_dict=True)
        if not info or info.user_type != "System User":
            frappe.throw(_("{0} không phải tài khoản cán bộ").format(self.user))
        if self.max_confidentiality_priority and self.max_confidentiality_priority < 0:
            frappe.throw(_("Mức mật cao nhất không hợp lệ"))
        validate_scope(self)

    def on_update(self):
        _forget()

    def on_trash(self):
        _forget()


def validate_scope(doc) -> None:
    """Shared by Staff Access and Staff Group: chosen fonds listed once each, and fonds to change among the fonds read."""
    doc.read_scope = doc.read_scope or READ_ALL
    doc.write_scope = doc.write_scope or WRITE_SAME
    if doc.read_scope != READ_CHOSEN:
        doc.set("read_fonds", [])
    if doc.write_scope != WRITE_CHOSEN:
        doc.set("write_fonds", [])
    for table in ("read_fonds", "write_fonds"):
        seen = set()
        for row in doc.get(table) or []:
            if row.fonds in seen:
                frappe.throw(_("Phông {0} xuất hiện hai lần").format(row.fonds))
            seen.add(row.fonds)
    if doc.read_scope == READ_CHOSEN and doc.write_scope == WRITE_CHOSEN:
        readable = {r.fonds for r in doc.get("read_fonds") or []}
        outside = [r.fonds for r in doc.get("write_fonds") or [] if r.fonds not in readable]
        if outside:
            frappe.throw(_("Phông được sửa phải nằm trong các phông được xem: {0}").format(", ".join(outside)))


def _forget():
    from document_manager.document_manager.policy import clear_cache

    clear_cache()
