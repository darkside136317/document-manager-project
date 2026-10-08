# -*- coding: utf-8 -*-
from frappe.model.document import Document


class IntegrityCheck(Document):
    """Đợt kiểm tra toàn vẹn: cơ sở dữ liệu, từng tệp tài liệu, siêu dữ liệu. Xem `services/preservation/integrity.py`."""
