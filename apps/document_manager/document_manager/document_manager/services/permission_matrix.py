# -*- coding: utf-8 -*-
"""What a permission group may do with each kind of data, read from and written to Frappe's own permission rules.

A cell of the matrix is one (DocType, role) pair:

    read create write delete submit cancel print export   the usual permissions (level 0)
    own_only    the rules apply only to records the user created (Frappe's `if_owner`)
    sensitive   may change the protected fields (permission level 1); seeing them comes with `read`

Writing a cell replaces the role's rows of that DocType in `Custom DocPerm` (Frappe copies the standard rules there
first, `setup_custom_perms`), so `get_list`, `has_permission`, reports and exports enforce it with no code of ours.
Only the DocTypes of `constants.ROLE_MATRIX` are reachable, and never for the administrators' role.
"""

import frappe
from frappe import _
from frappe.utils import cint

from document_manager.document_manager.constants import ADMIN_ROLE, DOCTYPE_LABELS, ROLE_MATRIX

PTYPES = ("read", "create", "write", "delete", "submit", "cancel", "print", "export")
COLUMN_LABELS = {"read": "Xem", "create": "Thêm", "write": "Sửa", "delete": "Xóa", "submit": "Gửi, duyệt", "cancel": "Hủy",
                 "print": "In", "export": "Xuất", "own_only": "Chỉ của mình", "sensitive": "Trường nhạy cảm"}
PERM_FIELDS = ["name", "role", "permlevel", "if_owner", *PTYPES, "report", "email", "share", "import", "amend", "select"]
MATRIX_DOCTYPES = tuple(dt for _section, doctypes in ROLE_MATRIX for dt in doctypes)


def _assert_editable(doctype: str, role: str) -> None:
    if doctype not in MATRIX_DOCTYPES:
        frappe.throw(_("Loại dữ liệu {0} không thuộc bảng phân quyền").format(doctype), frappe.PermissionError)
    if role == ADMIN_ROLE:
        frappe.throw(_("Quyền của quản trị viên không thay đổi được"), frappe.PermissionError)


def rules(doctype: str) -> list:
    """The rules in force for `doctype`: the customised ones when there are any (Frappe then ignores the standard ones)."""
    custom = frappe.get_all("Custom DocPerm", filters={"parent": doctype}, fields=PERM_FIELDS, limit_page_length=0)
    if custom:
        return custom
    return frappe.get_all("DocPerm", filters={"parent": doctype, "parenttype": "DocType"}, fields=PERM_FIELDS,
                          limit_page_length=0)


def columns_of(doctype: str) -> list:
    """The columns that mean something for `doctype` (submit/cancel only when it is submittable, ...)."""
    meta = frappe.get_meta(doctype)
    cols = ["read", "create", "write", "delete"]
    if meta.is_submittable:
        cols += ["submit", "cancel"]
    cols += ["print", "export", "own_only"]
    if any(cint(df.permlevel) >= 1 for df in meta.fields):
        cols.append("sensitive")
    return cols


def cell_from_rules(rows: list, role: str) -> dict:
    mine = [r for r in rows if r.role == role]
    base = [r for r in mine if cint(r.permlevel) == 0]
    cell = {ptype: any(cint(r.get(ptype)) for r in base) for ptype in PTYPES}
    cell["own_only"] = bool(base) and all(cint(r.if_owner) for r in base)
    cell["sensitive"] = any(cint(r.write) for r in mine if cint(r.permlevel) >= 1)
    return cell


def cell(doctype: str, role: str) -> dict:
    return cell_from_rules(rules(doctype), role)


def normalise(values: dict, columns: list) -> dict:
    """Keep only the columns of the DocType; any permission implies reading, unless reading is explicitly turned off:
    then the row is empty (unticking "Xem" takes every right away)."""
    out = {key: bool(values.get(key)) and key in columns for key in (*PTYPES, "own_only", "sensitive")}
    if "read" in values and not values["read"]:
        return {key: False for key in out}
    if any(out[p] for p in PTYPES if p != "read") or out["sensitive"]:
        out["read"] = True
    if not out["read"]:
        out = {key: False for key in out}
    if out["cancel"] and not out["submit"]:
        out["submit"] = True
    return out


def set_cell(doctype: str, role: str, values: dict) -> bool:
    """Write the role's rules for `doctype`. Returns True when something changed."""
    _assert_editable(doctype, role)
    wanted = normalise(values, columns_of(doctype))
    if wanted == cell(doctype, role):
        return False
    from frappe.permissions import setup_custom_perms

    setup_custom_perms(doctype)
    _sanitise(doctype)
    for name in frappe.get_all("Custom DocPerm", filters={"parent": doctype, "role": role}, pluck="name"):
        frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)
    if wanted["read"]:
        row = {ptype: int(wanted[ptype]) for ptype in PTYPES}
        _insert(doctype, role, 0, if_owner=int(wanted["own_only"]), report=1, **row)
        if "sensitive" in columns_of(doctype):  # whoever reads sees the protected fields; changing them is `sensitive`
            _insert(doctype, role, 1, read=1, write=int(wanted["sensitive"]))
    # (Frappe's validate_permissions_for_doctype checks the standard rules of the DocType, not these: `normalise`
    # and `_sanitise` keep the custom rules valid)
    _clear(doctype)
    return True


