# -*- coding: utf-8 -*-
"""Permission groups of the staff (nhóm quyền): list, read, change, create, delete, reset. Administrators only.

A group is a Frappe Role with a Staff Role Profile. What it may do with each kind of data is written to Frappe's own
permission rules (`services.permission_matrix`), the other functions are its capabilities. The administrators' group
holds everything and cannot be changed; the built-in groups cannot be deleted but can be put back to their defaults.
Every change is recorded in the system log.
"""

import frappe
from frappe import _

from document_manager.document_manager.constants import BUILTIN_CAPABILITIES, CAPABILITIES, CAPABILITY_CODES
from document_manager.document_manager.permissions import assert_capability
from document_manager.document_manager.policy import clear_cache, staff_role_profiles
from document_manager.document_manager.services import permission_matrix
from document_manager.document_manager.services.audit import log_activity

PROFILE = "Staff Role Profile"
GROUP_LABELS = ("Quản trị", "Tác nghiệp")
MAX_MEMBERS_SHOWN = 200


def _require() -> None:
    assert_capability("users.manage")


def _members(role: str) -> list[str]:
    holders = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent", distinct=True)
    if not holders:
        return []
    return frappe.get_all("User", filters={"name": ["in", holders], "user_type": "System User"}, pluck="name")


def _profile(role: str):
    if not frappe.db.exists(PROFILE, role):
        frappe.throw(_("Không tìm thấy nhóm quyền {0}").format(role), frappe.DoesNotExistError)
    return frappe.get_doc(PROFILE, role)


@frappe.whitelist()
def list_groups():
    """Every permission group with how many staff accounts hold it."""
    _require()
    counts = {}
    for row in frappe.get_all("Has Role", filters={"parenttype": "User", "role": ["in", [p["role"] for p in staff_role_profiles()] or [""]]},
                              fields=["role", "parent"]):
        counts.setdefault(row.role, set()).add(row.parent)
    staff = set(frappe.get_all("User", filters={"user_type": "System User", "enabled": 1}, pluck="name"))
    return [{**p, "members": len(counts.get(p["role"], set()) & staff)} for p in staff_role_profiles()]


def _capabilities(profile) -> list:
    granted = {r.capability for r in profile.get("capabilities") or []}
    modules = {}
    for code, label, module in CAPABILITIES:
        modules.setdefault(module, []).append({"code": code, "label": label,
                                               "checked": bool(profile.is_admin) or code in granted})
    return [{"module": module, "items": items} for module, items in modules.items()]


@frappe.whitelist()
def get_group(role):
    """A group with its matrix (what it may do with each kind of data), its functions and its members."""
    _require()
    profile = _profile(role)
    members = _members(role)
    users = frappe.get_all("User", filters={"name": ["in", members or [""]]}, fields=["name", "full_name", "enabled"],
                           order_by="full_name asc", limit_page_length=MAX_MEMBERS_SHOWN) if members else []
    return {
        "role": profile.role, "label": profile.label, "group": profile.group_label, "description": profile.description or "",
        "is_builtin": bool(profile.is_builtin), "is_admin": bool(profile.is_admin), "locked": bool(profile.is_admin),
        "modified": str(profile.modified),
        "matrix": permission_matrix.matrix(role),
        "columns": permission_matrix.COLUMN_LABELS,
        "capabilities": _capabilities(profile),
        "members": users, "member_count": len(members),
    }


def _apply(profile, values: dict) -> list[str]:
    """Write a group's description, matrix and functions; returns a short description of what changed."""
    changes = []
    for field, key in (("label", "label"), ("description", "description"), ("group_label", "group")):
        if key in values and (values[key] or "") != (profile.get(field) or ""):
            if key == "group" and values[key] not in GROUP_LABELS:
                frappe.throw(_("Loại nhóm không hợp lệ"))
            profile.set(field, (values[key] or "").strip())
            changes.append(_("đổi {0}").format({"label": "tên", "description": "mô tả", "group": "loại"}[key]))
    if "capabilities" in values:
        wanted = [c for c in (values.get("capabilities") or []) if c in CAPABILITY_CODES]
        before = {r.capability for r in profile.get("capabilities") or []}
        if set(wanted) != before:
            profile.set("capabilities", [{"capability": c} for c in wanted])
            added, removed = set(wanted) - before, before - set(wanted)
            if added:
                changes.append(_("thêm chức năng {0}").format(", ".join(sorted(added))))
            if removed:
                changes.append(_("bỏ chức năng {0}").format(", ".join(sorted(removed))))
    profile.flags.ignore_permissions = True
    profile.save()
    for doctype, cell in (values.get("matrix") or {}).items():
        if permission_matrix.set_cell(doctype, profile.role, cell or {}):
            changes.append(_("đổi quyền trên {0}").format(doctype))
    return changes


