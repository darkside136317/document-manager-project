# -*- coding: utf-8 -*-
"""Reader registration form (/dang-ky). The request is handled by `api.registration.register_reader`.

Which optional fields are shown or required comes from the active "Đăng ký độc giả" Request Template."""

from document_manager.document_manager.services import templates
from document_manager.document_manager.services.registration import registration_settings
from document_manager.document_manager.services.web import inline_json
from document_manager.www._reader_ui import guest_only, page_context


def get_context(context):
    guest_only()
    form = templates.registration_form()
    page_context(context, form.title, public=True)
    context.settings = registration_settings()
    context.form = form
    context.fields = {f["fieldname"]: f for f in form.fields}
    context.form_config = inline_json({"required": {f["fieldname"]: f["label"] for f in form.fields if f["required"]}})
    return context
