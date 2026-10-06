# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

class Reader(Document):
    """Độc giả — người dùng bên ngoài khai thác tài liệu."""

    def validate(self):
        self.max_confidentiality_priority = max(1, int(self.max_confidentiality_priority or 1))
        if self.user and not self.email:
            self.email = frappe.db.get_value("User", self.user, "email")

    def after_insert(self):
        if self.user:
            user_doc = frappe.get_doc("User", self.user)
            if "Reader" not in [r.role for r in user_doc.roles]:
                user_doc.append("roles", {"role": "Reader"})
                user_doc.save(ignore_permissions=True)

@frappe.whitelist()
def set_reader_password(reader_name, new_password):
    if not frappe.has_permission("Reader", "write", doc=reader_name):
        frappe.throw("Không có quyền thiết lập mật khẩu", frappe.PermissionError)
        
    reader = frappe.get_doc("Reader", reader_name)
    
    if not reader.user:
        if not reader.email:
            frappe.throw("Vui lòng cập nhật Email cho Độc giả trước khi tạo tài khoản đăng nhập.")
            
        # Create new user
        user = frappe.new_doc("User")
        user.email = reader.email
        user.first_name = reader.full_name
        user.send_welcome_email = 0
        user.append("roles", {"role": "Reader"})
        user.flags.ignore_permissions = True
        user.insert(ignore_permissions=True)
        
        # Link user to reader
        reader.user = user.email
        reader.flags.ignore_permissions = True
        reader.save(ignore_permissions=True)
        
    import frappe.utils.password
    frappe.utils.password.update_password("User", reader.user, new_password)
    return {"message": "Thành công", "user": reader.user}
