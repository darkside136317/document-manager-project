# -*- coding: utf-8 -*-
"""Public pages about the unit: /gioi-thieu (also the home page), /lanh-dao, /co-cau, /lien-he, /huong-dan.

One template, five sections (the route rule in hooks.py passes `section`). Everything shown comes
from `services.public_site`, which leaves out hidden leaders and units and sanitises rich text.
"""

import frappe

from document_manager.document_manager.services import public_site
from document_manager.www._reader_ui import page_context

TITLES = {
    "gioi-thieu": "Giới thiệu",
    "lanh-dao": "Ban lãnh đạo",
    "co-cau": "Cơ cấu tổ chức",
    "lien-he": "Liên hệ",
    "huong-dan": "Hướng dẫn khai thác tài liệu",
}


def get_context(context):
    section = frappe.form_dict.get("section") or "gioi-thieu"
    if section not in TITLES:
        raise frappe.DoesNotExistError
    page_context(context, TITLES[section], active=section, public=True)
    org = context.org
    if (section == "lanh-dao" and not org["show_leaders"]) or (section == "co-cau" and not org["show_structure"]):
        raise frappe.DoesNotExistError
    context.section = section
    context.description = org["tagline"] if section == "gioi-thieu" else f"{TITLES[section]} — {org['name']}"
    context.units = public_site.get_org_units() if section == "co-cau" else []
    return context
