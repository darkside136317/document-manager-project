# Ma trận truy vết: Phụ lục 03 → sản phẩm

Mỗi dòng của *Phụ lục 03 – Danh sách tính năng phần mềm quản lý và khai thác hồ sơ số hóa* được nối tới: màn hình
hoặc đường dẫn, API (module `document_manager/document_manager/api/…` hoặc dịch vụ), và các kiểm thử chứng minh.

Cách đọc cột kiểm thử:

- **Py** – module Python trong `apps/document_manager/document_manager/tests/` (`test_<tên>.py`), kèm tên rút gọn của test.
- **TĐ** – luồng trình duyệt trong `scripts/e2e/ui/<tên>.mjs` (Playwright, chạy trên stack thật).
- **HTTP** – `scripts/e2e/e2e_http.py` (ma trận quyền và địa chỉ cũ).
- **vitest** – `apps/document_manager/frontend/tests/<tên>.test.js`.

Đường dẫn bắt đầu bằng `/dashboard` là ứng dụng cán bộ (Vue 3); `/portal` và các trang công khai là giao diện độc giả (Jinja + Alpine).

## 1. Phân hệ Khai thác trực tuyến

| Yêu cầu | Màn hình / đường dẫn | API / dịch vụ | Kiểm thử |
|---|---|---|---|
| Giao diện khai thác trực tuyến cho độc giả và người dùng được cấp quyền | `/portal`, đăng nhập `/dang-nhap` | `www/_reader_ui.py`, `policy.get_reader_scope` | Py `reader_pages` (36), `policy` (15); TĐ `reader` |
| Giới thiệu đơn vị, lãnh đạo, cơ cấu tổ chức, liên hệ | `/gioi-thieu`, `/lanh-dao`, `/co-cau`, `/lien-he`, `/huong-dan` | `services/public_site.py` (Organization Info, Organization Leader, Organization Unit) | Py `reader_site`: profile_has_defaults, profile_hides_hidden_leaders, unit_tree_nests…; TĐ `reader` (trang công khai) |
| Tìm kiếm hồ sơ lưu trữ cơ bản và nâng cao | `/portal` (tab Hồ sơ), `/portal/ho-so/<tên>` | `api/search.search_archival_files`, `search_service.search_files` | Py `search_service`: basic_file_search…, advanced_file_filters…, date_filters…; TĐ `reader` |
| Tìm kiếm văn bản, tài liệu cơ bản và nâng cao | `/portal` (tab Văn bản), `/portal/van-ban/<tên>` | `api/search.search_documents`, `search_fulltext`; Meilisearch, dự phòng cơ sở dữ liệu | Py `search_service`: free_text_query…, falls_back…, readers_never_find_draft…; `volume_guards`; TĐ `reader` |
| Đăng ký, đăng nhập của độc giả | `/dang-ky`, `/dang-nhap`, `/quen-mat-khau`, `/dat-mat-khau?key=` | `api/registration.py`, `services/registration.py` | Py `reader_site`: registration_*, nobody_learns_whether_an_email…; TĐ `reader` (đăng ký → duyệt → đặt mật khẩu); HTTP |
| Quản lý danh mục, chi tiết phiếu yêu cầu sử dụng của độc giả | `/portal/phieu`, `/portal/phieu/<tên>` | `www/portal/phieu.py`, `api/requests.py` | Py `reader_pages`, `request_workflow`; TĐ `reader`, `slips` |
| Đưa hồ sơ, văn bản vào phiếu yêu cầu sử dụng | Nút "Thêm vào phiếu" trên kết quả tìm kiếm | `api/basket.add_to_basket`, `services/basket.py` | Py `reader_site`: adding_to_the_basket…, basket_refuses…, basket_follows_the_feature_flags…; TĐ `reader` |
| Gửi phiếu yêu cầu sử dụng cho phòng đọc | Trang chi tiết phiếu → "Gửi" | `api/requests.apply_action`, workflow `Usage Request Workflow` | Py `request_workflow`, `request_lifecycle`: a_slip_without_confidential_items…; TĐ `reader`, `slips` |
| Quản lý danh mục, chi tiết phiếu đăng ký sao chụp | `/portal/sao-chep`, `/portal/sao-chep/<tên>` | như trên (Copy Request) | Py `reader_pages`, `request_lifecycle`: copy_slips_follow_the_same_approval_rules; TĐ `reader` |
| Đưa hồ sơ, văn bản vào phiếu sao chụp | như phiếu sử dụng (giỏ riêng cho sao chụp) | `api/basket.py` | Py `reader_site`: copy_and_usage_baskets_are_separate |
| Gửi phiếu sao chụp cho phòng đọc | Trang chi tiết phiếu sao chụp | `api/requests.apply_action` | Py `request_lifecycle`; TĐ `reader` |
| Tiếp nhận góp ý của độc giả | `/portal/gop-y` → hàng đợi cán bộ `/dashboard/doc-gia/gop-y` | `api/requests.submit_feedback`, `api/feedback.py` | Py `reader_admin`: feedback_list_and_detail, feedback_is_for_the_reading_room…; `reader_site`: copy_slip_and_feedback_notify…; TĐ `reader`, `slips` |

