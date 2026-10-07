# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import now_datetime

from document_manager.document_manager.services import lifecycle as lc
from document_manager.document_manager.services.request_base import RequestDocument


class UsageRequest(RequestDocument):
    """Phiếu yêu cầu sử dụng tài liệu. Chuyển trạng thái qua Workflow "Usage Request":
    Nháp → Chờ duyệt → (Chờ lãnh đạo duyệt) → Đã duyệt → Đang sử dụng (giao) → Đã trả."""

    final_state_field = {lc.STATE_RETURNED: "returned_date"}
    required_feature = "can_request_usage"
    state_handlers = {**RequestDocument.state_handlers,
                      lc.STATE_IN_USE: "_on_issued", lc.STATE_RETURNED: "_on_returned"}

    def _on_issued(self, previous):
        """Handing the documents over starts the clock: the due date counts from today."""
        approved = self._rows(lc.ITEM_APPROVED)
        if not approved:
            frappe.throw(_("Phiếu không có hồ sơ, văn bản nào được duyệt để giao"))
        now = now_datetime()
        for row in approved:
            row.item_status, row.issued_on = lc.ITEM_ISSUED, now
        self.issued_on, self.issued_by = now, frappe.session.user
        self.due_date = lc.due_date_for(self.reader)
        self.renewal_count, self.is_overdue = 0, 0

    def _on_returned(self, previous):
        now = now_datetime()
        for row in self._rows(lc.ITEM_ISSUED):
            row.item_status, row.returned_on = lc.ITEM_RETURNED, now
            row.return_condition = row.return_condition or "Tốt"
        self.received_by = frappe.session.user
        self.is_overdue = 0
