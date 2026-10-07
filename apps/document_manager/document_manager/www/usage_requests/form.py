# -*- coding: utf-8 -*-
from document_manager.www._request_ui import form_context, readers_to_portal


def get_context(context):
    readers_to_portal("usage_requests")
    form_context(context, "usage_requests")