Bổ sung cho độc giả: thông báo trong ứng dụng (`/portal/thong-bao`, `api/account.get_notifications`), tài khoản và đổi mật khẩu
(`/portal/tai-khoan`, `api/account.change_password`) – Py `reader_site`: notifications_are_private…, a_wrong_current_password…

## 2. Phân hệ Biên mục tài liệu lưu trữ

| Yêu cầu | Màn hình / đường dẫn | API / dịch vụ | Kiểm thử |
|---|---|---|---|
| Biên mục, cập nhật, quản lý thông tin tài liệu | `/dashboard/bien-muc` (cây Phông → Khối → Mục lục → Hồ sơ) | `api/archive.get_tree`, `api/crud.py` | Py `archive_api`: tree_walks…; `staff_api`; TĐ `cataloguing`; vitest `archive` |
| Thêm, sửa, xóa khối tài liệu | Ngăn kéo "Khối tài liệu" trên cây; `/dashboard/danh-muc`… hoặc màn hình `khoi-tai-lieu` | `api/crud.save|delete`, `services/archive/hierarchy.py` | Py `archive_api`: catalogue_records_are_created_edited_and_protected…; `audit_and_hierarchy`; TĐ `cataloguing` |
| Thêm, sửa, xóa mục lục tài liệu | như trên (mục lục là lá của cây) | như trên | như trên |
| Thêm, sửa, xóa hồ sơ lưu trữ | Ngăn kéo hồ sơ; `/dashboard/ho-so/<tên>` | `api/crud.py`, `api/archive.get_file_overview` | Py `archive_api`: file_overview_has_breadcrumb…; `staff_api`: a_record_that_is_still_used_cannot_be_deleted; TĐ `cataloguing` |
| Tìm kiếm cơ bản, nâng cao hồ sơ lưu trữ | `/dashboard/tim-kiem` (tab Hồ sơ), Ctrl+K | `search_service.search_files`, `api/search.py` | Py `search_service`; TĐ `cataloguing`; vitest `archive` |
| Thêm, sửa, xóa văn bản trong hồ sơ | `/dashboard/ho-so/<tên>` (tải nhiều tệp), `/dashboard/van-ban/<tên>` | `api/archive.add_document_from_file|attach_file|reindex_document`, `services/file_processor.py` | Py `archive_api`: a_document_is_created_from_an_uploaded_file, replacing_the_file…, only_allowed_file_types…, a_file_over_the_limit…; TĐ `cataloguing` |
| In ấn tài liệu lưu trữ | Nút "In" ở trang hồ sơ và văn bản (phiếu mô tả, mục lục hồ sơ) | `api/archive.print_urls`, `download_print_pdf`; print format "Archival File Contents", "Archive Document Standard" | Py `archive_api`: the_two_new_print_formats_render, the_print_formats_download_as_pdf, the_pdf_page_has_no_external_resources; TĐ `cataloguing` |
| Tìm kiếm cơ bản, nâng cao tài liệu lưu trữ | `/dashboard/tim-kiem` (tab Văn bản; có nội dung văn bản, làm nổi từ khóa) | `search_service.search_documents`, `search_index.py` | Py `search_service`, `volume_guards`; TĐ `cataloguing` |

