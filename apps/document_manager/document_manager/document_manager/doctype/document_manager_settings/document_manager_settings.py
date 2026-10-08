# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

# the security fields mirror Frappe's System Settings: the one place Frappe itself reads them from
SYSTEM_SETTINGS = {
    "enforce_password_policy": "enable_password_policy",
    "minimum_password_score": "minimum_password_score",
    "login_max_attempts": "allow_consecutive_login_attempts",
    "login_lock_seconds": "allow_login_after_fail",
}


RANGES = (("backup_retention_days", 1, 3650), ("log_retention_days", 7, 3650), ("backup_keep_min", 1, 100),
          ("login_max_attempts", 3, 100), ("login_lock_seconds", 10, 86400))


class DocumentManagerSettings(Document):
    def load_from_db(self):
        """The account-security fields show what Frappe's System Settings holds: the one place that is in force. (A value
        stored here from a time before the field existed, or a form saved empty, must never say otherwise.)"""
        super().load_from_db()
        for field, target in SYSTEM_SETTINGS.items():
            value = frappe.db.get_single_value("System Settings", target)
            if field == "enforce_password_policy":
                self.set(field, cint(value))
            elif cint(value):
                self.set(field, str(cint(value)) if field == "minimum_password_score" else cint(value))
            else:  # 0 or empty means "off" for Frappe; the form offers the default instead
                default = self.meta.get_field(field).default
                self.set(field, default if field == "minimum_password_score" else cint(default))

    def validate(self):
        for field, low, high in RANGES:
            if self.get(field) in (None, ""):  # an empty number is "not set": the field's default applies (a typed 0 is refused below)
                self.set(field, cint(self.meta.get_field(field).default))
            if not low <= cint(self.get(field)) <= high:
                frappe.throw(_("{0} phải từ {1} đến {2}").format(self.meta.get_label(field), low, high))

    def on_update(self):
        """Apply the account-security settings where Frappe reads them."""
        values = {target: (cint(self.get(field)) if field != "minimum_password_score" else str(cint(self.get(field)) or 2))
                  for field, target in SYSTEM_SETTINGS.items() if self.get(field) not in (None, "")}
        if values:
            frappe.db.set_single_value("System Settings", values)
            frappe.clear_cache()
