# -*- coding: utf-8 -*-
from document_manager.www._request_ui import list_context, readers_to_portal


def get_context(context):
    readers_to_portal("copy_requests")
    list_context(context, "copy_requests")
