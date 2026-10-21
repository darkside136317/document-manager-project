# Báo cáo kiểm thử hệ thống quản lý tài liệu lưu trữ

Tài liệu này liệt kê **mọi test case** của ứng dụng `document_manager` theo từng nhóm chức năng, kèm kết quả của lần chạy toàn bộ ngày 21/10/2026. Mỗi test case ghi rõ trường hợp kiểm thử, kết quả mong đợi, loại trường hợp và kết quả thực tế.

| Mục | Giá trị |
|---|---|
| Ngày chạy | 21/10/2026 (lần chạy lại sau khi sửa; lần chạy đầu ngày 19/10/2026 có 18 test case không đạt) |
| Mã nguồn | Nhánh `main`, commit `42773fe`, cộng các sửa đổi chưa commit: bản sửa `test_reader_ui_logic` (`policy.py`, `tests/test_slip_queue.py`), test cập nhật theo commit `ac75540`, `d02ebbe`, `a2e4695`, helper thanh bên `scripts/e2e/ui/nav.mjs`, module mới `tests/test_digitization.py` |
| Nền tảng | Frappe 16.26.3, ERPNext 16.26.2, Python 3.14.2, MariaDB 11.8.6, Redis, Meilisearch |
| Môi trường | Stack phát triển Docker (`docker/docker-compose.yml` + `docker-compose.dev.yml`), site `docmanager.yourdomain.com`, http://localhost:8888 |
| Giao diện | Node.js 24.11.0, Vitest 3.2.7 |
| Trình duyệt | Microsoft Edge điều khiển bằng Playwright 1.63.0 |
| Dữ liệu | Dữ liệu sẵn có của site phát triển. Mỗi test tự tạo và tự dọn dữ liệu của mình; tài khoản thử `e2e.*` được tạo trước và xóa sau khi chạy HTTP và trình duyệt |

## 1. Tóm tắt kết quả

| Lớp kiểm thử | Công cụ | Test case | ✅ Đạt | ❌ Không đạt | ⏭ Không chạy | Tỉ lệ đạt |
|---|---|---:|---:|---:|---:|---:|
| Máy chủ (tích hợp) | Frappe run-tests (unittest) | 509 | 509 | 0 | 0 | 100.0% |
| API qua HTTP (đầu cuối) | scripts/e2e/e2e_http.py | 144 (502 lượt kiểm) | 144 | 0 | 0 | 100.0% |
| Giao diện (đơn vị) | Vitest + Vue Test Utils | 205 | 205 | 0 | 0 | 100.0% |
| Trình duyệt (đầu cuối) | Playwright (Microsoft Edge) | 125 | 125 | 0 | 0 | 100.0% |
| **Tổng** | | **983** | **983** | **0** | **0** | **100.0%** |

- Lần chạy đầu ngày 19/10/2026 có 18/1005 test case không đạt. Cả 18 do ba commit của người đóng góp khác ngày 16/10 (`ac75540`, `d02ebbe`, `a2e4695`) đổi giao diện, câu chữ hoặc tên hàm mà không cập nhật test. Các chức năng vẫn chạy đúng nên chỉ sửa test (mục 2).
- 37 ca kiểm thử bổ sung của lần chạy đầu (AI bóc tách, cấu hình trường số hóa, tổng quan workspace, mô tả form) đã thành test thường trực: 12 test trong `tests/test_digitization.py` (32 ca, gom theo chức năng) và 2 test trong `tests/test_staff_api.py` (5 ca). Module mới đã được thêm vào CI.
- Helper thanh bên `scripts/e2e/ui/nav.mjs` mở nhóm thu gọn trước khi tìm liên kết và đếm cả liên kết ẩn. Nhờ vậy các kiểm tra dạng "không được thấy menu X" thực sự có tác dụng trở lại; luồng quản trị có một bước đối chứng cho việc này.

## 2. Test case không đạt và nguyên nhân

Không có test case nào không đạt.

**Những gì đã sửa so với lần chạy ngày 19/10:**

| Nguyên nhân gốc | Commit | Sửa |
|---|---|---|
| Thanh bên đổi thành nhóm thu gọn | `ac75540` | Helper `nav.mjs` (`navLink`, `navOffers`, `navGroup`) dùng trong 6 luồng trình duyệt; bước đầu luồng phiếu kiểm bộ đếm ở tiêu đề nhóm rồi ở từng liên kết |
| Câu báo đăng nhập sai đổi chữ | `ac75540` | `reader.mjs` chờ câu "Thông tin đăng nhập không đúng" |
| Mục "Giới thiệu đơn vị" ẩn khi chưa có nội dung | `ac75540` | `test_public_pages_open_for_guests` điền nội dung giới thiệu; `test_hidden_leaders_and_empty_profile` kiểm mục bị ẩn khi chưa có |
| Đổi tên hàm dọn tệp khi chuyển sang MinIO | `d02ebbe` | Test patch `enqueue_delete_object_files` (đổi tên thành `test_deleting_a_document_releases_its_stored_files_after_commit`); test bộ đếm tự hết lỗi |
| Thêm menu "Cấu hình trường dữ liệu" và hai vai trò số hóa | `a2e4695` | `test_staff_api` so 5 mục đầu của nhóm Quản trị; `e2e_http.py` so các nhóm mẫu với 7 vai trò và kiểm không có vai trò hệ thống nào được đưa ra; `admin.mjs` thêm menu mới vào danh sách kiểm |

## 3. Độ phủ theo chức năng

### 3.1 Số test case theo nhóm chức năng và lớp kiểm thử

