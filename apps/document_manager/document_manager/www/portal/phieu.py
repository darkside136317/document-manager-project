# -*- coding: utf-8 -*-
"""Phiếu yêu cầu sử dụng of the signed-in reader: /portal/phieu and /portal/phieu/<name>."""

from document_manager.www._reader_slips import slip_context


def get_context(context):
    return slip_context(context, "usage")
