# Báo cáo tái cấu trúc Document Manager (G0 – G9)

Nhánh `refactor/v2` · cập nhật 13/10/2026 · phạm vi: tái cấu trúc ứng dụng Frappe `document_manager` theo
*Phụ lục 03 – Chức năng cơ bản phần mềm khai thác* (8 phân hệ).

Báo cáo này cho người quản lý dự án biết: đã làm gì ở từng giai đoạn, sản phẩm hiện đạt đến đâu so với yêu cầu,
những gì đã thay đổi về hành vi, và những gì còn dở. G0–G9 đều đã commit và đẩy lên `origin/refactor/v2`; xem mục 7.

## 1. Tóm tắt

| | Trước tái cấu trúc | Hiện tại |
|---|---|---|
| Giao diện | 47 trang `www` dùng chung một thanh điều hướng cho cán bộ và độc giả, 16 cặp trang CRUD trùng lặp, CSS/JS tải từ CDN | **Hai giao diện tách biệt**: ứng dụng Vue 3 cho cán bộ tại `/dashboard`; trang Jinja + Alpine cho độc giả tại `/portal` và các trang công khai; không dùng CDN |
| Phân quyền độc giả | `reader_group` chỉ là nhãn, 7 tham số không được đọc ở đâu | Một nguồn chính sách duy nhất (`policy.get_reader_scope`), dùng cho truy vấn SQL, `has_permission`, tìm kiếm, tải tệp, hạn mức phiếu |
| Sao lưu / khôi phục | Đếm tệp rồi báo "Thành công"; khôi phục không làm gì | Sao lưu thật (cơ sở dữ liệu + tệp, mã sha256), kiểm tra toàn vẹn từng tệp, khôi phục tệp theo đợt, khôi phục CSDL có kiểm soát |
| XML | Mở cho mọi người dùng đăng nhập, bỏ qua phân quyền | Chỉ Document Admin / System Manager, lược đồ có tài liệu, chọn trường, chạy thử, nhật ký từng dòng |
| Báo cáo | 2 báo cáo | 11 báo cáo + tổng kiểm kê, xuất CSV/XLSX, in HTML/PDF |
| Kiểm thử | 50 test Python | **426 test Python (19 module), 185 test vitest, 126 bước trình duyệt (8 luồng), 497 kiểm tra HTTP** |
| Quy mô | chưa đo | Đo ở **1.000.000 văn bản**: thao tác hằng ngày dưới 1 giây; xem `docs/HIEU_NANG.md` |

Mười giai đoạn G0–G9 đã được commit và đẩy lên `origin/refactor/v2`. Mỗi giai đoạn kết thúc khi toàn bộ test xanh, image
Docker dựng lại được và các luồng trình duyệt chạy qua.

## 2. Các giai đoạn đã hoàn thành

| GĐ | Commit | Nội dung chính |
|---|---|---|
| G0 – G2 | `dcdcae3` | Vệ sinh repo, vá lỗi P0, nền miền nghiệp vụ |
| G3 | `d40e908` | Khung ứng dụng cán bộ (Vue 3) và phân hệ Danh mục |
| G4 | `74ed3ac` | Biên mục và tìm kiếm cho cán bộ |
| G5 | `014224e` | Giao diện độc giả, trang công khai, đăng ký |
| G6 | `36de693` | Quản lý độc giả và vòng đời phiếu |
| G7 | `49ce9e5` | Báo cáo, tổng kiểm kê, xuất/nhập XML |
| G8 | `267366f` | Bảo quản và Quản trị |
| G9 | `590ec6f` | Hiệu năng ở một triệu văn bản, dọn mã cũ, tài liệu, ma trận truy vết |

### G0 – Vệ sinh repo
- Xóa script rác, hook chết; thêm `.gitattributes` (LF) và các mục bỏ qua.
- `patches.txt` có đủ phần `pre_model_sync` / `post_model_sync`; CI tạo site sạch, chạy migrate, lint lỗi thật và chạy mọi module test.

