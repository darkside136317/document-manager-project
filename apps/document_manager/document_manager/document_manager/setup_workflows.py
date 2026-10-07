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
    "Đã duyệt": "Success",
    "Từ chối": "Danger",
    "Đã trả": "Primary",
    "Đã hoàn thành": "Primary",
    "Đã hủy": "Inverse",
    "Mới": "Warning",
    "Đã xem": "Info",
    "Đã phản hồi": "Success",
}


def _request_workflow(final_state: str, final_action: str) -> dict:
    return {
        "states": [
            ("Nháp", 0, "Reader"),
            ("Chờ duyệt", 1, "Reading Room Officer"),
            ("Đã duyệt", 1, "Reading Room Officer"),
            ("Từ chối", 1, "Reading Room Officer"),
            (final_state, 1, "Reading Room Officer"),
            ("Đã hủy", 1, "Document Admin"),
        ],
        # (from, action, to, roles, allow_self_approval)
        "transitions": [
            ("Nháp", "Gửi duyệt", "Chờ duyệt", ("Reader", *STAFF), 1),
            ("Chờ duyệt", "Duyệt", "Đã duyệt", STAFF, 0),
            ("Chờ duyệt", "Từ chối", "Từ chối", STAFF, 0),
            ("Chờ duyệt", "Hủy phiếu", "Đã hủy", ("Reader",), 1),
            ("Đã duyệt", final_action, final_state, STAFF, 1),
        ],
    }


WORKFLOWS = {
    "Usage Request": {"field": "workflow_state", **_request_workflow("Đã trả", "Trả tài liệu")},
    "Copy Request": {"field": "workflow_state", **_request_workflow("Đã hoàn thành", "Hoàn thành")},
    "Reader Feedback": {
        "field": "status",
        "states": [
            ("Mới", 0, "Reading Room Officer"),
            ("Đã xem", 0, "Reading Room Officer"),
            ("Đã phản hồi", 0, "Reading Room Officer"),
        ],
        "transitions": [
            ("Mới", "Đánh dấu đã xem", "Đã xem", STAFF, 1),
            ("Mới", "Phản hồi", "Đã phản hồi", STAFF, 1),
            ("Đã xem", "Phản hồi", "Đã phản hồi", STAFF, 1),
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
    for state, action, next_state, roles, self_approval in spec["transitions"]:
        for role in roles:
            wf.append("transitions", {
                "state": state, "action": action, "next_state": next_state,
                "allowed": role, "allow_self_approval": self_approval,
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
