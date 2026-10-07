# -*- coding: utf-8 -*-
from document_manager.document_manager.services.request_base import RequestDocument


class UsageRequest(RequestDocument):
    """Phiếu yêu cầu sử dụng tài liệu. Chuyển trạng thái qua Workflow "Usage Request"."""

    final_state_field = {"Đã trả": "returned_date"}
    required_feature = "can_request_usage"