### G1 – Vá lỗi bảo mật và nói đúng sự thật
- **XML**: chỉ Document Admin / System Manager; cột được liệt kê rõ; không còn `ignore_permissions`; từ chối DTD/ENTITY.
- **Sao lưu / khôi phục** không còn báo thành công cho việc chưa làm (tạm thời báo "Một phần" / "Cần thao tác thủ công" cho đến khi G8 làm thật).
- **Độc giả** không thấy hồ sơ ở trạng thái "Nháp" hay "Đã tiêu hủy" cùng các văn bản bên trong; mức mật và vị trí của hồ sơ lan xuống văn bản.
- Bộ đếm tính lại khi thêm/chuyển/xóa; tệp GridFS được giải phóng sau commit; công việc nền được xếp hàng sau commit và chống trùng.
- Meilisearch không còn mở ra máy chủ, bắt buộc có khóa; site mới được gieo sẵn vai trò, mức mật "Thường", workflow.

### G2 – Nền miền nghiệp vụ
- `policy.get_reader_scope`: nhóm độc giả (mức mật tối đa, phạm vi phông, 6 cờ tính năng) cộng ghi đè cá nhân (chỉ Document Admin).
- Dịch vụ tìm kiếm hợp nhất (hồ sơ và văn bản, cơ bản và nâng cao, tổng đúng, lọc ngày, Meilisearch có dự phòng cơ sở dữ liệu).
- `services/audit.py`: một bộ ghi nhật ký duy nhất, `doc_events` cho các DocType nghiệp vụ, đăng nhập/đăng xuất.
- Lan truyền cấp bậc khi chuyển Khối/Mục lục/Hồ sơ, chỉ mục cơ sở dữ liệu, tách thiết lập hạ tầng khỏi DocType.

### G3 – Khung giao diện cán bộ và phân hệ Danh mục
- Ứng dụng Vue 3 + Vite + Tailwind tại `/dashboard`: thanh bên theo quyền, sáng/tối, đáp ứng điện thoại, đổi mật khẩu.
- Hạ tầng dùng chung thay cho 64 file trùng lặp: `constants.MASTERS` + `services/ui.py` mô tả DocType, `api/crud.py` liệt kê/lưu/xóa qua chính Frappe, nên quyền, kiểm tra hợp lệ và kiểm tra liên kết là của Frappe. Chỉ DocType đã đăng ký mới truy cập được.
- Danh mục: cơ quan lưu trữ, phông, loại hình, nhóm tài liệu, cây kho, mức mật, khung phân loại, từ điển đơn/đa cấp (mới: Dictionary Type; Quick Entry Dictionary thành cây).
- Dockerfile có tầng Node; CI có job frontend; tổng quan hết giới hạn đếm 10.000.

### G4 – Biên mục và tìm kiếm cho cán bộ
- `/dashboard/bien-muc`: cây Phông → Khối → Mục lục → Hồ sơ, trang hồ sơ, trang văn bản, tải nhiều tệp có tiến độ, xem trước PDF/ảnh/văn bản, in phiếu mô tả và mục lục hồ sơ.
- `/dashboard/tim-kiem` (cơ bản/nâng cao, bộ lọc đã lưu, làm nổi từ khóa), Ctrl+K.
- Độ bền tìm ra khi lái giao diện bằng trình duyệt thật: đọc tệp tải lên theo byte chính xác; MariaDB 11.8 `innodb_snapshot_isolation` tắt và các đường đọc-rồi-ghi có thử lại; xem trước/tải có dự phòng khi GridFS không với tới.

### G5 – Giao diện độc giả
- Trang công khai: `/gioi-thieu`, `/lanh-dao`, `/co-cau`, `/lien-he`, `/huong-dan`; `/dang-nhap`, `/dang-ky`, `/quen-mat-khau`, `/dat-mat-khau`.
- Đăng ký qua hàng đợi do cán bộ duyệt; duyệt tạo User + Reader và **liên kết đặt mật khẩu dùng một lần** (72 giờ, không cần email); giới hạn tần suất, ô bẫy, không lộ tài khoản có tồn tại hay không.
- Khu độc giả `/portal`: tìm hồ sơ và văn bản, trang hồ sơ/văn bản, phiếu sử dụng và sao chụp (phiếu nháp phía máy chủ là giỏ), góp ý, tài khoản, thông báo trong ứng dụng.

