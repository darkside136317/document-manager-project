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

# The staff app (/dashboard) and the reader site (/portal and the public pages) bring their own styles and scripts; nothing is
# injected into Frappe's own pages (/login, the Desk), so the app has no *_include_css / *_include_js hooks.

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
                "Archive Leader",
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
    # The reader hears (bell of the reader site) when an officer decides on a slip or answers a feedback.
    "Usage Request": {
        "on_update_after_submit": "document_manager.document_manager.services.notify.on_slip_change",
    },
    "Copy Request": {
        "on_update_after_submit": "document_manager.document_manager.services.notify.on_slip_change",
    },
    "Reader Feedback": {
        "on_update": "document_manager.document_manager.services.notify.on_feedback_change",
    },
}

# The staff app is a single-page application served by www/dashboard; its client-side routes
# (/dashboard/danh-muc/...) all render the same page.
website_route_rules = [
    {"from_route": "/dashboard/<path:app_path>", "to_route": "dashboard"},
    # Public pages about the unit: one page, five sections.
    {"from_route": "/<any('gioi-thieu', 'lanh-dao', 'co-cau', 'lien-he', 'huong-dan'):section>", "to_route": "don-vi"},
    # Reader site: lists and details share a page, the detail adds the record name.
    {"from_route": "/portal/ho-so/<name>", "to_route": "portal/ho-so"},
    {"from_route": "/portal/van-ban/<name>", "to_route": "portal/van-ban"},
    {"from_route": "/portal/phieu/<name>", "to_route": "portal/phieu"},
    {"from_route": "/portal/sao-chep/<name>", "to_route": "portal/sao-chep"},
    {"from_route": "/portal/gop-y/<name>", "to_route": "portal/gop-y"},
]

# The unit's introduction is the public home page of the site; signed-in users go to their role's page.
home_page = "gioi-thieu"

# The catalogue screens moved into the staff app; old bookmarks keep working.
website_redirects = [
    {"source": "organization_info", "target": "/app/organization-info", "redirect_http_status": 301},
    # The document viewer moved into the reader site; the query string (?name=DOC-...) is kept.
    {"source": "portal_document", "target": "/portal/van-ban", "redirect_http_status": 301,
     "forward_query_parameters": True},
    # the report pages moved into the staff app
    {"source": "reports/thong_ke_tai_lieu", "target": "/dashboard/bao-cao/thong-ke-phong", "redirect_http_status": 301},
    {"source": "reports/thong_ke_khai_thac", "target": "/dashboard/bao-cao/thong-ke-phieu", "redirect_http_status": 301},
    {"source": "reports(/.*)?", "target": "/dashboard/bao-cao", "redirect_http_status": 301},
    # preservation and administration moved into the staff app
    {"source": "backup_batches(/.*)?", "target": "/dashboard/bao-quan/sao-luu", "redirect_http_status": 301},
    {"source": "integrity_checks(/.*)?", "target": "/dashboard/bao-quan/kiem-tra", "redirect_http_status": 301},
    {"source": "restore_batches(/.*)?", "target": "/dashboard/bao-quan/khoi-phuc", "redirect_http_status": 301},
    {"source": "business_activity_log(/.*)?", "target": "/dashboard/quan-tri/nhat-ky", "redirect_http_status": 301},
    {"source": "document_manager_settings", "target": "/dashboard/quan-tri/thiet-lap-he-thong", "redirect_http_status": 301},
] + [
    {"source": f"{old}(/.*)?", "target": f"/dashboard/danh-muc/{slug}", "redirect_http_status": 301}
    for old, slug in (
        ("archival_agencies", "co-quan-luu-tru"), ("fonds", "phong-luu-tru"),
        ("document_type_categories", "loai-hinh-tai-lieu"), ("document_groups", "nhom-tai-lieu"),
        ("storage_warehouses", "kho-luu-tru"), ("confidentiality_levels", "muc-do-mat"),
        ("classification_schemes", "khung-phan-loai"), ("quick_entry_dictionaries", "tu-dien"),
    )
] + [
    {"source": f"{old}(/.*)?", "target": "/dashboard/bien-muc", "redirect_http_status": 301}
    for old in ("record_groups", "catalogs", "archival_files", "archive_documents")
]

# Audit trail: every business DocType also reports create / update / delete to the activity log.
_AUDIT_HANDLER = "document_manager.document_manager.services.audit.audit_doc_event"
_AUDITED = (
    "Fonds", "Record Group", "Catalog", "Archival File", "Archive Document",
    "Archival Agency", "Document Group", "Document Type Category", "Classification Scheme",
    "Confidentiality Level", "Storage Warehouse", "Quick Entry Dictionary",
    "Reader", "Reader Group", "Usage Request", "Copy Request", "Reader Feedback",
    "Backup Batch", "Restore Batch", "Integrity Check",
    "Organization Info", "Organization Unit", "Reader Settings", "Document Manager Settings",
    "Reader Registration", "Request Template", "Inventory Check", "Staff Group", "Data Exchange Job",
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
        "document_manager.document_manager.services.overdue.mark_overdue_and_remind",
        "document_manager.document_manager.services.preservation.backup.run_scheduled",
    ],
    "cron": {
        # Integrity check every Sunday at 2 AM
        "0 2 * * 0": [
            "document_manager.document_manager.services.preservation.integrity.schedule_integrity_check",
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
        "document_manager.document_manager.services.templates.dm_print_options",
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
    "Archive Leader": "dashboard",
    "Preservation Officer": "dashboard",
    "Reader": "portal",
    "System Manager": "dashboard"
}