## 3. Phân hệ Danh mục tài liệu

| Yêu cầu | Màn hình / đường dẫn | API / dịch vụ | Kiểm thử |
|---|---|---|---|
| Hệ thống danh mục dùng chung | `/dashboard/danh-muc/<slug>` (màn hình chung dựa trên `constants.MASTERS`) | `api/meta.get_doctype_ui`, `api/crud.py` | Py `staff_api`: every_registered_doctype_can_be_described, list_search_filter_sort_and_paging; TĐ `catalogues`; vitest `components`, `doctype` |
| Danh mục cơ quan lưu trữ | `co-quan-luu-tru` | Archival Agency qua `api/crud.py` | Py `staff_api`; TĐ `catalogues` |
| Danh mục phông lưu trữ | `phong-luu-tru` | Fonds | như trên |
| Danh mục loại hình tài liệu | `loai-hinh-tai-lieu` | Document Type Category | như trên |
| Danh mục nhóm tài liệu | `nhom-tai-lieu` | Document Group | như trên |
| Danh mục kho lưu trữ | `kho-luu-tru` (cây kho/phòng/giá/hộp) | Storage Warehouse (nested set) | Py `staff_api`: the_warehouse_tree_lists_roots_then_children; TĐ `catalogues` |
| Danh mục tính chất tài liệu: giá, hộp, hồ sơ, mức độ mật | `kho-luu-tru` (giá, hộp), `muc-do-mat` | Storage Warehouse, Confidentiality Level | Py `policy`, `p0_hardening` (cấp mức mật xuống văn bản); TĐ `catalogues` |
| Danh mục khung phân loại hồ sơ | `khung-phan-loai` (cây) | Classification Scheme | Py `staff_api`; TĐ `catalogues` |
| Danh mục từ điển phục vụ nhập nhanh | `tu-dien`, `loai-tu-dien`; gợi ý ở trường "Cơ quan ban hành" | Quick Entry Dictionary, Dictionary Type; `services/ui.suggest` | Py `archive_api`: author_suggests_the_values_of_the_matching_dictionary; TĐ `catalogues`, `cataloguing` |
| Từ điển đơn cấp và đa cấp | `loai-tu-dien` (một cấp/đa cấp), cây giá trị | Quick Entry Dictionary là nested set | Py `staff_api`: single_level_dictionary_rejects_parents, multi_level_dictionary_builds_a_tree…; TĐ `catalogues` |

## 4. Phân hệ Thống kê, Báo cáo

| Yêu cầu | Màn hình / đường dẫn | API / dịch vụ | Kiểm thử |
|---|---|---|---|
| Tổng hợp, thống kê, kết xuất báo cáo | `/dashboard/bao-cao` (trang chủ báo cáo), `/dashboard/bao-cao/<slug>` | `api/reports.list_reports|run_report|download_report|print_report`, `services/reports/` | Py `reports` (31): every_report_runs…, csv_has_a_bom…, xlsx_opens…; TĐ `reports`; HTTP (mọi báo cáo chạy trên dữ liệu thật) |
| Báo cáo phông lưu trữ | `phong` | `services/reports/archive.py` | Py `reports`: fonds_report_counts_every_level, fonds_report_filters_by_years_and_agency |
| Báo cáo mục lục tài liệu | `muc-luc` | như trên | Py `reports`: catalogue_report |
| Báo cáo hồ sơ lưu trữ | `ho-so` | như trên | Py `reports`: file_report_filters_pages_and_totals |
| Báo cáo văn bản, tài liệu lưu trữ | `van-ban` | như trên | Py `reports`: document_report_filters_by_author_date_and_type, a_search_text_is_matched_literally |
| Thống kê hồ sơ, tài liệu theo phông | `thong-ke-phong` (có biểu đồ) | như trên | Py `reports`: statistics_by_fonds_and_the_other_dimensions_agree; TĐ `reports` |
| Thống kê theo loại hình tài liệu, kho lưu trữ | `thong-ke-loai-hinh-kho` | như trên | Py `reports`: statistics_by_type_and_warehouse_roll_up_to_the_warehouse |
| Tổng kiểm kê phông tài liệu | `/dashboard/kiem-ke`, báo cáo `tong-kiem-ke` | `api/inventory.py`, DocType Inventory Check | Py `reports`: inventory_takes_the_figures…, a_check_is_completed_only_when_every_fonds_is_counted_then_it_is_locked…; TĐ `reports` |

