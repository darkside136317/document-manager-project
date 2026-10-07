# -*- coding: utf-8 -*-
"""Shared behaviour for reader requests (Usage Request, Copy Request).

State changes are driven by the Frappe Workflow (see setup_workflows.py); this
mixin only enforces data integrity and records who/when for each transition.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from document_manager.document_manager.permissions import assert_feature, get_reader_profile, is_staff

# Fields only staff may change once the request exists.
STAFF_ONLY_FIELDS = ("approved_by", "approved_date", "rejection_reason", "returned_date", "completed_date")


class RequestDocument(Document):
    # Set by subclasses: state name -> datetime field stamped on entering that state.
    final_state_field: dict[str, str] = {}
    # Reader Group feature a reader needs to file this kind of request.
    required_feature: str = ""

    def before_validate(self):
        if self.is_new():
            self._bind_reader()

    def validate(self):
        if not self.items:
            frappe.throw(_("Phải có ít nhất một hồ sơ/văn bản trong phiếu"))
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

    # -- transition side effects
    def _apply_state_effects(self):
        if self.is_new() or not self.has_value_changed("workflow_state"):
            return
        state = self.workflow_state
        if state == "Từ chối" and not (self.rejection_reason or "").strip():
            frappe.throw(_("Phải nhập lý do từ chối"))
        if state in ("Đã duyệt", "Từ chối"):
            self.approved_by = frappe.session.user
            self.approved_date = now_datetime()
        end_field = self.final_state_field.get(state)
        if end_field:
            self.set(end_field, now_datetime())
