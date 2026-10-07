# -*- coding: utf-8 -*-
"""Phiếu sao chụp of the signed-in reader: /portal/sao-chep and /portal/sao-chep/<name>."""

from document_manager.www._reader_slips import slip_context


def get_context(context):
    return slip_context(context, "copy")
