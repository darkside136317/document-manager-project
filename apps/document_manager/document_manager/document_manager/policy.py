# -*- coding: utf-8 -*-
"""Who may see and do what — the single source of truth for reader access.

`get_reader_scope(user)` resolves a user to one `frappe._dict`:

    is_staff      staff roles: unrestricted
    allowed       False for guests, readers without an active profile or in a disabled group
    profile       Reader record name (or None)
    group         Reader Group name (or None)
    max_priority  highest Confidentiality Level priority the user may read
    fonds         list of Fonds names the user may read, or None for "all fonds"
    can_*         feature flags (search / preview / download / request_usage / request_copy / feedback)

SQL conditions, `has_permission` hooks, the search APIs, the Meilisearch filter and the request
rules all consume this object, so a rule changes in exactly one place. Nothing is cached across
calls: a stale scope would be a security bug, and the lookups are indexed primary-key reads.
"""

import frappe
from frappe import _
from frappe.utils import cint

STAFF_ROLES = frozenset({
    "Document Admin", "Cataloger", "Reading Room Officer", "Archive Leader",
    "Preservation Officer", "System Manager", "Administrator",
})

FEATURES = ("can_search", "can_preview", "can_download", "can_request_usage", "can_request_copy", "can_feedback")

FEATURE_LABELS = {
    "can_search": "tìm kiếm",
    "can_preview": "xem trước tài liệu",
    "can_download": "tải tệp gốc",
    "can_request_usage": "lập phiếu yêu cầu sử dụng",
    "can_request_copy": "lập phiếu sao chụp",
    "can_feedback": "gửi góp ý",
}

UNLIMITED_PRIORITY = 10**6
ADMIN_ROLES = frozenset({"Document Admin", "System Manager", "Administrator"})


# --- per-request memo ---------------------------------------------------------------------------------------------
# Only facts that do not depend on the user are kept, and only for the current request (frappe.local is new for every
# request and job). Saving a permission group clears it, so a test or a request that edits groups sees the change.

def _memo() -> dict:
    memo = getattr(frappe.local, "dm_policy_memo", None)
    if memo is None:
        memo = frappe.local.dm_policy_memo = {}
    return memo


def clear_cache() -> None:
    frappe.local.dm_policy_memo = {}


def _profile_capabilities() -> dict:
    """{role: frozenset(capabilities)} of every permission group (the built-in defaults before the groups exist)."""
    memo = _memo()
    if "profiles" not in memo:
        from document_manager.document_manager.constants import BUILTIN_CAPABILITIES

        profiles = {role: frozenset(caps) for role, caps in BUILTIN_CAPABILITIES.items()}
        if frappe.db.table_exists("Staff Role Profile"):
            rows = frappe.get_all("Staff Role Capability", filters={"parenttype": "Staff Role Profile"},
                                  fields=["parent", "capability"], limit_page_length=0)
            granted = {}
            for row in rows:
                granted.setdefault(row.parent, set()).add(row.capability)
            for role in frappe.get_all("Staff Role Profile", pluck="name", limit_page_length=0):
                profiles[role] = frozenset(granted.get(role, ()))
        memo["profiles"] = profiles
    return memo["profiles"]


def staff_role_profiles() -> list[dict]:
    """The permission groups that can be given to a user, the built-in ones first (in their usual order):
    [{role, label, group, description, is_builtin, is_admin}]."""
    memo = _memo()
    if "profile_rows" not in memo:
        from document_manager.document_manager.constants import ROLE_INFO, STAFF_ASSIGNABLE_ROLES

        rows = []
        if frappe.db.table_exists("Staff Role Profile"):
            rows = frappe.get_all("Staff Role Profile", fields=["role", "label", "group_label", "description", "is_builtin", "is_admin"],
                                  limit_page_length=0)
        known = {r.role for r in rows}
        rows += [frappe._dict(role=role, label=info["label"], group_label=info["group"], description=info["description"],
                              is_builtin=1, is_admin=int(role == "Document Admin"))
                 for role, info in ROLE_INFO.items() if role not in known]
        order = {role: i for i, role in enumerate(STAFF_ASSIGNABLE_ROLES)}
        rows.sort(key=lambda r: (order.get(r.role, len(order)), r.label or r.role))
        memo["profile_rows"] = [{"role": r.role, "label": r.label or r.role, "group": r.group_label or "Tác nghiệp",
                                 "description": r.description or "", "is_builtin": bool(r.is_builtin), "is_admin": bool(r.is_admin)}
                                for r in rows]
    return memo["profile_rows"]