Bổ sung: in báo cáo có đầu đề đơn vị và chữ ký (HTML, PDF) – Py `reports`: the_printout_carries_the_unit_header…, the_printout_as_a_pdf.

## 5. Phân hệ Xuất, nhập dữ liệu

| Yêu cầu | Màn hình / đường dẫn | API / dịch vụ | Kiểm thử |
|---|---|---|---|
| Trao đổi, kết xuất và nhập dữ liệu | `/dashboard/trao-doi-du-lieu` (Xuất / Nhập / Lịch sử) | `api/exchange.py`, `services/exchange/`, DocType Data Exchange Job | Py `exchange` (37); TĐ `exchange`; HTTP |
| Tìm kiếm và kết xuất dữ liệu ra XML | tab "Xuất" (bộ lọc giống màn hình tìm kiếm, xem trước số lượng) | `exchange.preview_export|start_export|download`, `services/exchange/exporter.py` | Py `exchange`: export_writes_the_tree…, the_search_that_selects_the_export…; TĐ `exchange` |
| Nhập dữ liệu từ XML vào cơ sở dữ liệu | tab "Nhập" (phân tích, chạy thử, chạy thật) | `exchange.analyze_import|start_import`, `importer.py` | Py `exchange`: what_was_exported_comes_back_the_same, importing_the_same_file_again_adds_nothing, a_dry_run_does_everything_but_write; hostile_files_are_refused…; TĐ `exchange`; HTTP (tệp độc hại bị từ chối) |
| Cho phép chọn các trường dữ liệu | bước "Chọn trường" theo từng cấp | `schema.py` (danh sách trường được phép), `exchange.capabilities` | Py `exchange`: export_fields_are_chosen_per_level…, created_records_get_only_the_chosen_fields…, update_mode_changes_only_the_chosen_fields…; vitest `exchange` |

Lược đồ và quy ước: `docs/XML_SCHEMA.md`; XSD tải về từ `exchange.download_schema`.

## 6. Phân hệ Quản lý độc giả

