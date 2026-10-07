# -*- coding: utf-8 -*-
"""Reader registration form (/dang-ky). The request is handled by `api.registration.register_reader`."""

from document_manager.document_manager.services.registration import registration_settings
from document_manager.www._reader_ui import guest_only, page_context


def get_context(context):
    guest_only()
    page_context(context, "Đăng ký tài khoản độc giả", public=True)
    context.settings = registration_settings()
    return context
