# -*- coding: utf-8 -*-
from document_manager.www._request_ui import form_context, readers_to_portal


def get_context(context):
    readers_to_portal("reader_feedbacks")
    form_context(context, "reader_feedbacks")
