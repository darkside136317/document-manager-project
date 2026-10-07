# -*- coding: utf-8 -*-
from document_manager.document_manager.services.request_base import RequestDocument


class CopyRequest(RequestDocument):
    """Phiếu đăng ký sao chụp tài liệu. Chuyển trạng thái qua Workflow "Copy Request"."""

    final_state_field = {"Đã hoàn thành": "completed_date"}
    required_feature = "can_request_copy"
