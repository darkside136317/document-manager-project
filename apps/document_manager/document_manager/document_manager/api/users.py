# -*- coding: utf-8 -*-
"""Staff accounts of the app (module 8): list and search users, create, edit, lock, hand out a set-password link, delete,
and the matrix of what each role may do.

Who may: Document Admin and System Manager. The rules that keep an administrator from locking everyone out or
raising themselves above their station are enforced here, not in the screen:

* only the permission groups of the app can be given (`policy.assignable_roles`): never System Manager, never Administrator;
* an account that holds System Manager is shown but only a System Manager may change it; Administrator and Guest never;
* nobody disables themselves or takes their own Document Admin role away;
* at least one enabled user other than Administrator keeps Document Admin or System Manager;
* reader accounts (Website Users) are managed on the reader screens, not here.
"""

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, validate_email_address

from document_manager.document_manager.constants import DOCTYPE_LABELS, ROLE_MATRIX, STAFF_ASSIGNABLE_ROLES  # noqa: F401  (kept for callers)
from document_manager.document_manager.permissions import assert_capability
from document_manager.document_manager.policy import assignable_roles, staff_role_profiles
from document_manager.document_manager.services import permission_matrix
from document_manager.document_manager.services.audit import log_activity
from document_manager.document_manager.services.registration import SET_PASSWORD_PATH

ADMIN_ROLES = ("Document Admin", "System Manager")
RESERVED = ("Administrator", "Guest")
MAX_PAGE = 100
GROUP_DOCTYPE = "Staff Group"


def _require_admin() -> None:
    assert_capability("users.manage")


def _is_system_manager(user: str | None = None) -> bool:
    user = user or frappe.session.user
    return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def _protected(user: str) -> bool:
    """An account only a System Manager may change."""
    return user in RESERVED or "System Manager" in frappe.get_roles(user)


def _assert_editable(user: str) -> None:
    info = frappe.db.get_value("User", user, ["user_type", "name"], as_dict=True)
    if not info:
        frappe.throw(_("Không tìm thấy người dùng {0}").format(user), frappe.DoesNotExistError)
    if user in RESERVED:
        frappe.throw(_("Không thay đổi được tài khoản hệ thống {0}").format(user), frappe.PermissionError)
    if info.user_type != "System User":
        frappe.throw(_("{0} là tài khoản độc giả: quản lý ở màn hình Độc giả").format(user), frappe.PermissionError)
    if _protected(user) and not _is_system_manager():
        frappe.throw(_("Tài khoản {0} có quyền quản trị hệ thống: chỉ System Manager mới thay đổi được").format(user), frappe.PermissionError)


def _roles_of(users: list[str]) -> dict:
    out = {u: [] for u in users}
    if users:
        for row in frappe.get_all("Has Role", filters={"parent": ["in", users], "parenttype": "User"}, fields=["parent", "role"]):
            out[row.parent].append(row.role)
    return out


def _groups_of(users: list[str]) -> dict:
    out = {u: [] for u in users}
    if users:
        for row in frappe.get_all("Staff Group Member", filters={"parenttype": GROUP_DOCTYPE, "user": ["in", users]},
                                  fields=["parent", "user"]):
            out[row.user].append(row.parent)
    return out


def _shown(row, roles: dict, groups: dict) -> dict:
    mine = roles.get(row.name, [])
    return {"name": row.name, "full_name": row.full_name or row.name, "first_name": row.first_name or "", "last_name": row.last_name or "",
            "phone": row.phone or "", "enabled": cint(row.enabled), "last_login": row.last_login, "creation": row.creation,
            "roles": [r for r in assignable_roles() if r in mine], "protected": "System Manager" in mine or row.name in RESERVED,
            "groups": sorted(groups.get(row.name, [])), "is_me": row.name == frappe.session.user}


USER_FIELDS = ["name", "full_name", "first_name", "last_name", "phone", "enabled", "last_login", "creation"]
ACCESS = "Staff Access"
DEFAULT_ACCESS = {"read_scope": "Tất cả phông", "write_scope": "Như phạm vi xem", "read_fonds": [], "write_fonds": [],
                  "max_confidentiality_priority": 0}


def _fonds_rows(names) -> list[dict]:
    labels = dict(frappe.get_all("Fonds", filters={"name": ["in", list(names) or [""]]}, fields=["name", "fonds_name"], as_list=True))
    return [{"fonds": n, "fonds_name": labels.get(n) or n} for n in names]


