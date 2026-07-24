# Build-log 02 — Mô hình phân cấp 5 tầng

## Mục tiêu
Tạo 5 Doctype chính theo cấu trúc phân cấp chuẩn lưu trữ: Phông → Khối → Mục lục → Hồ sơ → Văn bản. Mỗi tầng liên kết với tầng cha qua Link field, có auto-fetch để tự động điền thông tin phân cấp.

## Danh sách Doctype đã tạo

| Doctype | Tầng | Parent Link | Naming | Fields chính |
|---------|------|-------------|--------|-------------|
| Fonds | 1 | — | FONDS-#### | fonds_name, fonds_code, archival_agency, start/end_year, total_shelf_meters, total_files |
| Record Group | 2 | fonds → Fonds | RG-#### | group_title, group_code, fonds, start/end_year |
| Catalog | 3 | record_group → Record Group | CAT-#### | catalog_title, catalog_number, record_group, fonds (fetch) |
| Archival File | 4 | catalog → Catalog | AF-##### | file_title, file_number, catalog, record_group (fetch), fonds (fetch), confidentiality_level, storage_warehouse, status |
| Archive Document | 5 | archival_file → Archival File | DOC-###### | document_title, file_attachment (Attach), file_type, checksum, storage_tier, content_text, search_index_status, s3_key |

## Code/file đã thay đổi
- `doctype/fonds/` — Controller: validate year range, auto-update total_files count
- `doctype/record_group/` — Controller: validate year range
- `doctype/catalog/` — Controller: validate year range, auto-fetch fonds from record_group
- `doctype/archival_file/` — Controller: validate dates, auto-update document count, cascade update to parent Fonds
- `doctype/archive_document/` — Controller: auto-detect file_type, compute_checksum (SHA-256), hooks for future S3/Meilisearch integration

## Quyết định kỹ thuật
- **Auto-fetch pattern**: Catalog fetches `fonds` from Record Group; Archival File fetches `record_group` + `fonds` from Catalog; Archive Document fetches full hierarchy. Avoids redundant user input while maintaining denormalized references for fast querying.
- **Naming convention**: Incrementing format (FONDS-####, AF-#####, DOC-######) cho ID ngắn gọn, dễ đọc. DOC dùng 6 chữ số (tối đa 999,999) phù hợp quy mô lớn.
- **Archive Document fields**: `content_text` (Long Text) lưu extracted text, `search_index_status` track trạng thái index, `storage_tier` cho tiered storage — tất cả chuẩn bị sẵn cho Giai đoạn 5.
- **Cascade count updates**: Archive Document → Archival File → Fonds — giữ tổng số hồ sơ/văn bản luôn chính xác.

## Rủi ro/Lưu ý
- **fetch_from**: Khi Record Group thay đổi Fonds, Catalog đã tạo sẽ không tự cập nhật fonds — cần migration patch nếu cho phép thay đổi parent
- **DOC-###### naming**: Hash naming sẽ tốt hơn cho distributed systems, nhưng sequential đủ cho single-instance
- **content_text Long Text**: MariaDB lưu TEXT type (64KB max) — với tài liệu dài hơn cần chuyển sang LONGTEXT hoặc chỉ lưu phần đầu + đẩy full text vào Meilisearch

## Việc cần làm tiếp
→ Giai đoạn 3: Biên mục tài liệu (Search page, Print Format)