| Yêu cầu | Màn hình / đường dẫn | API / dịch vụ | Kiểm thử |
|---|---|---|---|
| Quản lý danh sách độc giả: thêm, sửa, xóa, tìm kiếm | `/dashboard/doc-gia/doc-gia`; hàng đợi đăng ký `/dashboard/doc-gia/dang-ky` | `api/crud.py`, `api/registration.py` | Py `reader_admin`: readers_are_managed_through_the_generic_screen, online_access_creates_the_account_once…; `reader_site`: officer_approval_creates_the_account…; TĐ `reader`, `slips` |
| Phân quyền độc giả khai thác theo nhóm quyền, nhóm chức năng | `/dashboard/doc-gia/nhom-doc-gia` (mức mật tối đa, 6 cờ tính năng, hạn mức, phông cấp phép cho cả nhóm), `/dashboard/doc-gia/doc-gia` (phông cấp phép riêng, có thời hạn), chế độ khai thác của phông (Công khai / Theo cấp phép / Nội bộ) | `policy.get_reader_scope|reader_scope_of`, `services/fonds_access.py`, `api/fonds_access.who_may_use`, DocType Reader Group, Reader, Reader Group Scope | Py `policy` (15); `fonds_access` (15): a_reader_sees_public_fonds_and_licensed_ones_only_once_granted, an_internal_fonds_is_never_open_to_readers, a_grant_counts_only_within_its_dates, the_staff_filing_for_a_reader_without_an_account_is_held_to_that_readers_rights, a_grant_taken_back_after_sending_stops_the_approval, the_due_date_never_passes_the_end_of_the_grant…, copies_follow_the_fonds_and_the_level; `search_service`: a_reader_cannot_widen_the_scope_with_a_filter; `request_lifecycle`: the_reader_group_decides_how_slips_are_approved; TĐ `slips` bước 18 |
| Quản lý phiếu yêu cầu sử dụng; thêm, sửa, xóa, tìm kiếm | `/dashboard/doc-gia/phieu-su-dung` (hàng đợi theo trạng thái, tìm kiếm, phân trang) | `api/slips.list_slips|get_slip|delete_draft` | Py `slip_queue` (11); TĐ `slips` |
| Đưa hồ sơ, văn bản vào phiếu yêu cầu sử dụng | Ngăn kéo "Thêm mục" trong phiếu; hoặc từ giỏ của độc giả | `api/requests.search_items`, `save_request` | Py `request_workflow`; `reader_ui_logic`; TĐ `slips` |
| Lãnh đạo duyệt hồ sơ, văn bản trong phiếu sử dụng | Vai trò Archive Leader: tab "Chờ lãnh đạo duyệt", quyết định từng mục | `api/slips.decide_items`, workflow có bước lãnh đạo | Py `request_lifecycle`: confidential_items_need_a_leader, the_officer_decides_item_by_item, a_slip_cannot_be_approved_with_every_item_turned_down; TĐ `slips` |
| Trả hồ sơ, tài liệu cho người dùng sau khi phê duyệt | Giao, nhận trả, gia hạn, quá hạn trên trang phiếu | `api/slips.receive_return|renew`, `services/lifecycle.py`, `services/overdue.py` | Py `request_lifecycle`: handing_over_starts_the_clock, receiving_the_return_records_the_condition…, renewal_*, daily_job_*; TĐ `slips` |
| Quản lý phiếu sao chụp: thêm, sửa, xóa, tìm kiếm | `/dashboard/doc-gia/phieu-sao-chup` | như trên (kind = copy) | Py `slip_queue`, `request_lifecycle`; TĐ `slips` |
| Đưa hồ sơ, văn bản vào phiếu sao chụp | như phiếu sử dụng | như trên | Py `reader_site`, `request_workflow` |
| Lãnh đạo duyệt phiếu sao chụp | như phiếu sử dụng | như trên | Py `request_lifecycle`: copy_slips_follow_the_same_approval_rules |
| Báo cáo, thống kê, in ấn thông tin độc giả và phiếu | Báo cáo `doc-gia`, `thong-ke-phieu`, `phieu-qua-han`, `tai-lieu-duoc-khai-thac`; in phiếu, phiếu lấy tài liệu, thẻ độc giả | `services/reports/readers.py`, print format Usage Request / Copy Request / Reader | Py `reports`: reader_report_counts_slips_per_reader, overdue_report_lists_what_is_still_out; `reader_admin`: slips_print_with_their_items…, the_reader_card_prints; TĐ `reports`, `slips` |
| Cấu hình mẫu phiếu yêu cầu, mẫu đăng ký | `/dashboard/doc-gia/mau-phieu` (trường hiển thị/bắt buộc, mục đích, đầu/cuối bản in) | DocType Request Template, `services/templates.py` | Py `reader_admin`: registration_template_decides_which_fields_are_asked, a_slip_needs_a_purpose_only_when_the_template_says_so, print_options_carry_the_header_and_footer; TĐ `slips` |
| Cấu hình tham số hệ thống phục vụ độc giả khai thác | `/dashboard/doc-gia/thiet-lap-doc-gia` | DocType Reader Settings (hạn mức, gia hạn, nhắc hạn, đăng ký) | Py `request_lifecycle`: items_per_slip_are_limited, slips_per_day_are_limited…, open_slips_are_limited; `reader_admin`: the_reader_settings_form_is_a_single_document; TĐ `slips` |