def _access_of(user: str) -> dict:
    """The person's own scope (as the form edits it) and what they may really do (with their groups and roles)."""
    from document_manager.document_manager.constants import CAPABILITIES
    from document_manager.document_manager.policy import UNLIMITED_PRIORITY, get_access

    own = dict(DEFAULT_ACCESS)
    if frappe.db.exists(ACCESS, user):
        doc = frappe.get_doc(ACCESS, user)
        own = {"read_scope": doc.read_scope, "write_scope": doc.write_scope,
               "read_fonds": _fonds_rows([r.fonds for r in doc.read_fonds]), "write_fonds": _fonds_rows([r.fonds for r in doc.write_fonds]),
               "max_confidentiality_priority": cint(doc.max_confidentiality_priority)}
    access = get_access(user)
    labels = {code: label for code, label, _module in CAPABILITIES}
    effective = {
        "kind": access.kind,
        "read_fonds": None if access.read_fonds is None else _fonds_rows(access.read_fonds),
        "write_fonds": None if access.write_fonds is None else _fonds_rows(access.write_fonds),
        "max_priority": None if access.max_priority >= UNLIMITED_PRIORITY else access.max_priority,
        "capabilities": sorted(labels[c] for c in access.capabilities if c in labels),
    }
    return {**own, "effective": effective}


def _save_access(user: str, values: dict) -> bool:
    """Write the person's scope; the default scope (every fonds, every level) is no record at all. True when it changed."""
    wanted = {**DEFAULT_ACCESS, **{k: values[k] for k in DEFAULT_ACCESS if k in values}}
    wanted["read_fonds"] = [r["fonds"] if isinstance(r, dict) else r for r in wanted["read_fonds"] or []]
    wanted["write_fonds"] = [r["fonds"] if isinstance(r, dict) else r for r in wanted["write_fonds"] or []]
    wanted["max_confidentiality_priority"] = max(0, cint(wanted["max_confidentiality_priority"]))
    is_default = (wanted["read_scope"] == DEFAULT_ACCESS["read_scope"] and wanted["write_scope"] == DEFAULT_ACCESS["write_scope"]
                  and not wanted["max_confidentiality_priority"])
    exists = frappe.db.exists(ACCESS, user)
    if is_default:
        if exists:
            frappe.delete_doc(ACCESS, user, ignore_permissions=True, force=True)
            return True
        return False
    doc = frappe.get_doc(ACCESS, user) if exists else frappe.new_doc(ACCESS)
    before = (doc.read_scope, doc.write_scope, sorted(r.fonds for r in doc.get("read_fonds") or []),
              sorted(r.fonds for r in doc.get("write_fonds") or []), cint(doc.max_confidentiality_priority)) if exists else None
    doc.update({"user": user, "read_scope": wanted["read_scope"], "write_scope": wanted["write_scope"],
                "max_confidentiality_priority": wanted["max_confidentiality_priority"]})
    doc.set("read_fonds", [{"fonds": f} for f in wanted["read_fonds"]])
    doc.set("write_fonds", [{"fonds": f} for f in wanted["write_fonds"]])
    doc.flags.ignore_permissions = True
    doc.save()
    after = (doc.read_scope, doc.write_scope, sorted(r.fonds for r in doc.read_fonds), sorted(r.fonds for r in doc.write_fonds),
             cint(doc.max_confidentiality_priority))
    return before != after



@frappe.whitelist()
def roles_info():
    """The roles that can be given, with their description (for the forms and the matrix)."""
    _require_admin()
    return [{key: p[key] for key in ("role", "label", "group", "description", "is_builtin", "is_admin")} for p in staff_role_profiles()]


