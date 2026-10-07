# -*- coding: utf-8 -*-
"""Shared constants of the staff UI (`/dashboard`).

`MASTERS` (catalogues) and `ARCHIVE_SCREENS` (cataloguing) list the DocTypes the generic list /
form / tree screens may manage. The generic API (`api/crud.py`, `api/meta.py`) refuses every other
DocType, so adding a screen to the registry is the only way to expose a DocType to it. Permissions
still decide who may read or change what.

Optional keys of an entry:
  hide         fields the generic form never shows (system-managed, or handled by a dedicated panel)
  list_fields  columns of the list, when they should differ from the DocType's "in list view"
  suggest      {field: Dictionary Type}: the field offers the values of that quick-entry dictionary
  tree_filter  field that selects the list a tree belongs to (dictionary values)
"""

STAFF_HOME = "/dashboard"

# sidebar sections
GROUP_CATALOGUES = "Danh mục"
GROUP_CATALOGUING = "Biên mục"
GROUP_READERS = "Độc giả"
GROUP_SLIPS = "Khai thác tài liệu"

# `slug` is the URL segment: /dashboard/danh-muc/<slug>
MASTERS = [
    {"doctype": "Archival Agency", "slug": "co-quan-luu-tru", "label": "Cơ quan lưu trữ", "icon": "building-2"},
    {"doctype": "Fonds", "slug": "phong-luu-tru", "label": "Phông lưu trữ", "icon": "library"},
    {"doctype": "Document Type Category", "slug": "loai-hinh-tai-lieu", "label": "Loại hình tài liệu", "icon": "file-type"},
    {"doctype": "Document Group", "slug": "nhom-tai-lieu", "label": "Nhóm tài liệu", "icon": "layers"},
    {"doctype": "Storage Warehouse", "slug": "kho-luu-tru", "label": "Kho, giá, hộp lưu trữ", "icon": "warehouse"},
    {"doctype": "Confidentiality Level", "slug": "muc-do-mat", "label": "Mức độ mật", "icon": "shield-check"},
    {"doctype": "Classification Scheme", "slug": "khung-phan-loai", "label": "Khung phân loại hồ sơ", "icon": "network"},
    {"doctype": "Dictionary Type", "slug": "loai-tu-dien", "label": "Loại từ điển", "icon": "book-a"},
    {"doctype": "Quick Entry Dictionary", "slug": "tu-dien", "label": "Từ điển nhập nhanh", "icon": "book-open-text",
     "tree_filter": "dictionary_type"},
]

# Dictionary types the cataloguing forms draw suggestions from (created by the cataloguers as needed).
DICTIONARY_AUTHOR = "Cơ quan ban hành"
DICTIONARY_LANGUAGE = "Ngôn ngữ"

ARCHIVE_SCREENS = [
    {"doctype": "Record Group", "slug": "khoi-tai-lieu", "label": "Khối tài liệu", "icon": "layers",
     "list_fields": ["group_title", "group_code", "fonds", "status"]},
    {"doctype": "Catalog", "slug": "muc-luc", "label": "Mục lục tài liệu", "icon": "book-open-text",
     "list_fields": ["catalog_title", "catalog_number", "record_group", "fonds"]},
    {"doctype": "Archival File", "slug": "ho-so", "label": "Hồ sơ lưu trữ", "icon": "folder",
     "list_fields": ["file_number", "file_title", "catalog", "status", "confidentiality_level", "total_documents"]},
    {"doctype": "Archive Document", "slug": "van-ban", "label": "Văn bản, tài liệu", "icon": "file-text",
     "list_fields": ["document_number", "document_title", "document_date", "author", "file_type",
                     "file_size_kb", "search_index_status"],
     # system-managed or shown by the file panel instead of the form
     "hide": ["file_attachment", "file_type", "file_size_kb", "checksum", "version", "preview_url", "storage_tier",
              "gridfs_file_id", "gridfs_preview_id", "last_accessed", "search_index_status", "content_text"],
     "suggest": {"author": DICTIONARY_AUTHOR}},
]

# Reader management screens: /dashboard/doc-gia/<slug>. `readonly` fields are shown but changed only by an action.
READER_SCREENS = [
    {"doctype": "Reader", "slug": "doc-gia", "label": "Danh sách độc giả", "icon": "users",
     "list_fields": ["full_name", "email", "phone", "organization", "reader_group", "is_active"],
     "readonly": ["user"]},
    {"doctype": "Reader Group", "slug": "nhom-doc-gia", "label": "Nhóm độc giả", "icon": "shield-check",
     "list_fields": ["group_name", "max_confidentiality_priority", "approval_mode", "is_default", "is_active"]},
    {"doctype": "Request Template", "slug": "mau-phieu", "label": "Mẫu phiếu, mẫu đăng ký", "icon": "file-type",
     "list_fields": ["template_name", "kind", "is_active", "title"]},
]
# Single DocTypes edited as one form (no list): /dashboard/doc-gia/<slug>
SETTINGS_SCREENS = [
    {"doctype": "Reader Settings", "slug": "thiet-lap-doc-gia", "label": "Thiết lập độc giả", "icon": "settings"},
]

REGISTRY = {entry["doctype"]: entry for entry in [*MASTERS, *ARCHIVE_SCREENS, *READER_SCREENS, *SETTINGS_SCREENS]}
MASTER_BY_DOCTYPE = REGISTRY  # kept for older imports

# Files accepted for upload (documents). Legacy Office formats are stored but not text-extracted.
UPLOAD_EXTENSIONS = ["pdf", "docx", "xlsx", "doc", "xls", "jpg", "jpeg", "png", "tif", "tiff"]
UPLOAD_MAX_MB = 100

# Screens still served by the previous server-rendered pages while they are rebuilt in the SPA.
# (label, href, DocType used to decide whether the user sees it, sidebar section)
LEGACY_LINKS = [
    ("Thống kê tài liệu", "/reports/thong_ke_tai_lieu", "Archive Document", "Báo cáo"),
    ("Thống kê khai thác", "/reports/thong_ke_khai_thac", "Usage Request", "Báo cáo"),
    ("Đợt sao lưu", "/backup_batches", "Backup Batch", "Bảo quản"),
    ("Kiểm tra toàn vẹn", "/integrity_checks", "Integrity Check", "Bảo quản"),
    ("Khôi phục dữ liệu", "/restore_batches", "Restore Batch", "Bảo quản"),
    ("Nhật ký hệ thống", "/business_activity_log", "Business Activity Log", "Quản trị"),
    ("Thiết lập hệ thống", "/document_manager_settings", "Document Manager Settings", "Quản trị"),
    ("Thông tin đơn vị", "/app/organization-info", "Organization Info", "Quản trị"),
    ("Cơ cấu tổ chức", "/app/organization-unit", "Organization Unit", "Quản trị"),
]
