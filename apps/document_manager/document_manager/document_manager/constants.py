# -*- coding: utf-8 -*-
"""Shared constants of the staff UI (`/dashboard`).

`MASTERS` lists the DocTypes the generic list / form / tree screens may manage. The generic API
(`api/crud.py`, `api/meta.py`) refuses every other DocType, so adding a screen to the registry is
the only way to expose a DocType to it. Permissions still decide who may read or change what.
"""

STAFF_HOME = "/dashboard"

# group -> label of the sidebar section
GROUP_CATALOGUES = "Danh mục"

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

MASTER_BY_DOCTYPE = {m["doctype"]: m for m in MASTERS}

# Screens still served by the previous server-rendered pages while they are rebuilt in the SPA.
# (label, href, DocType used to decide whether the user sees it, sidebar section)
LEGACY_LINKS = [
    ("Khối tài liệu", "/record_groups", "Record Group", "Biên mục"),
    ("Mục lục tài liệu", "/catalogs", "Catalog", "Biên mục"),
    ("Hồ sơ lưu trữ", "/archival_files", "Archival File", "Biên mục"),
    ("Văn bản, tài liệu", "/archive_documents", "Archive Document", "Biên mục"),
    ("Tìm kiếm toàn văn", "/portal", "Archive Document", "Biên mục"),
    ("Hồ sơ độc giả", "/readers", "Reader", "Độc giả & khai thác"),
    ("Nhóm độc giả", "/app/reader-group", "Reader Group", "Độc giả & khai thác"),
    ("Phiếu yêu cầu sử dụng", "/usage_requests", "Usage Request", "Độc giả & khai thác"),
    ("Phiếu sao chụp", "/copy_requests", "Copy Request", "Độc giả & khai thác"),
    ("Phản hồi độc giả", "/reader_feedbacks", "Reader Feedback", "Độc giả & khai thác"),
    ("Thiết lập độc giả", "/reader_settings", "Reader Settings", "Độc giả & khai thác"),
    ("Thống kê tài liệu", "/reports/thong_ke_tai_lieu", "Archive Document", "Báo cáo"),
    ("Thống kê khai thác", "/reports/thong_ke_khai_thac", "Usage Request", "Báo cáo"),
    ("Đợt sao lưu", "/backup_batches", "Backup Batch", "Bảo quản"),
    ("Kiểm tra toàn vẹn", "/integrity_checks", "Integrity Check", "Bảo quản"),
    ("Khôi phục dữ liệu", "/restore_batches", "Restore Batch", "Bảo quản"),
    ("Nhật ký hệ thống", "/business_activity_log", "Business Activity Log", "Quản trị"),
    ("Thiết lập hệ thống", "/document_manager_settings", "Document Manager Settings", "Quản trị"),
    ("Thông tin đơn vị", "/organization_info", "Organization Info", "Quản trị"),
]