def _sanitise(doctype: str) -> None:
    """Some standard rules carry flags their DocType cannot use (import without "allow import", submit on a DocType that
    is not submittable). Frappe ignores them when it reads the definition but refuses them in custom rules."""
    meta = frappe.get_meta(doctype)
    if not meta.allow_import:
        frappe.db.sql("update `tabCustom DocPerm` set `import` = 0 where parent = %s", doctype)
    if not meta.is_submittable:
        frappe.db.sql("update `tabCustom DocPerm` set submit = 0, cancel = 0, amend = 0 where parent = %s", doctype)


def _clear(doctype: str) -> None:
    """Frappe keeps permissions in the DocType's cached meta, per user and, within a request, in
    `frappe.local.role_permissions`. Inside `batch()` the clearing waits for the end (rebuilding the meta after every
    single rule made copying a group take seconds)."""
    pending = getattr(frappe.local, "dm_matrix_pending", None)
    if pending is not None:
        pending.add(doctype)
        return
    clear_now([doctype])


def clear_now(doctypes) -> None:
    from frappe.cache_manager import clear_user_cache

    for doctype in doctypes:
        frappe.clear_cache(doctype=doctype)
    clear_user_cache()
    frappe.local.role_permissions = {}


class batch:
    """`with permission_matrix.batch(): ...` writes many rules and clears Frappe's caches once, at the end."""

    def __enter__(self):
        self.outer = getattr(frappe.local, "dm_matrix_pending", None)
        if self.outer is None:
            frappe.local.dm_matrix_pending = set()
        return self

    def __exit__(self, *exc):
        if self.outer is None:
            pending = frappe.local.dm_matrix_pending
            frappe.local.dm_matrix_pending = None
            if pending:
                clear_now(pending)
        return False


def _insert(doctype: str, role: str, permlevel: int, if_owner: int = 0, **flags) -> None:
    frappe.get_doc({"doctype": "Custom DocPerm", "parent": doctype, "parenttype": "DocType", "parentfield": "permissions",
                    "role": role, "permlevel": permlevel, "if_owner": if_owner, **flags}).insert(ignore_permissions=True)


def matrix(role: str) -> list:
    """[{section, rows: [{doctype, label, columns, cell}]}] for the permission screen."""
    sections = []
    for section, doctypes in ROLE_MATRIX:
        rows = []
        for doctype in doctypes:
            if not frappe.db.exists("DocType", doctype):
                continue
            rows.append({"doctype": doctype, "label": DOCTYPE_LABELS.get(doctype) or _(doctype), "columns": columns_of(doctype),
                         "cell": cell(doctype, role)})
        sections.append({"section": section, "rows": rows})
    return sections


def remove_role(role: str) -> None:
    """Take a role out of every customised rule set (before the role itself is deleted)."""
    _assert_editable(MATRIX_DOCTYPES[0], role)
    with batch():
        for doctype in frappe.get_all("Custom DocPerm", filters={"role": role}, pluck="parent", distinct=True):
            for name in frappe.get_all("Custom DocPerm", filters={"parent": doctype, "role": role}, pluck="name"):
                frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)
            _clear(doctype)


def reset_role(role: str) -> int:
    """Put back the standard rules (those of the DocType definitions) of a role; returns how many DocTypes changed.

    A DocType whose customised rules become identical to the standard ones goes back to the standard set entirely,
    so it follows future versions of the application again."""
    with batch():
        changed = _reset_role(role)
    return changed


def _reset_role(role: str) -> int:
    from frappe.permissions import reset_perms

    changed = 0
    for doctype in MATRIX_DOCTYPES:
        if not frappe.db.exists("Custom DocPerm", {"parent": doctype}):
            continue  # already the standard rules
        _assert_editable(doctype, role)
        for name in frappe.get_all("Custom DocPerm", filters={"parent": doctype, "role": role}, pluck="name"):
            frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)
        for row in frappe.get_all("DocPerm", filters={"parent": doctype, "parenttype": "DocType", "role": role}, fields=PERM_FIELDS):
            flags = {k: row.get(k) for k in PERM_FIELDS if k not in ("name", "role", "permlevel", "if_owner")}
            _insert(doctype, role, cint(row.permlevel), if_owner=cint(row.if_owner), **flags)
        _sanitise(doctype)
        if _same_as_standard(doctype):
            reset_perms(doctype)
        _clear(doctype)
        changed += 1
    return changed


def _signature(rows: list) -> set:
    return {(r.role, cint(r.permlevel), cint(r.if_owner), *(cint(r.get(p)) for p in (*PTYPES, "report"))) for r in rows}


def _same_as_standard(doctype: str) -> bool:
    custom = frappe.get_all("Custom DocPerm", filters={"parent": doctype}, fields=PERM_FIELDS, limit_page_length=0)
    standard = frappe.get_all("DocPerm", filters={"parent": doctype, "parenttype": "DocType"}, fields=PERM_FIELDS, limit_page_length=0)
    return _signature(custom) == _signature(standard)


def copy_role(source: str, target: str) -> None:
    """Give `target` the same rules as `source` on every DocType of the matrix (a new group made from another)."""
    with batch():
        for doctype in MATRIX_DOCTYPES:
            if frappe.db.exists("DocType", doctype):
                values = cell(doctype, source)
                if values["read"]:
                    set_cell(doctype, target, values)
