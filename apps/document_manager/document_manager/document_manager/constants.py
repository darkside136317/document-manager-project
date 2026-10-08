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
  drawer_width width of the record drawer when a form needs more room than the default (a wide grid)
"""

STAFF_HOME = "/dashboard"

# sidebar sections
GROUP_CATALOGUES = "Danh mục"
GROUP_CATALOGUING = "Biên mục"
GROUP_READERS = "Độc giả"
GROUP_SLIPS = "Khai thác tài liệu"
GROUP_REPORTS = "Thống kê, báo cáo"
GROUP_EXCHANGE = "Trao đổi dữ liệu"
GROUP_PRESERVATION = "Bảo quản"
GROUP_ADMIN = "Quản trị"

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
     "list_fields": ["file_number", "file_title", "catalog", "status", "confidentiality_level", "total_documents"],
     "search_fields": ["file_title", "file_number"]},
    {"doctype": "Archive Document", "slug": "van-ban", "label": "Văn bản, tài liệu", "icon": "file-text",
     "list_fields": ["document_number", "document_title", "document_date", "author", "file_type",
                     "file_size_kb", "search_index_status"],
     "search_fields": ["document_title", "document_number", "author"],  # not the link columns: they only slow the scan
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

# Inventory of the fonds (tổng kiểm kê): /dashboard/kiem-ke
INVENTORY_SCREENS = [
    {"doctype": "Inventory Check", "slug": "kiem-ke", "label": "Tổng kiểm kê phông", "icon": "clipboard-check",
     "list_fields": ["check_title", "check_date", "fonds", "status", "total_difference"],
     "hide": ["completed_on"], "drawer_width": "1080px"},
]

# Administration screens on the generic forms: /dashboard/quan-tri/<slug> (users, roles, log and monitor have their own pages)
ADMIN_SCREENS = [
    {"doctype": "Organization Info", "slug": "thong-tin-don-vi", "label": "Thông tin đơn vị", "icon": "building-2"},
    {"doctype": "Organization Unit", "slug": "co-cau-to-chuc", "label": "Cơ cấu tổ chức", "icon": "network"},
    {"doctype": "Staff Group", "slug": "nhom-can-bo", "label": "Nhóm cán bộ", "icon": "users",
     "list_fields": ["group_name", "description"]},
    {"doctype": "Document Manager Settings", "slug": "thiet-lap-he-thong", "label": "Thiết lập hệ thống", "icon": "settings"},
]

REGISTRY = {entry["doctype"]: entry for entry in [*MASTERS, *ARCHIVE_SCREENS, *READER_SCREENS, *SETTINGS_SCREENS,
                                                   *INVENTORY_SCREENS, *ADMIN_SCREENS]}
MASTER_BY_DOCTYPE = REGISTRY  # kept for older imports

# Files accepted for upload (documents). Legacy Office formats are stored but not text-extracted.
UPLOAD_EXTENSIONS = ["pdf", "docx", "xlsx", "doc", "xls", "jpg", "jpeg", "png", "tif", "tiff"]
UPLOAD_MAX_MB = 100

# Screens still served by the previous server-rendered pages while they are rebuilt in the SPA.
# (label, href, DocType used to decide whether the user sees it, sidebar section)
LEGACY_LINKS = []  # every screen is in the staff app now (kept so that older imports keep working)


# Roles the staff app may give to a user (never System Manager / Administrator) and how they are described.
STAFF_ASSIGNABLE_ROLES = ("Document Admin", "Cataloger", "Reading Room Officer", "Archive Leader", "Preservation Officer")
ROLE_INFO = {
    "Document Admin": {"label": "Quản trị tài liệu", "group": "Quản trị",
                       "description": "Quản trị toàn bộ hệ thống: người dùng, thiết lập, sao lưu, trao đổi dữ liệu, nhật ký; có mọi quyền nghiệp vụ."},
    "Archive Leader": {"label": "Lãnh đạo", "group": "Quản trị",
                       "description": "Xem toàn bộ dữ liệu và báo cáo; duyệt các phiếu yêu cầu cần lãnh đạo duyệt."},
    "Cataloger": {"label": "Biên mục viên", "group": "Tác nghiệp",
                  "description": "Biên mục phông, mục lục, hồ sơ, văn bản và danh mục; tải tệp; kiểm kê phông."},
    "Reading Room Officer": {"label": "Cán bộ phòng đọc", "group": "Tác nghiệp",
                             "description": "Quản lý độc giả, tiếp nhận, duyệt, giao và nhận trả phiếu; xử lý góp ý."},
    "Preservation Officer": {"label": "Cán bộ bảo quản", "group": "Tác nghiệp",
                             "description": "Sao lưu, kiểm tra toàn vẹn và phục hồi tài liệu; xem kho lưu trữ."},
}
# DocTypes shown in the permission matrix, by section
ROLE_MATRIX = (
    ("Biên mục", ("Fonds", "Record Group", "Catalog", "Archival File", "Archive Document", "Inventory Check")),
    ("Danh mục", ("Archival Agency", "Document Type Category", "Document Group", "Storage Warehouse", "Confidentiality Level",
                  "Classification Scheme", "Quick Entry Dictionary")),
    ("Độc giả và khai thác", ("Reader", "Reader Group", "Request Template", "Usage Request", "Copy Request", "Reader Feedback",
                              "Reader Registration")),
    ("Bảo quản", ("Backup Batch", "Integrity Check", "Restore Batch")),
    ("Quản trị", ("Document Manager Settings", "Reader Settings", "Organization Info", "Organization Unit", "Staff Group",
                  "Business Activity Log", "Data Exchange Job")),
)