## 7. Phân hệ Bảo quản tài liệu

| Yêu cầu | Màn hình / đường dẫn | API / dịch vụ | Kiểm thử |
|---|---|---|---|
| Nghiệp vụ bảo quản, kiểm tra, sao lưu, khôi phục | `/dashboard/bao-quan/sao-luu`, `kiem-tra`, `khoi-phuc` | `api/preservation.py`, `services/preservation/` | Py `preservation` (39); TĐ `preservation`; HTTP |
| Sao lưu cơ sở dữ liệu tài liệu lưu trữ | "Sao lưu mới" → loại "Cơ sở dữ liệu" hoặc "Cả hai" | `preservation.start_backup`, `backup.run_db_backup`; tải về `download_backup` | Py `preservation`: the_database_dump_is_recorded_with_its_size_and_hash, a_failed_dump_is_an_error_and_a_combined_backup_is_then_partial, a_download_is_logged_stays_inside_the_backup_folder…; TĐ `preservation` bước 3 |
| Sao lưu tệp tài liệu lưu trữ | loại "Tệp tài liệu" (kho tệp theo nội dung, tăng dần, sha256) | `backup.run_files_backup`, `filestore.py` | Py `preservation`: the_store_keeps_one_blob_per_content…, a_file_backup_copies_every_file_and_lists_it, a_second_backup_copies_only_what_the_store_lacks, a_missing_or_damaged_source_is_reported_and_never_replaces_a_good_copy, a_stopped_backup_continues_from_its_cursor…; TĐ `preservation` bước 2 |
| Thêm, sửa, xóa đợt sao lưu | Danh sách đợt, ngăn kéo chi tiết (dừng, chạy tiếp, xóa), "Dọn đợt cũ" theo thời hạn giữ | `preservation.cancel|resume|delete_job|run_retention`, `backup.apply_retention` | Py `preservation`: a_job_is_cancelled_resumed_and_deleted_only_when_its_state_allows, a_running_backup_cannot_be_deleted, deleting_a_backup_removes_its_dump_manifest…, retention_deletes_old_batches_but_keeps_the_newest_good_ones, the_schedule_knows_when_a_backup_is_due; TĐ `preservation` bước 10 |
| Kiểm tra cơ sở dữ liệu tài liệu lưu trữ | "Kiểm tra mới" → "Cơ sở dữ liệu" hoặc "Siêu dữ liệu" | `preservation.start_check`, `integrity.DB_CHECKS|META_CHECKS` | Py `preservation`: database_checks_find_structure_problems_and_the_counters_can_be_fixed, a_clean_scope_is_complete…, metadata_checks_report_what_an_electronic_archive_should_describe; TĐ `preservation` bước 6; `scripts/perf/volume_check.py` (thời gian ở 1 triệu văn bản) |
| Kiểm tra từng tài liệu để phát hiện lỗi hoặc dữ liệu không đáp ứng nghiệp vụ lưu trữ điện tử | loại "Tệp tài liệu" / "Toàn bộ": còn tệp, đúng mã kiểm, đúng loại tệp, bản GridFS | `integrity.run_files_phase`, `check_file` | Py `preservation`: file_checks_find_missing_changed_empty_and_wrongly_typed_files, an_empty_file_and_documents_without_files_are_told_apart, without_mongodb_the_check_says_so_and_with_it_gridfs_is_checked, a_check_continues_after_it_was_stopped; TĐ `preservation` bước 4 |
| Chuyển sang khôi phục khi phát hiện lỗi | Nút "Chuyển sang khôi phục (n tài liệu có thể phục hồi)" trong chi tiết kiểm tra | `preservation.start_restore(check=…)`, `restore.create_from_check` | Py `preservation`: a_finding_says_whether_a_backup_could_restore_it, a_check_leads_to_a_restore_batch_that_brings_the_files_back, a_restore_is_started_from_documents_or_from_a_check…; TĐ `preservation` bước 4–5 |
| Khôi phục cơ sở dữ liệu tài liệu lưu trữ | "Khôi phục từ bản này…" (hướng dẫn đã kiểm tra); tự chạy chỉ khi `dm_allow_db_restore`, mật khẩu root và gõ lại tên site | `preservation.prepare_db_restore|verify_backup|run_restore`, `restore.runbook` | Py `preservation`: a_dump_is_verified_before_anything_is_said_about_restoring_it, by_default_a_database_restore_is_a_checked_runbook_not_an_action, a_site_that_allows_it_restores_itself_only_with_the_site_name_typed, a_failing_restore_command_ends_in_error…, a_damaged_dump_ends_the_restore_in_error…; TĐ `preservation` bước 3, 7 |
| Khôi phục tài liệu bị lỗi theo các đợt đã thiết lập | Đợt khôi phục: tạo từ danh sách tài liệu hoặc từ kiểm tra; tiến độ từng tài liệu | `restore.create_files_restore|run_files_restore`, Restore Batch Item | Py `preservation`: a_check_leads_to_a_restore_batch_that_brings_the_files_back, a_restore_recreates_the_file_record_when_it_is_gone, documents_a_backup_cannot_restore_are_reported_one_by_one, a_document_that_is_in_no_backup_is_an_error…, a_restore_can_name_its_backup…; TĐ `preservation` bước 5 (byte-nguyên) |

