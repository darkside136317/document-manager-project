# -*- coding: utf-8 -*-
# Copyright (c) 2026, Document Manager Team and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ArchivalAgency(Document):
    """Cơ quan lưu trữ — Master data for archival agencies."""

    def validate(self):
        if self.agency_code:
            self.agency_code = self.agency_code.strip().upper()
