# -*- coding: utf-8 -*-
"""Records of the archive that are closed, and moves between fonds.

A fonds or a file marked "Đã đóng", and a file whose disposal is "Đã tiêu hủy", are sealed: changing them, or adding,
changing or deleting what they hold, needs the capability `archive.edit_closed` (administrators have it). Closing is a
normal edit; reopening is a change of a sealed record. "Đã hoàn thành" is not sealed: it is the published state readers
see and cataloguers keep adding to.

Moving a record to another fonds needs the right to change both fonds: Frappe checks the new one (`has_permission`),
`assert_move_allowed` the old one.
"""

import frappe
from frappe import _

CLOSED = "Đã đóng"
DISPOSED = "Đã tiêu hủy"
CAPABILITY = "archive.edit_closed"


def _fonds_closed(fonds: str | None) -> bool:
    return bool(fonds) and frappe.db.get_value("Fonds", fonds, "status") == CLOSED


def _file_reason(status, disposal, fonds) -> str | None:
    if status == CLOSED:
        return _("Hồ sơ đã đóng")
    if disposal == DISPOSED:
        return _("Hồ sơ đã tiêu hủy")
    if _fonds_closed(fonds):
        return _("Phông đã đóng")
    return None


def lock_reason(doc) -> str | None:
    """Why `doc` (as given: pass the stored version to judge an edit) is sealed, or None."""
    doctype = doc.doctype
    if doctype == "Fonds":
        return _("Phông đã đóng") if doc.get("status") == CLOSED else None
    if doctype in ("Record Group", "Catalog"):
        return _("Phông đã đóng") if _fonds_closed(doc.get("fonds")) else None
    if doctype == "Archival File":
        return _file_reason(doc.get("status"), doc.get("disposal_status"), doc.get("fonds"))
    if doctype == "Archive Document":
        parent = frappe.db.get_value("Archival File", doc.get("archival_file"), ["status", "disposal_status", "fonds"],
                                     as_dict=True) if doc.get("archival_file") else None
        if parent:
            return _file_reason(parent.status, parent.disposal_status, parent.fonds)
        return _("Phông đã đóng") if _fonds_closed(doc.get("fonds")) else None
    return None


def assert_unlocked(doc, action: str = "") -> None:
    """Refuse a change of a sealed record (judged on its stored version) to whoever lacks `archive.edit_closed`."""
    from document_manager.document_manager.policy import has_capability

    if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch:
        return
    stored = doc.get_doc_before_save() if not doc.is_new() and action != "delete" else None
    reason = lock_reason(stored or doc)
    if reason and not has_capability(CAPABILITY):
        frappe.throw(_("{0}: chỉ người được quyền sửa dữ liệu đã đóng mới thay đổi được").format(reason),
                     frappe.PermissionError)


def assert_move_allowed(doc) -> None:
    """A record leaving a fonds: the user must be allowed to change the fonds it leaves too."""
    from document_manager.document_manager.policy import assert_fonds_writable

    if doc.is_new() or frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch:
        return
    before = doc.get_doc_before_save()
    if before and before.get("fonds") and before.get("fonds") != doc.get("fonds"):
        assert_fonds_writable(before.get("fonds"))
