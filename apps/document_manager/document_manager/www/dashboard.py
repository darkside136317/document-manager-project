# -*- coding: utf-8 -*-
import frappe
from document_manager.document_manager.permissions import require_staff
from document_manager.document_manager.api.dashboard import get_workspace_summary

def get_context(context):
    """
    Context cho Web Portal Dashboard
    Route: /dashboard
    """
    context.no_cache = 1
    # Yêu cầu người dùng phải đăng nhập mới xem được Dashboard
    context.login_required = True
    
    require_staff()

    context.title = "Document Manager Dashboard"

    # Fetch dữ liệu tổng quan
    try:
        summary_data = get_workspace_summary()
        context.summary = summary_data
    except Exception:
        from document_manager.document_manager.services.errors import log_exception
        log_exception("Dashboard SSR", "Error fetching dashboard summary")
        context.summary = {
            "archival_files": 0,
            "documents": 0,
            "readers": 0,
            "index_percent": 0,
            "pending_usage": 0,
            "pending_copy": 0,
            "integrity_errors": 0,
            "recent_documents": []
        }
