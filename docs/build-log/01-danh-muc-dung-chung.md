# Build-log 01 — Danh mục dùng chung (Master Data)

## Mục tiêu
Tạo các Doctype danh mục đơn giản (Master Data), làm nền tảng Link field cho toàn bộ hệ thống. Đây là các dữ liệu dùng chung, chuẩn hóa để sử dụng xuyên suốt các phân hệ.

## Danh sách Doctype đã tạo

| Doctype | Mục đích | Kiểu | Fields chính |
|---------|----------|------|-------------|
| Archival Agency | Cơ quan lưu trữ | Setup | agency_name, agency_code, agency_type, address, phone, email |
| Document Type Category | Loại hình tài liệu | Setup | type_name, type_code, description |
| Document Group | Nhóm tài liệu | Setup | group_name, group_code, description |
| Storage Warehouse | Kho lưu trữ | Setup, **Tree** | warehouse_name, warehouse_code, warehouse_type, parent_warehouse, archival_agency |
| Confidentiality Level | Mức độ mật | Setup | level_name, level_code, priority |
| Classification Scheme | Khung phân loại | Setup, **Tree** | scheme_name, scheme_code, parent_scheme |
| Quick Entry Dictionary | Từ điển nhập nhanh | Setup | dictionary_type, entry_value, parent_entry, sort_order |

## Code/file đã thay đổi
- `doctype/archival_agency/` — JSON + Python controller (validate uppercase agency_code)
- `doctype/document_type_category/` — JSON + Python controller
- `doctype/document_group/` — JSON + Python controller
- `doctype/storage_warehouse/` — JSON + Python NestedSet controller (Tree)
- `doctype/confidentiality_level/` — JSON + Python controller
- `doctype/classification_scheme/` — JSON + Python NestedSet controller (Tree)
- `doctype/quick_entry_dictionary/` — JSON + Python controller (validate parent same type)

## Quyết định kỹ thuật
- **Storage Warehouse dùng Tree (NestedSet)**: cho phép cấu trúc Kho → Phòng → Giá → Hộp, truy vấn con/cháu nhanh bằng lft/rgt
- **Classification Scheme dùng Tree**: tương tự, hỗ trợ khung phân loại đa cấp
- **Quick Entry Dictionary**: thay vì tạo riêng Tree Doctype cho từ điển đa cấp, dùng self-referencing Link field (`parent_entry`) + validation cùng `dictionary_type` — linh hoạt hơn, không cần tạo nhiều Doctype
- **Confidentiality Level**: dùng `priority` (số nguyên) thay vì hardcode tên — dễ mở rộng thêm mức mật mới

## Rủi ro/Lưu ý
- Storage Warehouse Tree: khi dữ liệu lớn (>10,000 nodes), rebuild tree (`frappe.utils.nestedset.rebuild_tree`) có thể chậm — cần monitor
- Quick Entry Dictionary: với lượng lớn giá trị từ điển, cần index trên `(dictionary_type, entry_value)` — sẽ thêm ở giai đoạn tối ưu

## Việc cần làm tiếp
→ Giai đoạn 2: Mô hình phân cấp 5 tầng