| Nhóm chức năng | Máy chủ (tích hợp) | API qua HTTP (đầu cuối) | Giao diện (đơn vị) | Trình duyệt (đầu cuối) | Tổng | ✅ | ❌ |
|---|---:|---:|---:|---:|---:|---:|---:|
| [Đăng nhập, cổng truy cập và chuyển hướng](#acc) | 18 | 23 | – | 4 | 45 | 45 | 0 |
| [Biên mục hồ sơ, văn bản và tệp](#bm) | 28 | – | 24 | 11 | 63 | 63 | 0 |
| [Danh mục dùng chung và màn hình nghiệp vụ chung](#dm) | 24 | – | – | 8 | 32 | 32 | 0 |
| [Tìm kiếm](#tk) | 16 | 4 | 18 | 5 | 43 | 43 | 0 |
| [Cổng độc giả: trang công khai, đăng ký, tài khoản, thông báo](#cdg) | 60 | 13 | 28 | 14 | 115 | 115 | 0 |
| [Phiếu sử dụng và phiếu sao chụp](#ph) | 93 | 16 | 30 | 21 | 160 | 160 | 0 |
| [Quản lý độc giả, mẫu phiếu và góp ý](#qdg) | 23 | 11 | – | 5 | 39 | 39 | 0 |
| [Phạm vi khai thác của độc giả (phông, cấp phép, mức mật)](#pvdg) | 35 | 2 | – | 2 | 39 | 39 | 0 |
| [Nhóm quyền và phạm vi của cán bộ](#pq) | 43 | – | 5 | 1 | 49 | 49 | 0 |
| [Báo cáo, thống kê và kiểm kê](#bc) | 31 | 17 | 11 | 11 | 70 | 70 | 0 |
| [Trao đổi dữ liệu XML](#xml) | 37 | 21 | 16 | 9 | 83 | 83 | 0 |
| [Bảo quản: sao lưu, kiểm tra toàn vẹn, khôi phục](#bq) | 39 | 8 | 9 | 10 | 66 | 66 | 0 |
| [Quản trị hệ thống: người dùng, nhóm, nhật ký, giám sát](#qt) | 21 | 29 | 11 | 13 | 74 | 74 | 0 |
| [Nhật ký nghiệp vụ và toàn vẹn cây phân cấp](#nk) | 14 | – | – | – | 14 | 14 | 0 |
| [Hiệu năng, khối lượng lớn và lưu trữ đối tượng](#hn) | 15 | – | – | – | 15 | 15 | 0 |
| [Thành phần giao diện dùng chung](#ui) | – | – | 53 | 11 | 64 | 64 | 0 |
| [Số hóa và AI bóc tách](#sh) | 12 | – | – | – | 12 | 12 | 0 |
| **Tổng** | 509 | 144 | 205 | 125 | **983** | **983** | **0** |

### 3.2 Số test case theo loại trường hợp

| Nhóm chức năng | Chức năng | Ngoại lệ | Phân quyền | Biên | Bảo mật |
|---|---:|---:|---:|---:|---:|
| Đăng nhập, cổng truy cập và chuyển hướng | 26 | – | 16 | – | 3 |
| Biên mục hồ sơ, văn bản và tệp | 31 | 14 | 3 | 10 | 5 |
| Danh mục dùng chung và màn hình nghiệp vụ chung | 13 | 8 | 7 | 2 | 2 |
| Tìm kiếm | 22 | 5 | 5 | 4 | 7 |
| Cổng độc giả: trang công khai, đăng ký, tài khoản, thông báo | 53 | 22 | 11 | 8 | 21 |
| Phiếu sử dụng và phiếu sao chụp | 81 | 13 | 35 | 24 | 7 |
| Quản lý độc giả, mẫu phiếu và góp ý | 24 | 2 | 9 | 2 | 2 |
| Phạm vi khai thác của độc giả (phông, cấp phép, mức mật) | 11 | 1 | 17 | 3 | 7 |
| Nhóm quyền và phạm vi của cán bộ | 25 | 3 | 15 | 4 | 2 |
| Báo cáo, thống kê và kiểm kê | 44 | 5 | 12 | 6 | 3 |
| Trao đổi dữ liệu XML | 45 | 10 | 8 | 9 | 11 |
| Bảo quản: sao lưu, kiểm tra toàn vẹn, khôi phục | 30 | 15 | 5 | 8 | 8 |
| Quản trị hệ thống: người dùng, nhóm, nhật ký, giám sát | 44 | 6 | 8 | 5 | 11 |
| Nhật ký nghiệp vụ và toàn vẹn cây phân cấp | 8 | 1 | – | 2 | 3 |
| Hiệu năng, khối lượng lớn và lưu trữ đối tượng | 7 | 2 | – | 6 | – |
| Thành phần giao diện dùng chung | 39 | 7 | 5 | 11 | 2 |
| Số hóa và AI bóc tách | 2 | 4 | 5 | – | 1 |
| **Tổng** | **505** | **118** | **161** | **104** | **95** |

## 4. Quy ước

- **Mã test case**: `<nhóm>-<lớp>-<số thứ tự>`, ví dụ `PH-PY-012` là test case thứ 12 của nhóm Phiếu ở lớp máy chủ.
- **Lớp**: `PY` = Máy chủ (tích hợp) (apps/document_manager/document_manager/tests/); `API` = API qua HTTP (đầu cuối) (scripts/e2e/e2e_http.py); `UI` = Giao diện (đơn vị) (apps/document_manager/frontend/tests/); `E2E` = Trình duyệt (đầu cuối) (scripts/e2e/ui/*.mjs).
- **Loại trường hợp**: `C` = Chức năng; `N` = Ngoại lệ; `Q` = Phân quyền; `B` = Biên; `S` = Bảo mật. *Chức năng*: luồng đúng; *Ngoại lệ*: dữ liệu sai, thiếu, trạng thái không cho phép; *Phân quyền*: người không đủ quyền; *Biên*: giới hạn, hạn mức, giá trị ở ngưỡng, chạy lại; *Bảo mật*: giả mạo, XSS, đường dẫn độc hại, lộ thông tin.
- **Kết quả**: ✅ Đạt; ❌ Không đạt; ⏭ Không chạy (bước phụ thuộc bị dừng).
- Với lớp API, mỗi test case là một điểm kiểm trong script; nếu điểm kiểm chạy cho nhiều vai trò hoặc nhiều địa chỉ thì cột kết quả ghi số lượt đạt / tổng số lượt.
- Cột **Nguồn** chỉ tới test tương ứng trong mã nguồn để chạy lại hoặc xem chi tiết.

## 5. Danh mục test case chi tiết

<a id="acc"></a>

### 5.1 Đăng nhập, cổng truy cập và chuyển hướng

45 test case: 45 đạt.

**Máy chủ (tích hợp)** (18)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| ACC-PY-001 | Khách chưa đăng nhập mở /dashboard | Chuyển sang trang đăng nhập | Phân quyền | ✅ Đạt | `access_control · guest_redirected_to_login_from_dashboard` |
| ACC-PY-002 | Từng vai trò cán bộ mở /dashboard | Mở được ứng dụng cán bộ | Chức năng | ✅ Đạt | `access_control · every_staff_role_can_open_dashboard` |
| ACC-PY-003 | Administrator mở /dashboard | Mở được | Chức năng | ✅ Đạt | `access_control · administrator_can_open_dashboard` |
| ACC-PY-004 | Độc giả mở /dashboard | Bị chặn | Phân quyền | ✅ Đạt | `access_control · reader_cannot_open_dashboard` |
| ACC-PY-005 | Tài khoản không có vai trò nào mở /dashboard | Bị chặn | Phân quyền | ✅ Đạt | `access_control · user_without_roles_cannot_open_dashboard` |
| ACC-PY-006 | Gọi thẳng get_context của trang /dashboard | Cổng kiểm quyền vẫn chạy | Bảo mật | ✅ Đạt | `access_control · dashboard_get_context_enforces_gate` |
| ACC-PY-007 | Khách mở /portal | Chuyển sang trang đăng nhập | Phân quyền | ✅ Đạt | `access_control · guest_redirected_to_login_from_portal` |
| ACC-PY-008 | Cán bộ và độc giả mở /portal | Mở được | Chức năng | ✅ Đạt | `access_control · staff_and_reader_can_open_portal` |
| ACC-PY-009 | Tài khoản không phải độc giả hay cán bộ mở /portal | Bị chặn | Phân quyền | ✅ Đạt | `access_control · user_without_reader_or_staff_role_blocked_from_portal` |
| ACC-PY-010 | Tài khoản độc giả | Là Website User, không vào được Desk | Bảo mật | ✅ Đạt | `access_control · reader_is_website_user_without_desk` |
| ACC-PY-011 | Tài khoản chỉ có vai trò độc giả bị đặt thành System User | Tự hạ về Website User | Bảo mật | ✅ Đạt | `access_control · ensure_website_user_demotes_reader_only_account` |
| ACC-PY-012 | Tài khoản cán bộ đồng thời là độc giả | Giữ System User | Chức năng | ✅ Đạt | `access_control · ensure_website_user_keeps_staff_system_user` |
| ACC-PY-013 | Các trang chỉ dành cho cán bộ | Tồn tại và đều có cổng kiểm quyền | Phân quyền | ✅ Đạt | `access_control · staff_only_pages_exist_and_are_gated` |
| ACC-PY-014 | Danh sách vai trò cán bộ trong mã | Có đủ vai trò nghiệp vụ | Chức năng | ✅ Đạt | `access_control · staff_roles_constant_has_all_business_roles` |
| ACC-PY-015 | Cán bộ không có quyền trên một loại dữ liệu đọc dữ liệu đó | Bị từ chối | Phân quyền | ✅ Đạt | `access_control · staff_without_doctype_permission_is_denied` |
| ACC-PY-016 | Độc giả mở trang đời cũ | Chuyển sang trang mới | Chức năng | ✅ Đạt | `reader_pages · readers_are_sent_from_the_old_pages_to_the_new_ones` |
| ACC-PY-017 | Cán bộ mở trang đời cũ | Sang ứng dụng cán bộ | Chức năng | ✅ Đạt | `reader_pages · staff_are_sent_to_the_staff_app_from_the_old_pages` |
| ACC-PY-018 | Độc giả mở trang cũ chỉ dành cán bộ | Về cổng độc giả | Phân quyền | ✅ Đạt | `reader_pages · the_staff_only_old_pages_send_readers_to_the_portal` |

**API qua HTTP (đầu cuối)** (23)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| ACC-API-001 | Đăng nhập 7 tài khoản thử (độc giả, độc giả không hồ sơ, phòng đọc, lãnh đạo, biên mục, bảo quản, quản trị) | Đăng nhập được | Chức năng | ✅ Đạt (7/7) | `e2e_http.py:118` |
| ACC-API-002 | Khách mở /portal | Chuyển sang trang đăng nhập | Phân quyền | ✅ Đạt | `e2e_http.py:129` |
| ACC-API-003 | Độc giả mở /portal | 200 | Chức năng | ✅ Đạt | `e2e_http.py:130` |
| ACC-API-004 | Độc giả mở /dashboard | Bị chuyển ra ngoài ứng dụng cán bộ | Phân quyền | ✅ Đạt | `e2e_http.py:132` |
| ACC-API-005 | Phòng đọc mở /dashboard | 200 | Chức năng | ✅ Đạt | `e2e_http.py:133` |
| ACC-API-006 | Quản trị viên mở form độc giả đời cũ | 302 sang ứng dụng cán bộ | Chức năng | ✅ Đạt | `e2e_http.py:135` |
| ACC-API-007 | Mở trang thiết lập đời cũ | 301 sang ứng dụng cán bộ | Chức năng | ✅ Đạt | `e2e_http.py:137` |
| ACC-API-008 | Khách mở 6 trang khu vực độc giả | 302 sang đăng nhập kèm đường quay lại | Phân quyền | ✅ Đạt (6/6) | `e2e_http.py:178` |
| ACC-API-009 | Cán bộ mở cổng độc giả | 200 | Chức năng | ✅ Đạt | `e2e_http.py:182` |
| ACC-API-010 | Độc giả mở trang phiếu đời cũ | 302 sang trang mới | Chức năng | ✅ Đạt | `e2e_http.py:184` |
| ACC-API-011 | Mở địa chỉ trình xem văn bản đời cũ | 301 sang trang văn bản mới | Chức năng | ✅ Đạt | `e2e_http.py:186` |
| ACC-API-012 | Phòng đọc mở 5 trang đời cũ | 302 sang ứng dụng cán bộ | Chức năng | ✅ Đạt (5/5) | `e2e_http.py:222` |
| ACC-API-013 | Độc giả mở 5 trang đời cũ | 302 sang cổng độc giả | Chức năng | ✅ Đạt (5/5) | `e2e_http.py:224` |
| ACC-API-014 | Khách mở 5 trang đời cũ | 302 sang đăng nhập | Phân quyền | ✅ Đạt (5/5) | `e2e_http.py:226` |
| ACC-API-015 | Địa chỉ phiếu đời cũ kèm mã phiếu | Chuyển hướng giữ nguyên mã phiếu | Chức năng | ✅ Đạt | `e2e_http.py:228` |
| ACC-API-016 | Lãnh đạo mở ứng dụng cán bộ | 200 | Chức năng | ✅ Đạt | `e2e_http.py:229` |
| ACC-API-017 | Lãnh đạo mở /portal | 200 (cổng độc giả, không lỗi) | Chức năng | ✅ Đạt | `e2e_http.py:230` |
| ACC-API-018 | Trang báo cáo đời cũ | 301 sang báo cáo mới | Chức năng | ✅ Đạt | `e2e_http.py:357` |
| ACC-API-019 | Báo cáo phiếu đời cũ | 301 sang báo cáo mới | Chức năng | ✅ Đạt | `e2e_http.py:359` |
| ACC-API-020 | 5 trang quản trị/bảo quản đời cũ | 301 sang ứng dụng cán bộ | Chức năng | ✅ Đạt (5/5) | `e2e_http.py:549` |
| ACC-API-021 | Cán bộ mở các trang quản trị/bảo quản | 200 (vỏ trang; dữ liệu do API kiểm quyền) | Chức năng | ✅ Đạt (5/5) | `e2e_http.py:552` |
| ACC-API-022 | Độc giả mở trang quản trị | Bị chuyển đi | Phân quyền | ✅ Đạt | `e2e_http.py:553` |
| ACC-API-023 | Khách mở trang bảo quản | Bị chuyển đi | Phân quyền | ✅ Đạt | `e2e_http.py:554` |

**Trình duyệt (đầu cuối)** (4)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| ACC-E2E-001 | Khách mở khu vực độc giả | Sang đăng nhập, nhớ đường quay lại | Phân quyền | ✅ Đạt | `reader.mjs` |
| ACC-E2E-002 | Cán bộ đăng nhập ở cùng trang | Vào ứng dụng cán bộ | Chức năng | ✅ Đạt | `reader.mjs` |
| ACC-E2E-003 | Đăng xuất | Về trang đăng nhập; khu vực độc giả đóng | Chức năng | ✅ Đạt | `reader.mjs` |
| ACC-E2E-004 | Độc giả mở ứng dụng cán bộ, gọi API cán bộ | Bị chặn | Phân quyền | ✅ Đạt | `reader.mjs` |

<a id="bm"></a>

### 5.2 Biên mục hồ sơ, văn bản và tệp

63 test case: 63 đạt.

**Máy chủ (tích hợp)** (28)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| BM-PY-001 | Mở cây biên mục | Đi theo phông → khối → mục lục | Chức năng | ✅ Đạt | `archive_api · tree_walks_fonds_then_record_groups_then_catalogs` |
| BM-PY-002 | Tên và mã của nút cây | Lấy từ bản ghi | Chức năng | ✅ Đạt | `archive_api · tree_titles_and_codes_come_from_the_records` |
| BM-PY-003 | Độc giả gọi API cây biên mục | Bị từ chối | Phân quyền | ✅ Đạt | `archive_api · the_tree_is_for_staff_only` |
| BM-PY-004 | Mở tổng quan hồ sơ | Có đường dẫn, thống kê, quyền, liên kết in | Chức năng | ✅ Đạt | `archive_api · file_overview_has_breadcrumb_stats_permissions_and_print_links` |
| BM-PY-005 | Cán bộ phòng đọc mở hồ sơ | Xem được, không sửa được | Phân quyền | ✅ Đạt | `archive_api · an_officer_may_look_but_not_change` |
| BM-PY-006 | Mở tổng quan văn bản | Mô tả đúng tệp đã lưu | Chức năng | ✅ Đạt | `archive_api · document_overview_describes_the_stored_file` |
| BM-PY-007 | Tạo văn bản từ tệp tải lên | Văn bản được tạo và gắn tệp | Chức năng | ✅ Đạt | `archive_api · a_document_is_created_from_an_uploaded_file` |
| BM-PY-008 | Đặt tiêu đề khi tạo; tải tệp Office đời cũ (.doc) | Tiêu đề đúng; tệp cũ không trích nội dung | Chức năng | ✅ Đạt | `archive_api · the_title_can_be_given_and_legacy_office_files_are_not_extracted` |
| BM-PY-009 | Tải tệp ngoài các định dạng cho phép | Bị từ chối và tệp bị xóa | Ngoại lệ | ✅ Đạt | `archive_api · only_allowed_file_types_are_accepted_and_the_refused_file_is_removed` |
| BM-PY-010 | Tải tệp vượt giới hạn dung lượng | Bị từ chối | Biên | ✅ Đạt | `archive_api · a_file_over_the_limit_is_refused` |
| BM-PY-011 | Dùng tệp người khác tải lên để tạo văn bản | Bị từ chối | Bảo mật | ✅ Đạt | `archive_api · somebody_elses_upload_cannot_be_claimed` |
| BM-PY-012 | Dùng lại tệp đã gắn vào văn bản khác | Bị từ chối | Bảo mật | ✅ Đạt | `archive_api · an_upload_can_only_be_used_once` |
| BM-PY-013 | Cán bộ phòng đọc, độc giả thêm văn bản | Bị từ chối | Phân quyền | ✅ Đạt | `archive_api · officers_and_readers_cannot_add_documents` |
| BM-PY-014 | Thay tệp của văn bản | Tệp mới thay thế và được xử lý lại | Chức năng | ✅ Đạt | `archive_api · replacing_the_file_of_a_document` |
| BM-PY-015 | Yêu cầu index lại văn bản có/không có tệp | Không tệp bị từ chối; có tệp thì vào hàng đợi xử lý | Ngoại lệ | ✅ Đạt | `archive_api · reindex_needs_a_file_and_queues_the_pipeline` |
| BM-PY-016 | Xóa văn bản | Bộ đếm của hồ sơ giảm | Chức năng | ✅ Đạt | `archive_api · deleting_a_document_removes_it_from_the_count` |
| BM-PY-017 | Mô tả form các loại dữ liệu biên mục | Không lộ trường hệ thống | Bảo mật | ✅ Đạt | `archive_api · cataloguing_doctypes_are_described_without_their_system_fields` |
| BM-PY-018 | Gõ trường tác giả | Gợi ý giá trị từ từ điển tương ứng | Chức năng | ✅ Đạt | `archive_api · author_suggests_the_values_of_the_matching_dictionary` |
| BM-PY-019 | Tạo, sửa, xóa bản ghi mục lục | Hoạt động và được bảo vệ như bản ghi khác | Chức năng | ✅ Đạt | `archive_api · catalogue_records_are_created_edited_and_protected_like_any_other` |
| BM-PY-020 | In hai mẫu in của hồ sơ và văn bản | Hiển thị đúng dữ liệu | Chức năng | ✅ Đạt | `archive_api · the_two_new_print_formats_render` |
| BM-PY-021 | Chạy lại bước gieo giới hạn tải lên | Không đổi, giữ giá trị lớn hơn đã đặt | Biên | ✅ Đạt | `archive_api · upload_limit_seed_is_idempotent_and_keeps_a_larger_value` |
| BM-PY-022 | Đọc tệp đã lưu có nội dung giống văn bản | Trả đúng từng byte | Biên | ✅ Đạt | `archive_api · stored_files_are_read_as_exact_bytes_even_when_they_look_like_text` |
| BM-PY-023 | Deadlock khi cấp số văn bản | Tự thử lại và thành công | Biên | ✅ Đạt | `archive_api · a_deadlock_on_the_document_number_is_retried` |
| BM-PY-024 | Deadlock lặp lại liên tục | Báo lỗi rõ ràng | Ngoại lệ | ✅ Đạt | `archive_api · a_persistent_deadlock_is_reported` |
| BM-PY-025 | Tải mẫu in dạng PDF | Nhận tệp PDF | Chức năng | ✅ Đạt | `archive_api · the_print_formats_download_as_pdf` |
| BM-PY-026 | Trang dựng PDF | Không tải tài nguyên bên ngoài | Bảo mật | ✅ Đạt | `archive_api · the_pdf_page_has_no_external_resources` |
| BM-PY-027 | Đổi mức mật hồ sơ | Văn bản đổi theo | Chức năng | ✅ Đạt | `p0_hardening · reclassifying_a_file_reclassifies_its_documents` |
| BM-PY-028 | Chạy lại bước gieo dữ liệu | Không đổi; có mức mật mặc định | Biên | ✅ Đạt | `p0_hardening · seed_is_idempotent_and_provides_the_default_level` |

**Giao diện (đơn vị)** (24)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| BM-UI-001 | Nút cây biên mục | Khóa theo loại và mã | Chức năng | ✅ Đạt | `archive.test.js · archive tree` |
| BM-UI-002 | Mở tới một mục lục | Mở các nhánh cha | Chức năng | ✅ Đạt | `archive.test.js · archive tree` |
| BM-UI-003 | Làm mới cây | Tải lại gốc và nhánh đang mở; nhánh chỉ tải khi mở | Chức năng | ✅ Đạt | `archive.test.js · archive tree` |
| BM-UI-004 | Máy chủ từ chối | Danh sách rỗng kèm thông báo | Ngoại lệ | ✅ Đạt | `archive.test.js · archive tree` |
| BM-UI-005 | Đường dẫn (breadcrumb) | Liên kết tới cây biên mục và hồ sơ | Chức năng | ✅ Đạt | `archive.test.js · Breadcrumbs` |
| BM-UI-006 | Bảng dữ liệu | Hiện cột phụ, dung lượng dễ đọc, trạng thái dạng nhãn | Chức năng | ✅ Đạt | `archive.test.js · DataTable` |
| BM-UI-007 | Xem trước PDF, ảnh, văn bản, loại khác | Hiển thị đúng từng loại | Chức năng | ✅ Đạt | `archive.test.js · DocumentPreview` |
| BM-UI-008 | Không có tệp / lỗi / đang tải | Có thông báo tương ứng | Ngoại lệ | ✅ Đạt | `archive.test.js · DocumentPreview` |
| BM-UI-009 | Chọn nhiều tệp có tệp sai | Đánh dấu tệp sai kèm lý do; chỉ tải tệp hợp lệ | Ngoại lệ | ✅ Đạt | `archive.test.js · FileUploader` |
| BM-UI-010 | Chế độ thay tệp | Chỉ nhận một tệp | Biên | ✅ Đạt | `archive.test.js · FileUploader` |
| BM-UI-011 | Bấm tải khi chưa chọn tệp | Không bắt đầu | Ngoại lệ | ✅ Đạt | `archive.test.js · FileUploader` |
| BM-UI-012 | Đuôi tệp viết hoa | Nhận đúng | Biên | ✅ Đạt | `upload.test.js · validation` |
| BM-UI-013 | Tệp hợp lệ trong giới hạn | Được nhận | Chức năng | ✅ Đạt | `upload.test.js · validation` |
| BM-UI-014 | Tệp sai loại / quá lớn / rỗng | Nêu lý do từng trường hợp | Ngoại lệ | ✅ Đạt | `upload.test.js · validation` |
| BM-UI-015 | Dung lượng tệp | Đơn vị dễ đọc | Chức năng | ✅ Đạt | `upload.test.js · validation` |
| BM-UI-016 | Tải tệp | Riêng tư, có CSRF, báo tiến độ | Bảo mật | ✅ Đạt | `upload.test.js · uploadFile` |
| BM-UI-017 | Máy chủ từ chối tệp | Lỗi dễ đọc | Ngoại lệ | ✅ Đạt | `upload.test.js · uploadFile` |
| BM-UI-018 | Trang lỗi HTML; mất kết nối | Báo lỗi, không treo | Ngoại lệ | ✅ Đạt | `upload.test.js · uploadFile` |
| BM-UI-019 | Hàng đợi tải lên | Mỗi tệp hợp lệ thành một văn bản; tệp sai giữ lý do | Chức năng | ✅ Đạt | `upload.test.js · processQueue` |
| BM-UI-020 | Một tệp lỗi | Tiếp tục tệp khác; báo lỗi | Ngoại lệ | ✅ Đạt | `upload.test.js · processQueue` |
| BM-UI-021 | Nhiều tệp | Không vượt số tải đồng thời | Biên | ✅ Đạt | `upload.test.js · processQueue` |
| BM-UI-022 | Tệp đã xong/đã lỗi | Bỏ qua | Biên | ✅ Đạt | `upload.test.js · processQueue` |
| BM-UI-023 | Tải song song | Tạo văn bản tuần tự (tránh trùng số) | Biên | ✅ Đạt | `upload.test.js · document creation order` |
| BM-UI-024 | Tạo văn bản lỗi | Không chặn các tệp sau | Ngoại lệ | ✅ Đạt | `upload.test.js · document creation order` |

**Trình duyệt (đầu cuối)** (11)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| BM-E2E-001 | Mở cây biên mục | Liệt kê phông | Chức năng | ✅ Đạt | `cataloguing.mjs` |
| BM-E2E-002 | Thêm khối dưới phông | Thêm được | Chức năng | ✅ Đạt | `cataloguing.mjs` |
| BM-E2E-003 | Thêm mục lục rồi hồ sơ | Thêm được | Chức năng | ✅ Đạt | `cataloguing.mjs` |
| BM-E2E-004 | Trang hồ sơ mới | Có đường dẫn; danh sách văn bản rỗng | Chức năng | ✅ Đạt | `cataloguing.mjs` |
| BM-E2E-005 | Tải 2 PDF, 1 ảnh và 1 tệp văn bản không cho phép | 3 tệp được nhận; tệp văn bản bị từ chối | Ngoại lệ | ✅ Đạt | `cataloguing.mjs` |
| BM-E2E-006 | Sau khi tải | Thành văn bản của hồ sơ; được đếm và liệt kê | Chức năng | ✅ Đạt | `cataloguing.mjs` |
| BM-E2E-007 | Xử lý nền | Mọi văn bản tìm được | Chức năng | ✅ Đạt | `cataloguing.mjs` |
| BM-E2E-008 | Trang văn bản | Xem trước PDF; lưu mô tả với gợi ý từ điển | Chức năng | ✅ Đạt | `cataloguing.mjs` |
| BM-E2E-009 | In mục lục văn bản và phiếu văn bản | Đúng dữ liệu | Chức năng | ✅ Đạt | `cataloguing.mjs` |
| BM-E2E-010 | Thay tệp, xóa văn bản | Thực hiện được | Chức năng | ✅ Đạt | `cataloguing.mjs` |
| BM-E2E-011 | Xóa hồ sơ còn văn bản | Bị từ chối, nêu lý do | Ngoại lệ | ✅ Đạt | `cataloguing.mjs` |

<a id="dm"></a>

### 5.3 Danh mục dùng chung và màn hình nghiệp vụ chung

32 test case: 32 đạt.

**Máy chủ (tích hợp)** (24)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| DM-PY-001 | Mô tả các loại dữ liệu đã đăng ký | Đều mô tả được | Chức năng | ✅ Đạt | `staff_api · every_registered_doctype_can_be_described` |
| DM-PY-002 | Loại dữ liệu ngoài danh mục | Không truy cập được | Bảo mật | ✅ Đạt | `staff_api · unregistered_doctypes_are_out_of_reach` |
| DM-PY-003 | Người ngoài cán bộ gọi API chung | Bị từ chối, kể cả khi Frappe cho đọc | Phân quyền | ✅ Đạt | `staff_api · the_generic_api_is_for_the_staff_even_where_frappe_would_allow_the_read` |
| DM-PY-004 | Dữ liệu khởi động | Chỉ cán bộ; liệt kê thứ được đọc | Phân quyền | ✅ Đạt | `staff_api · boot_is_for_staff_and_lists_what_the_user_may_read` |
| DM-PY-005 | Thanh bên | Theo quyền | Phân quyền | ✅ Đạt | `staff_api · the_sidebar_follows_permissions` |
| DM-PY-006 | Quản trị viên | Có menu quản trị và bảo quản | Chức năng | ✅ Đạt | `staff_api · an_administrator_gets_the_administration_and_preservation_menus` |
| DM-PY-007 | Mô tả form | Theo quyền người dùng | Phân quyền | ✅ Đạt | `staff_api · description_reflects_the_users_permissions` |
| DM-PY-008 | Lấy mô tả form hồ sơ; chế độ làm việc không hợp lệ | Có trường và quyền đọc; chế độ sai bị từ chối | Ngoại lệ | ✅ Đạt | `staff_api · a_form_is_described_in_a_known_working_mode_only` |
| DM-PY-009 | Tổng quan workspace của quản trị viên và cán bộ bảo quản | Đủ chỉ số, tỉ lệ index 0–100%, tối đa 5 văn bản gần đây; loại dữ liệu không được đọc thì đếm 0 | Phân quyền | ✅ Đạt | `staff_api · the_workspace_summary_counts_only_what_the_user_may_read` |
| DM-PY-010 | Bố cục form | Phủ hết các trường | Chức năng | ✅ Đạt | `staff_api · layout_sections_cover_the_form_fields` |
| DM-PY-011 | Tạo, đọc, sửa, xóa | Đúng | Chức năng | ✅ Đạt | `staff_api · create_read_update_delete_round_trip` |
| DM-PY-012 | Bản ghi có tên lấy từ trường | Không đổi tên khi sửa trường đó | Biên | ✅ Đạt | `staff_api · the_name_of_a_record_built_from_a_field_does_not_change_on_edit` |
| DM-PY-013 | Gửi giá trị cho trường hệ thống | Không ghi được | Bảo mật | ✅ Đạt | `staff_api · system_fields_cannot_be_forged` |
| DM-PY-014 | Lưu bản đã cũ | Báo xung đột, không ghi đè | Ngoại lệ | ✅ Đạt | `staff_api · a_stale_edit_is_reported_not_overwritten` |
| DM-PY-015 | Thiếu trường bắt buộc, dữ liệu sai | Bị chặn | Ngoại lệ | ✅ Đạt | `staff_api · required_fields_and_validation_are_enforced_by_frappe` |
| DM-PY-016 | Danh sách | Tìm, lọc, sắp xếp, phân trang | Chức năng | ✅ Đạt | `staff_api · list_search_filter_sort_and_paging` |
| DM-PY-017 | Vai trò không có quyền ghi | Không sửa được | Phân quyền | ✅ Đạt | `staff_api · roles_without_write_access_cannot_change_data` |
| DM-PY-018 | Xóa bản ghi | Biên mục viên không được; quản trị viên được | Phân quyền | ✅ Đạt | `staff_api · a_cataloger_cannot_delete_but_an_admin_can` |
| DM-PY-019 | Xóa bản ghi đang được tham chiếu | Bị chặn | Ngoại lệ | ✅ Đạt | `staff_api · a_record_that_is_still_used_cannot_be_deleted` |
| DM-PY-020 | Tìm liên kết | Trả nhãn; theo bộ lọc | Chức năng | ✅ Đạt | `staff_api · link_search_returns_labels_and_respects_filters` |
| DM-PY-021 | Từ điển một cấp có giá trị cha | Bị từ chối | Ngoại lệ | ✅ Đạt | `staff_api · single_level_dictionary_rejects_parents` |
| DM-PY-022 | Từ điển nhiều cấp | Dựng cây; cùng giá trị dưới hai cha | Chức năng | ✅ Đạt | `staff_api · multi_level_dictionary_builds_a_tree_with_the_same_value_under_two_parents` |
| DM-PY-023 | Xóa con cuối cùng | Bỏ cờ nhóm của cha | Biên | ✅ Đạt | `staff_api · deleting_the_last_child_clears_the_group_flag` |
| DM-PY-024 | Cây kho | Gốc trước, con sau | Chức năng | ✅ Đạt | `staff_api · the_warehouse_tree_lists_roots_then_children` |

**Trình duyệt (đầu cuối)** (8)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| DM-E2E-001 | Tạo loại từ điển nhiều cấp | Tạo được | Chức năng | ✅ Đạt | `catalogues.mjs` |
| DM-E2E-002 | Bỏ trống trường bắt buộc | Báo lỗi ngay, chưa gửi máy chủ | Ngoại lệ | ✅ Đạt | `catalogues.mjs` |
| DM-E2E-003 | Tìm trong danh sách | Danh sách thu hẹp | Chức năng | ✅ Đạt | `catalogues.mjs` |
| DM-E2E-004 | Chọn từ điển, thêm giá trị gốc | Thêm được | Chức năng | ✅ Đạt | `catalogues.mjs` |
| DM-E2E-005 | Thêm giá trị con | Thêm được | Chức năng | ✅ Đạt | `catalogues.mjs` |
| DM-E2E-006 | Thêm giá trị trùng cùng cấp | Bị từ chối, thông báo dễ hiểu | Ngoại lệ | ✅ Đạt | `catalogues.mjs` |
| DM-E2E-007 | Sửa giá trị; xóa nút lá | Thực hiện được | Chức năng | ✅ Đạt | `catalogues.mjs` |
| DM-E2E-008 | Xóa nút còn con | Bị từ chối, hiện thông báo máy chủ | Ngoại lệ | ✅ Đạt | `catalogues.mjs` |

<a id="tk"></a>

### 5.4 Tìm kiếm

43 test case: 43 đạt.

**Máy chủ (tích hợp)** (16)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| TK-PY-001 | Dữ liệu đưa vào chỉ mục tìm kiếm thiếu thông tin quyền | Đóng mặc định (không lộ) | Bảo mật | ✅ Đạt | `p0_hardening · search_index_payload_is_fail_closed` |
| TK-PY-002 | Tìm kiếm | Cần hồ sơ độc giả hoặc là cán bộ | Phân quyền | ✅ Đạt | `reader_ui_logic · search_requires_reader_profile_or_staff` |
| TK-PY-003 | Kết quả tìm toàn văn | Không kèm nội dung trích xuất | Bảo mật | ✅ Đạt | `reader_ui_logic · fulltext_hits_do_not_carry_content_text` |
| TK-PY-004 | Tìm hồ sơ cơ bản | Khớp tiêu đề, số; đếm đúng | Chức năng | ✅ Đạt | `search_service · basic_file_search_matches_title_number_and_counts_correctly` |
| TK-PY-005 | Tìm hồ sơ nâng cao | Các bộ lọc kết hợp AND | Chức năng | ✅ Đạt | `search_service · advanced_file_filters_combine_with_and` |
| TK-PY-006 | Lọc theo ngày | Áp đúng | Chức năng | ✅ Đạt | `search_service · date_filters_are_applied` |
| TK-PY-007 | Phân trang với cỡ trang/trang quá lớn | Bị giới hạn | Biên | ✅ Đạt | `search_service · paging_is_bounded` |
| TK-PY-008 | Lọc văn bản dạng LIKE | Dùng CSDL | Chức năng | ✅ Đạt | `search_service · document_filters_with_like_use_the_database` |
| TK-PY-009 | Lọc khoảng ngày và bằng | Đúng | Chức năng | ✅ Đạt | `search_service · document_date_range_and_equality_filters` |
| TK-PY-010 | Tìm toàn văn | Qua Meilisearch; không trả nội dung trích xuất | Bảo mật | ✅ Đạt | `search_service · a_free_text_query_goes_to_meilisearch_without_the_extracted_text` |
| TK-PY-011 | Meilisearch ngừng | Chuyển sang CSDL | Biên | ✅ Đạt | `search_service · search_falls_back_to_the_database_when_meilisearch_is_down` |
| TK-PY-012 | Tìm toàn văn trên cổng độc giả | Vẫn hoạt động | Chức năng | ✅ Đạt | `search_service · search_fulltext_keeps_working_for_the_current_portal` |
| TK-PY-013 | Độc giả tìm hồ sơ nháp | Không thấy | Phân quyền | ✅ Đạt | `search_service · readers_never_find_draft_files_or_their_documents` |
| TK-PY-014 | Độc giả thêm bộ lọc để mở rộng phạm vi | Không mở rộng được | Bảo mật | ✅ Đạt | `search_service · a_reader_cannot_widen_the_scope_with_a_filter` |
| TK-PY-015 | Tìm khi không có hồ sơ độc giả hoạt động | Bị từ chối | Phân quyền | ✅ Đạt | `search_service · search_is_refused_without_an_active_reader_profile` |
| TK-PY-016 | Module dịch vụ tìm kiếm | Import được độc lập | Chức năng | ✅ Đạt | `search_service · service_helpers_are_importable_without_the_api` |

**API qua HTTP (đầu cuối)** (4)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| TK-API-001 | Độc giả, phòng đọc, quản trị viên tìm văn bản | 200, có dữ liệu | Chức năng | ✅ Đạt (3/3) | `e2e_http.py:142` |
| TK-API-002 | Độc giả, phòng đọc, quản trị viên tìm hồ sơ | 200, có tổng số | Chức năng | ✅ Đạt (3/3) | `e2e_http.py:144` |
| TK-API-003 | Độc giả không hồ sơ tìm kiếm | 403 | Phân quyền | ✅ Đạt | `e2e_http.py:145` |
| TK-API-004 | Khách tìm kiếm | 401/403 | Phân quyền | ✅ Đạt | `e2e_http.py:146` |

**Giao diện (đơn vị)** (18)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| TK-UI-001 | Đoạn tô sáng từ máy tìm kiếm | Chỉ giữ thẻ mark, escape phần còn lại | Bảo mật | ✅ Đạt | `reader.test.js · helpers` |
| TK-UI-002 | Mở trang tìm kiếm từ địa chỉ có tham số | Khôi phục điều kiện tìm | Chức năng | ✅ Đạt | `reader.test.js · searchPage` |
| TK-UI-003 | Gửi tìm kiếm | Chỉ các ô đã điền | Chức năng | ✅ Đạt | `reader.test.js · searchPage` |
| TK-UI-004 | Tìm khi chưa nhập gì | Yêu cầu nhập điều kiện | Ngoại lệ | ✅ Đạt | `reader.test.js · searchPage` |
| TK-UI-005 | Tìm hồ sơ | Giữ kết quả; ghi điều kiện lên địa chỉ | Chức năng | ✅ Đạt | `reader.test.js · searchPage` |
| TK-UI-006 | Tìm văn bản | Có tô sáng và đoạn trích | Chức năng | ✅ Đạt | `reader.test.js · searchPage` |
| TK-UI-007 | Máy chủ từ chối tìm | Hiện lỗi; xóa kết quả cũ | Ngoại lệ | ✅ Đạt | `reader.test.js · searchPage` |
| TK-UI-008 | Chuyển trang ngoài giới hạn | Chỉ trong giới hạn | Biên | ✅ Đạt | `reader.test.js · searchPage` |
| TK-UI-009 | Đổi giữa hồ sơ và văn bản | Bắt đầu lại | Chức năng | ✅ Đạt | `reader.test.js · searchPage` |
| TK-UI-010 | Tham số địa chỉ lạ | Mặc định văn bản; bỏ tham số lạ | Ngoại lệ | ✅ Đạt | `search.test.js · search state <-> URL` |
| TK-UI-011 | Lưu/đọc trạng thái qua địa chỉ | Như nhau | Chức năng | ✅ Đạt | `search.test.js · search state <-> URL` |
| TK-UI-012 | Kiểu sắp xếp lạ, số trang vô nghĩa | Bỏ qua | Ngoại lệ | ✅ Đạt | `search.test.js · search state <-> URL` |
| TK-UI-013 | Dựng tham số API | Không có ô trống, không có bộ lọc lạ | Bảo mật | ✅ Đạt | `search.test.js · search state <-> URL` |
| TK-UI-014 | Chưa có điều kiện | Biết là chưa có gì để tìm | Biên | ✅ Đạt | `search.test.js · search state <-> URL` |
| TK-UI-015 | Tô sáng kết quả | Giữ mark, escape phần còn lại | Bảo mật | ✅ Đạt | `search.test.js · safeHighlight` |
| TK-UI-016 | Bộ lọc đã lưu | Lưu, liệt kê có sắp xếp, xóa | Chức năng | ✅ Đạt | `search.test.js · saved filters` |
| TK-UI-017 | Tên trống; bộ nhớ trình duyệt hỏng/bị chặn | Bỏ qua; không lỗi | Ngoại lệ | ✅ Đạt | `search.test.js · saved filters` |
| TK-UI-018 | Nhãn trạng thái | Tô màu đủ trạng thái | Chức năng | ✅ Đạt | `search.test.js · status badges` |

**Trình duyệt (đầu cuối)** (5)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| TK-E2E-001 | Tìm hồ sơ cơ bản rồi thêm vào phiếu sử dụng | Tìm thấy; thêm được | Chức năng | ✅ Đạt | `reader.mjs` |
| TK-E2E-002 | Tìm văn bản nâng cao theo số và tác giả, thêm vào phiếu sao chụp | Tìm thấy; thêm được | Chức năng | ✅ Đạt | `reader.mjs` |
| TK-E2E-003 | Mở lại tìm kiếm từ địa chỉ | Khôi phục điều kiện và kết quả | Chức năng | ✅ Đạt | `reader.mjs` |
| TK-E2E-004 | Tìm theo nội dung tệp và bộ lọc nâng cao | Thấy văn bản, có tô sáng | Chức năng | ✅ Đạt | `cataloguing.mjs` |
| TK-E2E-005 | Tìm hồ sơ; lưu bộ lọc | Địa chỉ mang trạng thái | Chức năng | ✅ Đạt | `cataloguing.mjs` |

<a id="cdg"></a>

### 5.5 Cổng độc giả: trang công khai, đăng ký, tài khoản, thông báo

115 test case: 115 đạt.

**Máy chủ (tích hợp)** (60)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| CDG-PY-001 | Các luật định tuyến website | Đều biên dịch được | Chức năng | ✅ Đạt | `reader_pages · every_website_route_rule_compiles` |
| CDG-PY-002 | Phiên bản tài nguyên tĩnh | Đổi khi tài nguyên đổi | Chức năng | ✅ Đạt | `reader_pages · asset_version_changes_with_the_assets` |
| CDG-PY-003 | Khách mở các trang công khai | Mở được | Chức năng | ✅ Đạt | `reader_pages · public_pages_open_for_guests` |
| CDG-PY-004 | Mục đang mở | Được đánh dấu trên thanh điều hướng | Chức năng | ✅ Đạt | `reader_pages · active_section_is_marked_in_the_navigation` |
| CDG-PY-005 | Trang bị đơn vị tắt | Trả 404 | Biên | ✅ Đạt | `reader_pages · pages_the_unit_switched_off_are_not_found` |
| CDG-PY-006 | Lãnh đạo bị ẩn; hồ sơ đơn vị rỗng | Không hiện người bị ẩn; trang rỗng xử lý đúng | Biên | ✅ Đạt | `reader_pages · hidden_leaders_and_empty_profile` |
| CDG-PY-007 | Văn bản cán bộ nhập | Được escape ở mọi nơi (chống XSS) | Bảo mật | ✅ Đạt | `reader_pages · text_entered_by_staff_is_escaped_everywhere` |
| CDG-PY-008 | Văn bản định dạng của hồ sơ đơn vị | Được làm sạch, giữ định dạng | Bảo mật | ✅ Đạt | `reader_pages · rich_text_of_the_profile_is_sanitised_not_escaped` |
| CDG-PY-009 | Đăng nhập với địa chỉ quay lại ra ngoài site | Chỉ quay lại trong site | Bảo mật | ✅ Đạt | `reader_pages · sign_in_page_returns_only_to_this_site` |
| CDG-PY-010 | Người đã đăng nhập mở trang đăng nhập | Bỏ qua trang đăng nhập | Chức năng | ✅ Đạt | `reader_pages · people_who_are_already_in_skip_the_sign_in_page` |
| CDG-PY-011 | Trang đăng ký | Theo thiết lập của site | Chức năng | ✅ Đạt | `reader_pages · sign_up_page_follows_the_site_setting` |
| CDG-PY-012 | Link đặt mật khẩu đúng, sai, hết hạn | Xử lý đúng từng trường hợp | Ngoại lệ | ✅ Đạt | `reader_pages · set_password_page_knows_good_bad_and_expired_links` |
| CDG-PY-013 | Link đặt mật khẩu dùng cho tài khoản cán bộ | Bị từ chối | Bảo mật | ✅ Đạt | `reader_pages · set_password_link_refuses_staff` |
| CDG-PY-014 | Khách mở trang cần đăng nhập | Đăng nhập rồi quay lại đúng trang | Chức năng | ✅ Đạt | `reader_pages · guests_are_sent_to_sign_in_and_come_back` |
| CDG-PY-015 | Tài khoản không có vai trò | Bị từ chối | Phân quyền | ✅ Đạt | `reader_pages · user_without_reader_or_staff_role_is_refused` |
| CDG-PY-016 | Độc giả mở trang tìm kiếm | Hiển thị đúng | Chức năng | ✅ Đạt | `reader_pages · search_page_for_reader` |
| CDG-PY-017 | Cán bộ và người không hồ sơ mở trang tìm kiếm | Có lời giải thích | Ngoại lệ | ✅ Đạt | `reader_pages · search_page_tells_staff_and_users_without_a_profile` |
| CDG-PY-018 | Nhóm không được tìm mở trang tìm kiếm | Báo không được phép | Phân quyền | ✅ Đạt | `reader_pages · search_page_for_a_group_that_may_not_search` |
| CDG-PY-019 | Trang hồ sơ | Hiện hồ sơ và văn bản | Chức năng | ✅ Đạt | `reader_pages · file_page_shows_the_file_and_its_documents` |
| CDG-PY-020 | Trang hồ sơ/văn bản ngoài phạm vi | Bị ẩn | Phân quyền | ✅ Đạt | `reader_pages · file_and_document_pages_hide_what_the_reader_may_not_see` |
| CDG-PY-021 | Trang văn bản | Theo quyền xem trước | Phân quyền | ✅ Đạt | `reader_pages · document_page_follows_the_preview_flag` |
| CDG-PY-022 | Địa chỉ trình xem văn bản cũ | Vẫn hoạt động | Chức năng | ✅ Đạt | `reader_pages · old_document_viewer_address_still_works` |
| CDG-PY-023 | Trang góp ý | Hoạt động | Chức năng | ✅ Đạt | `reader_pages · feedback_pages` |
| CDG-PY-024 | Trang tài khoản | Hoạt động | Chức năng | ✅ Đạt | `reader_pages · account_page` |
| CDG-PY-025 | Trang thông báo và chuông | Hoạt động | Chức năng | ✅ Đạt | `reader_pages · notifications_page_and_bell` |
| CDG-PY-026 | Đầu trang | Hiện giỏ phiếu và liên kết sang ứng dụng cán bộ | Chức năng | ✅ Đạt | `reader_pages · header_shows_the_basket_and_the_staff_link` |
| CDG-PY-027 | Đăng ký độc giả | Chờ cán bộ duyệt | Chức năng | ✅ Đạt | `reader_site · registration_waits_for_an_officer` |
| CDG-PY-028 | Site tắt đăng ký | Bị từ chối | Phân quyền | ✅ Đạt | `reader_site · registration_is_refused_when_the_site_does_not_take_sign_ups` |
| CDG-PY-029 | Dữ liệu đăng ký sai, có HTML | Được kiểm và làm sạch | Ngoại lệ | ✅ Đạt | `reader_site · registration_input_is_validated_and_cleaned` |
| CDG-PY-030 | Đăng ký bằng email đã có tài khoản | Trả lời như mọi trường hợp khác | Bảo mật | ✅ Đạt | `reader_site · nobody_learns_whether_an_email_has_an_account` |
| CDG-PY-031 | Bot điền trường bẫy | Không lưu gì | Bảo mật | ✅ Đạt | `reader_site · api_honeypot_stores_nothing` |
| CDG-PY-032 | Site tự duyệt đăng ký | Tạo tài khoản ngay | Chức năng | ✅ Đạt | `reader_site · site_can_approve_registrations_by_itself` |
| CDG-PY-033 | Cán bộ duyệt đăng ký | Tạo tài khoản và link dùng một lần | Chức năng | ✅ Đạt | `reader_site · officer_approval_creates_the_account_and_a_one_time_link` |
| CDG-PY-034 | Duyệt lỗi giữa chừng | Không để lại dữ liệu dở dang | Ngoại lệ | ✅ Đạt | `reader_site · approval_that_cannot_finish_leaves_nothing_behind` |
| CDG-PY-035 | Từ chối đăng ký không có lý do | Bị chặn | Ngoại lệ | ✅ Đạt | `reader_site · rejection_needs_a_reason` |
| CDG-PY-036 | Ứng dụng cán bộ | Có hàng đợi đăng ký kèm bộ đếm | Chức năng | ✅ Đạt | `reader_site · staff_boot_lists_the_queue_with_its_counter` |
| CDG-PY-037 | Người khác xử lý hàng đợi đăng ký | Bị từ chối | Phân quyền | ✅ Đạt | `reader_site · only_officers_work_the_queue` |
| CDG-PY-038 | Cấp lại link bị mất | Chỉ sau khi đã duyệt | Biên | ✅ Đạt | `reader_site · lost_link_can_be_issued_again_only_after_approval` |
| CDG-PY-039 | Độc giả quên mật khẩu | Yêu cầu qua cán bộ | Chức năng | ✅ Đạt | `reader_site · forgotten_password_goes_through_an_officer` |
| CDG-PY-040 | Tài khoản cán bộ dùng kênh độc giả | Không nhận link hay yêu cầu đặt lại | Bảo mật | ✅ Đạt | `reader_site · staff_accounts_never_get_a_link_or_a_reset_request` |
| CDG-PY-041 | Hồ sơ đơn vị chưa điền | Có giá trị mặc định | Biên | ✅ Đạt | `reader_site · profile_has_defaults_when_nothing_is_filled_in` |
| CDG-PY-042 | Danh sách lãnh đạo | Ẩn người bị ẩn, sắp thứ tự phần còn lại | Chức năng | ✅ Đạt | `reader_site · profile_hides_hidden_leaders_and_orders_the_rest` |
| CDG-PY-043 | Văn bản hồ sơ đơn vị | Được làm sạch; liên kết được kiểm | Bảo mật | ✅ Đạt | `reader_site · profile_text_is_sanitised_and_links_are_checked` |
| CDG-PY-044 | Tắt một trang công khai | Trang bị tắt | Chức năng | ✅ Đạt | `reader_site · profile_can_switch_pages_off` |
| CDG-PY-045 | Cây cơ cấu tổ chức | Lồng nhau; ẩn theo đơn vị cha | Chức năng | ✅ Đạt | `reader_site · unit_tree_nests_and_hides_with_the_parent` |
| CDG-PY-046 | Đơn vị là cha của chính nó | Bị từ chối | Ngoại lệ | ✅ Đạt | `reader_site · unit_cannot_be_its_own_parent` |
| CDG-PY-047 | Cán bộ quyết định phiếu | Độc giả được thông báo | Chức năng | ✅ Đạt | `reader_site · reader_is_told_when_an_officer_decides` |
| CDG-PY-048 | Phiếu bị từ chối | Lý do tới độc giả | Chức năng | ✅ Đạt | `reader_site · rejection_reason_reaches_the_reader` |
| CDG-PY-049 | Thông báo phiếu sao chụp, góp ý | Có liên kết riêng | Chức năng | ✅ Đạt | `reader_site · copy_slip_and_feedback_notify_with_their_own_links` |
| CDG-PY-050 | Thông báo của độc giả | Riêng tư; đánh dấu đã đọc được | Bảo mật | ✅ Đạt | `reader_site · notifications_are_private_and_can_be_marked_read` |
| CDG-PY-051 | Gửi thông báo bị lỗi | Không làm hỏng thao tác chính | Biên | ✅ Đạt | `reader_site · notifying_never_breaks_the_caller` |
| CDG-PY-052 | Trang tài khoản | Hiện hồ sơ và quyền của nhóm | Chức năng | ✅ Đạt | `reader_site · account_shows_the_profile_and_what_the_group_allows` |
| CDG-PY-053 | Độc giả sửa hồ sơ | Chỉ sửa được trường liên hệ | Phân quyền | ✅ Đạt | `reader_site · profile_edit_is_limited_to_contact_fields` |
| CDG-PY-054 | Người không có hồ sơ mở trang tài khoản | Bị từ chối | Phân quyền | ✅ Đạt | `reader_site · account_needs_a_reader_profile` |
| CDG-PY-055 | Đổi mật khẩu với mật khẩu hiện tại sai | Báo lỗi; không bị đăng xuất | Ngoại lệ | ✅ Đạt | `reader_site · a_wrong_current_password_is_a_message_not_an_authentication_error` |
| CDG-PY-056 | Đổi mật khẩu thiếu một trường | Bị từ chối | Ngoại lệ | ✅ Đạt | `reader_site · password_change_asks_for_both_passwords` |
| CDG-PY-057 | Hạn của link đặt mật khẩu | Chỉ thay giá trị mặc định của Frappe | Biên | ✅ Đạt | `reader_site · set_password_link_expiry_only_replaces_the_factory_value` |
| CDG-PY-058 | Gieo dữ liệu | Đăng ký thông báo cho cán bộ | Chức năng | ✅ Đạt | `reader_site · seed_registers_the_officer_notification` |
| CDG-PY-059 | Liên kết xem trước | Trỏ tới trang văn bản của cổng độc giả | Chức năng | ✅ Đạt | `reader_ui_logic · preview_points_to_the_reader_site_document_page` |
| CDG-PY-060 | Trang văn bản | Có cổng kiểm quyền | Phân quyền | ✅ Đạt | `reader_ui_logic · document_page_gates_access` |

**API qua HTTP (đầu cuối)** (13)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| CDG-API-001 | Khách mở 9 trang công khai (trang chủ, giới thiệu, lãnh đạo, cơ cấu, liên hệ, hướng dẫn, đăng nhập, đăng ký, quên mật khẩu) | 200, là trang riêng của cổng (không phải Desk) | Chức năng | ✅ Đạt (9/9) | `e2e_http.py:173` |
| CDG-API-002 | Mở link đặt mật khẩu không hợp lệ | Báo "không hợp lệ" | Ngoại lệ | ✅ Đạt | `e2e_http.py:174` |
| CDG-API-003 | Độc giả mở 5 trang khu vực độc giả (phiếu, sao chụp, góp ý, tài khoản, thông báo) | 200 | Chức năng | ✅ Đạt (5/5) | `e2e_http.py:180` |
| CDG-API-004 | Độc giả mở hồ sơ không tồn tại | 404 | Ngoại lệ | ✅ Đạt | `e2e_http.py:181` |
| CDG-API-005 | Gửi đăng ký bằng GET | 403/405 | Bảo mật | ✅ Đạt | `e2e_http.py:190` |
| CDG-API-006 | Bot điền trường bẫy khi đăng ký | Trả lời như đăng ký thật | Bảo mật | ✅ Đạt | `e2e_http.py:192` |
| CDG-API-007 | Đăng ký với email sai | 400/417 | Ngoại lệ | ✅ Đạt | `e2e_http.py:194` |
| CDG-API-008 | Độc giả, độc giả không hồ sơ, khách xem hàng đợi đăng ký | 401/403 | Phân quyền | ✅ Đạt (3/3) | `e2e_http.py:196` |
| CDG-API-009 | Độc giả, độc giả không hồ sơ, khách đọc danh sách nhóm độc giả | 401/403 | Phân quyền | ✅ Đạt (3/3) | `e2e_http.py:197` |
| CDG-API-010 | Phòng đọc xem hàng đợi đăng ký | 200 | Chức năng | ✅ Đạt | `e2e_http.py:199` |
| CDG-API-011 | Hàng đợi sau khi bot đăng ký | Không có yêu cầu của bot | Bảo mật | ✅ Đạt | `e2e_http.py:200` |
| CDG-API-012 | Đổi mật khẩu với mật khẩu hiện tại sai | 417 | Ngoại lệ | ✅ Đạt | `e2e_http.py:206` |
| CDG-API-013 | Sau lần đổi mật khẩu sai | Độc giả vẫn đăng nhập | Biên | ✅ Đạt | `e2e_http.py:207` |

**Giao diện (đơn vị)** (28)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| CDG-UI-001 | Địa chỉ quay lại ra ngoài site | Không đi theo | Bảo mật | ✅ Đạt | `reader.test.js · helpers` |
| CDG-UI-002 | Ngày trên cổng độc giả | Kiểu Việt Nam | Chức năng | ✅ Đạt | `reader.test.js · helpers` |
| CDG-UI-003 | Thông báo máy chủ mã hóa hai lớp | Giải mã đúng | Chức năng | ✅ Đạt | `reader.test.js · helpers` |
| CDG-UI-004 | Gọi API đọc | GET với tham số đã điền và header CSRF | Bảo mật | ✅ Đạt | `reader.test.js · call` |
| CDG-UI-005 | Gọi API ghi | POST JSON | Chức năng | ✅ Đạt | `reader.test.js · call` |
| CDG-UI-006 | Phiên hết hạn | Sang đăng nhập, nhớ trang cũ | Chức năng | ✅ Đạt | `reader.test.js · call` |
| CDG-UI-007 | 401 do sai mật khẩu | Coi là câu trả lời, không chuyển trang | Biên | ✅ Đạt | `reader.test.js · call` |
| CDG-UI-008 | Mất mạng | Báo lỗi kết nối | Ngoại lệ | ✅ Đạt | `reader.test.js · call` |
| CDG-UI-009 | Đăng nhập thiếu email/mật khẩu | Bị chặn | Ngoại lệ | ✅ Đạt | `reader.test.js · loginForm` |
| CDG-UI-010 | Đăng nhập thành công | Về trang yêu cầu hoặc trang chủ theo vai trò | Chức năng | ✅ Đạt | `reader.test.js · loginForm` |
| CDG-UI-011 | Đăng nhập sai | Không nói sai email hay mật khẩu | Bảo mật | ✅ Đạt | `reader.test.js · loginForm` |
| CDG-UI-012 | Địa chỉ quay lại ra ngoài sau đăng nhập | Không đi theo | Bảo mật | ✅ Đạt | `reader.test.js · loginForm` |
| CDG-UI-013 | Đăng ký | Gửi kèm trường bẫy; hiện kết quả | Bảo mật | ✅ Đạt | `reader.test.js · guest forms` |
| CDG-UI-014 | Đăng ký thiếu tên/email | Yêu cầu nhập | Ngoại lệ | ✅ Đạt | `reader.test.js · guest forms` |
| CDG-UI-015 | Máy chủ từ chối đăng ký | Giữ form | Ngoại lệ | ✅ Đạt | `reader.test.js · guest forms` |
| CDG-UI-016 | Đặt mật khẩu từ link | Đặt được và đăng nhập | Chức năng | ✅ Đạt | `reader.test.js · guest forms` |
| CDG-UI-017 | Hai mật khẩu không khớp | Báo lỗi trước khi gửi | Ngoại lệ | ✅ Đạt | `reader.test.js · guest forms` |
| CDG-UI-018 | Link hết hạn | Giải thích | Ngoại lệ | ✅ Đạt | `reader.test.js · guest forms` |
| CDG-UI-019 | Mật khẩu mới không đạt | Báo lỗi trước khi gửi | Ngoại lệ | ✅ Đạt | `reader.test.js · account page` |
| CDG-UI-020 | Sai mật khẩu hiện tại | Báo sai | Ngoại lệ | ✅ Đạt | `reader.test.js · account page` |
| CDG-UI-021 | Đổi mật khẩu xong | Xóa các ô mật khẩu | Bảo mật | ✅ Đạt | `reader.test.js · account page` |
| CDG-UI-022 | Đánh dấu tất cả đã đọc | Chuông cập nhật | Chức năng | ✅ Đạt | `reader.test.js · notifications page` |
| CDG-UI-023 | Link đặt mật khẩu cho cán bộ trao | Dựng đầy đủ từ đường dẫn tương đối | Chức năng | ✅ Đạt | `registrations.test.js · registration queue helpers` |
| CDG-UI-024 | Hàng đợi đăng ký | Phân biệt đăng ký và yêu cầu mật khẩu | Chức năng | ✅ Đạt | `registrations.test.js · registration queue helpers` |
| CDG-UI-025 | Nút duyệt | Mô tả việc duyệt sẽ làm | Chức năng | ✅ Đạt | `registrations.test.js · registration queue helpers` |
| CDG-UI-026 | Trạng thái | Tô màu | Chức năng | ✅ Đạt | `registrations.test.js · registration queue helpers` |
| CDG-UI-027 | Bộ đếm thanh bên | Khớp hàng đợi | Chức năng | ✅ Đạt | `registrations.test.js · registration queue helpers` |
| CDG-UI-028 | Bộ lọc trạng thái | Hàng đợi trước, "tất cả" sau | Chức năng | ✅ Đạt | `registrations.test.js · registration queue helpers` |

**Trình duyệt (đầu cuối)** (14)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| CDG-E2E-001 | Khách mở trang chủ | Giới thiệu đơn vị; có nút đăng nhập, đăng ký | Chức năng | ✅ Đạt | `reader.mjs` |
| CDG-E2E-002 | Đăng nhập sai mật khẩu | Bị từ chối, không nói sai phần nào | Bảo mật | ✅ Đạt | `reader.mjs` |
| CDG-E2E-003 | Khách đăng ký | Báo yêu cầu đang chờ duyệt | Chức năng | ✅ Đạt | `reader.mjs` |
| CDG-E2E-004 | Đăng ký lại cùng email / email đã có tài khoản | Cùng một câu trả lời | Bảo mật | ✅ Đạt | `reader.mjs` |
| CDG-E2E-005 | Link đặt mật khẩu sai | Có giải thích | Ngoại lệ | ✅ Đạt | `reader.mjs` |
| CDG-E2E-006 | Hàng đợi đăng ký | Có yêu cầu mới; bộ đếm thanh bên | Chức năng | ✅ Đạt | `reader.mjs` |
| CDG-E2E-007 | Duyệt đăng ký | Tạo tài khoản; link hiện một lần | Chức năng | ✅ Đạt | `reader.mjs` |
| CDG-E2E-008 | Sau khi duyệt | Yêu cầu rời danh sách chờ | Chức năng | ✅ Đạt | `reader.mjs` |
| CDG-E2E-009 | Độc giả đặt mật khẩu từ link | Đăng nhập được | Chức năng | ✅ Đạt | `reader.mjs` |
| CDG-E2E-010 | Dùng lại link | Không còn hiệu lực | Bảo mật | ✅ Đạt | `reader.mjs` |
| CDG-E2E-011 | Trang hồ sơ và trang văn bản | Liệt kê văn bản; xem trước được | Chức năng | ✅ Đạt | `reader.mjs` |
| CDG-E2E-012 | Chuông thông báo | Đếm hai quyết định; liên kết tới phiếu | Chức năng | ✅ Đạt | `reader.mjs` |
| CDG-E2E-013 | Sửa thông tin liên hệ; đổi mật khẩu không có mật khẩu cũ | Lưu được; đổi mật khẩu cần mật khẩu hiện tại | Ngoại lệ | ✅ Đạt | `reader.mjs` |
| CDG-E2E-014 | Đăng nhập bằng mật khẩu mới | Về trang đã yêu cầu | Chức năng | ✅ Đạt | `reader.mjs` |

<a id="ph"></a>

### 5.6 Phiếu sử dụng và phiếu sao chụp

160 test case: 160 đạt.

**Máy chủ (tích hợp)** (93)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| PH-PY-001 | In phiếu | Có các mục và vị trí lấy tài liệu | Chức năng | ✅ Đạt | `reader_admin · slips_print_with_their_items_and_where_to_find_them` |
| PH-PY-002 | Mẫu in phiếu | Dùng văn bản của mẫu; bỏ mục bị từ chối | Chức năng | ✅ Đạt | `reader_admin · print_formats_use_the_template_texts_and_leave_out_turned_down_items` |
| PH-PY-003 | Liên kết in | Dẫn tới màn hình phiếu | Chức năng | ✅ Đạt | `reader_admin · print_links_reach_the_slip_screen` |
| PH-PY-004 | Phòng đọc mở ứng dụng | Thấy hàng đợi phiếu và màn hình độc giả | Phân quyền | ✅ Đạt | `reader_admin · the_reading_room_sees_the_queues_and_the_reader_screens` |
| PH-PY-005 | Lãnh đạo mở hàng đợi | Thấy phiếu chờ lãnh đạo | Phân quyền | ✅ Đạt | `reader_admin · a_leader_sees_what_waits_for_a_leader` |
| PH-PY-006 | Cán bộ không có vai trò liên quan | Không thấy hàng đợi và màn hình độc giả | Phân quyền | ✅ Đạt | `reader_admin · staff_without_a_role_here_see_none_of_it` |
| PH-PY-007 | Huy hiệu số trên thanh bên | Theo đúng số lượng | Chức năng | ✅ Đạt | `reader_admin · queue_badges_follow_the_counts` |
| PH-PY-008 | Phiếu cũ thiếu tên độc giả | Được bổ sung | Chức năng | ✅ Đạt | `reader_admin · backfill_gives_old_slips_their_reader_name` |
| PH-PY-009 | Danh sách phiếu trên cổng | Chỉ phiếu của độc giả | Phân quyền | ✅ Đạt | `reader_pages · slip_list_is_the_readers_own` |
| PH-PY-010 | Phiếu nháp | Sửa được | Chức năng | ✅ Đạt | `reader_pages · draft_slip_is_editable` |
| PH-PY-011 | Phiếu đã gửi | Chỉ đọc, có tiến trình và nút in | Chức năng | ✅ Đạt | `reader_pages · sent_slip_is_read_only_with_progress_and_print` |
| PH-PY-012 | Phiếu đã quyết định | Hiện kết quả | Chức năng | ✅ Đạt | `reader_pages · decided_slips_show_the_outcome` |
| PH-PY-013 | Mở phiếu người khác / phiếu không tồn tại | Bị từ chối; hai trường hợp trả lời như nhau | Bảo mật | ✅ Đạt | `reader_pages · nobody_opens_another_readers_slip_and_missing_ones_look_the_same` |
| PH-PY-014 | Trang phiếu sao chụp | Có số bản | Chức năng | ✅ Đạt | `reader_pages · copy_slip_page_has_copy_counts` |
| PH-PY-015 | Cán bộ không hồ sơ mở trang phiếu | Có lời giải thích | Ngoại lệ | ✅ Đạt | `reader_pages · slip_pages_for_staff_without_a_profile_explain_themselves` |
| PH-PY-016 | Thêm vào giỏ | Gom vào một phiếu nháp đang mở | Chức năng | ✅ Đạt | `reader_site · adding_to_the_basket_builds_one_open_draft` |
| PH-PY-017 | Giỏ sao chụp và giỏ sử dụng | Tách riêng | Chức năng | ✅ Đạt | `reader_site · copy_and_usage_baskets_are_separate` |
| PH-PY-018 | Thêm mục ngoài phạm vi vào giỏ | Bị từ chối | Phân quyền | ✅ Đạt | `reader_site · basket_refuses_what_the_reader_may_not_see` |
| PH-PY-019 | Nhóm không cho lập phiếu | Giỏ từ chối | Phân quyền | ✅ Đạt | `reader_site · basket_follows_the_feature_flags_of_the_group` |
| PH-PY-020 | Cán bộ không có hồ sơ độc giả | Không có giỏ | Phân quyền | ✅ Đạt | `reader_site · staff_without_a_reader_profile_has_no_basket` |
| PH-PY-021 | Cán bộ có hồ sơ độc giả | Dùng được giỏ | Chức năng | ✅ Đạt | `reader_site · staff_with_a_reader_profile_can_use_the_basket` |
| PH-PY-022 | Bỏ dòng; hủy giỏ | Thực hiện đúng | Chức năng | ✅ Đạt | `reader_site · removing_rows_and_discarding` |
| PH-PY-023 | Sửa giỏ người khác / phiếu đã gửi | Bị từ chối | Bảo mật | ✅ Đạt | `reader_site · nobody_edits_another_readers_basket_or_a_sent_slip` |
| PH-PY-024 | Cán bộ có hồ sơ độc giả lập phiếu | Mặc định dùng hồ sơ của mình | Chức năng | ✅ Đạt | `reader_ui_logic · staff_with_profile_defaults_to_own_profile` |
| PH-PY-025 | Cán bộ lập phiếu thay độc giả khác | Được phép | Chức năng | ✅ Đạt | `reader_ui_logic · staff_can_file_on_behalf_of_another_reader` |
| PH-PY-026 | Cán bộ không hồ sơ lập phiếu mà không chọn độc giả | Bị yêu cầu chọn độc giả | Ngoại lệ | ✅ Đạt | `reader_ui_logic · staff_without_profile_must_choose_a_reader` |
| PH-PY-027 | Độc giả không hồ sơ lập phiếu | Bị từ chối | Phân quyền | ✅ Đạt | `reader_ui_logic · reader_without_profile_cannot_file` |
| PH-PY-028 | Độc giả ngừng hoạt động lập phiếu | Bị từ chối | Phân quyền | ✅ Đạt | `reader_ui_logic · inactive_reader_cannot_file` |
| PH-PY-029 | Lãnh đạo lưu trữ | Đọc được kho lưu trữ, không sửa | Phân quyền | ✅ Đạt | `request_lifecycle · archive_leader_is_staff_who_reads_the_archive_but_does_not_edit_it` |
| PH-PY-030 | Gieo quy trình duyệt | Đầy đủ; chạy lại được | Chức năng | ✅ Đạt | `request_lifecycle · workflow_seed_is_complete_and_repeatable` |
| PH-PY-031 | Phiếu không có mục mật | Phòng đọc tự duyệt | Chức năng | ✅ Đạt | `request_lifecycle · a_slip_without_confidential_items_is_approved_by_the_reading_room` |
| PH-PY-032 | Phiếu có mục mật | Cần lãnh đạo duyệt | Phân quyền | ✅ Đạt | `request_lifecycle · confidential_items_need_a_leader` |
| PH-PY-033 | Lãnh đạo trả phiếu | Phiếu về phòng đọc | Chức năng | ✅ Đạt | `request_lifecycle · a_leader_can_return_a_slip_to_the_reading_room` |
| PH-PY-034 | Chế độ duyệt của nhóm độc giả | Quyết định cách duyệt | Chức năng | ✅ Đạt | `request_lifecycle · the_reader_group_decides_how_slips_are_approved` |
| PH-PY-035 | Phiếu sao chụp | Cùng luật duyệt | Chức năng | ✅ Đạt | `request_lifecycle · copy_slips_follow_the_same_approval_rules` |
| PH-PY-036 | Duyệt từng mục | Được | Chức năng | ✅ Đạt | `request_lifecycle · the_officer_decides_item_by_item` |
| PH-PY-037 | Duyệt phiếu khi mọi mục bị từ chối | Bị chặn | Ngoại lệ | ✅ Đạt | `request_lifecycle · a_slip_cannot_be_approved_with_every_item_turned_down` |
| PH-PY-038 | Từ chối phiếu | Mọi mục bị từ chối | Chức năng | ✅ Đạt | `request_lifecycle · rejecting_a_slip_rejects_all_its_items` |
| PH-PY-039 | Người không đúng vai trò duyệt mục | Bị từ chối | Phân quyền | ✅ Đạt | `request_lifecycle · only_the_right_staff_decide_items` |
| PH-PY-040 | Giao tài liệu | Bắt đầu tính hạn trả | Chức năng | ✅ Đạt | `request_lifecycle · handing_over_starts_the_clock` |
| PH-PY-041 | Nhận trả tài liệu | Ghi tình trạng từng mục | Chức năng | ✅ Đạt | `request_lifecycle · receiving_the_return_records_the_condition_of_each_item` |
| PH-PY-042 | Gia hạn | Trong giới hạn số lần | Biên | ✅ Đạt | `request_lifecycle · renewal_extends_within_the_limit` |
| PH-PY-043 | Gia hạn phiếu quá hạn | Tính từ hôm nay; bỏ cờ quá hạn | Biên | ✅ Đạt | `request_lifecycle · an_overdue_slip_is_extended_from_today_and_loses_its_flag` |
| PH-PY-044 | Gia hạn | Chỉ phòng đọc, chỉ phiếu đang sử dụng | Phân quyền | ✅ Đạt | `request_lifecycle · only_the_reading_room_renews_and_only_slips_in_use` |
| PH-PY-045 | Số mục mỗi phiếu | Bị giới hạn | Biên | ✅ Đạt | `request_lifecycle · items_per_slip_are_limited` |
| PH-PY-046 | Số phiếu mỗi ngày | Giới hạn theo loại; hủy phiếu trả lại lượt | Biên | ✅ Đạt | `request_lifecycle · slips_per_day_are_limited_per_kind_and_cancelling_frees_one` |
| PH-PY-047 | Số phiếu đang mở | Bị giới hạn | Biên | ✅ Đạt | `request_lifecycle · open_slips_are_limited` |
| PH-PY-048 | Độc giả đang giữ tài liệu quá hạn | Chặn phiếu sử dụng mới; không chặn sao chụp | Biên | ✅ Đạt | `request_lifecycle · overdue_documents_block_new_usage_slips_but_not_copies` |
| PH-PY-049 | Cán bộ lập phiếu thay | Không bị hạn mức của độc giả | Chức năng | ✅ Đạt | `request_lifecycle · staff_filing_for_a_reader_are_not_held_to_the_readers_limits` |
| PH-PY-050 | Độc giả sửa phiếu đã gửi | Bị chặn | Phân quyền | ✅ Đạt | `request_lifecycle · the_reader_cannot_change_a_sent_slip` |
| PH-PY-051 | Job hằng ngày | Đánh dấu quá hạn; báo độc giả một lần | Chức năng | ✅ Đạt | `request_lifecycle · daily_job_flags_overdue_slips_and_tells_the_reader_once` |
| PH-PY-052 | Job nhắc trước hạn | Nhắc; xóa cờ đã cũ | Chức năng | ✅ Đạt | `request_lifecycle · daily_job_reminds_before_the_due_date_and_clears_stale_flags` |
| PH-PY-053 | Tắt nhắc | Cờ quá hạn vẫn giữ | Biên | ✅ Đạt | `request_lifecycle · reminders_can_be_switched_off_but_the_flag_stays` |
| PH-PY-054 | Lịch job | Đã đăng ký | Chức năng | ✅ Đạt | `request_lifecycle · daily_job_is_registered` |
| PH-PY-055 | Giá trị mặc định của thiết lập | Lưu một lần; không đè lựa chọn | Biên | ✅ Đạt | `request_lifecycle · defaults_are_stored_once_and_never_override_a_choice` |
| PH-PY-056 | Mức mật trên "Thường" | Cần lãnh đạo duyệt | Phân quyền | ✅ Đạt | `request_lifecycle · levels_above_the_public_one_ask_for_a_leader` |
| PH-PY-057 | Độc giả gửi phiếu | Chờ duyệt; gắn hồ sơ của chính độc giả | Chức năng | ✅ Đạt | `request_workflow · reader_submit_goes_to_pending_and_is_bound_to_own_profile` |
| PH-PY-058 | Độc giả tự đặt trạng thái Đã duyệt | Bị chặn | Bảo mật | ✅ Đạt | `request_workflow · reader_cannot_self_approve_by_saving_state` |
| PH-PY-059 | Độc giả chạy thao tác của cán bộ | Bị chặn | Phân quyền | ✅ Đạt | `request_workflow · reader_cannot_run_staff_actions` |
| PH-PY-060 | Độc giả sửa trường được bảo vệ | Bị chặn | Bảo mật | ✅ Đạt | `request_workflow · reader_cannot_edit_protected_fields` |
| PH-PY-061 | Phòng đọc duyệt phiếu | Ghi người duyệt | Chức năng | ✅ Đạt | `request_workflow · officer_approves_and_stamps_approver` |
| PH-PY-062 | Từ chối phiếu không lý do | Bị chặn | Ngoại lệ | ✅ Đạt | `request_workflow · reject_requires_reason` |
| PH-PY-063 | Thao tác sai thứ tự quy trình | Bị chặn | Ngoại lệ | ✅ Đạt | `request_workflow · actions_must_follow_order` |
| PH-PY-064 | Độc giả hủy phiếu | Hủy được khi chờ duyệt; không được khi đã duyệt | Biên | ✅ Đạt | `request_workflow · reader_can_cancel_pending_but_not_approved` |
| PH-PY-065 | Danh sách thao tác | Theo vai trò | Phân quyền | ✅ Đạt | `request_workflow · get_actions_depends_on_role` |
| PH-PY-066 | Vòng đời phiếu sao chụp | Đúng các bước | Chức năng | ✅ Đạt | `request_workflow · copy_request_lifecycle` |
| PH-PY-067 | Hồ sơ mật vượt mức của độc giả | Bị từ chối | Phân quyền | ✅ Đạt | `request_workflow · confidential_file_is_rejected` |
| PH-PY-068 | Văn bản không thuộc hồ sơ đã chọn | Bị từ chối | Ngoại lệ | ✅ Đạt | `request_workflow · document_must_belong_to_file` |
| PH-PY-069 | Chọn văn bản | Tự điền hồ sơ | Chức năng | ✅ Đạt | `request_workflow · file_is_filled_from_document` |
| PH-PY-070 | Phiếu không có mục | Bị từ chối | Ngoại lệ | ✅ Đạt | `request_workflow · empty_request_is_rejected` |
| PH-PY-071 | Độc giả xem phiếu | Chỉ thấy phiếu của mình | Phân quyền | ✅ Đạt | `request_workflow · reader_only_sees_own_requests` |
| PH-PY-072 | Đọc hồ sơ độc giả khác | Bị từ chối | Phân quyền | ✅ Đạt | `request_workflow · reader_cannot_read_other_reader_profile` |
| PH-PY-073 | Hàng đợi phiếu | Mỗi phiếu nằm đúng tab theo trạng thái | Chức năng | ✅ Đạt | `slip_queue · each_slip_lands_in_the_view_of_its_state` |
| PH-PY-074 | Tab quá hạn | Có tab riêng, sắp theo hạn trả | Chức năng | ✅ Đạt | `slip_queue · overdue_slips_have_their_own_view_sorted_by_due_date` |
| PH-PY-075 | Bộ đếm các tab | Theo đúng hàng đợi | Chức năng | ✅ Đạt | `slip_queue · counters_follow_the_queue` |
| PH-PY-076 | Tìm và phân trang hàng đợi | Đúng | Chức năng | ✅ Đạt | `slip_queue · search_and_paging` |
| PH-PY-077 | Phiếu nháp | Liệt kê riêng | Chức năng | ✅ Đạt | `slip_queue · drafts_are_listed_apart` |
| PH-PY-078 | Chi tiết phiếu | Đủ dữ liệu màn hình cần | Chức năng | ✅ Đạt | `slip_queue · the_slip_carries_what_the_screen_shows` |
| PH-PY-079 | Cờ cho phép thao tác | Theo vai trò và bước quy trình | Phân quyền | ✅ Đạt | `slip_queue · can_flags_follow_the_role_and_the_step` |
| PH-PY-080 | Phiếu quá hạn khi job hằng ngày chưa chạy | Vẫn hiện quá hạn | Biên | ✅ Đạt | `slip_queue · overdue_shows_even_before_the_daily_job_ran` |
| PH-PY-081 | Phòng đọc xóa phiếu | Nháp xóa được; phiếu đã gửi thì không | Ngoại lệ | ✅ Đạt | `slip_queue · a_draft_can_be_deleted_by_the_reading_room_but_a_sent_slip_cannot` |
| PH-PY-082 | Phiếu của một độc giả | Hiện trên trang độc giả | Chức năng | ✅ Đạt | `slip_queue · a_readers_slips_for_the_reader_page` |
| PH-PY-083 | Người khác mở hàng đợi | Chỉ phòng đọc, lãnh đạo, quản trị viên | Phân quyền | ✅ Đạt | `slip_queue · the_queue_is_for_the_reading_room_leaders_and_admin` |
| PH-PY-084 | Lưu phiếu nháp | Lưu tại chỗ; giữ dòng thêm từ tab khác | Chức năng | ✅ Đạt | `slip_queue · the_draft_saves_the_readers_fields_in_place_and_keeps_rows_added_from_another_tab` |
| PH-PY-085 | Giỏ phiếu | Cho biết kết quả nào đã có trong phiếu nháp | Chức năng | ✅ Đạt | `slip_queue · the_basket_tells_which_results_are_already_in_a_draft` |
| PH-PY-086 | Hạn mức độc giả | Báo trước khi gửi và vẫn chặn khi gửi | Biên | ✅ Đạt | `slip_queue · the_readers_limits_are_told_before_sending_and_still_enforced` |
| PH-PY-087 | Cán bộ lập phiếu thay | Hiện tiêu đề; kiểm từng mục theo quyền độc giả | Phân quyền | ✅ Đạt | `slip_queue · filing_for_a_reader_shows_titles_and_checks_each_item_against_the_readers_rights` |
| PH-PY-088 | Thêm hồ sơ khi văn bản của nó đã có (và ngược lại) | Không cùng nằm trong phiếu nháp | Biên | ✅ Đạt | `slip_queue · a_file_and_its_documents_are_never_both_in_a_draft` |
| PH-PY-089 | Chuyển dòng sang loại phiếu khác | Được, trừ khi luật từ chối | Chức năng | ✅ Đạt | `slip_queue · a_row_moves_to_the_other_kind_of_slip_unless_the_rules_refuse_it` |
| PH-PY-090 | Lập lại phiếu đã xong; xin sao chụp từ phiếu đã duyệt | Tạo phiếu nháp mới đúng | Chức năng | ✅ Đạt | `slip_queue · a_finished_slip_is_filed_again_and_a_granted_one_asks_for_copies` |
| PH-PY-091 | Độc giả tự gia hạn trực tuyến | Chỉ trong luật | Biên | ✅ Đạt | `slip_queue · the_reader_renews_online_within_the_rules` |
| PH-PY-092 | Kết quả tìm và phiếu nháp | Báo trước cần lãnh đạo duyệt / sao chụp được không | Chức năng | ✅ Đạt | `slip_queue · results_and_drafts_tell_beforehand_what_the_slip_will_do` |
| PH-PY-093 | Cán bộ có hồ sơ độc giả dùng cổng độc giả | Chỉ thấy những gì hồ sơ độc giả được phép | Bảo mật | ✅ Đạt | `slip_queue · on_the_reader_site_a_staff_account_with_a_reader_profile_finds_only_what_that_profile_may_use` |

**API qua HTTP (đầu cuối)** (16)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| PH-API-001 | Thêm hồ sơ không tồn tại vào giỏ | 403/404/417 | Ngoại lệ | ✅ Đạt | `e2e_http.py:209` |
| PH-API-002 | Khách dùng giỏ phiếu | 401/403 | Phân quyền | ✅ Đạt | `e2e_http.py:210` |
| PH-API-003 | Phòng đọc, lãnh đạo, quản trị viên đọc 5 API hàng đợi phiếu và góp ý | 200 | Chức năng | ✅ Đạt (15/15) | `e2e_http.py:238` |
| PH-API-004 | Độc giả, độc giả không hồ sơ, khách đọc 5 API hàng đợi phiếu và góp ý | 401/403 | Phân quyền | ✅ Đạt (15/15) | `e2e_http.py:240` |
| PH-API-005 | Hàng đợi của lãnh đạo | Có tab "chờ lãnh đạo" | Chức năng | ✅ Đạt | `e2e_http.py:243` |
| PH-API-006 | Tab mặc định của lãnh đạo | Là tab "chờ lãnh đạo" | Chức năng | ✅ Đạt | `e2e_http.py:244` |
| PH-API-007 | Liệt kê phiếu với cỡ trang 100000 | Tối đa 100 dòng | Biên | ✅ Đạt | `e2e_http.py:246` |
| PH-API-008 | Gọi 4 thao tác phiếu (duyệt mục, nhận trả, gia hạn, xóa nháp) bằng GET | 403/405 | Bảo mật | ✅ Đạt (4/4) | `e2e_http.py:252` |
| PH-API-009 | Độc giả, độc giả không hồ sơ, khách gọi 4 thao tác phiếu | 401/403 | Phân quyền | ✅ Đạt (12/12) | `e2e_http.py:255` |
| PH-API-010 | Lãnh đạo nhận trả tài liệu | 403 | Phân quyền | ✅ Đạt | `e2e_http.py:256` |
| PH-API-011 | Lãnh đạo gia hạn phiếu | 403 | Phân quyền | ✅ Đạt | `e2e_http.py:257` |
| PH-API-012 | Mở phiếu không tồn tại | 404/417 | Ngoại lệ | ✅ Đạt | `e2e_http.py:259` |
| PH-API-013 | Người ngoài cán bộ xem thẻ và phiếu của một độc giả | 401/403 | Phân quyền | ✅ Đạt | `e2e_http.py:260` |
| PH-API-014 | Khách, độc giả không hồ sơ, cán bộ tự gia hạn / lập lại / chuyển dòng trên phiếu không phải của mình | 401/403 | Phân quyền | ✅ Đạt (3/3) | `e2e_http.py:265` |
| PH-API-015 | Độc giả, không hồ sơ, khách, lãnh đạo chuẩn bị phiếu tại quầy; phòng đọc chuẩn bị phiếu | Người khác bị chặn; phòng đọc được (200) | Phân quyền | ✅ Đạt | `e2e_http.py:266` |
| PH-API-016 | Khách, độc giả, độc giả không hồ sơ in phiếu của người khác | Bị chặn | Bảo mật | ✅ Đạt (3/3) | `e2e_http.py:297` |

**Giao diện (đơn vị)** (30)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| PH-UI-001 | Giỏ phiếu khi mở trang | Lấy bộ đếm từ trang | Chức năng | ✅ Đạt | `reader.test.js · basket store` |
| PH-UI-002 | Thêm mục vào giỏ | Cập nhật số; báo độc giả | Chức năng | ✅ Đạt | `reader.test.js · basket store` |
| PH-UI-003 | Thêm mục bị từ chối | Báo lỗi; bộ đếm giữ nguyên | Ngoại lệ | ✅ Đạt | `reader.test.js · basket store` |
| PH-UI-004 | Lưu phiếu nháp | Chỉ gửi trường độc giả sửa theo dòng; giữ dòng thêm nơi khác | Chức năng | ✅ Đạt | `reader.test.js · slipEditor` |
| PH-UI-005 | Ngừng gõ | Tự lưu | Chức năng | ✅ Đạt | `reader.test.js · slipEditor` |
| PH-UI-006 | Lưu tự động bị lỗi | Giữ dấu chưa lưu; báo lỗi | Ngoại lệ | ✅ Đạt | `reader.test.js · slipEditor` |
| PH-UI-007 | Rời sang trang tìm kiếm | Lưu trước khi rời | Chức năng | ✅ Đạt | `reader.test.js · slipEditor` |
| PH-UI-008 | Chọn mục đích; chọn "Mục đích khác" | Đánh dấu; ô trống để tự ghi | Chức năng | ✅ Đạt | `reader.test.js · slipEditor` |
| PH-UI-009 | Gửi phiếu thiếu mục đích, quá số mục, vượt hạn mức | Không gửi | Biên | ✅ Đạt | `reader.test.js · slipEditor` |
| PH-UI-010 | Gửi duyệt | Không ghi đè dòng; tải lại trang | Chức năng | ✅ Đạt | `reader.test.js · slipEditor` |
| PH-UI-011 | Xóa dòng; xóa dòng cuối | Dòng cuối cần xác nhận hủy phiếu | Biên | ✅ Đạt | `reader.test.js · slipEditor` |
| PH-UI-012 | Hủy phiếu nháp | Hỏi xác nhận trong trang | Chức năng | ✅ Đạt | `reader.test.js · slipEditor` |
| PH-UI-013 | Chuyển dòng sang loại phiếu khác | Hai giỏ đúng số | Chức năng | ✅ Đạt | `reader.test.js · filing logic for the reader` |
| PH-UI-014 | Chuyển dòng cuối khỏi phiếu | Đi theo dòng sang phiếu mới | Biên | ✅ Đạt | `reader.test.js · filing logic for the reader` |
| PH-UI-015 | Tự gia hạn | Hỏi xác nhận; hiện hạn mới | Chức năng | ✅ Đạt | `reader.test.js · filing logic for the reader` |
| PH-UI-016 | Lập lại phiếu cũ | Báo mục không mang theo được | Chức năng | ✅ Đạt | `reader.test.js · filing logic for the reader` |
| PH-UI-017 | Kết quả không được sao chụp | Hiện lý do trên kết quả | Phân quyền | ✅ Đạt | `reader.test.js · filing logic for the reader` |
| PH-UI-018 | Kết quả đã có trong phiếu nháp | Mở phiếu thay vì thêm lần hai | Biên | ✅ Đạt | `reader.test.js · what is already in a draft` |
| PH-UI-019 | Hộp xác nhận của trang | Trả lời một lần; câu hỏi mới hủy câu cũ | Biên | ✅ Đạt | `reader.test.js · what is already in a draft` |
| PH-UI-020 | Loại phiếu | Hai loại; mặc định phiếu sử dụng | Chức năng | ✅ Đạt | `slips.test.js · slip helpers` |
| PH-UI-021 | Nút thao tác quy trình | Kiểu theo tác dụng | Chức năng | ✅ Đạt | `slips.test.js · slip helpers` |
| PH-UI-022 | Thứ tự nút | Bước thường làm lên đầu | Chức năng | ✅ Đạt | `slips.test.js · slip helpers` |
| PH-UI-023 | Phiếu cần lãnh đạo | Giải thích và hướng dẫn tiếp | Phân quyền | ✅ Đạt | `slips.test.js · slip helpers` |
| PH-UI-024 | Duyệt tất cả các dòng | Một thao tác | Chức năng | ✅ Đạt | `slips.test.js · slip helpers` |
| PH-UI-025 | Từ chối; thao tác không hoàn tác | Hỏi lý do; hỏi xác nhận | Ngoại lệ | ✅ Đạt | `slips.test.js · slip helpers` |
| PH-UI-026 | Quyết định từng mục | Đúng định dạng API | Chức năng | ✅ Đạt | `slips.test.js · slip helpers` |
| PH-UI-027 | Số ngày trễ | Tính từ hạn trả | Biên | ✅ Đạt | `slips.test.js · slip helpers` |
| PH-UI-028 | Tab yêu cầu không tồn tại | Dùng tab máy chủ gợi ý | Biên | ✅ Đạt | `slips.test.js · slip helpers` |
| PH-UI-029 | Bộ đếm lớn | Hiển thị gọn | Biên | ✅ Đạt | `slips.test.js · slip helpers` |
| PH-UI-030 | Trạng thái phiếu | Tô màu đủ | Chức năng | ✅ Đạt | `slips.test.js · slip helpers` |

**Trình duyệt (đầu cuối)** (21)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| PH-E2E-001 | Bấm thêm kết quả đã có trong phiếu nháp | Mở phiếu nháp, không thêm lần hai | Biên | ✅ Đạt | `reader.mjs` |
| PH-E2E-002 | Hoàn thiện phiếu sử dụng nháp, gửi duyệt | Gửi được | Chức năng | ✅ Đạt | `reader.mjs` |
| PH-E2E-003 | Sửa số bản phiếu sao chụp, gửi | Gửi được | Chức năng | ✅ Đạt | `reader.mjs` |
| PH-E2E-004 | Danh sách phiếu của độc giả | Theo trạng thái | Chức năng | ✅ Đạt | `reader.mjs` |
| PH-E2E-005 | Cán bộ duyệt phiếu sử dụng, từ chối phiếu sao chụp | Đúng trạng thái | Chức năng | ✅ Đạt | `reader.mjs` |
| PH-E2E-006 | Phiếu bị từ chối | Hiện lý do; không sửa được | Chức năng | ✅ Đạt | `reader.mjs` |
| PH-E2E-007 | Thanh bên phòng đọc | Đếm phiếu chờ | Chức năng | ✅ Đạt | `slips.mjs` |
| PH-E2E-008 | Mở hàng đợi | Ở tab tiếp nhận; có phiếu mới | Chức năng | ✅ Đạt | `slips.mjs` |
| PH-E2E-009 | Tìm trong hàng đợi | Thu hẹp | Chức năng | ✅ Đạt | `slips.mjs` |
| PH-E2E-010 | Mở phiếu | Có độc giả, các mục, vị trí kho | Chức năng | ✅ Đạt | `slips.mjs` |
| PH-E2E-011 | Từ chối một mục có lý do, duyệt phần còn lại | Đúng trạng thái từng mục | Chức năng | ✅ Đạt | `slips.mjs` |
| PH-E2E-012 | Giao tài liệu | Có hạn trả; mục "Đã giao" | Chức năng | ✅ Đạt | `slips.mjs` |
| PH-E2E-013 | Gia hạn | Hạn mới; đếm số lần | Biên | ✅ Đạt | `slips.mjs` |
| PH-E2E-014 | Phiếu đang sử dụng | Đúng tab; độc giả thấy trên cổng | Chức năng | ✅ Đạt | `slips.mjs` |
| PH-E2E-015 | Nhận trả | Ghi tình trạng từng mục | Chức năng | ✅ Đạt | `slips.mjs` |
| PH-E2E-016 | Phiếu có mục mật | Phòng đọc không tự duyệt được | Phân quyền | ✅ Đạt | `slips.mjs` |
| PH-E2E-017 | Lãnh đạo mở hàng đợi | Ở tab chờ lãnh đạo; quyết định được | Chức năng | ✅ Đạt | `slips.mjs` |
| PH-E2E-018 | Thanh bên của lãnh đạo | Không có quản lý độc giả, thiết lập | Phân quyền | ✅ Đạt | `slips.mjs` |
| PH-E2E-019 | Phòng đọc sau khi lãnh đạo duyệt | Thấy quyết định; giao được | Chức năng | ✅ Đạt | `slips.mjs` |
| PH-E2E-020 | Phiếu sao chụp | Duyệt và hoàn tất | Chức năng | ✅ Đạt | `slips.mjs` |
| PH-E2E-021 | Lập phiếu cho độc giả tại quầy | Gửi được | Chức năng | ✅ Đạt | `slips.mjs` |

<a id="qdg"></a>

### 5.7 Quản lý độc giả, mẫu phiếu và góp ý

39 test case: 39 đạt.

**Máy chủ (tích hợp)** (23)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| QDG-PY-001 | Mẫu phiếu của site | Mỗi loại có một mẫu đang dùng | Chức năng | ✅ Đạt | `reader_admin · a_site_gets_one_active_template_per_kind` |
| QDG-PY-002 | Không có mẫu | Dùng mặc định có sẵn | Biên | ✅ Đạt | `reader_admin · without_a_template_the_built_in_defaults_apply` |
| QDG-PY-003 | Kích hoạt mẫu thứ hai cùng loại | Mẫu cũ tự tắt | Biên | ✅ Đạt | `reader_admin · only_one_template_of_a_kind_is_active` |
| QDG-PY-004 | Quy tắc mẫu sai | Bị từ chối | Ngoại lệ | ✅ Đạt | `reader_admin · template_rules_are_validated` |
| QDG-PY-005 | Mẫu đăng ký | Quyết định trường được hỏi | Chức năng | ✅ Đạt | `reader_admin · registration_template_decides_which_fields_are_asked` |
| QDG-PY-006 | Mục đích của phiếu | Chỉ bắt buộc khi mẫu yêu cầu | Chức năng | ✅ Đạt | `reader_admin · a_slip_needs_a_purpose_only_when_the_template_says_so` |
| QDG-PY-007 | Tùy chọn in của mẫu | Có đầu trang, chân trang | Chức năng | ✅ Đạt | `reader_admin · print_options_carry_the_header_and_footer` |
| QDG-PY-008 | Trường bảng con trong form | Được mô tả kèm cột | Chức năng | ✅ Đạt | `reader_admin · a_table_field_is_described_with_its_columns` |
| QDG-PY-009 | Lưu dòng bảng con | Lưu, thay, đọc lại đúng | Chức năng | ✅ Đạt | `reader_admin · table_rows_are_saved_replaced_and_read_back` |
| QDG-PY-010 | Màn hình mẫu phiếu | Sửa được bảng con | Chức năng | ✅ Đạt | `reader_admin · the_template_screen_edits_its_tables` |
| QDG-PY-011 | Tìm giá trị liên kết | Gợi ý đúng loại; không bao giờ lộ User | Bảo mật | ✅ Đạt | `reader_admin · link_search_offers_what_the_forms_link_to_but_never_users` |
| QDG-PY-012 | Quản lý độc giả | Qua màn hình chung | Chức năng | ✅ Đạt | `reader_admin · readers_are_managed_through_the_generic_screen` |
| QDG-PY-013 | Thiết lập độc giả | Là một form duy nhất | Chức năng | ✅ Đạt | `reader_admin · the_reader_settings_form_is_a_single_document` |
| QDG-PY-014 | Cấp truy cập trực tuyến cho độc giả | Tạo tài khoản một lần; lần sau cấp lại link | Chức năng | ✅ Đạt | `reader_admin · online_access_creates_the_account_once_and_then_reissues_the_link` |
| QDG-PY-015 | Cấp truy cập cho độc giả không email, ngừng hoạt động, email cán bộ | Bị từ chối | Ngoại lệ | ✅ Đạt | `reader_admin · online_access_refuses_what_it_should` |
| QDG-PY-016 | Danh sách và chi tiết góp ý | Hiển thị đúng | Chức năng | ✅ Đạt | `reader_admin · feedback_list_and_detail` |
| QDG-PY-017 | Người ngoài phòng đọc, lãnh đạo xem góp ý | Bị từ chối | Phân quyền | ✅ Đạt | `reader_admin · feedback_is_for_the_reading_room_and_leaders` |
| QDG-PY-018 | In thẻ độc giả | In được | Chức năng | ✅ Đạt | `reader_admin · the_reader_card_prints` |
| QDG-PY-019 | Gửi góp ý | Dùng hồ sơ của chính người gửi | Chức năng | ✅ Đạt | `reader_ui_logic · feedback_uses_own_profile_for_everyone` |
| QDG-PY-020 | Người không hồ sơ gửi góp ý | Bị từ chối | Phân quyền | ✅ Đạt | `reader_ui_logic · feedback_without_profile_is_refused` |
| QDG-PY-021 | Ngừng hoạt động độc giả | Khóa tài khoản, trừ tài khoản cán bộ | Chức năng | ✅ Đạt | `reader_ui_logic · deactivating_reader_disables_user_but_never_staff` |
| QDG-PY-022 | Gắn tài khoản cho độc giả sau | Tài khoản nhận vai trò độc giả | Chức năng | ✅ Đạt | `reader_ui_logic · linking_a_user_later_grants_reader_role` |
| QDG-PY-023 | Quy trình góp ý | Đúng các bước | Chức năng | ✅ Đạt | `request_workflow · feedback_flow` |

**API qua HTTP (đầu cuối)** (11)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| QDG-API-001 | Lãnh đạo xem danh sách độc giả | 200 | Chức năng | ✅ Đạt | `e2e_http.py:272` |
| QDG-API-002 | Lãnh đạo tạo độc giả | 403/417 | Phân quyền | ✅ Đạt | `e2e_http.py:274` |
| QDG-API-003 | Độc giả, không hồ sơ, khách xem danh sách độc giả | 401/403 | Phân quyền | ✅ Đạt (3/3) | `e2e_http.py:276` |
| QDG-API-004 | Độc giả, không hồ sơ, khách xem mẫu phiếu | 401/403 | Phân quyền | ✅ Đạt (3/3) | `e2e_http.py:277` |
| QDG-API-005 | Độc giả, không hồ sơ, khách cấp truy cập trực tuyến | 401/403 | Phân quyền | ✅ Đạt (3/3) | `e2e_http.py:279` |
| QDG-API-006 | Lãnh đạo cấp truy cập trực tuyến | 403 | Phân quyền | ✅ Đạt | `e2e_http.py:281` |
| QDG-API-007 | Cấp truy cập trực tuyến bằng GET | 403/405 | Bảo mật | ✅ Đạt | `e2e_http.py:282` |
| QDG-API-008 | Quản trị viên đọc thiết lập độc giả | 200, có trường hạn mức | Chức năng | ✅ Đạt | `e2e_http.py:284` |
| QDG-API-009 | Lãnh đạo sửa thiết lập độc giả | 403/417 | Phân quyền | ✅ Đạt | `e2e_http.py:286` |
| QDG-API-010 | Dữ liệu khởi động của quản trị viên | Có các màn hình độc giả | Chức năng | ✅ Đạt | `e2e_http.py:288` |
| QDG-API-011 | Dữ liệu khởi động của lãnh đạo | Thiết lập độc giả ở chế độ chỉ đọc | Phân quyền | ✅ Đạt | `e2e_http.py:291` |

**Trình duyệt (đầu cuối)** (5)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| QDG-E2E-001 | Gửi góp ý | Thấy trả lời của cán bộ | Chức năng | ✅ Đạt | `reader.mjs` |
| QDG-E2E-002 | Xử lý góp ý | Đọc, đánh dấu, trả lời; độc giả thấy trả lời | Chức năng | ✅ Đạt | `slips.mjs` |
| QDG-E2E-003 | Tạo độc giả tại quầy, cấp truy cập trực tuyến | Có link đặt mật khẩu | Chức năng | ✅ Đạt | `slips.mjs` |
| QDG-E2E-004 | Mẫu phiếu thêm mục đích | Form phiếu của độc giả có mục đích đó | Chức năng | ✅ Đạt | `slips.mjs` |
| QDG-E2E-005 | Sửa thiết lập độc giả | Lưu được | Chức năng | ✅ Đạt | `slips.mjs` |

<a id="pvdg"></a>

### 5.8 Phạm vi khai thác của độc giả (phông, cấp phép, mức mật)

39 test case: 39 đạt.

**Máy chủ (tích hợp)** (35)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| PVDG-PY-001 | Độc giả xem phông Công khai và phông Theo cấp phép | Thấy phông công khai; phông theo cấp phép chỉ sau khi được cấp | Chức năng | ✅ Đạt | `fonds_access · a_reader_sees_public_fonds_and_licensed_ones_only_once_granted` |
| PVDG-PY-002 | Phông Nội bộ, kể cả khi có cấp phép | Độc giả không bao giờ thấy | Phân quyền | ✅ Đạt | `fonds_access · an_internal_fonds_is_never_open_to_readers` |
| PVDG-PY-003 | Chuyển phông sang Công khai | Mọi độc giả thấy ngay | Chức năng | ✅ Đạt | `fonds_access · making_a_fonds_public_opens_it_to_every_reader_at_once` |
| PVDG-PY-004 | Cấp phép trước ngày bắt đầu, sau ngày kết thúc | Chỉ có hiệu lực trong thời hạn | Biên | ✅ Đạt | `fonds_access · a_grant_counts_only_within_its_dates` |
| PVDG-PY-005 | Nhiều cấp phép chồng nhau | Lấy hạn dài nhất | Biên | ✅ Đạt | `fonds_access · the_longest_grant_wins` |
| PVDG-PY-006 | Cấp phép phông | Ghi người cấp; cần quyền "cấp phép phông" | Phân quyền | ✅ Đạt | `fonds_access · a_grant_records_who_gave_it_and_needs_the_right_to` |
| PVDG-PY-007 | Tìm kiếm và trang tài khoản độc giả | Theo đúng cấp phép | Chức năng | ✅ Đạt | `fonds_access · search_and_the_account_page_follow_the_grants` |
| PVDG-PY-008 | Thêm hồ sơ thuộc phông chưa cấp vào phiếu | Bị từ chối | Phân quyền | ✅ Đạt | `fonds_access · a_reader_cannot_put_an_ungranted_file_in_a_slip` |
| PVDG-PY-009 | Cán bộ lập phiếu thay độc giả không có tài khoản | Áp quyền của độc giả đó, không phải của cán bộ | Bảo mật | ✅ Đạt | `fonds_access · the_staff_filing_for_a_reader_without_an_account_is_held_to_that_readers_rights` |
| PVDG-PY-010 | Thu hồi cấp phép sau khi phiếu đã gửi | Không duyệt được mục đó | Phân quyền | ✅ Đạt | `fonds_access · a_grant_taken_back_after_sending_stops_the_approval` |
| PVDG-PY-011 | Hạn trả, gia hạn khi cấp phép sắp hết | Không vượt ngày hết hạn cấp phép | Biên | ✅ Đạt | `fonds_access · the_due_date_never_passes_the_end_of_the_grant_and_renewal_stops_there` |
| PVDG-PY-012 | Sao chụp tài liệu của phông/mức mật không cho sao chụp | Bị từ chối | Phân quyền | ✅ Đạt | `fonds_access · copies_follow_the_fonds_and_the_level` |
| PVDG-PY-013 | Job nhắc cấp phép sắp hết hạn | Độc giả được nhắc đúng một lần | Chức năng | ✅ Đạt | `fonds_access · a_reader_is_told_once_that_a_grant_ends_soon` |
| PVDG-PY-014 | Nâng cấp dữ liệu với nhóm "Tất cả phông" | Thành cấp phép tường minh cho mọi phông; quyền thấy không đổi | Chức năng | ✅ Đạt | `fonds_access · the_upgrade_turns_every_fonds_into_explicit_grants_for_groups_that_saw_every_fonds` |
| PVDG-PY-015 | Vòng đời phiếu đọc phông của từng mục | Lấy đúng phông của hồ sơ/văn bản | Chức năng | ✅ Đạt | `fonds_access · the_lifecycle_reads_the_fonds_of_an_item` |
| PVDG-PY-016 | Hồ sơ Nháp và văn bản của nó | Độc giả không thấy; cán bộ thấy | Phân quyền | ✅ Đạt | `p0_hardening · draft_file_and_its_documents_are_hidden_from_readers_but_not_staff` |
| PVDG-PY-017 | Hồ sơ Đã tiêu hủy | Độc giả không thấy | Phân quyền | ✅ Đạt | `p0_hardening · disposed_file_is_hidden_from_readers` |
| PVDG-PY-018 | Kiểm quyền từng bản ghi so với điều kiện truy vấn | Cùng kết quả với hồ sơ chưa công bố | Bảo mật | ✅ Đạt | `p0_hardening · has_permission_matches_the_query_for_unpublished_files` |
| PVDG-PY-019 | Điều kiện truy vấn của độc giả | Có điều kiện trạng thái công bố | Bảo mật | ✅ Đạt | `p0_hardening · reader_query_conditions_mention_the_published_state` |
| PVDG-PY-020 | Phạm vi của khách, cán bộ, tài khoản không có hồ sơ độc giả | Khách, người không hồ sơ: không có gì; cán bộ: theo quyền cán bộ | Phân quyền | ✅ Đạt | `policy · guest_staff_and_profileless_scopes` |
| PVDG-PY-021 | Độc giả chưa có nhóm | Áp nhóm mặc định | Chức năng | ✅ Đạt | `policy · default_group_applies_when_a_reader_has_none` |
| PVDG-PY-022 | Nhóm độc giả | Quyết định chức năng và phông | Chức năng | ✅ Đạt | `policy · group_defines_features_and_fonds` |
| PVDG-PY-023 | Mức mật cá nhân | Ghi đè nhóm, chỉ cho độc giả đó | Chức năng | ✅ Đạt | `policy · personal_clearance_overrides_the_group_for_that_reader_only` |
| PVDG-PY-024 | Nhóm bị tắt; độc giả ngừng hoạt động | Không có quyền gì | Phân quyền | ✅ Đạt | `policy · disabled_group_and_inactive_reader_get_nothing` |
| PVDG-PY-025 | Nhóm có phông trùng; xóa nhóm mặc định; hai nhóm mặc định | Bị từ chối; chỉ còn một nhóm mặc định | Ngoại lệ | ✅ Đạt | `policy · group_validation_and_single_default` |
| PVDG-PY-026 | Phạm vi phông | Giới hạn cả cây phân cấp và nội dung | Phân quyền | ✅ Đạt | `policy · fonds_scope_limits_the_hierarchy_and_the_content` |
| PVDG-PY-027 | Kiểm quyền từng bản ghi | Theo phạm vi phông | Phân quyền | ✅ Đạt | `policy · has_permission_follows_the_fonds_scope` |
| PVDG-PY-028 | Độc giả không có hồ sơ đọc qua /api/resource | Không đọc được gì | Bảo mật | ✅ Đạt | `policy · a_reader_without_a_profile_reads_nothing_through_the_resource_api` |
| PVDG-PY-029 | Bộ lọc gửi Meilisearch | Dựng từ phạm vi | Bảo mật | ✅ Đạt | `policy · meilisearch_filter_is_built_from_the_scope` |
| PVDG-PY-030 | Nhóm không có quyền tìm kiếm | Bị từ chối tìm | Phân quyền | ✅ Đạt | `policy · search_needs_the_search_feature` |
| PVDG-PY-031 | Xem trước và tải tệp gốc | Là hai quyền riêng | Phân quyền | ✅ Đạt | `policy · download_and_preview_are_separate_features` |
| PVDG-PY-032 | Lập phiếu, gửi góp ý khi nhóm không cho phép | Bị từ chối | Phân quyền | ✅ Đạt | `policy · requests_and_feedback_need_the_matching_feature` |
| PVDG-PY-033 | Đổi nhóm và mức mật của độc giả | Chỉ quản trị viên | Phân quyền | ✅ Đạt | `policy · only_admins_can_change_group_and_clearance` |
| PVDG-PY-034 | Cán bộ phòng đọc tạo độc giả | Độc giả vào nhóm mặc định | Chức năng | ✅ Đạt | `policy · an_officer_can_create_a_reader_who_lands_in_the_default_group` |
| PVDG-PY-035 | Văn bản không có mức mật | Ẩn với độc giả | Phân quyền | ✅ Đạt | `reader_ui_logic · document_without_level_is_hidden_from_readers` |

**API qua HTTP (đầu cuối)** (2)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| PVDG-API-001 | Độc giả không hồ sơ đọc văn bản qua /api/resource | Không có dữ liệu | Bảo mật | ✅ Đạt | `e2e_http.py:150` |
| PVDG-API-002 | Độc giả đọc hồ sơ qua /api/resource | Không có hồ sơ Nháp | Bảo mật | ✅ Đạt | `e2e_http.py:152` |

**Trình duyệt (đầu cuối)** (2)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| PVDG-E2E-001 | Hồ sơ vượt mức mật của độc giả | Không thấy khi tìm và khi gõ địa chỉ | Phân quyền | ✅ Đạt | `reader.mjs` |
| PVDG-E2E-002 | Cấp phông cho nhóm độc giả qua lưới | Lưu được | Chức năng | ✅ Đạt | `slips.mjs` |

<a id="pq"></a>

### 5.9 Nhóm quyền và phạm vi của cán bộ

49 test case: 49 đạt.

**Máy chủ (tích hợp)** (43)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| PQ-PY-001 | Nhóm quyền mẫu | Mỗi vai trò cán bộ là nhóm mẫu với đúng chức năng cũ | Chức năng | ✅ Đạt | `permission_profiles · every_staff_role_is_a_built_in_group_with_the_functions_it_had` |
| PQ-PY-002 | Ma trận của nhóm mẫu | Giữ đúng ai được làm gì | Chức năng | ✅ Đạt | `permission_profiles · the_built_in_groups_keep_who_may_do_what` |
| PQ-PY-003 | Quản trị viên | Có mọi chức năng | Chức năng | ✅ Đạt | `permission_profiles · administrators_hold_every_function` |
| PQ-PY-004 | Nhóm tự tạo | Thành viên là cán bộ với đúng chức năng của nhóm | Chức năng | ✅ Đạt | `permission_profiles · a_custom_group_makes_its_members_staff_with_exactly_its_functions` |
| PQ-PY-005 | Sửa nhóm quyền | Có hiệu lực ngay | Chức năng | ✅ Đạt | `permission_profiles · editing_a_group_takes_effect_at_once` |
| PQ-PY-006 | Nhóm khai chức năng lạ hoặc chức năng riêng của quản trị viên | Bị từ chối | Ngoại lệ | ✅ Đạt | `permission_profiles · a_group_only_lists_known_functions_and_never_the_administrators_own` |
| PQ-PY-007 | Nhóm Quản trị viên; nhóm mẫu sau khi sửa | Nhóm QTV không cần liệt kê (luôn đủ quyền); nhóm mẫu vẫn còn | Biên | ✅ Đạt | `permission_profiles · the_administrators_group_lists_nothing_and_built_in_groups_stay` |
| PQ-PY-008 | Người không có chức năng gọi API | Bị từ chối với cùng một thông báo | Phân quyền | ✅ Đạt | `permission_profiles · people_outside_a_function_are_refused_with_the_same_message` |
| PQ-PY-009 | Khôi phục tệp và khôi phục CSDL | Mỗi loại cần đúng quyền chức năng | Phân quyền | ✅ Đạt | `permission_profiles · a_restore_needs_the_capability_of_its_kind` |
| PQ-PY-010 | Lãnh đạo kiêm phòng đọc mở hàng đợi | Mở ở tab tiếp nhận | Chức năng | ✅ Đạt | `permission_profiles · a_leader_who_also_works_the_reading_room_opens_on_reception` |
| PQ-PY-011 | Thông báo phiếu mới | Gửi tới các nhóm xử lý phiếu | Chức năng | ✅ Đạt | `permission_profiles · slip_notifications_go_to_the_groups_that_handle_them` |
| PQ-PY-012 | Dữ liệu khởi động ứng dụng cán bộ | Nêu đúng quyền người dùng | Chức năng | ✅ Đạt | `permission_profiles · the_boot_tells_the_staff_app_what_the_user_may_do` |
| PQ-PY-013 | Tính quyền cho quản trị viên, cán bộ, độc giả, khách | Trả đúng loại và phạm vi | Chức năng | ✅ Đạt | `permission_profiles · access_answers_for_every_kind_of_user` |
| PQ-PY-014 | Người không phải quản trị viên sửa nhóm quyền | Bị từ chối | Phân quyền | ✅ Đạt | `permission_profiles · only_administrators_manage_groups` |
| PQ-PY-015 | Xem ma trận quyền | Hiện quy tắc đang áp dụng | Chức năng | ✅ Đạt | `permission_profiles · the_matrix_shows_the_rules_in_force` |
| PQ-PY-016 | Bỏ một quyền rồi khôi phục mặc định | Frappe chặn ngay; khôi phục trả lại quyền | Chức năng | ✅ Đạt | `permission_profiles · taking_a_right_away_is_enforced_by_frappe_and_reset_puts_it_back` |
| PQ-PY-017 | Tick một quyền bất kỳ; bỏ quyền đọc | Tự có quyền đọc; bỏ đọc thì mất mọi quyền | Biên | ✅ Đạt | `permission_profiles · any_right_brings_reading_and_no_reading_means_nothing` |
| PQ-PY-018 | Tạo nhóm mới | Thành viên chỉ có quyền của nhóm | Chức năng | ✅ Đạt | `permission_profiles · a_new_group_makes_its_members_staff_with_only_its_rights` |
| PQ-PY-019 | Nhân bản nhóm | Có cùng quyền với nhóm gốc | Chức năng | ✅ Đạt | `permission_profiles · a_group_copied_from_another_starts_with_the_same_rights` |
| PQ-PY-020 | Quyền "Chỉ bản ghi của mình" | Chỉ thấy/sửa bản ghi mình tạo | Phân quyền | ✅ Đạt | `permission_profiles · only_my_own_records` |
| PQ-PY-021 | Cột "Sửa trường nhạy cảm" | Quyết định ai sửa được trường nhạy cảm | Phân quyền | ✅ Đạt | `permission_profiles · the_protected_fields_follow_the_sensitive_column` |
| PQ-PY-022 | Nhóm có quyền tiếp nhận phiếu | Chuyển được phiếu trong quy trình | Chức năng | ✅ Đạt | `permission_profiles · a_group_that_receives_slips_can_move_them_in_the_workflow` |
| PQ-PY-023 | Xóa nhóm đang dùng hoặc nhóm mẫu | Bị từ chối | Ngoại lệ | ✅ Đạt | `permission_profiles · groups_in_use_and_built_in_groups_are_not_deleted` |
| PQ-PY-024 | Sửa nhóm Quản trị viên | Bị từ chối | Bảo mật | ✅ Đạt | `permission_profiles · the_administrators_group_cannot_be_changed` |
| PQ-PY-025 | Tên nhóm trùng/rỗng; lưu bản đã cũ | Bị từ chối | Ngoại lệ | ✅ Đạt | `permission_profiles · names_and_a_stale_edit_are_checked` |
| PQ-PY-026 | Danh sách nhóm quyền | Đếm đúng thành viên | Chức năng | ✅ Đạt | `permission_profiles · the_list_counts_the_members_of_each_group` |
| PQ-PY-027 | Cán bộ chưa được giới hạn phạm vi | Đọc và sửa mọi phông | Chức năng | ✅ Đạt | `staff_scope · without_a_scope_a_staff_member_reads_and_changes_every_fonds` |
| PQ-PY-028 | Phạm vi xem và phạm vi sửa khác nhau | Áp riêng từng phạm vi | Phân quyền | ✅ Đạt | `staff_scope · reading_and_changing_are_scoped_apart` |
| PQ-PY-029 | Tạo bản ghi | Theo phông nơi bản ghi được tạo | Phân quyền | ✅ Đạt | `staff_scope · creating_follows_the_fonds_a_record_lands_in` |
| PQ-PY-030 | Chuyển bản ghi giữa phông | Cần quyền sửa cả hai phông | Phân quyền | ✅ Đạt | `staff_scope · moving_a_record_needs_both_fonds` |
| PQ-PY-031 | Nhóm cán bộ có phạm vi | Cộng phông cho thành viên | Chức năng | ✅ Đạt | `staff_scope · a_staff_group_adds_fonds_to_its_members` |
| PQ-PY-032 | Mức mật tối đa của cán bộ | Ẩn tài liệu mức cao hơn | Phân quyền | ✅ Đạt | `staff_scope · the_highest_level_hides_what_is_above_it` |
| PQ-PY-033 | Phông được sửa ngoài phông được xem | Chỉ tính phần nằm trong phông được xem | Biên | ✅ Đạt | `staff_scope · fonds_to_change_stay_within_the_fonds_read` |
| PQ-PY-034 | Quản trị viên có phạm vi | Không bao giờ bị thu hẹp | Chức năng | ✅ Đạt | `staff_scope · administrators_are_never_narrowed` |
| PQ-PY-035 | Tìm kiếm và danh sách chung | Chỉ phông được xem | Phân quyền | ✅ Đạt | `staff_scope · search_and_the_generic_lists_show_only_the_fonds_read` |
| PQ-PY-036 | Mọi báo cáo | Chỉ phông được xem | Phân quyền | ✅ Đạt | `staff_scope · every_report_shows_only_the_fonds_read` |
| PQ-PY-037 | Mô tả bản ghi | Nêu người dùng được làm gì | Chức năng | ✅ Đạt | `staff_scope · a_record_says_what_the_user_may_do_with_it` |
| PQ-PY-038 | Sao lưu/khôi phục toàn kho với phạm vi hẹp | Bị từ chối | Phân quyền | ✅ Đạt | `staff_scope · preservation_of_the_whole_archive_needs_every_fonds` |
| PQ-PY-039 | Hồ sơ đã đóng | Khóa với người không có quyền sửa hồ sơ đã đóng | Phân quyền | ✅ Đạt | `staff_scope · a_closed_file_is_sealed_for_whoever_may_not_change_sealed_records` |
| PQ-PY-040 | Đóng hồ sơ; mở lại | Đóng là sửa thường; nhóm có quyền mới mở lại được | Chức năng | ✅ Đạt | `staff_scope · closing_is_a_normal_edit_and_the_capability_lets_a_group_reopen` |
| PQ-PY-041 | Phông đã đóng | Khóa mọi thứ bên trong | Phân quyền | ✅ Đạt | `staff_scope · a_closed_fonds_seals_what_it_holds` |
| PQ-PY-042 | Trường nhạy cảm (mức mật, thời hạn bảo quản) | Theo mức quyền trường | Phân quyền | ✅ Đạt | `staff_scope · the_protected_fields_follow_the_permission_level` |
| PQ-PY-043 | Quản trị viên đặt phạm vi trên màn hình người dùng | Thấy quyền thực tế | Chức năng | ✅ Đạt | `staff_scope · the_administrator_sets_a_scope_on_the_users_screen_and_sees_the_result` |

**Giao diện (đơn vị)** (5)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| PQ-UI-001 | Tick quyền bất kỳ; bỏ quyền đọc | Tự tick đọc; bỏ đọc thì bỏ hết | Biên | ✅ Đạt | `permissions.test.js · matrix helpers` |
| PQ-UI-002 | Lưu ma trận quyền | Chỉ gửi dòng thay đổi; tóm tắt bằng lời | Chức năng | ✅ Đạt | `permissions.test.js · matrix helpers` |
| PQ-UI-003 | Danh sách nhóm quyền | Nhóm mẫu trước | Chức năng | ✅ Đạt | `permissions.test.js · matrix helpers` |
| PQ-UI-004 | Trang phân quyền | Mở nhóm đầu; xem trước thay đổi; chỉ lưu phần đổi | Chức năng | ✅ Đạt | `permissions.test.js · RolesPage` |
| PQ-UI-005 | Nhóm Quản trị viên | Chỉ đọc | Bảo mật | ✅ Đạt | `permissions.test.js · RolesPage` |

**Trình duyệt (đầu cuối)** (1)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| PQ-E2E-001 | Sửa ma trận nhóm quyền | Bỏ quyền có hiệu lực ngay; khôi phục nhóm mẫu; nhân bản và xóa nhóm | Chức năng | ✅ Đạt | `admin.mjs` |

<a id="bc"></a>

### 5.10 Báo cáo, thống kê và kiểm kê

70 test case: 70 đạt.

**Máy chủ (tích hợp)** (31)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| BC-PY-001 | Chạy mọi báo cáo không bộ lọc | Chạy được, trả đúng các cột đã khai | Chức năng | ✅ Đạt | `reports · every_report_runs_with_no_filter_and_returns_what_it_declares` |
| BC-PY-002 | Danh mục báo cáo | Theo quyền người dùng | Phân quyền | ✅ Đạt | `reports · the_catalogue_of_reports_follows_the_users_rights` |
| BC-PY-003 | Độc giả, khách chạy báo cáo | Bị từ chối | Phân quyền | ✅ Đạt | `reports · readers_and_guests_cannot_run_a_report` |
| BC-PY-004 | Bộ lọc sai kiểu | Bị từ chối | Ngoại lệ | ✅ Đạt | `reports · filters_are_typed_and_validated` |
| BC-PY-005 | Báo cáo phông | Đếm mọi cấp | Chức năng | ✅ Đạt | `reports · fonds_report_counts_every_level` |
| BC-PY-006 | Báo cáo phông lọc theo năm, cơ quan | Đúng | Chức năng | ✅ Đạt | `reports · fonds_report_filters_by_years_and_agency` |
| BC-PY-007 | Báo cáo mục lục | Đúng số liệu | Chức năng | ✅ Đạt | `reports · catalogue_report` |
| BC-PY-008 | Báo cáo hồ sơ | Lọc, phân trang, dòng tổng đúng | Chức năng | ✅ Đạt | `reports · file_report_filters_pages_and_totals` |
| BC-PY-009 | Báo cáo văn bản | Lọc theo tác giả, ngày, loại | Chức năng | ✅ Đạt | `reports · document_report_filters_by_author_date_and_type` |
| BC-PY-010 | Chuỗi tìm có ký tự đặc biệt (%, _) | So khớp nguyên văn | Bảo mật | ✅ Đạt | `reports · a_search_text_is_matched_literally` |
| BC-PY-011 | Thống kê theo phông và các chiều khác | Số liệu khớp nhau | Chức năng | ✅ Đạt | `reports · statistics_by_fonds_and_the_other_dimensions_agree` |
| BC-PY-012 | Thống kê theo loại và kho | Cộng dồn lên kho | Chức năng | ✅ Đạt | `reports · statistics_by_type_and_warehouse_roll_up_to_the_warehouse` |
| BC-PY-013 | Báo cáo độc giả | Đếm phiếu của mỗi độc giả | Chức năng | ✅ Đạt | `reports · reader_report_counts_slips_per_reader` |
| BC-PY-014 | Thống kê phiếu | Theo trạng thái và tháng | Chức năng | ✅ Đạt | `reports · slip_statistics_group_by_state_and_month` |
| BC-PY-015 | Báo cáo quá hạn | Liệt kê tài liệu chưa trả | Chức năng | ✅ Đạt | `reports · overdue_report_lists_what_is_still_out` |
| BC-PY-016 | Tài liệu được yêu cầu nhiều nhất | Đúng thứ tự | Chức năng | ✅ Đạt | `reports · most_requested_items` |
| BC-PY-017 | Kiểm kê | Lấy số hệ thống; số kiểm đếm cho chênh lệch | Chức năng | ✅ Đạt | `reports · inventory_takes_the_figures_of_the_system_and_the_count_gives_the_difference` |
| BC-PY-018 | Số liệu hệ thống trong phiếu kiểm kê | Không nhập tay được; dòng phông mới đọc từ hệ thống | Bảo mật | ✅ Đạt | `reports · the_recorded_figures_are_not_typed_and_a_new_fonds_line_reads_the_system` |
| BC-PY-019 | Hoàn tất kiểm kê | Chỉ khi đếm đủ phông; sau đó bị khóa | Biên | ✅ Đạt | `reports · a_check_is_completed_only_when_every_fonds_is_counted_then_it_is_locked` |
| BC-PY-020 | Mở lại kiểm kê đã hoàn tất | Chỉ quản trị viên | Phân quyền | ✅ Đạt | `reports · only_an_administrator_reopens_a_completed_check` |
| BC-PY-021 | Thao tác kiểm kê | Chỉ vai trò biên mục | Phân quyền | ✅ Đạt | `reports · inventory_actions_belong_to_the_cataloguing_roles` |
| BC-PY-022 | Dòng phông trùng, số âm | Bị từ chối | Ngoại lệ | ✅ Đạt | `reports · duplicate_fonds_lines_and_negative_counts_are_refused` |
| BC-PY-023 | Báo cáo kiểm kê khi chưa có kiểm kê | Nói rõ chưa có | Biên | ✅ Đạt | `reports · without_a_check_the_inventory_report_says_so` |
| BC-PY-024 | Tải CSV | Có BOM, đủ cột, ngày kiểu Việt Nam | Chức năng | ✅ Đạt | `reports · csv_has_a_bom_the_columns_and_vietnamese_dates` |
| BC-PY-025 | Tải XLSX | Số ở dạng số; có đầu đơn vị | Chức năng | ✅ Đạt | `reports · xlsx_opens_with_numbers_and_the_unit_header` |
| BC-PY-026 | Tải vượt giới hạn | Bị từ chối | Biên | ✅ Đạt | `reports · a_download_larger_than_the_limit_is_refused` |
| BC-PY-027 | Bản in | Có đầu đơn vị, bộ lọc; nội dung được escape | Bảo mật | ✅ Đạt | `reports · the_printout_carries_the_unit_header_the_filters_and_escapes_what_it_prints` |
| BC-PY-028 | In PDF | Nhận tệp PDF | Chức năng | ✅ Đạt | `reports · the_printout_as_a_pdf` |
| BC-PY-029 | Xuất báo cáo | Chỉ cán bộ; định dạng lạ bị từ chối | Phân quyền | ✅ Đạt | `reports · output_is_staff_only_and_unknown_formats_are_refused` |
| BC-PY-030 | Xuất báo cáo | Được ghi nhật ký | Chức năng | ✅ Đạt | `reports · exports_are_logged` |
| BC-PY-031 | Định dạng số, ngày | Kiểu Việt Nam | Chức năng | ✅ Đạt | `reports · number_and_date_formats_are_vietnamese` |

**API qua HTTP (đầu cuối)** (17)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| BC-API-001 | Quản trị viên, lãnh đạo, phòng đọc, biên mục xem danh mục báo cáo | 200, ít nhất 6 báo cáo | Chức năng | ✅ Đạt (4/4) | `e2e_http.py:320` |
| BC-API-002 | Quản trị viên và lãnh đạo xem danh mục | Thấy mọi báo cáo (≥ 11), như nhau | Chức năng | ✅ Đạt | `e2e_http.py:321` |
| BC-API-003 | Danh mục của phòng đọc | Có báo cáo độc giả, không có kiểm kê | Phân quyền | ✅ Đạt | `e2e_http.py:322` |
| BC-API-004 | Danh mục của biên mục viên | Có báo cáo lưu trữ, không có báo cáo độc giả | Phân quyền | ✅ Đạt | `e2e_http.py:323` |
| BC-API-005 | Độc giả, không hồ sơ, khách gọi 4 API báo cáo | 401/403 | Phân quyền | ✅ Đạt (12/12) | `e2e_http.py:327` |
| BC-API-006 | Biên mục viên chạy báo cáo độc giả | 403 | Phân quyền | ✅ Đạt | `e2e_http.py:328` |
| BC-API-007 | Chạy báo cáo không tồn tại | 404 | Ngoại lệ | ✅ Đạt | `e2e_http.py:329` |
| BC-API-008 | Chạy từng báo cáo trên dữ liệu thật | 200, có cột và dòng | Chức năng | ✅ Đạt (11/11) | `e2e_http.py:335` |
| BC-API-009 | Báo cáo phân trang cỡ 2 | Tối đa 2 dòng, có cờ phân trang | Biên | ✅ Đạt | `e2e_http.py:337` |
| BC-API-010 | Giá trị bộ lọc sai | 400/417 | Ngoại lệ | ✅ Đạt | `e2e_http.py:339` |
| BC-API-011 | Tải báo cáo XLSX | Tệp XLSX hợp lệ | Chức năng | ✅ Đạt | `e2e_http.py:343` |
| BC-API-012 | Tải báo cáo CSV | Có BOM | Chức năng | ✅ Đạt | `e2e_http.py:345` |
| BC-API-013 | Trang in báo cáo | Có khối chữ ký | Chức năng | ✅ Đạt | `e2e_http.py:347` |
| BC-API-014 | In báo cáo PDF | Tệp PDF | Chức năng | ✅ Đạt | `e2e_http.py:349` |
| BC-API-015 | Tải báo cáo định dạng lạ (exe) | 400/417 | Ngoại lệ | ✅ Đạt | `e2e_http.py:350` |
| BC-API-016 | Cán bộ mở trang báo cáo | 200 | Chức năng | ✅ Đạt (4/4) | `e2e_http.py:354` |
| BC-API-017 | Độc giả mở trang báo cáo | Bị chuyển đi | Phân quyền | ✅ Đạt | `e2e_http.py:355` |

**Giao diện (đơn vị)** (11)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| BC-UI-001 | Bộ lọc khai báo | Thành ô nhập; chỉ có lựa chọn trống khi không có mặc định | Chức năng | ✅ Đạt | `reports.test.js · report filters` |
| BC-UI-002 | Mở báo cáo | Lấy mặc định và tham số trên địa chỉ | Chức năng | ✅ Đạt | `reports.test.js · report filters` |
| BC-UI-003 | Chạy báo cáo | Chỉ gửi bộ lọc có giá trị | Chức năng | ✅ Đạt | `reports.test.js · report filters` |
| BC-UI-004 | Đổi bộ lọc cha | Đặt lại mọi bộ lọc con | Biên | ✅ Đạt | `reports.test.js · report filters` |
| BC-UI-005 | Bộ lọc phụ thuộc | Tìm trong phạm vi bộ lọc cha | Chức năng | ✅ Đạt | `reports.test.js · report filters` |
| BC-UI-006 | Dựng bộ lọc | Báo thay đổi kèm xóa bộ lọc con | Chức năng | ✅ Đạt | `reports.test.js · report filters` |
| BC-UI-007 | Ô kết quả | Số, ngày, phần trăm kiểu Việt Nam | Chức năng | ✅ Đạt | `reports.test.js · report cells` |
| BC-UI-008 | Ô có liên kết thiếu dữ liệu | Chỉ liên kết khi đủ | Biên | ✅ Đạt | `reports.test.js · report cells` |
| BC-UI-009 | Chênh lệch kiểm kê | Có dấu và màu | Chức năng | ✅ Đạt | `reports.test.js · report cells` |
| BC-UI-010 | Liên kết tải/in | Mã báo cáo, định dạng, bộ lọc đang dùng | Chức năng | ✅ Đạt | `reports.test.js · report output links` |
| BC-UI-011 | Biểu đồ cột | Tỉ lệ theo cột lớn nhất; số giữ dạng chữ | Chức năng | ✅ Đạt | `reports.test.js · bar chart` |

**Trình duyệt (đầu cuối)** (11)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| BC-E2E-001 | Trang báo cáo | Liệt kê theo nhóm; có mục thanh bên | Chức năng | ✅ Đạt | `reports.mjs` |
| BC-E2E-002 | Báo cáo phông | Đếm đủ cấp | Chức năng | ✅ Đạt | `reports.mjs` |
| BC-E2E-003 | Bộ lọc phụ thuộc | Tìm trong bộ lọc cha | Chức năng | ✅ Đạt | `reports.mjs` |
| BC-E2E-004 | Thống kê | Có biểu đồ; đổi chiều nhóm được | Chức năng | ✅ Đạt | `reports.mjs` |
| BC-E2E-005 | Tải kết quả | Có Excel và CSV | Chức năng | ✅ Đạt | `reports.mjs` |
| BC-E2E-006 | Trang in | Đầu đơn vị, bộ lọc, chữ ký | Chức năng | ✅ Đạt | `reports.mjs` |
| BC-E2E-007 | Phòng đọc | Có báo cáo độc giả | Phân quyền | ✅ Đạt | `reports.mjs` |
| BC-E2E-008 | Biên mục viên | Có báo cáo lưu trữ, không có báo cáo độc giả | Phân quyền | ✅ Đạt | `reports.mjs` |
| BC-E2E-009 | Tạo kiểm kê | Lấy số hệ thống | Chức năng | ✅ Đạt | `reports.mjs` |
| BC-E2E-010 | Nhập số kiểm đếm, hoàn tất | Có chênh lệch; bị khóa | Chức năng | ✅ Đạt | `reports.mjs` |
| BC-E2E-011 | Báo cáo kiểm kê | Có chênh lệch; in thành biên bản | Chức năng | ✅ Đạt | `reports.mjs` |

<a id="xml"></a>

### 5.11 Trao đổi dữ liệu XML

83 test case: 83 đạt.

**Máy chủ (tích hợp)** (37)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| XML-PY-001 | Người không phải quản trị viên dùng trao đổi XML | Bị từ chối | Phân quyền | ✅ Đạt | `exchange · only_administrators_exchange` |
| XML-PY-002 | Danh sách trường trao đổi | Đều là trường thật, ghi được | Chức năng | ✅ Đạt | `exchange · every_exchanged_field_is_a_real_writable_field_of_its_doctype` |
| XML-PY-003 | Biên dịch XSD và kiểm tệp đúng định dạng | XSD hợp lệ; tệp được chấp nhận | Chức năng | ✅ Đạt | `exchange · the_xsd_compiles_and_accepts_a_well_formed_file` |
| XML-PY-004 | Tệp sai định dạng | XSD từ chối | Ngoại lệ | ✅ Đạt | `exchange · the_xsd_refuses_what_is_not_the_format` |
| XML-PY-005 | Tệp XML độc hại (khai báo entity, XXE) | Bị từ chối trước khi đọc | Bảo mật | ✅ Đạt | `exchange · hostile_files_are_refused_before_anything_is_read` |
| XML-PY-006 | Phân tích tệp của người khác hoặc tệp công khai | Bị từ chối | Bảo mật | ✅ Đạt | `exchange · only_your_own_private_xml_files_are_read` |
| XML-PY-007 | Tệp vượt giới hạn dung lượng | Bị từ chối | Biên | ✅ Đạt | `exchange · a_file_over_the_size_limit_is_refused` |
| XML-PY-008 | Phân tích tệp nhập | Báo số bản ghi, trường, bản trùng | Chức năng | ✅ Đạt | `exchange · analysis_reports_counts_fields_and_duplicates` |
| XML-PY-009 | Xuất XML | Ghi cây và đúng các trường đã chọn | Chức năng | ✅ Đạt | `exchange · export_writes_the_tree_with_its_fields_and_nothing_else` |
| XML-PY-010 | Xuất từ cấp dưới (hồ sơ) | Kèm cấp trên dạng tham chiếu khóa | Chức năng | ✅ Đạt | `exchange · a_lower_level_export_carries_its_ancestors_as_key_only_references` |
| XML-PY-011 | Chọn trường theo từng cấp | Trường khóa luôn được xuất | Chức năng | ✅ Đạt | `exchange · export_fields_are_chosen_per_level_and_the_key_fields_always_travel` |
| XML-PY-012 | Chọn dữ liệu xuất bằng tìm kiếm | Dùng cùng bộ lọc với màn hình tìm kiếm | Chức năng | ✅ Đạt | `exchange · the_search_that_selects_the_export_is_the_one_of_the_screens` |
| XML-PY-013 | Bộ lọc lạ; tìm kiếm rỗng | Bộ lọc lạ bị bỏ; tìm kiếm rỗng bị từ chối | Ngoại lệ | ✅ Đạt | `exchange · unknown_filters_are_dropped_and_an_empty_search_is_refused` |
| XML-PY-014 | Xuất vượt giới hạn số bản ghi | Bị từ chối | Biên | ✅ Đạt | `exchange · an_export_beyond_the_limit_is_refused` |
| XML-PY-015 | Xuất dữ liệu | Chỉ gồm bản ghi người dùng được đọc | Phân quyền | ✅ Đạt | `exchange · export_reads_with_the_permissions_of_the_user` |
| XML-PY-016 | Tệp kết quả xuất | Là tệp riêng tư của job, bị xóa cùng job | Bảo mật | ✅ Đạt | `exchange · the_export_file_is_a_private_attachment_of_its_job_and_goes_with_it` |
| XML-PY-017 | Nhập lại tệp vừa xuất | Dữ liệu giống hệt | Chức năng | ✅ Đạt | `exchange · what_was_exported_comes_back_the_same` |
| XML-PY-018 | Nhập lại cùng một tệp | Không thêm bản ghi | Biên | ✅ Đạt | `exchange · importing_the_same_file_again_adds_nothing` |
| XML-PY-019 | Nhập ở chế độ cập nhật | Chỉ đổi trường đã chọn của bản ghi khớp | Chức năng | ✅ Đạt | `exchange · update_mode_changes_only_the_chosen_fields_of_matching_records` |
| XML-PY-020 | Bản ghi tạo mới khi nhập | Chỉ nhận trường đã chọn và trường bắt buộc | Chức năng | ✅ Đạt | `exchange · created_records_get_only_the_chosen_fields_and_always_their_required_ones` |
| XML-PY-021 | Chạy thử nhập | Làm mọi bước trừ ghi dữ liệu | Chức năng | ✅ Đạt | `exchange · a_dry_run_does_everything_but_write` |
| XML-PY-022 | Một bản ghi lỗi khi nhập | Ghi lỗi, bỏ nhánh con, phần còn lại vẫn nhập | Ngoại lệ | ✅ Đạt | `exchange · a_failing_record_is_logged_and_its_subtree_skipped_while_the_rest_goes_on` |
| XML-PY-023 | Nhập tệp cấp dưới khi thiếu cấp trên | Cấp trên được tạo | Chức năng | ✅ Đạt | `exchange · ancestors_of_a_lower_level_file_are_created_when_missing` |
| XML-PY-024 | Giá trị danh mục chưa có | Báo lỗi, trừ khi cho phép tạo mới | Ngoại lệ | ✅ Đạt | `exchange · a_missing_catalogue_value_is_an_error_unless_the_import_may_create_it` |
| XML-PY-025 | Hai bản ghi cùng khóa | Không đoán, báo lỗi | Ngoại lệ | ✅ Đạt | `exchange · two_records_with_the_same_key_are_not_guessed_between` |
| XML-PY-026 | Bản ghi không có mã | Khớp theo tiêu đề | Chức năng | ✅ Đạt | `exchange · import_matches_a_record_without_a_code_by_its_title` |
| XML-PY-027 | Văn bản nhập có HTML | Được làm sạch | Bảo mật | ✅ Đạt | `exchange · html_in_imported_text_is_cleaned` |
| XML-PY-028 | Chạy nhập | Theo quyền của người khởi chạy | Phân quyền | ✅ Đạt | `exchange · the_import_runs_with_the_permissions_of_whoever_started_it` |
| XML-PY-029 | Phần tử lạ cố ghi trường hệ thống (bỏ qua XSD) | Không ghi được | Bảo mật | ✅ Đạt | `exchange · an_unknown_element_cannot_set_a_system_field_even_if_the_schema_is_bypassed` |
| XML-PY-030 | Theo dõi job | Có tiến độ và lịch sử | Chức năng | ✅ Đạt | `exchange · jobs_report_progress_and_history` |
| XML-PY-031 | Tiến độ job đang chạy | Lấy từ lần chạy thực | Chức năng | ✅ Đạt | `exchange · the_progress_of_a_running_job_comes_from_the_run` |
| XML-PY-032 | Hủy job đang chờ và job đang chạy | Job chờ bị hủy; job chạy được yêu cầu dừng | Chức năng | ✅ Đạt | `exchange · a_queued_job_can_be_cancelled_and_a_running_one_is_asked_to_stop` |
| XML-PY-033 | Hủy nhập giữa chừng | Không để lại dữ liệu | Biên | ✅ Đạt | `exchange · a_cancelled_import_leaves_nothing_behind` |
| XML-PY-034 | Khởi chạy nhập với tham số sai | Bị từ chối | Ngoại lệ | ✅ Đạt | `exchange · import_start_is_checked` |
| XML-PY-035 | Tải XSD, tệp xuất | Tải được, đúng quyền | Chức năng | ✅ Đạt | `exchange · downloads` |
| XML-PY-036 | Nhật ký của lần chạy rất dài | Bị giới hạn độ dài | Biên | ✅ Đạt | `exchange · the_log_of_a_run_is_capped` |
| XML-PY-037 | Gọi các endpoint mở đời cũ | Không còn tồn tại | Bảo mật | ✅ Đạt | `exchange · the_old_open_endpoints_are_gone` |

**API qua HTTP (đầu cuối)** (21)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| XML-API-001 | Quản trị viên mở trang trao đổi dữ liệu | 200 | Chức năng | ✅ Đạt | `e2e_http.py:360` |
| XML-API-002 | 6 vai trò không phải quản trị viên gọi 4 API trao đổi | 401/403 | Phân quyền | ✅ Đạt (24/24) | `e2e_http.py:365` |
| XML-API-003 | 6 vai trò không phải quản trị viên khởi chạy xuất | 401/403 | Phân quyền | ✅ Đạt (6/6) | `e2e_http.py:367` |
| XML-API-004 | 6 vai trò không phải quản trị viên phân tích tệp nhập | 401/403 | Phân quyền | ✅ Đạt (6/6) | `e2e_http.py:369` |
| XML-API-005 | Quản trị viên đọc khả năng trao đổi | 200, đủ 5 cấp | Chức năng | ✅ Đạt | `e2e_http.py:371` |
| XML-API-006 | Tải XSD | Có lược đồ ArchiveExchange | Chức năng | ✅ Đạt | `e2e_http.py:373` |
| XML-API-007 | Xuất khi không có bản ghi khớp | 400/417 | Ngoại lệ | ✅ Đạt | `e2e_http.py:375` |
| XML-API-008 | Xuất trường ngoài định dạng | 400/417 | Ngoại lệ | ✅ Đạt | `e2e_http.py:377` |
| XML-API-009 | Khởi chạy xuất | Vào hàng đợi | Chức năng | ✅ Đạt | `e2e_http.py:382` |
| XML-API-010 | Worker xử lý xuất | Hoàn thành, có kết quả | Chức năng | ✅ Đạt | `e2e_http.py:385` |
| XML-API-011 | Tải kết quả xuất | Tệp XML ArchiveExchange | Chức năng | ✅ Đạt | `e2e_http.py:387` |
| XML-API-012 | Nội dung tệp xuất | Không có trường lưu trữ hay hệ thống | Bảo mật | ✅ Đạt | `e2e_http.py:388` |
| XML-API-013 | Phòng đọc tải tệp xuất | 401/403 | Phân quyền | ✅ Đạt | `e2e_http.py:389` |
| XML-API-014 | Tải tệp nhập lên | Là tệp riêng tư | Bảo mật | ✅ Đạt | `e2e_http.py:392` |
| XML-API-015 | Phân tích tệp nhập | Hợp lệ | Chức năng | ✅ Đạt | `e2e_http.py:395` |
| XML-API-016 | Khởi chạy chạy thử | Vào hàng đợi | Chức năng | ✅ Đạt | `e2e_http.py:398` |
| XML-API-017 | Kết quả chạy thử | Không lỗi, không tạo bản ghi | Chức năng | ✅ Đạt | `e2e_http.py:400` |
| XML-API-018 | Tóm tắt chạy thử | Ghi rõ "Chạy thử" | Chức năng | ✅ Đạt | `e2e_http.py:401` |
| XML-API-019 | Tệp có khai báo entity, phần tử gốc lạ, ngày sai định dạng | Đều bị từ chối | Bảo mật | ✅ Đạt (3/3) | `e2e_http.py:416` |
| XML-API-020 | Phân tích tệp .txt | 400/417 | Ngoại lệ | ✅ Đạt | `e2e_http.py:418` |
| XML-API-021 | Phân tích tệp công khai | 403/417 | Bảo mật | ✅ Đạt | `e2e_http.py:420` |

**Giao diện (đơn vị)** (16)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| XML-UI-001 | Chọn cấp xuất | Xuất cấp đó và cấp dưới nếu chọn | Chức năng | ✅ Đạt | `exchange.test.js · choosing the levels and fields of an exchange` |
| XML-UI-002 | Danh sách trường ban đầu | Mọi trường / trường có trong tệp | Chức năng | ✅ Đạt | `exchange.test.js · choosing the levels and fields of an exchange` |
| XML-UI-003 | Bật/tắt trường | Không tắt được trường khóa; không sửa lựa chọn cũ | Biên | ✅ Đạt | `exchange.test.js · choosing the levels and fields of an exchange` |
| XML-UI-004 | Gửi lựa chọn trường | Chỉ của các cấp được xuất | Chức năng | ✅ Đạt | `exchange.test.js · choosing the levels and fields of an exchange` |
| XML-UI-005 | Số lượng theo cấp | Kèm cấp trên | Chức năng | ✅ Đạt | `exchange.test.js · choosing the levels and fields of an exchange` |
| XML-UI-006 | Trạng thái job | Tô màu đủ trạng thái | Chức năng | ✅ Đạt | `exchange.test.js · how a job is told` |
| XML-UI-007 | Tiêu đề job đang chạy/đã xong | Đúng nội dung | Chức năng | ✅ Đạt | `exchange.test.js · how a job is told` |
| XML-UI-008 | Kết quả job | Chỉ các cấp có số liệu | Chức năng | ✅ Đạt | `exchange.test.js · how a job is told` |
| XML-UI-009 | Theo dõi job đang chạy | Hỏi lại tới khi xong | Chức năng | ✅ Đạt | `exchange.test.js · following a running job` |
| XML-UI-010 | Dừng theo dõi; yêu cầu lỗi | Dừng; báo lỗi | Ngoại lệ | ✅ Đạt | `exchange.test.js · following a running job` |
| XML-UI-011 | Bảng chọn trường | Trường khóa được tick và khóa | Biên | ✅ Đạt | `exchange.test.js · FieldPicker` |
| XML-UI-012 | Bật/tắt từng trường, chọn tất cả | Báo thay đổi đúng | Chức năng | ✅ Đạt | `exchange.test.js · FieldPicker` |
| XML-UI-013 | Hai trường cùng nhãn | Phân biệt bằng mã | Biên | ✅ Đạt | `exchange.test.js · FieldPicker` |
| XML-UI-014 | Trường của tệp nhập | Chỉ trường có trong tệp, kèm số bản ghi | Chức năng | ✅ Đạt | `exchange.test.js · FieldPicker` |
| XML-UI-015 | Thẻ kết quả nhập | Bộ đếm theo cấp và nhật ký lỗi | Chức năng | ✅ Đạt | `exchange.test.js · JobCard` |
| XML-UI-016 | Thẻ job | Tiến độ, nút dừng; nút tải khi xong | Chức năng | ✅ Đạt | `exchange.test.js · JobCard` |

**Trình duyệt (đầu cuối)** (9)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| XML-E2E-001 | Màn hình trao đổi | Có mục thanh bên và ba tab | Chức năng | ✅ Đạt | `exchange.mjs` |
| XML-E2E-002 | Chuẩn bị xuất | Tìm, đếm, chọn trường | Chức năng | ✅ Đạt | `exchange.mjs` |
| XML-E2E-003 | Xuất nền | Hoàn tất; tải XML | Chức năng | ✅ Đạt | `exchange.mjs` |
| XML-E2E-004 | Tải tệp nhập | Hiện nội dung | Chức năng | ✅ Đạt | `exchange.mjs` |
| XML-E2E-005 | Chạy thử | Báo kết quả, không ghi | Chức năng | ✅ Đạt | `exchange.mjs` |
| XML-E2E-006 | Nhập rồi nhập lại | Lần đầu thêm; lần hai không thêm | Biên | ✅ Đạt | `exchange.mjs` |
| XML-E2E-007 | Tệp độc hại, sai cấu trúc | Bị từ chối kèm lý do | Bảo mật | ✅ Đạt | `exchange.mjs` |
| XML-E2E-008 | Lịch sử | Xem và xóa lần chạy | Chức năng | ✅ Đạt | `exchange.mjs` |
| XML-E2E-009 | Phòng đọc | Không có màn hình trao đổi | Phân quyền | ✅ Đạt | `exchange.mjs` |

<a id="bq"></a>

### 5.12 Bảo quản: sao lưu, kiểm tra toàn vẹn, khôi phục

66 test case: 66 đạt.

**Máy chủ (tích hợp)** (39)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| BQ-PY-001 | Kho sao lưu | Mỗi nội dung một blob; phát hiện blob hỏng | Chức năng | ✅ Đạt | `preservation · the_store_keeps_one_blob_per_content_and_notices_a_damaged_one` |
| BQ-PY-002 | Manifest và dọn rác | Liệt kê lô; giữ blob còn được tham chiếu | Chức năng | ✅ Đạt | `preservation · manifests_list_a_batch_and_garbage_collection_keeps_what_is_referenced` |
| BQ-PY-003 | Sao lưu tệp | Sao chép mọi tệp và liệt kê | Chức năng | ✅ Đạt | `preservation · a_file_backup_copies_every_file_and_lists_it` |
| BQ-PY-004 | Sao lưu lần hai | Chỉ sao chép phần còn thiếu | Biên | ✅ Đạt | `preservation · a_second_backup_copies_only_what_the_store_lacks` |
| BQ-PY-005 | Tệp nguồn mất hoặc hỏng | Báo lỗi; không đè bản tốt | Ngoại lệ | ✅ Đạt | `preservation · a_missing_or_damaged_source_is_reported_and_never_replaces_a_good_copy` |
| BQ-PY-006 | Sao lưu bị dừng rồi chạy tiếp | Tiếp từ vị trí cũ, không lặp | Biên | ✅ Đạt | `preservation · a_stopped_backup_continues_from_its_cursor_without_repeating_documents` |
| BQ-PY-007 | Sao lưu CSDL | Ghi kích thước và mã băm | Chức năng | ✅ Đạt | `preservation · the_database_dump_is_recorded_with_its_size_and_hash` |
| BQ-PY-008 | Dump CSDL lỗi | Báo lỗi; sao lưu kết hợp thành "một phần" | Ngoại lệ | ✅ Đạt | `preservation · a_failed_dump_is_an_error_and_a_combined_backup_is_then_partial` |
| BQ-PY-009 | Xóa bản sao lưu | Xóa dump, manifest, blob không dùng chung | Chức năng | ✅ Đạt | `preservation · deleting_a_backup_removes_its_dump_manifest_and_unshared_blobs` |
| BQ-PY-010 | Xóa bản sao lưu đang chạy | Bị từ chối | Ngoại lệ | ✅ Đạt | `preservation · a_running_backup_cannot_be_deleted` |
| BQ-PY-011 | Chính sách lưu giữ | Xóa lô cũ, giữ các lô tốt mới nhất | Biên | ✅ Đạt | `preservation · retention_deletes_old_batches_but_keeps_the_newest_good_ones` |
| BQ-PY-012 | Lịch sao lưu | Biết khi nào đến hạn | Chức năng | ✅ Đạt | `preservation · the_schedule_knows_when_a_backup_is_due` |
| BQ-PY-013 | Job hằng ngày | Chỉ chạy khi bật, đến hạn và không có job khác | Biên | ✅ Đạt | `preservation · the_daily_job_starts_a_scheduled_backup_only_when_enabled_due_and_idle` |
| BQ-PY-014 | Kiểm tra CSDL | Phát hiện lỗi cấu trúc; sửa được bộ đếm | Chức năng | ✅ Đạt | `preservation · database_checks_find_structure_problems_and_the_counters_can_be_fixed` |
| BQ-PY-015 | Kiểm tra theo phạm vi phông | Sạch thì hoàn tất; chỉ xét phông trong phạm vi | Chức năng | ✅ Đạt | `preservation · a_clean_scope_is_complete_and_a_scope_only_looks_at_its_fonds` |
| BQ-PY-016 | Kiểm tra siêu dữ liệu | Báo thiếu thông tin bắt buộc của lưu trữ điện tử | Chức năng | ✅ Đạt | `preservation · metadata_checks_report_what_an_electronic_archive_should_describe` |
| BQ-PY-017 | Kiểm tra tệp | Phát hiện tệp mất, bị đổi, rỗng, sai kiểu | Ngoại lệ | ✅ Đạt | `preservation · file_checks_find_missing_changed_empty_and_wrongly_typed_files` |
| BQ-PY-018 | Một phát hiện lỗi | Nêu có bản sao lưu khôi phục được hay không | Chức năng | ✅ Đạt | `preservation · a_finding_says_whether_a_backup_could_restore_it` |
| BQ-PY-019 | Tệp rỗng và văn bản không có tệp | Phân biệt được | Biên | ✅ Đạt | `preservation · an_empty_file_and_documents_without_files_are_told_apart` |
| BQ-PY-020 | MinIO tắt / bật | Tắt không báo lỗi; bật thì kiểm đối tượng | Chức năng | ✅ Đạt | `preservation · disabled_minio_is_not_reported_down_and_enabled_objects_are_checked` |
| BQ-PY-021 | Kiểm tra bị dừng | Tiếp tục được | Biên | ✅ Đạt | `preservation · a_check_continues_after_it_was_stopped` |
| BQ-PY-022 | Tạo lô khôi phục từ kết quả kiểm tra | Tệp được khôi phục | Chức năng | ✅ Đạt | `preservation · a_check_leads_to_a_restore_batch_that_brings_the_files_back` |
| BQ-PY-023 | Khôi phục khi bản ghi File đã mất | Tạo lại bản ghi | Chức năng | ✅ Đạt | `preservation · a_restore_recreates_the_file_record_when_it_is_gone` |
| BQ-PY-024 | Văn bản không khôi phục được | Báo từng văn bản | Ngoại lệ | ✅ Đạt | `preservation · documents_a_backup_cannot_restore_are_reported_one_by_one` |
| BQ-PY-025 | Văn bản không có trong bản sao lưu nào | Báo lỗi, không đụng dữ liệu khác | Ngoại lệ | ✅ Đạt | `preservation · a_document_that_is_in_no_backup_is_an_error_and_nothing_else_is_touched` |
| BQ-PY-026 | Khôi phục từ bản sao lưu không có tệp | Bị từ chối | Ngoại lệ | ✅ Đạt | `preservation · a_restore_can_name_its_backup_and_refuses_one_without_files` |
| BQ-PY-027 | Dump CSDL | Được kiểm trước khi chuẩn bị khôi phục | Bảo mật | ✅ Đạt | `preservation · a_dump_is_verified_before_anything_is_said_about_restoring_it` |
| BQ-PY-028 | Khôi phục CSDL ở chế độ mặc định | Chỉ tạo hướng dẫn đã kiểm, không tự chạy | Bảo mật | ✅ Đạt | `preservation · by_default_a_database_restore_is_a_checked_runbook_not_an_action` |
| BQ-PY-029 | Site cho phép tự khôi phục | Phải gõ đúng tên site | Bảo mật | ✅ Đạt | `preservation · a_site_that_allows_it_restores_itself_only_with_the_site_name_typed` |
| BQ-PY-030 | Lệnh khôi phục lỗi | Kết thúc lỗi, tắt chế độ bảo trì | Ngoại lệ | ✅ Đạt | `preservation · a_failing_restore_command_ends_in_error_and_maintenance_mode_is_switched_off` |
| BQ-PY-031 | Dump bị hỏng | Kết thúc lỗi, không tạo hướng dẫn | Ngoại lệ | ✅ Đạt | `preservation · a_damaged_dump_ends_the_restore_in_error_without_a_runbook` |
| BQ-PY-032 | Vai trò khác gọi API bảo quản | Bị từ chối | Phân quyền | ✅ Đạt | `preservation · only_preservation_roles_use_the_api` |
| BQ-PY-033 | Khởi chạy job khi đang có job cùng loại | Từ chối job thứ hai | Biên | ✅ Đạt | `preservation · the_api_starts_jobs_lists_them_and_refuses_a_second_at_once` |
| BQ-PY-034 | Hủy, tiếp tục, xóa job ở trạng thái không cho phép | Bị từ chối | Ngoại lệ | ✅ Đạt | `preservation · a_job_is_cancelled_resumed_and_deleted_only_when_its_state_allows` |
| BQ-PY-035 | Chi tiết một lần kiểm tra | Liệt kê phát hiện; đánh dấu bỏ qua được | Chức năng | ✅ Đạt | `preservation · the_detail_of_a_check_lists_its_findings_and_they_can_be_set_aside` |
| BQ-PY-036 | Khởi chạy khôi phục | Từ danh sách văn bản hoặc từ kiểm tra; CSDL chỉ được chuẩn bị | Chức năng | ✅ Đạt | `preservation · a_restore_is_started_from_documents_or_from_a_check_and_a_database_restore_is_prepared_not_run` |
| BQ-PY-037 | Tải bản sao lưu | Ghi nhật ký; không ra ngoài thư mục sao lưu; có giới hạn dung lượng | Bảo mật | ✅ Đạt | `preservation · a_download_is_logged_stays_inside_the_backup_folder_and_has_a_size_limit` |
| BQ-PY-038 | Lưu thiết lập bảo mật | Được kiểm và ghi vào System Settings của Frappe | Chức năng | ✅ Đạt | `preservation · the_security_settings_reach_frappes_system_settings_and_are_validated` |
| BQ-PY-039 | Endpoint mở đời cũ | Không còn tồn tại | Bảo mật | ✅ Đạt | `preservation · the_old_open_entry_points_are_gone` |

**API qua HTTP (đầu cuối)** (8)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| BQ-API-001 | 6 vai trò ngoài bảo quản gọi 5 API đọc của bảo quản | 401/403 | Phân quyền | ✅ Đạt (30/30) | `e2e_http.py:435` |
| BQ-API-002 | 6 vai trò ngoài bảo quản gọi 8 thao tác bảo quản | 401/403 | Phân quyền | ✅ Đạt (48/48) | `e2e_http.py:440` |
| BQ-API-003 | Quản trị viên, cán bộ bảo quản đọc tổng quan bảo quản | 200 | Chức năng | ✅ Đạt (2/2) | `e2e_http.py:443` |
| BQ-API-004 | Quản trị viên, cán bộ bảo quản liệt kê job sao lưu / kiểm tra / khôi phục | 200 | Chức năng | ✅ Đạt (6/6) | `e2e_http.py:446` |
| BQ-API-005 | Liệt kê loại job lạ | 400/417 | Ngoại lệ | ✅ Đạt | `e2e_http.py:447` |
| BQ-API-006 | Tải bản sao lưu với đường dẫn ../ và mã không tồn tại | Bị từ chối | Bảo mật | ✅ Đạt (3/3) | `e2e_http.py:450` |
| BQ-API-007 | Khôi phục không chỉ định gì | 400/417 | Ngoại lệ | ✅ Đạt | `e2e_http.py:451` |
| BQ-API-008 | Khôi phục CSDL với lô không tồn tại | Bị từ chối | Ngoại lệ | ✅ Đạt | `e2e_http.py:453` |

**Giao diện (đơn vị)** (9)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| BQ-UI-001 | Hiển thị phát hiện của kiểm tra toàn vẹn | Gọi tên lỗi bằng lời; biết lỗi nào sửa được bằng tính lại bộ đếm | Chức năng | ✅ Đạt | `admin.test.js · preservation helpers` |
| BQ-UI-002 | Tóm tắt kết quả job bảo quản | Câu ngắn gọn, đúng nội dung | Chức năng | ✅ Đạt | `admin.test.js · preservation helpers` |
| BQ-UI-003 | Hiển thị dung lượng và tuổi bản sao lưu | Đúng đơn vị | Chức năng | ✅ Đạt | `admin.test.js · preservation helpers` |
| BQ-UI-004 | Tuổi bản sao lưu gần nhất so với lịch | Tô màu theo mức trễ | Biên | ✅ Đạt | `admin.test.js · preservation helpers` |
| BQ-UI-005 | Nhập mã văn bản lẫn dấu phẩy, xuống dòng; chạy khôi phục | Đọc đúng danh sách; bắt nhập tên site | Ngoại lệ | ✅ Đạt | `admin.test.js · preservation helpers` |
| BQ-UI-006 | Mở chi tiết kiểm tra | Liệt kê phát hiện; mời tạo khôi phục | Chức năng | ✅ Đạt | `admin.test.js · PreserveJobDrawer` |
| BQ-UI-007 | Bỏ qua một phát hiện | Danh sách tải lại | Chức năng | ✅ Đạt | `admin.test.js · PreserveJobDrawer` |
| BQ-UI-008 | Job sao lưu đang chạy / đã dừng | Có tiến độ, nút dừng / các thao tác tiếp theo | Chức năng | ✅ Đạt | `admin.test.js · PreserveJobDrawer` |
| BQ-UI-009 | Chạy khôi phục CSDL | Phải gõ tên site trước | Bảo mật | ✅ Đạt | `admin.test.js · PreserveJobDrawer` |

**Trình duyệt (đầu cuối)** (10)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| BQ-E2E-001 | Menu bảo quản | Có tổng quan sao lưu | Chức năng | ✅ Đạt | `preservation.mjs` |
| BQ-E2E-002 | Sao lưu tệp | Chạy nền; sao chép đủ tệp | Chức năng | ✅ Đạt | `preservation.mjs` |
| BQ-E2E-003 | Sao lưu CSDL | Được kiểm; tải gzip; khôi phục chỉ chuẩn bị | Chức năng | ✅ Đạt | `preservation.mjs` |
| BQ-E2E-004 | Tệp bị mất | Kiểm tra phát hiện, báo khôi phục được | Ngoại lệ | ✅ Đạt | `preservation.mjs` |
| BQ-E2E-005 | Khôi phục | Đúng từng byte | Chức năng | ✅ Đạt | `preservation.mjs` |
| BQ-E2E-006 | Kiểm tra lại | Sạch; kiểm tra CSDL, siêu dữ liệu chạy | Chức năng | ✅ Đạt | `preservation.mjs` |
| BQ-E2E-007 | Trang khôi phục | Liệt kê lô; khôi phục CSDL thành hướng dẫn | Bảo mật | ✅ Đạt | `preservation.mjs` |
| BQ-E2E-008 | Biên mục viên | Không có menu bảo quản | Phân quyền | ✅ Đạt | `preservation.mjs` |
| BQ-E2E-009 | Cán bộ bảo quản | Có bảo quản, không có quản trị người dùng | Phân quyền | ✅ Đạt | `preservation.mjs` |
| BQ-E2E-010 | Xóa bản sao lưu cũ | Xóa được | Chức năng | ✅ Đạt | `preservation.mjs` |

<a id="qt"></a>

### 5.13 Quản trị hệ thống: người dùng, nhóm, nhật ký, giám sát

74 test case: 74 đạt.

**Máy chủ (tích hợp)** (21)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| QT-PY-001 | Người không phải quản trị viên gọi API người dùng, nhật ký | Bị từ chối; quản trị viên dùng được | Phân quyền | ✅ Đạt | `administration · only_administrators_manage_users_and_see_the_log` |
| QT-PY-002 | Xem danh sách người dùng | Chỉ gồm cán bộ; tìm và lọc được | Chức năng | ✅ Đạt | `administration · the_list_holds_staff_only_and_can_be_searched_and_filtered` |
| QT-PY-003 | Tạo tài khoản cán bộ | Có đúng vai trò và link đặt mật khẩu dùng một lần | Chức năng | ✅ Đạt | `administration · a_new_account_gets_its_roles_and_a_one_time_link_to_set_the_password` |
| QT-PY-004 | Tạo tài khoản thiếu tên, email sai, email trùng, vai trò lạ | Bị từ chối kèm thông báo | Ngoại lệ | ✅ Đạt | `administration · account_creation_is_checked` |
| QT-PY-005 | Sửa vai trò tài khoản | Đồng bộ vai trò cán bộ, giữ nguyên vai trò khác | Chức năng | ✅ Đạt | `administration · editing_syncs_the_staff_roles_and_leaves_the_others_alone` |
| QT-PY-006 | Sửa, khóa, xóa tài khoản độc giả hoặc tài khoản hệ thống | Bị từ chối | Phân quyền | ✅ Đạt | `administration · accounts_that_are_not_staff_or_not_ours_cannot_be_touched` |
| QT-PY-007 | Quản trị viên tự khóa, tự hạ quyền | Bị từ chối | Bảo mật | ✅ Đạt | `administration · nobody_locks_themselves_out_or_demotes_themselves` |
| QT-PY-008 | Khóa, hạ quyền, xóa quản trị viên cuối cùng | Bị từ chối | Biên | ✅ Đạt | `administration · the_last_administrator_cannot_be_locked_demoted_or_deleted` |
| QT-PY-009 | Khóa, mở khóa, cấp lại link mật khẩu | Thực hiện đúng; tài khoản đang khóa không được cấp link | Chức năng | ✅ Đạt | `administration · locking_unlocking_and_the_password_link` |
| QT-PY-010 | Xóa tài khoản đã có dữ liệu và tài khoản chưa dùng | Tài khoản có dữ liệu chỉ bị khóa; tài khoản sạch bị xóa | Chức năng | ✅ Đạt | `administration · an_account_with_records_is_locked_not_deleted_and_a_clean_one_goes` |
| QT-PY-011 | Lưu nhóm cán bộ | Thành viên nhận vai trò của nhóm, không mất vai trò sẵn có | Chức năng | ✅ Đạt | `administration · saving_a_group_gives_its_roles_to_the_members_and_never_takes_one_away` |
| QT-PY-012 | Nhóm có vai trò ngoài danh sách, thành viên không phải cán bộ, thành viên trùng | Bị từ chối | Ngoại lệ | ✅ Đạt | `administration · a_group_takes_only_staff_roles_and_staff_members_once_each` |
| QT-PY-013 | Nhóm trên hồ sơ người dùng, lọc theo nhóm, sửa/xóa nhóm | Danh sách cập nhật theo | Chức năng | ✅ Đạt | `administration · groups_appear_on_users_filter_the_list_and_follow_edits_and_deletion` |
| QT-PY-014 | Xem ma trận quyền | Mô tả đúng quyền của từng vai trò | Chức năng | ✅ Đạt | `administration · the_matrix_says_what_each_role_may_do` |
| QT-PY-015 | Xem nhật ký | Liệt kê, lọc, phân trang, xem chi tiết được | Chức năng | ✅ Đạt | `administration · the_log_is_listed_filtered_paged_and_read` |
| QT-PY-016 | Tải nhật ký CSV | Tải được; việc tải cũng được ghi nhật ký | Chức năng | ✅ Đạt | `administration · the_log_downloads_as_csv_and_the_download_is_itself_logged` |
| QT-PY-017 | Xem trước dọn nhật ký; dọn nhật ký mới | Hiện số sẽ xóa; từ chối xóa nhật ký gần đây | Biên | ✅ Đạt | `administration · a_cleanup_shows_what_it_would_delete_and_refuses_recent_logs` |
| QT-PY-018 | Dọn nhật ký với số xác nhận sai/đúng | Sai bị từ chối; đúng thì xóa đúng số đó | Bảo mật | ✅ Đạt | `administration · a_cleanup_needs_the_count_typed_back_and_deletes_exactly_that` |
| QT-PY-019 | Mở giám sát hệ thống | Có dịch vụ, tài liệu, job, lưu trữ, người dùng, sao lưu | Chức năng | ✅ Đạt | `administration · the_monitor_gathers_the_state_of_the_system` |
| QT-PY-020 | Thiết lập mới thêm vào site cũ (đang đọc ra 0) | Lần lưu đầu lấy giá trị mặc định hoặc giá trị đang áp dụng | Biên | ✅ Đạt | `administration · settings_added_to_an_existing_site_start_from_their_defaults_or_from_what_is_in_force` |
| QT-PY-021 | Xóa tài khoản đang thuộc nhóm | Được gỡ khỏi nhóm trước khi xóa | Chức năng | ✅ Đạt | `administration · deleting_an_account_takes_it_out_of_its_groups_first` |

**API qua HTTP (đầu cuối)** (29)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| QT-API-001 | Độc giả đọc trạng thái dịch vụ | 403 | Phân quyền | ✅ Đạt | `e2e_http.py:156` |
| QT-API-002 | Quản trị viên đọc trạng thái dịch vụ | 200, có Meilisearch | Chức năng | ✅ Đạt | `e2e_http.py:158` |
| QT-API-003 | 7 vai trò không phải quản trị viên gọi 9 API đọc của quản trị | 401/403 | Phân quyền | ✅ Đạt (63/63) | `e2e_http.py:459` |
| QT-API-004 | 7 vai trò không phải quản trị viên gọi 5 thao tác quản trị | 401/403 | Phân quyền | ✅ Đạt (35/35) | `e2e_http.py:466` |
| QT-API-005 | Sau các lần gọi trái phép | Mọi tài khoản vẫn hoạt động | Bảo mật | ✅ Đạt | `e2e_http.py:467` |
| QT-API-006 | Danh sách người dùng | Có các tài khoản cán bộ | Chức năng | ✅ Đạt | `e2e_http.py:474` |
| QT-API-007 | Danh sách người dùng | Không có độc giả, tài khoản hệ thống | Bảo mật | ✅ Đạt | `e2e_http.py:475` |
| QT-API-008 | Danh sách người dùng | Đánh dấu chính người đang xem | Chức năng | ✅ Đạt | `e2e_http.py:476` |
| QT-API-009 | Các nhóm quyền mẫu được đưa ra để gán | Đúng 7 vai trò cán bộ (5 vai trò gốc và 2 vai trò số hóa) | Chức năng | ✅ Đạt | `e2e_http.py:480` |
| QT-API-010 | Danh sách vai trò được gán | Không bao giờ có System Manager, Administrator, Reader, Guest | Bảo mật | ✅ Đạt | `e2e_http.py:483` |
| QT-API-011 | Ma trận vai trò | Có các phần Biên mục, Danh mục, Bảo quản, Quản trị | Chức năng | ✅ Đạt | `e2e_http.py:486` |
| QT-API-012 | 14 thao tác nguy hiểm: tạo System Manager/Administrator; sửa, khóa, xóa, cấp link cho Administrator; sửa/xóa tài khoản độc giả; tự khóa, tự xóa, tự hạ quyền; email sai/trùng; dọn nhật ký ngày gần | Đều bị từ chối | Bảo mật | ✅ Đạt (14/14) | `e2e_http.py:507` |
| QT-API-013 | Sau các lần thử nguy hiểm | Quản trị viên giữ nguyên vai trò | Bảo mật | ✅ Đạt | `e2e_http.py:508` |
| QT-API-014 | Xem trước dọn nhật ký | Có số lượng, không xóa | Chức năng | ✅ Đạt | `e2e_http.py:510` |
| QT-API-015 | Dọn nhật ký với số xác nhận sai | 400/417 | Bảo mật | ✅ Đạt | `e2e_http.py:511` |
| QT-API-016 | Tạo tài khoản | Có vai trò và link một lần | Chức năng | ✅ Đạt | `e2e_http.py:517` |
| QT-API-017 | Vai trò của tài khoản mới | Đúng vai trò đã chọn | Chức năng | ✅ Đạt | `e2e_http.py:518` |
| QT-API-018 | Đổi vai trò | Được thay | Chức năng | ✅ Đạt | `e2e_http.py:520` |
| QT-API-019 | Tìm tài khoản theo từ khóa và vai trò | Thấy đúng tài khoản | Chức năng | ✅ Đạt | `e2e_http.py:522` |
| QT-API-020 | Khóa tài khoản | enabled = 0 | Chức năng | ✅ Đạt | `e2e_http.py:524` |
| QT-API-021 | Cấp link cho tài khoản đang khóa | Bị từ chối | Biên | ✅ Đạt | `e2e_http.py:525` |
| QT-API-022 | Mở khóa tài khoản | enabled = 1 | Chức năng | ✅ Đạt | `e2e_http.py:527` |
| QT-API-023 | Cấp link mới | Có link | Chức năng | ✅ Đạt | `e2e_http.py:529` |
| QT-API-024 | Xóa tài khoản chưa dùng | Xóa được | Chức năng | ✅ Đạt | `e2e_http.py:531` |
| QT-API-025 | Đọc lại tài khoản đã xóa | 404 | Chức năng | ✅ Đạt | `e2e_http.py:532` |
| QT-API-026 | Tải nhật ký | CSV có BOM | Chức năng | ✅ Đạt | `e2e_http.py:537` |
| QT-API-027 | Lọc nhật ký theo loại | Chỉ có loại đã chọn | Chức năng | ✅ Đạt | `e2e_http.py:539` |
| QT-API-028 | Liệt kê nhật ký với cỡ trang 100000 | Tối đa 200 dòng | Biên | ✅ Đạt | `e2e_http.py:540` |
| QT-API-029 | Mở giám sát hệ thống | Đủ các phần | Chức năng | ✅ Đạt | `e2e_http.py:542` |

**Giao diện (đơn vị)** (11)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| QT-UI-001 | Mở form người dùng mới / có sẵn | Form trống / điền từ tài khoản | Chức năng | ✅ Đạt | `admin.test.js · administration helpers` |
| QT-UI-002 | Lưu người dùng có/không đổi phạm vi; phạm vi sai | Chỉ gửi phạm vi khi đổi; báo lỗi trước khi gửi | Ngoại lệ | ✅ Đạt | `admin.test.js · administration helpers` |
| QT-UI-003 | Lưu người dùng khi đổi thứ tự vai trò/nhóm | Chỉ gửi phần thay đổi thật | Chức năng | ✅ Đạt | `admin.test.js · administration helpers` |
| QT-UI-004 | Bật/tắt vai trò | Không sửa danh sách gốc | Chức năng | ✅ Đạt | `admin.test.js · administration helpers` |
| QT-UI-005 | Form người dùng thiếu dữ liệu | Nêu lý do không gửi được | Ngoại lệ | ✅ Đạt | `admin.test.js · administration helpers` |
| QT-UI-006 | Sửa tài khoản có vai trò System Manager | Chỉ System Manager được sửa | Phân quyền | ✅ Đạt | `admin.test.js · administration helpers` |
| QT-UI-007 | Mô tả vai trò | Câu chữ dễ hiểu | Chức năng | ✅ Đạt | `admin.test.js · administration helpers` |
| QT-UI-008 | Lọc và tải nhật ký | Chỉ dùng các ô đã điền | Chức năng | ✅ Đạt | `admin.test.js · administration helpers` |
| QT-UI-009 | Dọn nhật ký tuần gần nhất; không gõ lại số | Bị chặn | Bảo mật | ✅ Đạt | `admin.test.js · administration helpers` |
| QT-UI-010 | Dữ liệu nhật ký không phải JSON | Hiển thị bình thường | Ngoại lệ | ✅ Đạt | `admin.test.js · administration helpers` |
| QT-UI-011 | Số liệu giám sát | Tô màu theo ngưỡng | Chức năng | ✅ Đạt | `admin.test.js · administration helpers` |

**Trình duyệt (đầu cuối)** (13)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| QT-E2E-001 | Menu quản trị | Đủ màn hình | Chức năng | ✅ Đạt | `admin.mjs` |
| QT-E2E-002 | Danh sách người dùng | Tìm, lọc theo vai trò; đánh dấu chính mình | Chức năng | ✅ Đạt | `admin.mjs` |
| QT-E2E-003 | Tạo tài khoản thiếu tên/email; tạo đủ | Báo thiếu; tạo xong hiện link một lần | Ngoại lệ | ✅ Đạt | `admin.mjs` |
| QT-E2E-004 | Người dùng mới đặt mật khẩu | Chỉ có quyền của vai trò | Phân quyền | ✅ Đạt | `admin.mjs` |
| QT-E2E-005 | Đổi vai trò, khóa/mở, cấp link mới | Thực hiện được | Chức năng | ✅ Đạt | `admin.mjs` |
| QT-E2E-006 | Quản trị viên tự khóa/hạ quyền/xóa | Bị chặn | Bảo mật | ✅ Đạt | `admin.mjs` |
| QT-E2E-007 | Xóa tài khoản chưa dùng | Xóa được | Chức năng | ✅ Đạt | `admin.mjs` |
| QT-E2E-008 | Nhóm cán bộ | Cấp vai trò cho thành viên; xóa được | Chức năng | ✅ Đạt | `admin.mjs` |
| QT-E2E-009 | Nhật ký | Lọc, xem, tải CSV | Chức năng | ✅ Đạt | `admin.mjs` |
| QT-E2E-010 | Dọn nhật ký | Xem trước; từ chối ngày gần; cần gõ lại số | Bảo mật | ✅ Đạt | `admin.mjs` |
| QT-E2E-011 | Giám sát | Đủ các mục | Chức năng | ✅ Đạt | `admin.mjs` |
| QT-E2E-012 | Thông tin đơn vị, cơ cấu, thiết lập | Là form; lưu và trả lại được | Chức năng | ✅ Đạt | `admin.mjs` |
| QT-E2E-013 | Vai trò khác vào màn hình quản trị | Không có màn hình người dùng, nhật ký, giám sát | Phân quyền | ✅ Đạt (2/2) | `admin.mjs` |

<a id="nk"></a>

### 5.14 Nhật ký nghiệp vụ và toàn vẹn cây phân cấp

14 test case: 14 đạt.

**Máy chủ (tích hợp)** (14)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| NK-PY-001 | Tạo, sửa, xóa bản ghi | Ghi nhật ký kèm thay đổi trạng thái | Chức năng | ✅ Đạt | `audit_and_hierarchy · create_update_delete_are_recorded_with_state_changes` |
| NK-PY-002 | Sửa trường thông thường | Giá trị không bị chép vào nhật ký | Bảo mật | ✅ Đạt | `audit_and_hierarchy · values_of_ordinary_fields_are_not_copied_into_the_log` |
| NK-PY-003 | Tắt ghi nhật ký; thao tác trên chính nhật ký | Không ghi nữa; nhật ký không tự ghi chính nó | Biên | ✅ Đạt | `audit_and_hierarchy · the_setting_switches_logging_off_and_the_log_does_not_log_itself` |
| NK-PY-004 | Đăng nhập, đăng xuất | Được ghi nhật ký | Chức năng | ✅ Đạt | `audit_and_hierarchy · login_and_logout_are_recorded` |
| NK-PY-005 | Tạo/sửa dòng nhật ký qua quyền thông thường | Bị từ chối | Bảo mật | ✅ Đạt | `audit_and_hierarchy · nobody_can_forge_or_edit_log_rows_through_permissions` |
| NK-PY-006 | Dọn nhật ký cũ | Xóa theo lô, để lại dòng tóm tắt | Chức năng | ✅ Đạt | `audit_and_hierarchy · purge_deletes_in_batches_and_leaves_a_summary` |
| NK-PY-007 | Chuyển hồ sơ sang mục lục khác | Văn bản cập nhật vị trí; bộ đếm nơi cũ và nơi mới đúng | Chức năng | ✅ Đạt | `audit_and_hierarchy · moving_a_file_updates_the_position_of_its_documents_and_both_counters` |
| NK-PY-008 | Chuyển mục lục | Hồ sơ và văn bản đi theo | Chức năng | ✅ Đạt | `audit_and_hierarchy · moving_a_catalog_moves_files_and_documents` |
| NK-PY-009 | Chuyển khối sang phông khác | Toàn bộ cấp dưới đi theo | Chức năng | ✅ Đạt | `audit_and_hierarchy · moving_a_record_group_to_another_fonds_moves_everything_below` |
| NK-PY-010 | Lưu cấp cha mà không đổi vị trí | Không cập nhật cấp con | Biên | ✅ Đạt | `audit_and_hierarchy · an_unrelated_save_does_not_touch_children` |
| NK-PY-011 | Xóa nút còn cấp con | Bị từ chối | Ngoại lệ | ✅ Đạt | `audit_and_hierarchy · a_node_that_still_has_children_cannot_be_deleted` |
| NK-PY-012 | Gọi job dọn dữ liệu từ web | Không gọi được | Bảo mật | ✅ Đạt | `p0_hardening · retention_job_is_not_callable_from_the_web` |
| NK-PY-013 | Thêm, chuyển, xóa văn bản | Bộ đếm đúng | Chức năng | ✅ Đạt | `p0_hardening · document_counters_follow_adds_moves_and_deletes` |
| NK-PY-014 | Xóa hồ sơ | Bộ đếm phông đúng | Chức năng | ✅ Đạt | `p0_hardening · fonds_counter_follows_deletes` |

<a id="hn"></a>

### 5.15 Hiệu năng, khối lượng lớn và lưu trữ đối tượng

15 test case: 15 đạt.

**Máy chủ (tích hợp)** (15)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| HN-PY-001 | Ghi, đọc, xóa tệp riêng tư qua bộ chuyển MinIO (máy chủ giả lập); đọc bằng mã kiểu cũ (GridFS) | Đọc lại đúng nội dung, tên tệp tiếng Việt, sha256; mã cũ bị từ chối | Chức năng | ✅ Đạt | `object_storage · private_object_round_trip_and_legacy_id_guard` |
| HN-PY-002 | Xóa văn bản có tệp gốc và bản xem trước | Đưa việc xóa cả hai tệp trong kho (MinIO) vào hàng đợi sau khi commit | Chức năng | ✅ Đạt | `p0_hardening · deleting_a_document_releases_its_stored_files_after_commit` |
| HN-PY-003 | Đếm bảng rất lớn | Dừng ở trần | Biên | ✅ Đạt | `volume_guards · a_count_stops_at_its_ceiling` |
| HN-PY-004 | Tìm văn bản trên bảng lớn | Báo khi tổng bị cắt | Biên | ✅ Đạt | `volume_guards · a_text_search_reports_when_its_total_was_cut_short` |
| HN-PY-005 | Danh sách thường | Vẫn đếm chính xác | Chức năng | ✅ Đạt | `volume_guards · a_plain_list_still_counts_exactly` |
| HN-PY-006 | Tìm bằng CSDL | Báo khi đếm tới trần | Biên | ✅ Đạt | `volume_guards · the_database_search_says_when_it_counted_to_a_ceiling` |
| HN-PY-007 | Ô tìm của bảng lớn | Tìm theo tiêu đề và số, không theo cột liên kết | Chức năng | ✅ Đạt | `volume_guards · the_search_boxes_of_big_tables_look_at_titles_and_numbers_not_at_link_columns` |
| HN-PY-008 | Truy vấn quét quá lâu | Dừng kèm thông báo; trả lại giới hạn | Biên | ✅ Đạt | `volume_guards · a_scan_that_takes_too_long_is_stopped_with_a_message_and_the_limit_is_put_back` |
| HN-PY-009 | Lỗi khác trong truy vấn có trần | Đi qua nguyên vẹn | Ngoại lệ | ✅ Đạt | `volume_guards · other_errors_pass_through_the_ceiling_untouched` |
| HN-PY-010 | Tìm nhật ký không chọn ngày | Chỉ xét tháng gần nhất | Biên | ✅ Đạt | `volume_guards · a_log_text_search_without_dates_looks_at_the_recent_month` |
| HN-PY-011 | Kiểm tra trạng thái dịch vụ | Được nhớ vài giây | Chức năng | ✅ Đạt | `volume_guards · service_probes_are_kept_for_a_few_seconds` |
| HN-PY-012 | Cấu hình MinIO thiếu thông tin | Bị từ chối | Ngoại lệ | ✅ Đạt | `volume_guards · minio_requires_complete_application_credentials` |
| HN-PY-013 | Dung lượng tệp đã tải | Được đo trong nền | Chức năng | ✅ Đạt | `volume_guards · the_size_of_the_uploaded_files_is_measured_in_the_background` |
| HN-PY-014 | Kiểm tra số trùng | Có chỉ mục kết hợp | Chức năng | ✅ Đạt | `volume_guards · the_duplicate_number_checks_have_their_composite_indexes` |
| HN-PY-015 | Trang kết quả ngắn | Tự là tổng; không quét lần hai | Biên | ✅ Đạt | `volume_guards · a_short_page_is_its_own_total_and_costs_no_second_scan` |

<a id="ui"></a>

### 5.16 Thành phần giao diện dùng chung

64 test case: 64 đạt.

**Giao diện (đơn vị)** (53)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| UI-UI-001 | Thông báo Frappe có HTML | Chuyển thành văn bản thường | Chức năng | ✅ Đạt | `api.test.js · stripHtml` |
| UI-UI-002 | Đầu vào rỗng | Không lỗi | Biên | ✅ Đạt | `api.test.js · stripHtml` |
| UI-UI-003 | Thông báo máy chủ mã hóa hai lớp | Giải mã đúng | Chức năng | ✅ Đạt | `api.test.js · server messages` |
| UI-UI-004 | Thông báo máy chủ hỏng | Không lỗi | Ngoại lệ | ✅ Đạt | `api.test.js · server messages` |
| UI-UI-005 | Có thông báo máy chủ và mã trạng thái | Ưu tiên thông báo máy chủ | Chức năng | ✅ Đạt | `api.test.js · server messages` |
| UI-UI-006 | Không có thông báo máy chủ | Câu dễ hiểu theo mã trạng thái | Biên | ✅ Đạt | `api.test.js · server messages` |
| UI-UI-007 | Gọi API đọc | GET, đối tượng mã hóa JSON, bỏ giá trị rỗng | Chức năng | ✅ Đạt | `api.test.js · call` |
| UI-UI-008 | Gọi API ghi | POST, thân JSON, có header CSRF | Bảo mật | ✅ Đạt | `api.test.js · call` |
| UI-UI-009 | Máy chủ báo lỗi | Ném ApiError kèm giải thích | Ngoại lệ | ✅ Đạt | `api.test.js · call` |
| UI-UI-010 | Mất mạng | Báo lỗi kết nối | Ngoại lệ | ✅ Đạt | `api.test.js · call` |
| UI-UI-011 | Lỗi 401 do sai mật khẩu hiện tại | Không chuyển sang trang đăng nhập | Biên | ✅ Đạt | `api.test.js · call` |
| UI-UI-012 | Phiên hết hạn | Sang trang đăng nhập rồi quay lại chỗ cũ | Chức năng | ✅ Đạt | `api.test.js · call` |
| UI-UI-013 | Bảng lệnh Ctrl+K | Liệt kê màn hình; lọc khi gõ | Chức năng | ✅ Đạt | `archive.test.js · CommandPalette` |
| UI-UI-014 | Tìm hồ sơ, văn bản trong bảng lệnh | Mở đúng mục chọn | Chức năng | ✅ Đạt | `archive.test.js · CommandPalette` |
| UI-UI-015 | Gõ một ký tự; phím mũi tên; Esc | Không tìm; điều hướng bằng phím; đóng | Biên | ✅ Đạt | `archive.test.js · CommandPalette` |
| UI-UI-016 | Ô nhập chữ | Trả đúng văn bản | Chức năng | ✅ Đạt | `components.test.js · FieldInput` |
| UI-UI-017 | Ô số nguyên để trống/có số | Trả số hoặc null | Biên | ✅ Đạt | `components.test.js · FieldInput` |
| UI-UI-018 | Ô đánh dấu | Trả 1/0 | Chức năng | ✅ Đạt | `components.test.js · FieldInput` |
| UI-UI-019 | Ô chọn | Có các lựa chọn và dòng gợi ý | Chức năng | ✅ Đạt | `components.test.js · FieldInput` |
| UI-UI-020 | Trường bắt buộc có lỗi | Đánh dấu; hiện lỗi thay mô tả | Ngoại lệ | ✅ Đạt | `components.test.js · FieldInput` |
| UI-UI-021 | Trường chỉ đọc | Không sửa được | Phân quyền | ✅ Đạt | `components.test.js · FieldInput` |
| UI-UI-022 | Dựng form | Đủ trường, đúng thứ tự, có tiêu đề phần | Chức năng | ✅ Đạt | `components.test.js · FormRenderer` |
| UI-UI-023 | Sửa trên form | Cập nhật bản ghi tại chỗ | Chức năng | ✅ Đạt | `components.test.js · FormRenderer` |
| UI-UI-024 | Trường tạo tên bản ghi sau khi lưu | Bị khóa | Biên | ✅ Đạt | `components.test.js · FormRenderer` |
| UI-UI-025 | Người không có quyền ghi | Toàn bộ form chỉ đọc | Phân quyền | ✅ Đạt | `components.test.js · FormRenderer` |
| UI-UI-026 | Ô liên kết | Tìm khi gõ, chọn được giá trị | Chức năng | ✅ Đạt | `components.test.js · LinkSelect` |
| UI-UI-027 | Ô liên kết có giá trị | Hiện nhãn thay mã | Chức năng | ✅ Đạt | `components.test.js · LinkSelect` |
| UI-UI-028 | Ô liên kết có bộ lọc | Gửi bộ lọc; xóa được giá trị | Chức năng | ✅ Đạt | `components.test.js · LinkSelect` |
| UI-UI-029 | Ô liên kết bị khóa | Không mở danh sách | Phân quyền | ✅ Đạt | `components.test.js · LinkSelect` |
| UI-UI-030 | Cây dữ liệu | Tải con khi mở; giữ vị trí khi làm mới | Chức năng | ✅ Đạt | `components.test.js · tree` |
| UI-UI-031 | Cây có bộ lọc | Gửi bộ lọc; đặt lại thì xóa hết | Chức năng | ✅ Đạt | `components.test.js · tree` |
| UI-UI-032 | Nút cây | Tiêu đề, số con; nút thêm con chỉ khi có quyền | Phân quyền | ✅ Đạt | `components.test.js · tree` |
| UI-UI-033 | Hộp xác nhận | Xác nhận, hủy; hiện lỗi máy chủ | Ngoại lệ | ✅ Đạt | `components.test.js · dialogs and paging` |
| UI-UI-034 | Thanh phân trang ở trang đầu/cuối | Hiện khoảng; khóa nút đầu/cuối | Biên | ✅ Đạt | `components.test.js · dialogs and paging` |
| UI-UI-035 | Tổng bị cắt ở trần | Hiện dấu "+" | Biên | ✅ Đạt | `components.test.js · dialogs and paging` |
| UI-UI-036 | Tạo bản ghi trống | Lấy giá trị mặc định | Chức năng | ✅ Đạt | `lib.test.js · doctype helpers` |
| UI-UI-037 | Tạo bản ghi con dưới cha | Giá trị ghi đè được ưu tiên | Chức năng | ✅ Đạt | `lib.test.js · doctype helpers` |
| UI-UI-038 | Tùy chọn của ô chọn | Mỗi dòng một lựa chọn; dòng đầu có thể trống | Biên | ✅ Đạt | `lib.test.js · doctype helpers` |
| UI-UI-039 | Danh sách trường | Theo thứ tự bố cục | Chức năng | ✅ Đạt | `lib.test.js · doctype helpers` |
| UI-UI-040 | Trường bắt buộc còn trống | Báo thiếu; bỏ qua trường chỉ đọc và ô đánh dấu | Ngoại lệ | ✅ Đạt | `lib.test.js · doctype helpers` |
| UI-UI-041 | Ngày, ngày giờ | Kiểu Việt Nam | Chức năng | ✅ Đạt | `lib.test.js · formatting` |
| UI-UI-042 | Số lớn | Có dấu phân cách | Chức năng | ✅ Đạt | `lib.test.js · formatting` |
| UI-UI-043 | Chuỗi dài có thẻ HTML | Cắt ngắn, bỏ thẻ | Bảo mật | ✅ Đạt | `lib.test.js · formatting` |
| UI-UI-044 | Hiển thị giá trị | Theo kiểu trường | Chức năng | ✅ Đạt | `lib.test.js · formatting` |
| UI-UI-045 | Chữ viết tắt tên | Đúng | Chức năng | ✅ Đạt | `lib.test.js · formatting` |
| UI-UI-046 | Hàm trì hoãn (debounce) | Chạy một lần sau lần gọi cuối; hủy được | Chức năng | ✅ Đạt | `lib.test.js · debounce` |
| UI-UI-047 | Thêm dòng bảng con | Lấy mặc định của cột | Chức năng | ✅ Đạt | `slips.test.js · child tables in forms` |
| UI-UI-048 | Bảng con bắt buộc còn trống | Yêu cầu thêm dòng | Ngoại lệ | ✅ Đạt | `slips.test.js · child tables in forms` |
| UI-UI-049 | Thêm, sửa, xóa dòng | Không sửa mảng gốc | Chức năng | ✅ Đạt | `slips.test.js · child tables in forms` |
| UI-UI-050 | Form chỉ đọc | Bảng con chỉ đọc | Phân quyền | ✅ Đạt | `slips.test.js · child tables in forms` |
| UI-UI-051 | Trường phụ thuộc điều kiện | Chỉ hiện khi điều kiện đúng | Chức năng | ✅ Đạt | `slips.test.js · forms that depend on a value` |
| UI-UI-052 | Trường bắt buộc đang ẩn | Không bắt nhập | Biên | ✅ Đạt | `slips.test.js · forms that depend on a value` |
| UI-UI-053 | Trường ngày mặc định Today | Điền ngày hôm nay | Biên | ✅ Đạt | `slips.test.js · forms that depend on a value` |

**Trình duyệt (đầu cuối)** (11)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| UI-E2E-001 | Đổi giao diện sáng/tối | Được ghi nhớ | Chức năng | ✅ Đạt | `reader.mjs` |
| UI-E2E-002 | Cổng độc giả trên điện thoại | Vừa màn hình | Chức năng | ✅ Đạt | `reader.mjs` |
| UI-E2E-003 | Đổi giao diện tối | Đổi màu | Chức năng | ✅ Đạt | `catalogues.mjs` |
| UI-E2E-004 | Màn hình điện thoại | Menu dạng ngăn kéo; nội dung vừa | Chức năng | ✅ Đạt | `catalogues.mjs` |
| UI-E2E-005 | Bảng lệnh Ctrl+K | Tìm và mở hồ sơ | Chức năng | ✅ Đạt | `cataloguing.mjs` |
| UI-E2E-006 | Biên mục trên điện thoại | Vừa màn hình | Chức năng | ✅ Đạt | `cataloguing.mjs` |
| UI-E2E-007 | Hàng đợi, phiếu trên điện thoại | Vừa màn hình | Chức năng | ✅ Đạt | `slips.mjs` |
| UI-E2E-008 | Báo cáo trên điện thoại | Vừa màn hình | Chức năng | ✅ Đạt | `reports.mjs` |
| UI-E2E-009 | Trao đổi trên điện thoại | Vừa màn hình | Chức năng | ✅ Đạt | `exchange.mjs` |
| UI-E2E-010 | Bảo quản trên điện thoại | Vừa màn hình | Chức năng | ✅ Đạt | `preservation.mjs` |
| UI-E2E-011 | Quản trị trên điện thoại | Vừa màn hình | Chức năng | ✅ Đạt | `admin.mjs` |

<a id="sh"></a>

### 5.17 Số hóa và AI bóc tách

12 test case: 12 đạt.

**Máy chủ (tích hợp)** (12)

| Mã | Trường hợp kiểm thử | Kết quả mong đợi | Loại | Kết quả | Nguồn |
|---|---|---|---|---|---|
| SH-PY-001 | Chế độ số hóa tắt: gửi, xem, duyệt job AI; mở form ở chế độ số hóa | Đều bị từ chối ("Chế độ số hóa đang tắt") | Phân quyền | ✅ Đạt | `digitization · everything_is_refused_while_digitization_is_off` |
| SH-PY-002 | Người nhập liệu, người duyệt số hóa gửi job AI | Bị từ chối: chỉ quản trị viên được gửi | Phân quyền | ✅ Đạt | `digitization · only_administrators_send_a_job` |
| SH-PY-003 | Gửi job với phạm vi bóc tách lạ; khối tài liệu không tồn tại | Bị từ chối | Ngoại lệ | ✅ Đạt | `digitization · a_job_needs_a_known_selection_and_record_group` |
| SH-PY-004 | Xem job: quản trị viên (job không tồn tại), biên mục viên, độc giả, người nhập liệu | Báo không tìm thấy; biên mục viên và độc giả bị từ chối; người nhập liệu xem được (rỗng khi chưa có job) | Phân quyền | ✅ Đạt | `digitization · reading_a_job_needs_a_digitization_right` |
| SH-PY-005 | Người nhập liệu và người duyệt duyệt kết quả AI | Người nhập liệu bị từ chối; người duyệt qua bước quyền (job không tồn tại thì báo không tìm thấy) | Phân quyền | ✅ Đạt | `digitization · only_reviewers_approve_results` |
| SH-PY-006 | AI engine gọi lại với khóa sai, không khóa, khóa đúng; site chưa cấu hình khóa | Sai/thiếu khóa bị từ chối (lỗi xác thực); khóa đúng đi tiếp tới bước kiểm job; site chưa có khóa không nhận callback nào | Bảo mật | ✅ Đạt | `digitization · the_engine_callback_needs_the_shared_key` |
| SH-PY-007 | Người nhập liệu mở form hồ sơ ở chế độ số hóa | Có danh sách trường | Chức năng | ✅ Đạt | `digitization · the_digitization_mode_shows_the_form_to_digitization_staff` |
| SH-PY-008 | Đọc, sửa cấu hình trường và thêm trường: quản trị viên, biên mục viên, người nhập liệu | Chỉ quản trị viên được | Phân quyền | ✅ Đạt | `digitization · only_administrators_read_and_change_the_field_configuration` |
| SH-PY-009 | Cấu hình trường của loại dữ liệu lạ, trường được bảo vệ, chế độ lạ, trường bắt buộc chỉ một chế độ, thứ tự âm | Đều bị từ chối kèm thông báo | Ngoại lệ | ✅ Đạt | `digitization · a_field_configuration_is_checked_before_it_is_saved` |
| SH-PY-010 | Quản trị viên lưu cấu hình hợp lệ của một trường | Lưu và đọc lại đúng | Chức năng | ✅ Đạt | `digitization · a_valid_field_configuration_is_saved` |
| SH-PY-011 | Thêm trường mới: mã không bắt đầu bằng custom_, kiểu Attach, tên rỗng | Bị từ chối; không có cột nào được tạo | Ngoại lệ | ✅ Đạt | `digitization · a_new_field_is_checked_before_any_column_is_made` |
| SH-PY-012 | Xóa trường chuẩn; xóa trường tùy chỉnh không tồn tại | Bị từ chối | Ngoại lệ | ✅ Đạt | `digitization · only_existing_custom_fields_are_removed` |

## 6. Chức năng chưa có test tự động

Phần phân quyền và kiểm tra dữ liệu đầu vào của các chức năng số hóa nay có test thường trực (`tests/test_digitization.py`, 12 test; 2 test mới trong `tests/test_staff_api.py` cho tổng quan workspace và mô tả form). Những phần dưới đây vẫn chưa có test tự động:

| Chức năng | Chưa kiểm | Đề xuất |
|---|---|---|
| AI bóc tách (`services/ai_integration.py`) | Gửi job thật tới AI engine (PDFluent); callback hợp lệ theo thứ tự trạng thái; `refresh` khi mất callback; duyệt kết quả và ghi trường vào hồ sơ/văn bản; các lỗi "tệp đã đổi", "văn bản đã sửa", "đã chuyển vị trí" | Thêm test dùng engine giả lập (mock `requests`) và bản ghi `AI Extraction Job` dựng sẵn |
| Cấu hình trường số hóa (`api/digitization.py`) | Thêm và xóa trường tùy chỉnh thành công (tạo/xóa cột CSDL); xóa trường đã có dữ liệu | Test trên site thử riêng vì thao tác đổi cấu trúc bảng |
| Giao diện số hóa (`FieldConfig.vue`, `AiJobPage.vue`, chuyển chế độ làm việc `workMode.js`) | Toàn bộ | Thêm test Vitest cho hai trang và một luồng Playwright |
| Lưu trữ đối tượng (`tests/test_object_storage.py`) | Có test nhưng chưa nằm trong danh sách chạy của CI | Thêm vào `.github/workflows/ci.yml` |
| Hiệu năng với dữ liệu lớn (`scripts/perf/volume_check.py`) | Đo thời gian trên bộ dữ liệu lớn (không chạy trong lần này vì cần site riêng) | Chạy theo `docs/HIEU_NANG.md` trước mỗi đợt phát hành |

## 7. Chi tiết lần chạy

### 7.1 Máy chủ: theo module

| Module | Số test | Đạt | Không đạt | Thời gian |
|---|---:|---:|---:|---:|
| `test_access_control` | 15 | 15 | 0 | 4.053 s |
| `test_administration` | 21 | 21 | 0 | 8.844 s |
| `test_archive_api` | 26 | 26 | 0 | 8.818 s |
| `test_audit_and_hierarchy` | 11 | 11 | 0 | 3.992 s |
| `test_digitization` | 12 | 12 | 0 | 4.353 s |
| `test_exchange` | 37 | 37 | 0 | 8.186 s |
| `test_fonds_access` | 15 | 15 | 0 | 7.859 s |
| `test_object_storage` | 1 | 1 | 0 | 0.003 s |
| `test_p0_hardening` | 11 | 11 | 0 | 3.83 s |
| `test_permission_profiles` | 26 | 26 | 0 | 36.007 s |
| `test_policy` | 15 | 15 | 0 | 5.031 s |
| `test_preservation` | 39 | 39 | 0 | 10.29 s |
| `test_reader_admin` | 26 | 26 | 0 | 8.424 s |
| `test_reader_pages` | 36 | 36 | 0 | 15.678 s |
| `test_reader_site` | 40 | 40 | 0 | 10.516 s |
| `test_reader_ui_logic` | 14 | 14 | 0 | 5.222 s |
| `test_reports` | 31 | 31 | 0 | 8.375 s |
| `test_request_lifecycle` | 28 | 28 | 0 | 13.493 s |
| `test_request_workflow` | 17 | 17 | 0 | 7.289 s |
| `test_search_service` | 13 | 13 | 0 | 3.814 s |
| `test_slip_queue` | 21 | 21 | 0 | 9.941 s |
| `test_staff_api` | 24 | 24 | 0 | 4.532 s |
| `test_staff_scope` | 17 | 17 | 0 | 20.311 s |
| `test_volume_guards` | 13 | 13 | 0 | 2.519 s |

### 7.2 Giao diện: theo tệp test

| Tệp | Số test | Đạt | Không đạt |
|---|---:|---:|---:|
| `admin.test.js` | 20 | 20 | 0 |
| `api.test.js` | 12 | 12 | 0 |
| `archive.test.js` | 14 | 14 | 0 |
| `components.test.js` | 20 | 20 | 0 |
| `exchange.test.js` | 16 | 16 | 0 |
| `lib.test.js` | 11 | 11 | 0 |
| `permissions.test.js` | 5 | 5 | 0 |
| `reader.test.js` | 50 | 50 | 0 |
| `registrations.test.js` | 6 | 6 | 0 |
| `reports.test.js` | 11 | 11 | 0 |
| `search.test.js` | 9 | 9 | 0 |
| `slips.test.js` | 18 | 18 | 0 |
| `upload.test.js` | 13 | 13 | 0 |

### 7.3 Trình duyệt và HTTP: theo luồng

| Phần | Bước / lượt kiểm | Đạt | Không đạt | Thời gian |
|---|---:|---:|---:|---:|
| HTTP (`e2e_http.py`, 144 điểm kiểm) | 502 lượt | 502 | 0 | 1096 s |
| Luồng độc giả (`reader.mjs`) | 31 | 31 | 0 | 48 s |
| Luồng danh mục từ điển (`catalogues.mjs`) | 10 | 10 | 0 | 30 s |
| Luồng biên mục (`cataloguing.mjs`) | 15 | 15 | 0 | 31 s |
| Luồng phiếu (`slips.mjs`) | 21 | 21 | 0 | 32 s |
| Luồng báo cáo (`reports.mjs`) | 12 | 12 | 0 | 26 s |
| Luồng trao đổi XML (`exchange.mjs`) | 10 | 10 | 0 | 29 s |
| Luồng bảo quản (`preservation.mjs`) | 11 | 11 | 0 | 49 s |
| Luồng quản trị (`admin.mjs`) | 16 | 16 | 0 | 84 s |

Luồng quản trị có 16 bước vì bước "vai trò khác không có màn hình quản trị" chạy cho hai vai trò.

## 8. Cách chạy lại

Chạy trên stack phát triển (thư mục `docker/`). Các lệnh dưới đây dùng Git Bash.

```bash
C="docker compose -f docker-compose.yml -f docker-compose.dev.yml"

# 1. Máy chủ: một module (bỏ --verbose nếu chỉ cần tóm tắt)
$C exec -T -w /home/frappe/frappe-bench/sites backend \
  bench --verbose --site docmanager.yourdomain.com run-tests --app document_manager \
  --module document_manager.tests.test_slip_queue

# 2. Giao diện
(cd ../apps/document_manager/frontend && npx vitest run)

# 3. HTTP: tạo tài khoản thử, chạy, xóa tài khoản
export DM_E2E_PASSWORD=...   # mật khẩu tự chọn cho các tài khoản e2e.*
$C exec -T -e DM_E2E_PASSWORD -w /home/frappe/frappe-bench/sites backend /home/frappe/frappe-bench/env/bin/python - up < ../scripts/e2e/accounts.py
python ../scripts/e2e/e2e_http.py
$C exec -T -e DM_E2E_PASSWORD -w /home/frappe/frappe-bench/sites backend /home/frappe/frappe-bench/env/bin/python - down < ../scripts/e2e/accounts.py

# 4. Trình duyệt: từng luồng (sau bước 'up' ở trên)
(cd ../scripts/e2e/ui && OUT_DIR=out SAMPLES_DIR=samples PW_CHANNEL=msedge node reader.mjs)
```

Danh sách module máy chủ: `access_control`, `administration`, `archive_api`, `audit_and_hierarchy`, `digitization`, `exchange`, `fonds_access`, `object_storage`, `p0_hardening`, `permission_profiles`, `policy`, `preservation`, `reader_admin`, `reader_pages`, `reader_site`, `reader_ui_logic`, `reports`, `request_lifecycle`, `request_workflow`, `search_service`, `slip_queue`, `staff_api`, `staff_scope`, `volume_guards`. Luồng trình duyệt: `reader`, `catalogues`, `cataloguing`, `slips`, `reports`, `exchange`, `preservation`, `admin`.
