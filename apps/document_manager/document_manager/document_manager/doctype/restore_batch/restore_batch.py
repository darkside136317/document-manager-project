# -*- coding: utf-8 -*-
from frappe.model.document import Document


class RestoreBatch(Document):
    """Đợt phục hồi: tệp của các tài liệu từ bản sao lưu, hoặc cơ sở dữ liệu (có kiểm soát). Xem `services/preservation/restore.py`."""
