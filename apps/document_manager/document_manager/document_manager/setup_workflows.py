# -*- coding: utf-8 -*-
"""Idempotent seed of Workflows and in-app Notifications for reader requests.

Called from `setup.after_migrate`. Workflow State / Action Master records are created
first (a Workflow links to them), then each Workflow is rebuilt from the tables below.
"""

import frappe

STAFF = ("Reading Room Officer", "Document Admin")

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


LEADER = ("Archive Leader", "Document Admin")


def _request_workflow(final_state: str, in_use: bool) -> dict:
    """Nháp → Chờ duyệt (phòng đọc) → [Chờ lãnh đạo duyệt] → Đã duyệt → [Đang sử dụng →] final state.

    The reading room approves by itself only a slip that needs no leader (`doc.requires_leader`);
    Document Admin can always decide. The reader withdraws a slip nobody decided on yet.
    """
    states = [
        ("Nháp", 0, "Reader"),
        ("Chờ duyệt", 1, "Reading Room Officer"),
        ("Chờ lãnh đạo duyệt", 1, "Archive Leader"),
        ("Đã duyệt", 1, "Reading Room Officer"),
        ("Từ chối", 1, "Reading Room Officer"),
    ]
    # (from, action, to, roles, allow_self_approval, condition)
    transitions = [
        ("Nháp", "Gửi duyệt", "Chờ duyệt", ("Reader", *STAFF), 1, None),
        ("Chờ duyệt", "Chuyển lãnh đạo", "Chờ lãnh đạo duyệt", STAFF, 0, None),
        ("Chờ duyệt", "Duyệt", "Đã duyệt", ("Reading Room Officer",), 0, "doc.requires_leader == 0"),
        ("Chờ duyệt", "Duyệt", "Đã duyệt", ("Document Admin",), 0, None),
        ("Chờ duyệt", "Từ chối", "Từ chối", STAFF, 0, None),
        ("Chờ duyệt", "Hủy phiếu", "Đã hủy", ("Reader",), 1, None),
        ("Chờ lãnh đạo duyệt", "Duyệt", "Đã duyệt", LEADER, 0, None),
        ("Chờ lãnh đạo duyệt", "Từ chối", "Từ chối", LEADER, 0, None),
        ("Chờ lãnh đạo duyệt", "Trả lại phòng đọc", "Chờ duyệt", LEADER, 1, None),
        ("Chờ lãnh đạo duyệt", "Hủy phiếu", "Đã hủy", ("Reader",), 1, None),
        ("Đã duyệt", "Hủy phiếu", "Đã hủy", ("Document Admin",), 1, None),
    ]
    if in_use:
        states.append(("Đang sử dụng", 1, "Reading Room Officer"))
        transitions += [("Đã duyệt", "Giao tài liệu", "Đang sử dụng", STAFF, 1, None),
                        ("Đang sử dụng", "Nhận trả", final_state, STAFF, 1, None)]
    else:
        transitions.append(("Đã duyệt", "Hoàn thành", final_state, STAFF, 1, None))
    states += [(final_state, 1, "Reading Room Officer"), ("Đã hủy", 1, "Document Admin")]
    return {"states": states, "transitions": transitions}


WORKFLOWS = {
    "Usage Request": {"field": "workflow_state", **_request_workflow("Đã trả", in_use=True)},
    "Copy Request": {"field": "workflow_state", **_request_workflow("Đã hoàn thành", in_use=False)},
    "Reader Feedback": {
        "field": "status",
        "states": [
            ("Mới", 0, "Reading Room Officer"),
            ("Đã xem", 0, "Reading Room Officer"),
            ("Đã phản hồi", 0, "Reading Room Officer"),
        ],
        "transitions": [
            ("Mới", "Đánh dấu đã xem", "Đã xem", STAFF, 1, None),
            ("Mới", "Phản hồi", "Đã phản hồi", STAFF, 1, None),
            ("Đã xem", "Phản hồi", "Đã phản hồi", STAFF, 1, None),
        ],
    },
}

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
    _ensure_masters()
    for doctype, spec in WORKFLOWS.items():
        _ensure_workflow(doctype, spec)
    for args in NOTIFICATIONS:
        _ensure_notification(*args)


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


def _ensure_notification(name, doctype, event, subject, message):
    values = {
        "document_type": doctype, "event": event, "channel": "System Notification",
        "subject": subject, "message": message, "enabled": 1,
        "recipients": [{"receiver_by_role": "Reading Room Officer"}],
    }
    doc = frappe.get_doc("Notification", name) if frappe.db.exists("Notification", name)         else frappe.new_doc("Notification")
    doc.update(values)
    doc.flags.ignore_permissions = True
    if doc.is_new():
        doc.__newname = name
        doc.insert()
    else:
        doc.save()
