# -*- coding: utf-8 -*-
"""Hooks configuration for Document Manager app.

This file defines how the Document Manager app integrates with the Frappe framework:
- App metadata
- Document events (on_update, on_trash) for search index sync
- Scheduled tasks (backup, integrity check, log cleanup)
- Permission query conditions (access_level filtering)
- Website/Portal configuration
- Fixtures for roles, workflows, and master data
"""

app_name = "document_manager"
app_title = "Document Manager"
app_publisher = "Document Manager Team"
app_description = "Hệ thống Quản lý & Khai thác Hồ sơ Lưu trữ Số hóa"
app_email = "admin@docmanager.local"
app_license = "MIT"
app_icon = "octicon octicon-archive"
app_color = "#2b5797"

# UI design system. Brand changes belong in theme-tokens.css; components remain stable.
app_include_css = [
    "/assets/document_manager/css/theme-tokens.css",
    "/assets/document_manager/css/document-manager-ui.css",
]
page_include_js = {
    "workspace": "/assets/document_manager/js/document-manager-dashboard.js"
}
web_include_css = [
    "/assets/document_manager/css/theme-tokens.css",
    "/assets/document_manager/css/document-manager-ui.css",
]

# =============================================================================
# Website / Portal
# =============================================================================
website_route_rules = [
    {"from_route": "/documents/<path:app_path>", "to_route": "documents"},
]

portal_menu_items = [
    {"title": "Tìm kiếm tài liệu", "route": "/search", "role": "Reader"},
    {"title": "Phiếu yêu cầu", "route": "/usage-requests", "role": "Reader"},
    {"title": "Phiếu sao chụp", "route": "/copy-requests", "role": "Reader"},
    {"title": "Góp ý", "route": "/feedback", "role": "Reader"},
]

# =============================================================================
# Fixtures — exported to JSON, imported on app install
# =============================================================================
fixtures = [
    # Roles
    {
        "dt": "Role",
        "filters": [
            ["name", "in", [
                "Document Admin",
                "Cataloger",
                "Reading Room Officer",
                "Preservation Officer",
                "Reader",
            ]]
        ],
    },
]

# =============================================================================
# Document Events — hooks into Doctype lifecycle
# =============================================================================
doc_events = {
    "Archive Document": {
        "on_update": "document_manager.document_manager.services.file_processor.enqueue_processing_or_index",
        "on_trash": "document_manager.document_manager.services.search_index.enqueue_deindex",
        "after_insert": "document_manager.document_manager.services.file_processor.enqueue_extract_and_store",
    },
    "Archival File": {
        "on_update": "document_manager.document_manager.services.search_index.enqueue_index_file",
        "on_trash": "document_manager.document_manager.services.search_index.enqueue_deindex_file",
    },
}

# =============================================================================
# Scheduled Tasks
# =============================================================================
scheduler_events = {
    "daily": [
        "document_manager.document_manager.services.search_index.reconcile_index",
        "document_manager.document_manager.doctype.business_activity_log.business_activity_log.cleanup_old_logs",
    ],
    "cron": {
        # Integrity check every Sunday at 2 AM
        "0 2 * * 0": [
            "document_manager.document_manager.services.backup_service.schedule_integrity_check",
        ],
    },
}

# =============================================================================
# Permission Query Conditions — filter by access_level for Reader role
# =============================================================================
permission_query_conditions = {
    "Archival File": "document_manager.document_manager.permissions.archival_file_query",
    "Archive Document": "document_manager.document_manager.permissions.archive_document_query",
}

has_permission = {
    "Archival File": "document_manager.document_manager.permissions.has_archival_file_permission",
    "Archive Document": "document_manager.document_manager.permissions.has_archive_document_permission",
}

# =============================================================================
# Jinja template helpers (for Print Formats, Portal pages)
# =============================================================================
# jinja = {
#     "methods": [
#         "document_manager.document_manager.utils.jinja_helpers",
#     ],
# }

# =============================================================================
# Override default Frappe whitelisted methods (if needed)
# =============================================================================
# override_whitelisted_methods = {}

# =============================================================================
# Installation hooks
# =============================================================================
# after_install = "document_manager.document_manager.setup.after_install"
after_migrate = "document_manager.document_manager.setup.after_migrate"
