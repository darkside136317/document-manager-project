# -*- coding: utf-8 -*-
"""Idempotent seed of Workflows and in-app Notifications for reader requests.

Called from `setup.after_migrate` and whenever a permission group's slip functions change. Workflow State / Action
Master records are created first (a Workflow links to them), then each Workflow is rebuilt from the tables below.

Who may move a slip is decided by capabilities, not by fixed roles: the reading room is every permission group with
`slips.receive`, the leaders every group with `slips.leader_approve`; Document Admin may always decide.
"""

import frappe

ADMIN = "Document Admin"
DEFAULT_OFFICERS = ("Reading Room Officer",)
DEFAULT_LEADERS = ("Archive Leader",)

STATE_STYLE = {
    "Nháp": "Inverse",
    "Chờ duyệt": "Warning",
    "Chờ lãnh đạo duyệt": "Warning",
    "Đã duyệt": "Success",
    "Đang sử dụng": "Info",
    "Từ chối": "Danger",
    "Đã trả": "Primary",
    "Đã hoàn thành": "Primary",
    "Đã hủy": "Inverse",
    "Mới": "Warning",
    "Đã xem": "Info",
    "Đã phản hồi": "Success",
}


def _roles_with(capability: str, default: tuple) -> tuple:
    """The roles whose permission group grants `capability` (the built-in role before the groups exist)."""
    from document_manager.document_manager.policy import _profile_capabilities

    roles = sorted(role for role, caps in _profile_capabilities().items()
                   if capability in caps and role != ADMIN and frappe.db.exists("Role", role))
    return tuple(roles) or default


def _request_workflow(final_state: str, in_use: bool, officers: tuple, leaders: tuple) -> dict:
    """Nháp → Chờ duyệt (phòng đọc) → [Chờ lãnh đạo duyệt] → Đã duyệt → [Đang sử dụng →] final state.

    The reading room approves by itself only a slip that needs no leader (`doc.requires_leader`);
    Document Admin can always decide. The reader withdraws a slip nobody decided on yet.
    """
    staff = (*officers, ADMIN)
    leader = (*leaders, ADMIN)
    states = [
        ("Nháp", 0, "Reader"),
        ("Chờ duyệt", 1, "Reading Room Officer"),
        ("Chờ lãnh đạo duyệt", 1, "Archive Leader"),
        ("Đã duyệt", 1, "Reading Room Officer"),
        ("Từ chối", 1, "Reading Room Officer"),
    ]
    # (from, action, to, roles, allow_self_approval, condition)
    transitions = [
        ("Nháp", "Gửi duyệt", "Chờ duyệt", ("Reader", *staff), 1, None),
        ("Chờ duyệt", "Chuyển lãnh đạo", "Chờ lãnh đạo duyệt", staff, 0, None),
        ("Chờ duyệt", "Duyệt", "Đã duyệt", officers, 0, "doc.requires_leader == 0"),
        ("Chờ duyệt", "Duyệt", "Đã duyệt", (ADMIN,), 0, None),
        ("Chờ duyệt", "Từ chối", "Từ chối", staff, 0, None),
        ("Chờ duyệt", "Hủy phiếu", "Đã hủy", ("Reader",), 1, None),
        ("Chờ lãnh đạo duyệt", "Duyệt", "Đã duyệt", leader, 0, None),
        ("Chờ lãnh đạo duyệt", "Từ chối", "Từ chối", leader, 0, None),
        ("Chờ lãnh đạo duyệt", "Trả lại phòng đọc", "Chờ duyệt", leader, 1, None),
        ("Chờ lãnh đạo duyệt", "Hủy phiếu", "Đã hủy", ("Reader",), 1, None),
        ("Đã duyệt", "Hủy phiếu", "Đã hủy", (ADMIN,), 1, None),
    ]
    if in_use:
        states.append(("Đang sử dụng", 1, "Reading Room Officer"))
        transitions += [("Đã duyệt", "Giao tài liệu", "Đang sử dụng", staff, 1, None),
                        ("Đang sử dụng", "Nhận trả", final_state, staff, 1, None)]
    else:
        transitions.append(("Đã duyệt", "Hoàn thành", final_state, staff, 1, None))
    states += [(final_state, 1, "Reading Room Officer"), ("Đã hủy", 1, "Document Admin")]
    return {"states": states, "transitions": transitions}