### G6 – Quản lý độc giả và vòng đời phiếu
- Vai trò **Archive Leader**; workflow có bước lãnh đạo duyệt; quyết định theo từng mục, giao, nhận trả, gia hạn, hạn trả, quá hạn (công việc hằng ngày).
- Hạn mức và cờ tính năng lấy từ Reader Group; mẫu phiếu (Request Template); thẻ độc giả, phiếu giao, phiếu lấy tài liệu.
- Giao diện cán bộ `/dashboard/doc-gia/...`: hàng đợi phiếu, độc giả, nhóm độc giả, mẫu phiếu, góp ý, thiết lập.

### G7 – Báo cáo và Xuất/Nhập XML
- 11 báo cáo (phông, mục lục, hồ sơ, văn bản; thống kê theo phông/năm/mức mật/tình trạng và theo loại hình/nhóm/kho; độc giả, thống kê phiếu, phiếu quá hạn, tài liệu được yêu cầu nhiều nhất), phân trang, tổng, biểu đồ, CSV/XLSX, in HTML/PDF có đầu đề đơn vị.
- Tổng kiểm kê phông (Inventory Check): dòng lấy từ số liệu hệ thống, nhập số đếm thực tế, chênh lệch, hoàn thành thì khóa số liệu.
- XML: cây lồng Phông → … → Văn bản khớp theo khóa nghiệp vụ, XSD sinh tự động, phân tích an toàn, công việc nền (Data Exchange Job), chọn trường theo cấp, chạy thử rồi hoàn tác, quyền của người gọi.

### G8 – Bảo quản và Quản trị
- **Bảo quản**: kho tệp định danh theo nội dung (`private/dm-backup-store`), sao lưu tăng dần có bảng kê sha256, chạy tiếp được, phát hiện công việc treo (6 giờ), giữ tối thiểu các đợt mới nhất khi dọn; kiểm tra toàn vẹn cơ sở dữ liệu, siêu dữ liệu và từng tệp; đợt khôi phục tạo thẳng từ kết quả kiểm tra; khôi phục CSDL là hướng dẫn đã kiểm tra, chỉ tự chạy khi site cho phép.
- **Quản trị**: người dùng (liên kết mật khẩu một lần, sửa vai trò, khóa/mở khóa, xóa), nhóm cán bộ, ma trận phân quyền, nhật ký (lọc, CSV, dọn có kiểm soát), giám sát hệ thống, thiết lập hệ thống.
- Rào chắn: chỉ năm vai trò cán bộ được cấp; tài khoản System Manager được bảo vệ; không ai tự khóa hoặc tự hạ quyền mình; luôn còn ít nhất một quản trị; dọn nhật ký chỉ với dòng cũ hơn 7 ngày, phải gõ lại số dòng, và việc dọn cũng được ghi lại.

### G9 – Hoàn thiện
- **Đo ở quy mô một triệu văn bản** bằng `scripts/perf/volume_check.py` trên site thử riêng (1.000.000 văn bản, 200.000 hồ sơ, 1.000.000 dòng nhật ký, 20.000 độc giả, 100.000 phiếu).
  Thao tác hằng ngày (danh sách, cây biên mục, hàng đợi phiếu, thanh bên) dưới 1 giây; báo cáo vài giây theo yêu cầu; 27 phép kiểm tra toàn vẹn khoảng 15 giây.
- **Sửa theo số đo**: hai chỉ mục kép cho phép kiểm tra số trùng (27 s → 0,8 s và 8 s → 0,2 s); tìm chữ trong nhật ký chỉ nhìn 30 ngày gần nhất nếu không ghi ngày (9 s → 0,35 s);
  tổng số kết quả của tìm kiếm có trần 10.000 ("10.000+") và không đếm lần hai khi trang chưa đầy; mọi truy vấn quét chuỗi con bị chặn ở 8 giây với thông báo rõ ràng;
  màn hình giám sát nhớ kết quả thăm dò và đo dung lượng tệp trong nền (6 s → 1 s); MongoDB vừa lỗi thì không bắt mọi lời gọi chờ lại 5 giây.
- **Dọn mã cũ**: bỏ các tệp CSS/JS/mẫu của giao diện cũ vẫn bị chèn vào mọi trang của Frappe (`web_include_*`, `app_include_css`), bốn hàm không ai gọi, và API đặt mật khẩu độc giả
  (đã có liên kết đặt mật khẩu một lần thay thế).
