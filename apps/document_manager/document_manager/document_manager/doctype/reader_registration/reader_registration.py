# -*- coding: utf-8 -*-
from frappe.model.document import Document

REQUEST_REGISTER = "Đăng ký tài khoản"
REQUEST_RESET = "Quên mật khẩu"
STATUS_NEW, STATUS_APPROVED, STATUS_REJECTED = "Mới", "Đã duyệt", "Từ chối"


class ReaderRegistration(Document):
    """Yêu cầu của người chưa đăng nhập: đăng ký tài khoản độc giả hoặc xin cấp lại mật khẩu.

    Bản ghi chỉ do `services/registration.py` tạo và xử lý; cán bộ duyệt ở giao diện cán bộ.
    """

    def validate(self):
        self.email = (self.email or "").strip().lower()
        self.full_name = (self.full_name or "").strip()
