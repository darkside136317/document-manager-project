# -*- coding: utf-8 -*-
"""Shared behaviour for reader requests (Usage Request, Copy Request).

State changes are driven by the Frappe Workflow (see setup_workflows.py); this class enforces data
integrity (a reader acts only as themselves and cannot edit a sent slip), applies the lifecycle rules of
services/lifecycle.py at each transition (quota, leader approval, issue and return) and records
who/when. Item decisions of the officer or leader are stored on the item rows.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from document_manager.document_manager.permissions import assert_feature, get_reader_profile, is_staff
from document_manager.document_manager.services import lifecycle as lc
from document_manager.document_manager.services import templates

# Fields only staff (the workflow actions they run, or the daily job) may change once the request exists.
STAFF_ONLY_FIELDS = (
    "approved_by", "approved_date", "rejection_reason", "returned_date", "completed_date", "requires_leader",
    "leader", "issued_on", "issued_by", "due_date", "renewal_count", "is_overdue", "received_by", "submitted_on",
)


def _signature(doc) -> list:
    """What a reader must not change in a slip that was sent: which items it holds and their handling."""
    return [(row.name, row.archival_file, row.archive_document, row.get("copy_count"), row.get("item_status"),
             row.get("decision_note"), row.get("return_condition")) for row in doc.get("items") or []]


class RequestDocument(Document):
    # Set by subclasses: state name -> datetime field stamped on entering that state.
    final_state_field: dict[str, str] = {}
    # Reader Group feature a reader needs to file this kind of request.
    required_feature: str = ""
    # state name -> method run when the document enters it (the previous state is passed).
    state_handlers: dict[str, str] = {
        lc.STATE_PENDING: "_on_pending", lc.STATE_LEADER: "_on_leader",
        lc.STATE_APPROVED: "_on_approved", lc.STATE_REJECTED: "_on_rejected",
    }

    def before_validate(self):
        if self.is_new():
            self._bind_reader()

    def validate(self):
        if not self.items:
            frappe.throw(_("Phải có ít nhất một hồ sơ/văn bản trong phiếu"))
        if self.reader and not self.reader_name:
            # fetch_from does not reach readers (they cannot read the Reader record through the link check)
            self.reader_name = frappe.db.get_value("Reader", self.reader, "full_name")
        self._guard_protected_fields()
        self._validate_items()
        self._apply_state_effects()

    def before_update_after_submit(self):
        # `validate` does not run for submitted documents, but workflow transitions land here.
        self._guard_protected_fields()
        self._apply_state_effects()

    # -- reader identity
    def _bind_reader(self):
        """Readers can only file requests as themselves, whatever the client sent.

        Staff may file on behalf of a reader; without an explicit choice they file as their own profile.
        """
        profile = get_reader_profile()
        if is_staff():
            if self.reader:
                return
            if not profile:
                frappe.throw(_("Vui lòng chọn độc giả cho phiếu"))
        elif not profile:
            frappe.throw(_("Tài khoản chưa có hồ sơ độc giả"), frappe.PermissionError)
        if not is_staff():
            if not frappe.db.get_value("Reader", profile, "is_active"):
                frappe.throw(_("Hồ sơ độc giả đang bị khóa"), frappe.PermissionError)
            if self.required_feature:
                assert_feature(self.required_feature)  # the reader's group must allow this request
        self.reader = profile

    def _guard_protected_fields(self):
        if is_staff() or self.is_new():
            return
        for fieldname in ("reader", *STAFF_ONLY_FIELDS):
            if self.has_value_changed(fieldname):
                frappe.throw(_("Bạn không được sửa trường {0}").format(self.meta.get_label(fieldname)),
                             frappe.PermissionError)
        before = self.get_doc_before_save()
        if before and before.docstatus == 1:
            # a sent slip is the officers' to handle: the reader may only add a note or withdraw it
            if self.has_value_changed("purpose") or _signature(before) != _signature(self):
                frappe.throw(_("Phiếu đã gửi không sửa được. Hãy hủy phiếu và lập phiếu mới nếu cần thay đổi."),
                             frappe.PermissionError)

    # -- items
    def _validate_items(self):
        check_user = frappe.db.get_value("Reader", self.reader, "user") or frappe.session.user
        for row in self.items:
            if row.archive_document:
                parent_file = frappe.db.get_value("Archive Document", row.archive_document, "archival_file")
                if row.archival_file and parent_file and row.archival_file != parent_file:
                    frappe.throw(_("Dòng {0}: văn bản {1} không thuộc hồ sơ {2}").format(
                        row.idx, row.archive_document, row.archival_file))
                row.archival_file = row.archival_file or parent_file
            if not row.archival_file:
                frappe.throw(_("Dòng {0}: phải chọn hồ sơ hoặc văn bản").format(row.idx))
            self._check_readable(row, "Archival File", row.archival_file, check_user)
            if row.archive_document:
                self._check_readable(row, "Archive Document", row.archive_document, check_user)

    @staticmethod
    def _check_readable(row, doctype, name, user):
        if not frappe.has_permission(doctype, "read", doc=name, user=user):
            frappe.throw(_("Dòng {0}: không có quyền khai thác {1} {2}").format(row.idx, doctype, name),
                         frappe.PermissionError)

    def _rows(self, *statuses):
        return [row for row in self.items if row.item_status in statuses]

    # -- transition side effects
    def _apply_state_effects(self):
        if self.is_new() or not self.has_value_changed("workflow_state"):
            return
        state = self.workflow_state
        before = self.get_doc_before_save()
        previous = before.workflow_state if before else None
        if state == lc.STATE_REJECTED and not (self.rejection_reason or "").strip():
            frappe.throw(_("Phải nhập lý do từ chối"))
        if state in (lc.STATE_APPROVED, lc.STATE_REJECTED):
            self.approved_by = frappe.session.user
            self.approved_date = now_datetime()
        handler = self.state_handlers.get(state)
        if handler:
            getattr(self, handler)(previous)
        end_field = self.final_state_field.get(state)
        if end_field:
            self.set(end_field, now_datetime())

    def _on_pending(self, previous):
        """The slip reaches the reading room: first time (from the draft) it is checked against the reader's
        limits and decides whether a leader must approve; coming back from the leader it keeps its items."""
        if previous not in (None, lc.STATE_DRAFT):
            return
        if templates.slip_options_for(self.doctype).require_purpose and not (self.purpose or "").strip():
            frappe.throw(_("Vui lòng nhập mục đích trước khi gửi phiếu"))
        if not is_staff():
            lc.check_quota(self)
        self.submitted_on = now_datetime()
        self.requires_leader = int(lc.needs_leader(self))
        for row in self.items:
            row.item_status = lc.ITEM_PENDING

    def _on_leader(self, previous):
        self.requires_leader = 1

    def _on_approved(self, previous):
        for row in self._rows(lc.ITEM_PENDING):
            row.item_status = lc.ITEM_APPROVED  # items nobody turned down are approved with the slip
        if not self._rows(lc.ITEM_APPROVED):
            frappe.throw(_("Phải duyệt ít nhất một hồ sơ/văn bản trong phiếu (hoặc từ chối cả phiếu)"))
        if previous == lc.STATE_LEADER:
            self.leader = frappe.session.user

    def _on_rejected(self, previous):
        for row in self.items:
            row.item_status = lc.ITEM_REJECTED
        if previous == lc.STATE_LEADER:
            self.leader = frappe.session.user
