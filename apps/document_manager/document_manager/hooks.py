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

web_include_css = [
    "/assets/document_manager/css/theme-tokens.css",
    "/assets/document_manager/css/document-manager-ui.css",
]

web_include_js = [
    "/assets/document_manager/js/dm-portal.js",
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

# Audit trail: every business DocType also reports create / update / delete to the activity log.
_AUDIT_HANDLER = "document_manager.document_manager.services.audit.audit_doc_event"
_AUDITED = (
    "Fonds", "Record Group", "Catalog", "Archival File", "Archive Document",
    "Archival Agency", "Document Group", "Document Type Category", "Classification Scheme",
    "Confidentiality Level", "Storage Warehouse", "Quick Entry Dictionary",
    "Reader", "Reader Group", "Usage Request", "Copy Request", "Reader Feedback",
    "Backup Batch", "Restore Batch", "Integrity Check",
    "Organization Info", "Reader Settings", "Document Manager Settings",
)
for _doctype in _AUDITED:
    _events = doc_events.setdefault(_doctype, {})
    for _event in ("after_insert", "on_update", "on_update_after_submit", "on_trash"):
        _existing = _events.get(_event)
        _events[_event] = [_existing, _AUDIT_HANDLER] if isinstance(_existing, str) else [*(_existing or []), _AUDIT_HANDLER]

on_login = "document_manager.document_manager.services.audit.on_login"
on_logout = "document_manager.document_manager.services.audit.on_logout"

# =============================================================================
# Scheduled Tasks
# =============================================================================
scheduler_events = {
    "daily": [
        "document_manager.document_manager.services.search_index.reconcile_index",
        "document_manager.document_manager.doctype.business_activity_log.business_activity_log.cleanup_old_logs",
        "document_manager.document_manager.doctype.archival_file.archival_file.check_retention_periods",
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
    "Fonds": "document_manager.document_manager.permissions.fonds_query",
    "Record Group": "document_manager.document_manager.permissions.record_group_query",
    "Catalog": "document_manager.document_manager.permissions.catalog_query",
    "Usage Request": "document_manager.document_manager.permissions.usage_request_query",
    "Copy Request": "document_manager.document_manager.permissions.copy_request_query",
    "Reader Feedback": "document_manager.document_manager.permissions.reader_feedback_query",
    "Reader": "document_manager.document_manager.permissions.reader_query",
}

has_permission = {
    "Archival File": "document_manager.document_manager.permissions.has_archival_file_permission",
    "Archive Document": "document_manager.document_manager.permissions.has_archive_document_permission",
    "Fonds": "document_manager.document_manager.permissions.has_fonds_permission",
    "Record Group": "document_manager.document_manager.permissions.has_record_group_permission",
    "Catalog": "document_manager.document_manager.permissions.has_catalog_permission",
    "Usage Request": "document_manager.document_manager.permissions.has_usage_request_permission",
    "Copy Request": "document_manager.document_manager.permissions.has_copy_request_permission",
    "Reader Feedback": "document_manager.document_manager.permissions.has_reader_feedback_permission",
    "Reader": "document_manager.document_manager.permissions.has_reader_permission",
}

# =============================================================================
# Jinja template helpers (for Print Formats, Portal pages)
# =============================================================================
jinja = {
    "methods": [
        "document_manager.document_manager.permissions.dm_is_staff",
        "document_manager.document_manager.permissions.dm_display_name",
    ],
}

# =============================================================================
# Override default Frappe whitelisted methods (if needed)
# =============================================================================
# override_whitelisted_methods = {}

# =============================================================================
# Installation hooks
# =============================================================================
after_install = "document_manager.document_manager.setup.after_install"
after_migrate = "document_manager.document_manager.setup.after_migrate"

# =============================================================================
# Login Redirects
# =============================================================================
role_home_page = {
    "Document Admin": "dashboard",
    "Cataloger": "dashboard",
    "Reading Room Officer": "dashboard",
    "Preservation Officer": "dashboard",
    "Reader": "portal",
    "System Manager": "dashboard"
}