def assignable_roles() -> tuple:
    """The roles the staff app may give to a user: every permission group (never System Manager / Administrator)."""
    return tuple(p["role"] for p in staff_role_profiles())


def staff_roles() -> frozenset:
    """Every role that makes its holder a member of the staff: the permission groups and Frappe's administrators."""
    return STAFF_ROLES | frozenset(_profile_capabilities())


def is_staff(user: str | None = None) -> bool:
    """True if `user` (default: session user) has any staff role."""
    return bool(staff_roles().intersection(set(frappe.get_roles(user or frappe.session.user))))


def is_admin(user: str | None = None) -> bool:
    """Administrators of the application: every capability, every fonds."""
    user = user or frappe.session.user
    return user == "Administrator" or bool(ADMIN_ROLES.intersection(frappe.get_roles(user)))


def capabilities_of(user: str | None = None) -> frozenset:
    """The functions `user` may use: every one for an administrator, else the union of their groups' capabilities."""
    from document_manager.document_manager.constants import ADMIN_ONLY_CAPABILITIES, CAPABILITY_CODES

    user = user or frappe.session.user
    if is_admin(user):
        return CAPABILITY_CODES | ADMIN_ONLY_CAPABILITIES
    profiles = _profile_capabilities()
    granted = set()
    for role in frappe.get_roles(user):
        granted |= profiles.get(role, frozenset())
    return frozenset(granted)


def has_capability(*codes: str, user: str | None = None) -> bool:
    """True when `user` may use at least one of `codes`."""
    return bool(capabilities_of(user).intersection(codes))


def assert_capability(*codes: str, user: str | None = None) -> None:
    """Raise PermissionError unless `user` may use one of `codes` (also enforced while tests run)."""
    if not has_capability(*codes, user=user):
        frappe.throw(_("Bạn không có quyền thực hiện thao tác này"), frappe.PermissionError)


def users_with_capability(code: str) -> list[str]:
    """Enabled users whose permission groups grant `code` explicitly (administrators are not listed: they hold
    every capability implicitly and are not told about every slip)."""
    roles = [role for role, caps in _profile_capabilities().items() if code in caps]
    if not roles:
        return []
    holders = frappe.get_all("Has Role", filters={"role": ["in", roles], "parenttype": "User"}, pluck="parent", distinct=True)
    if not holders:
        return []
    return frappe.get_all("User", filters={"name": ["in", holders], "enabled": 1}, pluck="name")


def get_reader_profile(user: str | None = None) -> str | None:
    """Name of the Reader record linked to `user`, if any."""
    return frappe.db.get_value("Reader", {"user": user or frappe.session.user}, "name")


def _scope(**values) -> frappe._dict:
    base = {"user": None, "is_staff": False, "allowed": False, "profile": None, "group": None,
            "max_priority": 0, "fonds": None, **{f: False for f in FEATURES}}
    base.update(values)
    return frappe._dict(base)


def _default_group_name() -> str | None:
    return frappe.db.get_value("Reader Group", {"is_default": 1, "is_active": 1}, "name")


def get_reader_scope(user: str | None = None) -> frappe._dict:
    user = user or frappe.session.user
    if user == "Guest":
        return _scope(user=user)
    if is_staff(user):
        return _scope(user=user, is_staff=True, allowed=True, max_priority=UNLIMITED_PRIORITY,
                      **{f: True for f in FEATURES})

    profile = frappe.db.get_value(
        "Reader", {"user": user},
        ["name", "is_active", "max_confidentiality_priority", "reader_group"], as_dict=True)
    if not profile or not profile.is_active:
        return _scope(user=user, profile=profile.name if profile else None)

    group_name = profile.reader_group or _default_group_name()
    if group_name:
        group = frappe.db.get_value(
            "Reader Group", group_name,
            ["is_active", "max_confidentiality_priority", "fonds_scope", *FEATURES], as_dict=True)
        if not group or not group.is_active:
            return _scope(user=user, profile=profile.name, group=group_name)  # disabled group
        fonds = None
        if group.fonds_scope == "Chỉ các phông được chọn":
            fonds = frappe.get_all("Reader Group Scope", filters={"parent": group_name, "parenttype": "Reader Group"},
                                   pluck="fonds")
        features = {f: bool(cint(group.get(f))) for f in FEATURES}
        group_priority = cint(group.max_confidentiality_priority)
    else:  # no group configured anywhere: the safe built-in default (public level, every feature)
        fonds, features, group_priority = None, {f: True for f in FEATURES}, 1

    return _scope(user=user, allowed=True, profile=profile.name, group=group_name,
                  max_priority=cint(profile.max_confidentiality_priority) or group_priority or 1,
                  fonds=fonds, **features)


