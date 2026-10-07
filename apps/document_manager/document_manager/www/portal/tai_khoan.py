# -*- coding: utf-8 -*-
"""The reader's own account (/portal/tai-khoan): profile, what the group allows, password."""

import frappe

from document_manager.document_manager.api.account import get_account
from document_manager.document_manager.services.web import inline_json
from document_manager.www._reader_ui import page_context, require_reader


def get_context(context):
    require_reader()
    page_context(context, "Tài khoản của tôi", active="")
    if not context.has_profile:
        raise frappe.DoesNotExistError  # staff without a reader profile manage their account in the staff app
    account = get_account()
    context.update({"account": account, "profile": account["profile"],
                    "account_config": inline_json({"profile": account["profile"]})})
    return context