## 8. Phân hệ Quản trị hệ thống

| Yêu cầu | Màn hình / đường dẫn | API / dịch vụ | Kiểm thử |
|---|---|---|---|
| Công cụ quản trị, cấu hình, giám sát vận hành | `/dashboard/quan-tri/*` | `api/users.py`, `logs.py`, `admin.py` | Py `administration` (21); TĐ `admin`; HTTP |
| Cấu hình tham số hệ thống | `/dashboard/quan-tri/thiet-lap-he-thong` (sao lưu tự động, giữ nhật ký, độ mạnh mật khẩu, khóa đăng nhập sai) | DocType Document Manager Settings (bảo mật phản chiếu sang System Settings) | Py `preservation`: the_security_settings_reach_frappes_system_settings…; `administration`: settings_added_to_an_existing_site…; TĐ `admin` bước 13 |
| Quản lý người dùng theo nhóm: thêm, sửa, xóa, tìm kiếm | `/dashboard/quan-tri/nguoi-dung`, `/dashboard/quan-tri/nhom-can-bo` | `users.list_users|save_user|set_enabled|issue_password_link|delete_user`, Staff Group | Py `administration`: the_list_holds_staff_only_and_can_be_searched_and_filtered, a_new_account_gets_its_roles_and_a_one_time_link…, editing_syncs_the_staff_roles…, locking_unlocking_and_the_password_link, an_account_with_records_is_locked_not_deleted…, saving_a_group_gives_its_roles_to_the_members…, groups_appear_on_users_filter…; TĐ `admin` bước 2–8; HTTP |
| Phân quyền theo vai trò quản trị, tác nghiệp và nhóm quyền khác | `/dashboard/quan-tri/phan-quyen` (trình sửa nhóm quyền: ma trận dữ liệu × thao tác, trường nhạy cảm, chức năng; tạo, chép, xóa, khôi phục mặc định); phạm vi phông xem/sửa ở Người dùng và Nhóm cán bộ | `api/permissions.py`, `services/permission_matrix.py`, `policy.capabilities_of|staff_scope|get_access`, `constants.CAPABILITIES`, DocType Staff Role Profile, Staff Access | Py `permission_profiles` (26): taking_a_right_away_is_enforced_by_frappe_and_reset_puts_it_back, a_group_copied_from_another_starts_with_the_same_rights, the_administrators_group_cannot_be_changed, groups_in_use_and_built_in_groups_are_not_deleted; `staff_scope` (17): reading_and_changing_are_scoped_apart, moving_a_record_needs_both_fonds, every_report_shows_only_the_fonds_read, a_closed_file_is_sealed…, the_protected_fields_follow_the_permission_level; `administration`: nobody_locks_themselves_out_or_demotes_themselves, the_last_administrator_cannot_be_locked_demoted_or_deleted; `access_control`; TĐ `admin` bước 6, 9; HTTP (các rào chắn) |
| Sao lưu, khôi phục cơ sở dữ liệu phần mềm | `/dashboard/bao-quan/sao-luu`, `khoi-phuc` (cùng phân hệ 7) | như mục 7 | như mục 7 |
| Quản lý nhật ký hệ thống | `/dashboard/quan-tri/nhat-ky` (lọc theo loại, người dùng, đối tượng, ngày; xem chi tiết; tải CSV) | `logs.list_logs|get_log|download_logs`, `services/audit.py` | Py `administration`: the_log_is_listed_filtered_paged_and_read, the_log_downloads_as_csv…; `audit_and_hierarchy`; `volume_guards`; TĐ `admin` bước 10 |
| Tìm kiếm và dọn dẹp nhật ký | "Dọn dẹp": xem trước, chỉ dòng cũ hơn 7 ngày, gõ lại số dòng | `logs.preview_purge|purge` | Py `administration`: a_cleanup_shows_what_it_would_delete…, a_cleanup_needs_the_count_typed_back…; TĐ `admin` bước 11; HTTP |
| Hỗ trợ đổi mật khẩu | Menu tài khoản → "Đổi mật khẩu" (cán bộ); `/portal/tai-khoan` (độc giả); liên kết đặt mật khẩu một lần | `api/account.change_password`, `users.issue_password_link` | Py `reader_site`: password_change_asks_for_both_passwords, a_wrong_current_password…; TĐ `reader` (đổi mật khẩu), `admin` bước 4 |
| Quản lý thông tin về đơn vị: giới thiệu, cơ cấu tổ chức, thông tin liên hệ | `/dashboard/quan-tri/thong-tin-don-vi`, `/dashboard/quan-tri/co-cau-to-chuc`; hiển thị ở các trang công khai | DocType Organization Info, Organization Leader, Organization Unit | Py `reader_site`: profile_*, unit_tree_*; TĐ `admin` bước 13, `reader` |