- **Kiểm tra cài mới**: site tạo mới sạch (không ERPNext) cài được và tự gieo dữ liệu; chỉ mục kép có cả ở site mới (`on_doctype_update`) lẫn site cũ (patch `add_volume_indexes`).
- **Tài liệu viết lại**: `README`, `DEPLOYMENT`, `KICH_BAN_DEMO…`, `DEV_WORKFLOW`, `UI_CUSTOMIZATION`; mới: `TRACEABILITY` (Phụ lục 03 → màn hình, API, kiểm thử), `SAO_LUU_KHOI_PHUC`, `HIEU_NANG`.
- **Kiểm thử mới**: `test_volume_guards` (13) và một test vitest; thêm vào CI.

## 3. Đối chiếu với Phụ lục 03

| Phân hệ | Trạng thái | Ghi chú |
|---|---|---|
| 1 Khai thác trực tuyến | Đạt | Trang đơn vị, đăng ký/đăng nhập/quên mật khẩu, tìm cơ bản/nâng cao, giỏ phiếu, góp ý |
| 2 Biên mục | Đạt | CRUD có luật xóa/chuyển, tải nhiều tệp, tìm nâng cao, in |
| 3 Danh mục | Đạt | Dùng cây `Storage Warehouse` (Kho/Phòng/Giá/Hộp) thay vì tạo thêm DocType Giá và Hộp (lệch so với kế hoạch ban đầu, có chủ đích) |
| 4 Thống kê/Báo cáo | Đạt | 11 báo cáo + tổng kiểm kê |
| 5 Xuất/Nhập XML | Đạt, theo lược đồ nội bộ | Chưa theo XSD chính thức vì chưa có từ phía khách hàng |
| 6 Quản lý độc giả | Đạt, trừ cấp quyền xem có thời hạn | Độc giả chỉ yêu cầu được thứ họ đã xem được (quyết định D5 hoãn) |
| 7 Bảo quản | Đạt | Khôi phục CSDL tự động tắt mặc định |
| 8 Quản trị | Đạt, chưa có 2FA | Đăng nhập `/dang-nhap` chưa có bước OTP |

## 4. Thay đổi hành vi cần biết
- Độc giả không còn thấy hồ sơ "Nháp" hoặc "Đã tiêu hủy" (hồ sơ demo AF-00004 và AF-00018 đang ở "Nháp").
- Meilisearch chỉ nghe trên `127.0.0.1`; cần khóa chính (master key).
- `Reader.max_confidentiality_priority` là ghi đè cá nhân (0 = theo nhóm), chỉ Document Admin sửa.
- Hạn mức phiếu của Reader Settings / Reader Group **có hiệu lực thật** (số mục/phiếu, phiếu/ngày, phiếu mở, chặn khi quá hạn).
- Ngôn ngữ site mặc định là tiếng Việt (chỉ đổi nếu site còn ở tiếng Anh).
- Cán bộ đặt mật khẩu từ liên kết một lần vào thẳng `/dashboard` (trước đây bị đưa vào giao diện Desk của Frappe).
- Các trang `www` cũ của backup, nhật ký, thiết lập, độc giả, phiếu… đã bị xóa hoặc chuyển hướng 301/302 sang giao diện mới.
- MariaDB: `innodb_snapshot_isolation` đặt OFF trong `docker/mariadb/my_custom.cnf`.

## 5. Chất lượng và kiểm thử

| Lớp kiểm thử | Số lượng | Cách chạy |
|---|---|---|
| Python (Frappe `IntegrationTestCase`) | 426 test, 19 module, tất cả nằm trong `ci.yml` | `bench --site <site> run-tests --app document_manager --module document_manager.tests.test_<tên>` |
| vitest (giao diện cán bộ) | 185 test, 12 file | `npx vitest run` trong `apps/document_manager/frontend` |
| Trình duyệt (Playwright) | 126 bước, 8 luồng: reader, catalogues, cataloguing, slips, reports, exchange, preservation, admin | `scripts/e2e/ui/*.mjs` (xem đầu mỗi file) |
| HTTP đầu-cuối | 497 kiểm tra, gồm ma trận quyền cho mọi API mới | `python scripts/e2e/e2e_http.py` |

