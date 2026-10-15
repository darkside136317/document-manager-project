# -*- coding: utf-8 -*-
"""Which fonds a reader may use, and the grants that open them.

A fonds is "Công khai" (every approved reader), "Theo cấp phép" (only the readers or reader groups it is granted to) or
"Nội bộ" (staff only, never a reader, whatever is granted). Grants are rows of `Reader Group Scope`, on a reader group
(every member) or on a reader (that person), each with an optional validity (from / until). Giving or taking a grant
needs the capability `readers.grant_fonds`.
"""

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

PUBLIC, LICENSED, INTERNAL = "Công khai", "Theo cấp phép", "Nội bộ"
GRANT = "Reader Group Scope"
CAPABILITY = "readers.grant_fonds"


def _memo() -> dict:
    from document_manager.document_manager.policy import _memo as policy_memo

    return policy_memo()


def fonds_by_mode() -> dict:
    """{mode: set(fonds)} for the whole archive (kept for the current request)."""
    memo = _memo()
    if "fonds_modes" not in memo:
        modes = {PUBLIC: set(), LICENSED: set(), INTERNAL: set()}
        has_mode = frappe.db.has_column("Fonds", "access_mode")
        for name, mode in frappe.get_all("Fonds", fields=["name", "access_mode" if has_mode else "name as access_mode"], as_list=True,
                                         limit_page_length=0):
            modes.get(mode if mode in modes else LICENSED, modes[LICENSED]).add(name)
        memo["fonds_modes"] = modes
    return memo["fonds_modes"]


def _valid_rows(parenttype: str, parent: str, today) -> list:
    rows = frappe.get_all(GRANT, filters={"parenttype": parenttype, "parent": parent},
                          fields=["fonds", "valid_from", "valid_until"], limit_page_length=0)
    return [r for r in rows if (not r.valid_from or getdate(r.valid_from) <= today)
            and (not r.valid_until or getdate(r.valid_until) >= today)]


def reader_fonds(group: str | None, profile: str | None) -> dict:
    """{fonds: last day of access or None (no end)} of a reader: public fonds, grants of their group, their own grants
    (valid today), never an internal fonds."""
    today = getdate(nowdate())
    modes = fonds_by_mode()
    until = {name: None for name in modes[PUBLIC]}
    sources = []
    if group:
        sources += _valid_rows("Reader Group", group, today)
    if profile:
        sources += _valid_rows("Reader", profile, today)
    for row in sources:
        if row.fonds in modes[INTERNAL]:
            continue
        end = getdate(row.valid_until) if row.valid_until else None
        if row.fonds not in until:
            until[row.fonds] = end
        elif until[row.fonds] is not None and (end is None or end > until[row.fonds]):
            until[row.fonds] = end  # the longest grant wins
    return until


def validate_grants(doc, table: str) -> None:
    """Rows of a grant table: one row per fonds, a sensible validity, no internal fonds; stamped with who granted them.
    Changing them needs the capability to grant fonds."""
    from document_manager.document_manager.policy import has_capability

    rows = doc.get(table) or []
    before = doc.get_doc_before_save() if not doc.is_new() else None
    old = {(r.fonds, str(r.valid_from or ""), str(r.valid_until or "")) for r in (before.get(table) if before else []) or []}
    new = {(r.fonds, str(r.valid_from or ""), str(r.valid_until or "")) for r in rows}
    if old != new and not (frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch) and not has_capability(CAPABILITY):
        frappe.throw(_("Bạn không có quyền cấp phép khai thác phông"), frappe.PermissionError)
    internal = fonds_by_mode()[INTERNAL]
    seen = set()
    for row in rows:
        if row.fonds in seen:
            frappe.throw(_("Dòng {0}: phông {1} bị trùng").format(row.idx, row.fonds))
        seen.add(row.fonds)
        if row.fonds in internal:
            frappe.throw(_("Dòng {0}: phông {1} là phông nội bộ, không cấp cho độc giả").format(row.idx, row.fonds))
        if row.valid_from and row.valid_until and getdate(row.valid_from) > getdate(row.valid_until):
            frappe.throw(_("Dòng {0}: ngày bắt đầu sau ngày kết thúc").format(row.idx))
        key = (row.fonds, str(row.valid_from or ""), str(row.valid_until or ""))
        if key not in old or not row.granted_by:
            row.granted_by = row.granted_by if key in old else frappe.session.user
            row.granted_on = row.granted_on if key in old else nowdate()
            if key not in old:
                row.reminded_on = None


def remind_expiring(days: int = 7) -> int:
    """Daily job: tell each reader once that a personal grant ends within `days`. Returns how many were told."""
    from document_manager.document_manager.services.notify import notify_user

    today = getdate(nowdate())
    rows = frappe.get_all(GRANT, filters={"parenttype": "Reader", "valid_until": ["between", [today, add_days(today, days)]],
                                         "reminded_on": ["is", "not set"]},
                          fields=["name", "parent", "fonds", "fonds_name", "valid_until"], limit_page_length=0)
    told = 0
    for row in rows:
        user = frappe.db.get_value("Reader", row.parent, "user")
        if user and notify_user(user, _("Quyền khai thác phông {0} hết hạn ngày {1}").format(
                row.fonds_name or row.fonds, getdate(row.valid_until).strftime("%d/%m/%Y")), "/portal/tai-khoan", "Reader", row.parent):
            told += 1
        frappe.db.set_value(GRANT, row.name, "reminded_on", today, update_modified=False)
    return told


def who_may_use(fonds: str) -> dict:
    """For the fonds screen: its mode, the groups and the readers it is granted to (with their validity)."""
    mode = frappe.db.get_value("Fonds", fonds, "access_mode") or LICENSED
    rows = frappe.get_all(GRANT, filters={"fonds": fonds, "parenttype": ["in", ["Reader Group", "Reader"]]},
                          fields=["parenttype", "parent", "valid_from", "valid_until", "granted_by", "granted_on"],
                          order_by="parenttype asc, parent asc", limit_page_length=500)
    names = {}
    for doctype, field in (("Reader Group", "group_name"), ("Reader", "full_name")):
        parents = [r.parent for r in rows if r.parenttype == doctype]
        if parents:
            names.update({(doctype, n): label for n, label in frappe.get_all(doctype, filters={"name": ["in", parents]},
                                                                             fields=["name", field], as_list=True)})
    today = getdate(nowdate())
    out = [{"kind": "group" if r.parenttype == "Reader Group" else "reader", "name": r.parent,
            "label": names.get((r.parenttype, r.parent)) or r.parent, "valid_from": r.valid_from, "valid_until": r.valid_until,
            "active": (not r.valid_from or getdate(r.valid_from) <= today) and (not r.valid_until or getdate(r.valid_until) >= today),
            "granted_by": r.granted_by, "granted_on": r.granted_on} for r in rows]
    return {"fonds": fonds, "mode": mode, "grants": out}