@frappe.whitelist()
def list_users(search=None, role=None, group=None, enabled=None, page=1, page_size=20):
    _require_admin()
    page, size = max(1, cint(page) or 1), min(MAX_PAGE, max(1, cint(page_size) or 20))
    filters = [["user_type", "=", "System User"], ["name", "not in", list(RESERVED)]]
    if enabled not in (None, ""):
        filters.append(["enabled", "=", cint(enabled)])
    names = None
    if role:
        if role not in assignable_roles():
            frappe.throw(_("Vai trò {0} không hợp lệ").format(role))
        names = set(frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"))
    if group:
        members = set(frappe.get_all("Staff Group Member", filters={"parent": group}, pluck="user"))
        names = members if names is None else names & members
    if names is not None:
        filters.append(["name", "in", list(names) or [""]])
    or_filters = None
    text = (search or "").strip()
    if text:
        like = f"%{text}%"
        or_filters = [["name", "like", like], ["full_name", "like", like], ["phone", "like", like]]
    total = len(frappe.get_all("User", filters=filters, or_filters=or_filters, pluck="name", page_length=0))
    rows = frappe.get_all("User", filters=filters, or_filters=or_filters, fields=USER_FIELDS, order_by="full_name asc, name asc",
                          start=(page - 1) * size, page_length=size)
    users = [r.name for r in rows]
    roles, groups = _roles_of(users), _groups_of(users)
    scoped = set(frappe.get_all(ACCESS, filters={"name": ["in", users or [""]]}, pluck="name")) if users else set()
    return {"data": [{**_shown(r, roles, groups), "scoped": r.name in scoped} for r in rows], "total": total, "page": page,
            "page_size": size}


@frappe.whitelist()
def get_user(name):
    _require_admin()
    row = frappe.db.get_value("User", name, USER_FIELDS, as_dict=True)
    if not row or name in RESERVED:
        frappe.throw(_("Không tìm thấy người dùng {0}").format(name), frappe.DoesNotExistError)
    row["name"] = name
    return {**_shown(row, _roles_of([name]), _groups_of([name])), "access": _access_of(name)}


def _admins_left(excluding: str | None, becoming_enabled_admin: bool = False) -> int:
    """Enabled users (not Administrator) holding Document Admin or System Manager, not counting `excluding`."""
    holders = set(frappe.get_all("Has Role", filters={"role": ["in", list(ADMIN_ROLES)], "parenttype": "User"}, pluck="parent"))
    holders -= {"Administrator", "Guest", excluding or ""}
    count = len(frappe.get_all("User", filters={"name": ["in", list(holders) or [""]], "enabled": 1}, pluck="name")) if holders else 0
    return count + (1 if becoming_enabled_admin else 0)


def _clean_roles(roles) -> list[str]:
    roles = frappe.parse_json(roles) if isinstance(roles, str) else (roles or [])
    known = assignable_roles()
    bad = [r for r in roles if r not in known]
    if bad:
        frappe.throw(_("Vai trò {0} không được cấp ở đây").format(", ".join(bad)))
    return [r for r in known if r in roles]


def _sync_roles(user, wanted: list[str]) -> None:
    """Make the staff roles of `user` exactly `wanted`; roles outside the app's staff roles are left alone."""
    current = {h.role for h in user.roles}
    known = assignable_roles()
    for role in known:
        if role in wanted and role not in current:
            user.append("roles", {"role": role})
    user.roles = [h for h in user.roles if h.role not in known or h.role in wanted]


def _sync_groups(user_name: str, wanted: list[str] | None) -> None:
    if wanted is None:
        return
    wanted = frappe.parse_json(wanted) if isinstance(wanted, str) else wanted
    for group in frappe.get_all(GROUP_DOCTYPE, pluck="name"):
        doc = frappe.get_doc(GROUP_DOCTYPE, group)
        member = any(m.user == user_name for m in doc.members)
        if group in wanted and not member:
            doc.append("members", {"user": user_name})
            doc.save(ignore_permissions=True)
        elif group not in wanted and member:
            doc.members = [m for m in doc.members if m.user != user_name]
            doc.save(ignore_permissions=True)
    unknown = [g for g in wanted if not frappe.db.exists(GROUP_DOCTYPE, g)]
    if unknown:
        frappe.throw(_("Không có nhóm {0}").format(", ".join(unknown)))


@frappe.whitelist(methods=["POST"])
def save_user(values, name=None):
    """Create (no `name`) or edit a staff account: names, phone, enabled, roles and groups."""
    _require_admin()
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
    roles = _clean_roles(values["roles"]) if "roles" in values else None
    link = None
    if name:
        _assert_editable(name)
        user = frappe.get_doc("User", name)
        me = name == frappe.session.user
        if me and "enabled" in values and not cint(values["enabled"]):
            frappe.throw(_("Không thể tự khóa tài khoản của chính mình"))
        if me and roles is not None and "Document Admin" in {h.role for h in user.roles} and "Document Admin" not in roles:
            frappe.throw(_("Không thể tự bỏ quyền Quản trị viên của chính mình"))
        existing = {h.role for h in user.roles}
        new_enabled = cint(values["enabled"]) if "enabled" in values else cint(user.enabled)
        kept = (existing - set(assignable_roles())) | (set(roles) if roles is not None else existing)
        if cint(user.enabled) and existing & set(ADMIN_ROLES) and not (new_enabled and kept & set(ADMIN_ROLES)) \
                and _admins_left(name) < 1:
            frappe.throw(_("Phải còn ít nhất một người dùng đang hoạt động có quyền Quản trị viên"))
    else:
        email = (values.get("email") or "").strip().lower()
        if not validate_email_address(email):
            frappe.throw(_("Địa chỉ email không hợp lệ"))
        if frappe.db.exists("User", email):
            frappe.throw(_("Email {0} đã có tài khoản").format(email))
        if not (values.get("first_name") or "").strip():
            frappe.throw(_("Vui lòng nhập tên"))
        user = frappe.new_doc("User")
        user.update({"email": email, "send_welcome_email": 0, "user_type": "System User"})
        user.flags.no_welcome_mail = True
    for field in ("first_name", "last_name", "phone"):
        if field in values:
            user.set(field, (values[field] or "").strip())
    if "enabled" in values:
        user.enabled = 1 if cint(values["enabled"]) else 0
    if roles is not None:
        _sync_roles(user, roles)
    user.flags.ignore_permissions = True
    user.save() if name else user.insert()
    _sync_groups(user.name, values.get("groups"))
    scope_changed = False
    if isinstance(values.get("access"), dict):
        if user.name == frappe.session.user:
            frappe.throw(_("Không tự thay đổi phạm vi truy cập của chính mình"))
        scope_changed = _save_access(user.name, values["access"])
    if not name:
        link = _staff_link(user)
    log_activity("Quản lý người dùng", "User", user.name, f"{'Sửa' if name else 'Tạo'} tài khoản cán bộ {user.name}: "
                 f"vai trò {', '.join(roles) if roles is not None else 'giữ nguyên'}" + ("; đổi phạm vi phông" if scope_changed else ""))
    out = get_user(user.name)
    if link:
        out["set_password_path"] = link
    return out


def _staff_link(user) -> str:
    link = user._reset_password(send_email=False)
    return f"{SET_PASSWORD_PATH}?key={link.split('key=', 1)[1]}"


@frappe.whitelist(methods=["POST"])
def set_enabled(name, enabled):
    """Lock or unlock a staff account; a locked account cannot sign in and keeps its records."""
    return save_user({"enabled": cint(enabled)}, name)


@frappe.whitelist(methods=["POST"])
def issue_password_link(name):
    """A one-time link to hand to the user so they can set their own password (the old password stops working then)."""
    _require_admin()
    _assert_editable(name)
    user = frappe.get_doc("User", name)
    if not cint(user.enabled):
        frappe.throw(_("Tài khoản đang bị khóa"))
    link = _staff_link(user)
    log_activity("Quản lý người dùng", "User", name, f"Cấp liên kết đặt mật khẩu cho {name}")
    return {"user": name, "set_password_path": link}


@frappe.whitelist(methods=["POST"])
def delete_user(name):
    """Delete a staff account that has never been used; one with records is locked instead (the message says so)."""
    _require_admin()
    _assert_editable(name)
    if name == frappe.session.user:
        frappe.throw(_("Không thể xóa tài khoản của chính mình"))
    if "Document Admin" in frappe.get_roles(name) and _admins_left(name) < 1:
        frappe.throw(_("Phải còn ít nhất một người dùng đang hoạt động có quyền Quản trị viên"))
    for group in frappe.get_all("Staff Group Member", filters={"user": name}, pluck="parent"):  # membership is not "records"
        doc = frappe.get_doc(GROUP_DOCTYPE, group)
        doc.members = [m for m in doc.members if m.user != name]
        doc.save(ignore_permissions=True)
    try:  # when this refuses, the request is rolled back as a whole (no savepoint: it may not survive), so the groups keep the member
        frappe.delete_doc("User", name, ignore_permissions=True)
    except frappe.LinkExistsError:
        frappe.throw(_("Người dùng {0} đã có dữ liệu liên quan nên không xóa được. Hãy khóa tài khoản.").format(name))
    log_activity("Quản lý người dùng", "User", name, f"Xóa tài khoản cán bộ {name}")
    return {"name": name}


@frappe.whitelist()
def role_matrix():
    """What each staff role may do on the app's DocTypes: [{section, doctypes: [{doctype, label, perms: {role: {...}}}]}]."""
    _require_admin()
    sections = []
    for section, doctypes in ROLE_MATRIX:
        rows = []
        for doctype in doctypes:
            if not frappe.db.exists("DocType", doctype):
                continue
            perms = {role: {"read": 0, "write": 0, "create": 0, "delete": 0} for role in assignable_roles()}
            for rule in permission_matrix.rules(doctype):  # the customised rules when there are any
                if cint(rule.permlevel) == 0 and rule.role in perms:
                    for key in ("read", "write", "create", "delete"):
                        perms[rule.role][key] = perms[rule.role][key] or cint(rule.get(key))
            rows.append({"doctype": doctype, "label": DOCTYPE_LABELS.get(doctype) or _(doctype), "perms": perms})
        sections.append({"section": section, "doctypes": rows})
    return {"roles": roles_info(), "sections": sections, "checked_on": str(now_datetime())}