Tài khoản và dữ liệu thử do `scripts/e2e/accounts.py up|down` tạo và dọn.

Khi viết các luồng trình duyệt đã phát hiện và sửa nhiều lỗi thật mà test đơn vị không bắt được: đọc tệp lỗi kiểu str/bytes,
HTTP 500 do snapshot isolation, danh sách hiện kết quả cũ sau khi đổi bộ lọc, rò rỉ sự tồn tại của phiếu, thiết lập sau nâng cấp
đọc ra 0, liên kết đặt mật khẩu đưa cán bộ vào Desk.

## 6. Tồn đọng và rủi ro đã biết

| Việc | Mức | Ghi chú |
|---|---|---|
| MongoDB Atlas không kết nối được từ container (SSL handshake) | Cao, ngoài mã nguồn | Có thể do danh sách IP được phép của Atlas. Hệ thống đang chạy ở chế độ dự phòng: không có `gridfs_file_id`, xem trước/tải dùng tệp riêng của Frappe; kiểm tra toàn vẹn ghi cảnh báo "Không kết nối MongoDB" |
| Cấp quyền xem có thời hạn cho tài liệu vượt mức (D5) | Trung bình | Hoãn từ G6 |
| 2FA cho cán bộ | Trung bình | Người bật 2FA phải dùng `/login` của Frappe |
| Lược đồ XML là lược đồ nội bộ | Thấp | Cần XSD chính thức từ khách hàng nếu có |
| ERPNext vẫn nằm trong image | Thấp | Không dùng; dọn ở lần sau |
| Tìm văn bản bằng cơ sở dữ liệu với từ hiếm chậm (4–8 s ở một triệu văn bản) | Thấp | Chỉ là đường dự phòng khi Meilisearch hỏng; bị chặn ở 8 s. Báo cáo văn bản không lọc 9 s. Chi tiết và khuyến nghị: `docs/HIEU_NANG.md` |
| Các tệp trong `docs/build-log/` là nhật ký lịch sử của giai đoạn đầu | Thấp | Giữ nguyên, không còn mô tả hiện trạng |
| Các trang `www` cũ (`usage_requests`, `readers`, …) chỉ còn là vỏ chuyển hướng theo người hỏi (độc giả và cán bộ đến nơi khác nhau, nên không thể là chuyển hướng cố định) | Thấp | Có thể xóa sau một bản phát hành khi không còn liên kết cũ |

## 7. Sau G9: việc còn lại đề xuất
1. **Dọn dữ liệu thử** trên site phát triển (nhật ký lỗi và bản ghi đã xóa sinh ra khi chạy kiểm thử, các đợt bảo quản cũ còn "Đang chờ").
2. **MongoDB Atlas**: cho phép địa chỉ IP của máy chủ rồi kiểm tra lại ở Giám sát hệ thống; sau đó chạy một đợt kiểm tra toàn vẹn "Tệp tài liệu" để kiểm tra các bản GridFS.
3. **Chọn một trong hai** nếu cần: cấp quyền xem có thời hạn (D5), hoặc OTP (2FA) trên `/dang-nhap`.
4. **Chạy `scripts/perf/volume_check.py` trên cấu hình máy chủ thật** (bộ nhớ đệm InnoDB lớn hơn 1 GB) để có số đo chính thức.
5. Xóa các trang `www` cũ và `docs/build-log/` sau một bản phát hành.

## 8. Phụ lục: số liệu theo giai đoạn

| Sau giai đoạn | Python | vitest | Ghi chú |
|---|---|---|---|
| Trước tái cấu trúc | 50 | – | |
| G2 | 106 (7 module) | – | cộng script HTTP e2e |
| G3 | 126 | 42 | |
| G4 | 152 (9 module) | 78 | luồng trình duyệt đầu tiên |
| G5 | 227 (11 module) | 123 | HTTP e2e 67 kiểm tra |
| G6 | + 3 module | – | luồng slips |
| G7 | 16 module | 165 | HTTP e2e 257 kiểm tra |
| G8 | 415 (18 module) | 184 | HTTP e2e 497 kiểm tra |
| G9 | 426 (19 module) | 185 | đo ở một triệu văn bản |
