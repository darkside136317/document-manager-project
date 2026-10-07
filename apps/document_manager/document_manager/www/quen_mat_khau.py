# -*- coding: utf-8 -*-
"""Forgotten password (/quen-mat-khau): the reader asks, an officer issues a new one-time link."""

from document_manager.www._reader_ui import guest_only, page_context


def get_context(context):
    guest_only()
    page_context(context, "Quên mật khẩu", public=True)
    return context