## 9. Yêu cầu phi chức năng và nơi kiểm chứng

| Yêu cầu | Cách bảo đảm | Kiểm chứng |
|---|---|---|
| Phân quyền đúng từng tầng (độc giả, cán bộ, quản trị) | `policy.get_access` (một điểm quyết định cho mọi loại người dùng), `permissions.py`, `assert_capability` ở mọi API, `services/archive/locks.py` | Py `access_control`, `policy`, `permission_profiles`, `staff_scope`, `fonds_access`, `p0_hardening`; HTTP (497 kiểm tra, gồm cả "người ngoài không được gọi") |
| Quy mô ~1 triệu văn bản | Chỉ mục (gồm hai chỉ mục kép), đếm có trần, trần thời gian cho truy vấn quét, thăm dò dịch vụ có bộ nhớ đệm | `scripts/perf/volume_check.py`; Py `volume_guards`; kết quả ở `docs/HIEU_NANG.md` |
| Dữ liệu không mất khi sao lưu/khôi phục | sha256, không ghi đè bản nguồn đã đổi, khôi phục byte-nguyên | Py `preservation` |
| Giao diện dùng được trên điện thoại | Bố cục đáp ứng, kiểm tra không tràn ngang | TĐ: bước "fit a phone" ở mọi luồng |
| Không phụ thuộc CDN | Biểu tượng SVG và Alpine đi kèm, Vue build vào `public/staff` | CI: job `frontend`; kiểm tra thủ công mạng |
