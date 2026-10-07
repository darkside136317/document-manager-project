# -*- coding: utf-8 -*-
from document_manager.document_manager.services import lifecycle as lc
from document_manager.document_manager.services.request_base import RequestDocument


class CopyRequest(RequestDocument):
    """Phiếu đăng ký sao chụp tài liệu. Chuyển trạng thái qua Workflow "Copy Request":
    Nháp → Chờ duyệt → (Chờ lãnh đạo duyệt) → Đã duyệt → Đã hoàn thành."""

    final_state_field = {lc.STATE_COMPLETED: "completed_date"}
    required_feature = "can_request_copy"
    state_handlers = {**RequestDocument.state_handlers, lc.STATE_COMPLETED: "_on_completed"}

    def _on_completed(self, previous):
        for row in self._rows(lc.ITEM_APPROVED):
            row.item_status = lc.ITEM_COPIED
