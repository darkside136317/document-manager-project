"""Whitelisted endpoints for AI extraction and authenticated engine callbacks."""

import frappe

from document_manager.document_manager.services import ai_integration


@frappe.whitelist(methods=["POST"])
def start(record_group, selection="unprocessed"):
    return ai_integration.start(record_group, selection)


@frappe.whitelist()
def status(job_id):
    return ai_integration.status(job_id)


@frappe.whitelist()
def latest(record_group):
    return ai_integration.latest(record_group)


@frappe.whitelist(methods=["POST"])
def refresh(job_id):
    return ai_integration.refresh(job_id)


@frappe.whitelist(methods=["POST"])
def review(job_id, document_id, approved_fields):
    return ai_integration.review(job_id, document_id, frappe.parse_json(approved_fields))


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive_status(**kwargs):
    payload = frappe.request.get_json(silent=True) or kwargs
    return ai_integration.receive_callback(payload, frappe.request.headers.get("X-AI-Callback-Key", ""))