def get_access(user: str | None = None) -> frappe._dict:
    """One answer for every kind of user: what they may read and write, how high, and which functions they may use.

        kind          "admin" | "staff" | "reader" | "guest"
        read_fonds    None for every fonds, else the list of fonds the user may read
        write_fonds   None for every fonds, else the list of fonds the user may change ([] for readers and guests)
        max_priority  highest confidentiality priority the user may read
        capabilities  frozenset of capability codes (staff); readers use `reader.can_*`
        reader        the reader scope (`get_reader_scope`) for readers, else None
    """
    user = user or frappe.session.user
    if user == "Guest":
        return frappe._dict(user=user, kind="guest", read_fonds=[], write_fonds=[], max_priority=0,
                            capabilities=frozenset(), reader=None)
    if is_staff(user):
        return frappe._dict(user=user, kind="admin" if is_admin(user) else "staff", read_fonds=None, write_fonds=None,
                            max_priority=UNLIMITED_PRIORITY, capabilities=capabilities_of(user), reader=None)
    scope = get_reader_scope(user)
    return frappe._dict(user=user, kind="reader", read_fonds=scope.fonds if scope.allowed else [], write_fonds=[],
                        max_priority=scope.max_priority, capabilities=frozenset(), reader=scope)


def assert_feature(feature: str, user: str | None = None) -> frappe._dict:
    """Raise PermissionError unless the user may use `feature`; returns the scope."""
    scope = get_reader_scope(user)
    if scope.is_staff:
        return scope
    if scope.user == "Guest":
        frappe.throw(_("Vui lòng đăng nhập"), frappe.PermissionError)
    if not scope.allowed:
        frappe.throw(_("Tài khoản chưa có hồ sơ độc giả đang hoạt động"), frappe.PermissionError)
    if not scope.get(feature):
        frappe.throw(_("Nhóm độc giả của bạn không được phép {0}").format(FEATURE_LABELS.get(feature, feature)),
                     frappe.PermissionError)
    return scope


def fonds_allowed(scope: frappe._dict, fonds: str | None) -> bool:
    return scope.fonds is None or (bool(fonds) and fonds in scope.fonds)


def scope_fonds_sql(scope: frappe._dict, column: str) -> str:
    """SQL condition restricting `column` to the fonds of the scope ("" when unrestricted)."""
    if scope.fonds is None:
        return ""
    if not scope.fonds:
        return "1=0"
    return f"{column} IN ({', '.join(frappe.db.escape(f) for f in scope.fonds)})"


# --- limits of slips -------------------------------------------------------------------------------

def get_limits(profile: str | None = None) -> frappe._dict:
    """The rules a reader's slips follow: the group's own value when it sets one (> 0), else the
    site-wide Reader Settings. 0 means "no limit" for the counts. `approval_mode` is the group's
    way of deciding whether a leader must approve ("Theo mức mật" by default)."""
    settings = frappe.get_cached_doc("Reader Settings")
    group = None
    if profile:
        name = frappe.db.get_value("Reader", profile, "reader_group") or _default_group_name()
        if name:
            group = frappe.db.get_value("Reader Group", name, [
                "approval_mode", "max_requests_per_day", "max_copy_requests_per_day", "max_items_per_request",
                "max_open_requests", "hold_days", "max_renewals"], as_dict=True)

    def pick(group_field, setting_field):
        own = cint(group.get(group_field)) if group else 0
        return own or cint(settings.get(setting_field))

    return frappe._dict(
        max_requests_per_day=pick("max_requests_per_day", "max_requests_per_day"),
        max_copy_requests_per_day=pick("max_copy_requests_per_day", "max_copy_requests_per_day"),
        max_items_per_request=pick("max_items_per_request", "max_items_per_request"),
        max_open_requests=pick("max_open_requests", "max_open_requests"),
        hold_days=pick("hold_days", "document_hold_days") or DEFAULT_HOLD_DAYS,
        max_renewals=pick("max_renewals", "max_renewals"),
        renewal_days=cint(settings.renewal_days) or DEFAULT_HOLD_DAYS,
        reminder_days_before=cint(settings.reminder_days_before),
        remind_overdue=bool(cint(settings.auto_return_overdue)),
        block_when_overdue=bool(cint(settings.block_when_overdue)),
        approval_mode=(group.approval_mode if group and group.approval_mode else "Theo mức mật"),
    )


DEFAULT_HOLD_DAYS = 7