def workflows(officers: tuple = DEFAULT_OFFICERS, leaders: tuple = DEFAULT_LEADERS) -> dict:
    staff = (*officers, ADMIN)
    return {
        "Usage Request": {"field": "workflow_state", **_request_workflow("Đã trả", True, officers, leaders)},
        "Copy Request": {"field": "workflow_state", **_request_workflow("Đã hoàn thành", False, officers, leaders)},
        "Reader Feedback": {
            "field": "status",
            "states": [
                ("Mới", 0, "Reading Room Officer"),
                ("Đã xem", 0, "Reading Room Officer"),
                ("Đã phản hồi", 0, "Reading Room Officer"),
            ],
            "transitions": [
                ("Mới", "Đánh dấu đã xem", "Đã xem", staff, 1, None),
                ("Mới", "Phản hồi", "Đã phản hồi", staff, 1, None),
                ("Đã xem", "Phản hồi", "Đã phản hồi", staff, 1, None),
            ],
        },
    }


# the tables in force (refreshed in place by setup_all, from the permission groups of the site)
WORKFLOWS = workflows()

# (name, doctype, event, subject, message)
NOTIFICATIONS = [
    ("Phiếu yêu cầu mới chờ duyệt", "Usage Request", "Submit",
     "Phiếu yêu cầu {{ doc.name }} chờ duyệt",
     "Độc giả {{ doc.reader_name }} gửi phiếu yêu cầu {{ doc.name }}."),
    ("Phiếu sao chụp mới chờ duyệt", "Copy Request", "Submit",
     "Phiếu sao chụp {{ doc.name }} chờ duyệt",
     "Độc giả {{ doc.reader_name }} gửi phiếu sao chụp {{ doc.name }}."),
    ("Góp ý mới của độc giả", "Reader Feedback", "New",
     "Góp ý mới: {{ doc.subject }}",
     "Độc giả {{ doc.reader_name }} gửi góp ý {{ doc.name }}."),
    ("Đăng ký độc giả mới", "Reader Registration", "New",
     "{{ doc.request_type }}: {{ doc.full_name }}",
     "{{ doc.full_name }} ({{ doc.email }}) gửi yêu cầu \"{{ doc.request_type }}\" — {{ doc.name }}."),
]


def setup_all():
    officers = _roles_with("slips.receive", DEFAULT_OFFICERS)
    WORKFLOWS.clear()
    WORKFLOWS.update(workflows(officers, _roles_with("slips.leader_approve", DEFAULT_LEADERS)))
    _ensure_masters()
    for doctype, spec in WORKFLOWS.items():
        _ensure_workflow(doctype, spec)
    for args in NOTIFICATIONS:
        _ensure_notification(*args, recipients=officers)


def _ensure_masters():
    for name, style in STATE_STYLE.items():
        if not frappe.db.exists("Workflow State", name):
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": name, "style": style}
                           ).insert(ignore_permissions=True)
    actions = {t[1] for spec in WORKFLOWS.values() for t in spec["transitions"]}
    for name in actions:
        if not frappe.db.exists("Workflow Action Master", name):
            frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": name}
                           ).insert(ignore_permissions=True)


def _ensure_workflow(doctype: str, spec: dict):
    name = f"{doctype} Workflow"
    if frappe.db.exists("Workflow", name):
        wf = frappe.get_doc("Workflow", name)
        wf.set("states", [])
        wf.set("transitions", [])
    else:
        wf = frappe.new_doc("Workflow")
        wf.workflow_name = name
    wf.document_type = doctype
    wf.workflow_state_field = spec["field"]
    wf.is_active = 1
    wf.send_email_alert = 0
    wf.override_status = 0
    for state, doc_status, role in spec["states"]:
        wf.append("states", {"state": state, "doc_status": str(doc_status), "allow_edit": role})
    for state, action, next_state, roles, self_approval, condition in spec["transitions"]:
        for role in roles:
            wf.append("transitions", {
                "state": state, "action": action, "next_state": next_state,
                "allowed": role, "allow_self_approval": self_approval, "condition": condition,
            })
    wf.flags.ignore_permissions = True
    wf.save()


def _ensure_notification(name, doctype, event, subject, message, recipients=DEFAULT_OFFICERS):
    values = {
        "document_type": doctype, "event": event, "channel": "System Notification",
        "subject": subject, "message": message, "enabled": 1,
        "recipients": [{"receiver_by_role": role} for role in recipients],
    }
    doc = frappe.get_doc("Notification", name) if frappe.db.exists("Notification", name)         else frappe.new_doc("Notification")
    doc.update(values)
    doc.flags.ignore_permissions = True
    if doc.is_new():
        doc.__newname = name
        doc.insert()
    else:
        doc.save()