@frappe.whitelist(methods=["POST"])
def save_group(role, values):
    """Change a group: `values` = {label, description, group, capabilities: [codes], matrix: {doctype: cell}}."""
    _require()
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
    profile = _profile(role)
    if profile.is_admin:
        frappe.throw(_("Nhóm quản trị viên luôn có mọi quyền và không thay đổi được"))
    if values.get("modified") and str(profile.modified) != str(values["modified"]):
        frappe.throw(_("Nhóm quyền vừa được người khác thay đổi. Hãy tải lại rồi sửa tiếp."))
    changes = _apply(profile, values)
    clear_cache()
    if changes:
        log_activity("Đổi cấu hình", PROFILE, role, f"Sửa nhóm quyền {profile.label}: " + "; ".join(changes))
    return get_group(role)


@frappe.whitelist(methods=["POST"])
def create_group(label, description=None, group=None, copy_from=None):
    """A new group (and its Frappe role); `copy_from` starts it with the rules and functions of another group."""
    _require()
    label = (label or "").strip()
    if not 2 <= len(label) <= 60:
        frappe.throw(_("Tên nhóm quyền cần từ 2 đến 60 ký tự"))
    if frappe.db.exists("Role", label) or frappe.db.exists(PROFILE, label):
        frappe.throw(_("Đã có vai trò hoặc nhóm quyền tên {0}").format(label))
    source = _profile(copy_from) if copy_from else None
    frappe.get_doc({"doctype": "Role", "role_name": label, "desk_access": 1, "is_custom": 1}).insert(ignore_permissions=True)
    if source is None:
        capabilities = []
    elif source.is_admin:
        capabilities = sorted(CAPABILITY_CODES)
    else:
        capabilities = [r.capability for r in source.get("capabilities") or []]
    frappe.get_doc({"doctype": PROFILE, "role": label, "label": label, "description": (description or "").strip(),
                    "group_label": group if group in GROUP_LABELS else "Tác nghiệp",
                    "capabilities": [{"capability": c} for c in capabilities]}).insert(ignore_permissions=True)
    if source is not None:
        permission_matrix.copy_role(source.role, label)
    clear_cache()
    log_activity("Đổi cấu hình", PROFILE, label,
                 f"Tạo nhóm quyền {label}" + (f" từ nhóm {source.label}" if source is not None else ""))
    return get_group(label)


@frappe.whitelist(methods=["POST"])
def delete_group(role):
    """Delete a group nobody holds any more (built-in groups stay)."""
    _require()
    profile = _profile(role)
    if profile.is_builtin or profile.is_admin:
        frappe.throw(_("Không xóa được nhóm quyền có sẵn"))
    members = _members(role)
    if members:
        frappe.throw(_("Còn {0} người dùng thuộc nhóm quyền này: bỏ họ ra khỏi nhóm trước").format(len(members)))
    if frappe.db.exists("Staff Group Role", {"role": role}):
        frappe.throw(_("Nhóm cán bộ còn cấp nhóm quyền này: bỏ khỏi nhóm cán bộ trước"))
    had_slip_functions = bool({r.capability for r in profile.capabilities} & {"slips.receive", "slips.leader_approve"})
    permission_matrix.remove_role(role)
    frappe.delete_doc(PROFILE, role, ignore_permissions=True, force=True)
    frappe.delete_doc("Role", role, ignore_permissions=True, force=True)
    clear_cache()
    if had_slip_functions:
        from document_manager.document_manager.doctype.staff_role_profile.staff_role_profile import sync_workflows

        sync_workflows()
    log_activity("Đổi cấu hình", PROFILE, role, f"Xóa nhóm quyền {profile.label}")
    return {"role": role}


@frappe.whitelist(methods=["POST"])
def reset_group(role):
    """Put a built-in group back to what it could do when the application was installed."""
    _require()
    profile = _profile(role)
    if profile.is_admin or not profile.is_builtin:
        frappe.throw(_("Chỉ khôi phục được nhóm quyền có sẵn"))
    changed = permission_matrix.reset_role(role)
    profile.set("capabilities", [{"capability": c} for c in BUILTIN_CAPABILITIES.get(role, ())])
    profile.flags.ignore_permissions = True
    profile.save()
    clear_cache()
    log_activity("Đổi cấu hình", PROFILE, role, f"Khôi phục quyền mặc định của nhóm {profile.label} ({changed} loại dữ liệu)")
    return get_group(role)
