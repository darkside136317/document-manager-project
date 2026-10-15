# Kịch bản demo chức năng và phân quyền

## 1. Mục đích và phạm vi

Kịch bản dùng để demo và nghiệm thu **Document Manager** theo một luồng nghiệp vụ xuyên suốt: quản trị viên dựng tài khoản, biên mục viên biên mục tài liệu số,
độc giả đăng ký và khai thác, phòng đọc và lãnh đạo xử lý phiếu, cán bộ bảo quản sao lưu và kiểm tra, quản trị viên giám sát.

Thời lượng gợi ý: **70 phút**. Mọi thao tác thực hiện trên site đã cài ứng dụng `document_manager` (xem [DEPLOYMENT.md](DEPLOYMENT.md)).
Ánh xạ từng bước tới yêu cầu của Phụ lục 03: [TRACEABILITY.md](TRACEABILITY.md).

> Trước buổi demo: worker (`queue-long`, `queue-short`, `scheduler`), Redis, MariaDB và Meilisearch đang chạy. MongoDB Atlas là tùy chọn: nếu không kết nối, mọi thứ
> vẫn chạy và màn hình **Giám sát hệ thống** ghi rõ trạng thái đó. Trích xuất nội dung và lập chỉ mục mất khoảng 15 giây sau khi lưu một tệp.

## 2. Tài khoản

Tạo bằng `Administrator` ở **Quản trị → Người dùng → Thêm người dùng**; mỗi tài khoản nhận một liên kết đặt mật khẩu dùng một lần (hiện đúng một lần, gửi cho người dùng).

| Tài khoản gợi ý | Nhóm quyền | Dùng để demo |
|---|---|---|
| `admin.demo` | Quản trị viên | Mọi quyền: quản trị, phân quyền, thiết lập, xuất/nhập, báo cáo, sao lưu, mọi phông |
| `bienmuc.demo` | Biên mục viên | Danh mục, biên mục, tổng kiểm kê |
| `phongdoc.demo` | Cán bộ phòng đọc | Độc giả, phiếu sử dụng và sao chụp, góp ý |
| `lanhdao.demo` | Lãnh đạo | Xem toàn bộ dữ liệu và báo cáo; duyệt phiếu cần lãnh đạo |
| `baoquan.demo` | Cán bộ bảo quản | Sao lưu, kiểm tra toàn vẹn, khôi phục |
| độc giả | Đăng ký ở `/dang-ky` | Tra cứu và gửi phiếu (không cần tạo tay) |

## 3. Dữ liệu chuẩn bị

Do `bienmuc.demo` hoặc `admin.demo` nhập qua giao diện (hoặc nhập một tệp XML mẫu ở **Xuất, nhập dữ liệu**):

1. **Danh mục**: cơ quan lưu trữ, mức độ mật (đã gieo sẵn *Thường*, *Mật*, *Tối mật*, *Tuyệt mật*), kho/giá/hộp, loại hình, nhóm tài liệu, khung phân loại, từ điển "Cơ quan ban hành".
2. **Biên mục**: Phông `P-2024` → Khối `HC` → Mục lục `ML-01` → Hồ sơ `HS-001 – Hồ sơ công tác năm 2024`. Thêm phông thứ hai `P-2025` có ít nhất
   một hồ sơ, để demo phạm vi phông.
3. **Văn bản** của `HS-001`: một văn bản mức *Thường* và một mức *Mật* (tải PDF có chữ để thử tìm theo nội dung).
4. **Chế độ khai thác của phông**: phông mới mặc định *Theo cấp phép* (độc giả chưa thấy). Đặt `P-2024` là *Công khai*; giữ `P-2025` *Theo cấp phép*.
5. **Giới thiệu đơn vị**: `scripts/demo/seed_organization.py up` gieo nội dung mẫu cho các trang công khai (đây là dữ liệu mẫu; `down` gỡ đi), hoặc nhập ở **Quản trị → Thông tin đơn vị**.

## 4. Ma trận phân quyền thực tế

Quyền của một cán bộ gồm ba lớp (chi tiết: [PHAN_QUYEN_DOC_GIA.md](PHAN_QUYEN_DOC_GIA.md)):

| Lớp | Quyết định gì | Ai chỉnh, ở đâu |
|---|---|---|
| **Nhóm quyền** | Được làm gì với từng loại dữ liệu và dùng chức năng nào | Quản trị viên, **Quản trị → Phân quyền** |
| **Phạm vi phông** | Phông nào được xem, phông nào được sửa, mức mật cao nhất | Quản trị viên, **Quản trị → Người dùng** hoặc **Nhóm cán bộ** |
| **Khóa theo trạng thái** | Hồ sơ, phông *Đã đóng* và hồ sơ *Đã tiêu hủy* không sửa được | Tự động; chỉ người có chức năng "Sửa hồ sơ, phông đã hoàn thành hoặc đã đóng" |

Màn hình **Phân quyền** đọc và ghi thẳng vào cấu hình quyền thật: mỗi nhóm quyền có một ma trận *loại dữ liệu × thao tác* và danh sách chức năng.
Nhóm **Quản trị viên** luôn có mọi quyền và không sửa được. Năm nhóm có sẵn sửa được và có nút *Khôi phục mặc định*; quản trị viên có thể tạo thêm nhóm
(bắt đầu trống hoặc chép từ một nhóm khác). Bảng dưới là **mặc định khi cài đặt**:

| Nhóm chức năng | Quản trị viên | Biên mục viên | Cán bộ phòng đọc | Lãnh đạo | Cán bộ bảo quản | Độc giả |
|---|---|---|---|---|---|---|
| Phông | Toàn quyền | Tạo, sửa (không xóa) | Xem | Xem | – | Xem phần được cấp phép |
| Khối, mục lục, hồ sơ, văn bản | Toàn quyền | Tạo, sửa, xóa | Xem | Xem | – | Xem phần được cấp phép |
| Trường nhạy cảm (mức mật của hồ sơ, văn bản; thời hạn và tình trạng bảo quản) | Sửa | Sửa | Xem | Xem | – | – |
| Sửa hồ sơ, phông đã đóng hoặc đã tiêu hủy | Có | – | – | – | – | – |
| Tổng kiểm kê phông | Toàn quyền, mở lại kỳ đã xong | Tạo, sửa (không xóa) | – | Xem | Xem | – |
| Danh mục chung (cơ quan, loại hình, nhóm, kho, từ điển…) | Toàn quyền | Tạo, sửa (từ điển: cả xóa) | Xem | Xem | Chỉ xem kho | – |
| Mức độ mật | Toàn quyền | Xem | Xem | Xem | – | – |
| Độc giả | Toàn quyền | – | Tạo, sửa | Xem | – | Sửa liên hệ của mình |
| Nhóm độc giả, mẫu phiếu | Toàn quyền | – | Xem | Xem | – | – |
| Cấp phép khai thác phông cho độc giả | Có | – | Có | – | – | – |
| Đăng ký độc giả (hàng đợi duyệt) | Toàn quyền | – | Duyệt, từ chối | – | – | Gửi đăng ký |
| Phiếu sử dụng, phiếu sao chụp | Toàn quyền | – | Tiếp nhận, quyết định từng mục, giao, nhận trả, gia hạn | Duyệt phiếu cần lãnh đạo | – | Tạo, gửi, hủy phiếu của mình |
| Góp ý | Toàn quyền | – | Xử lý | Xử lý | – | Gửi |
| Thiết lập độc giả | Toàn quyền | – | Sửa | Xem | – | – |
| Báo cáo | Toàn bộ | Báo cáo phông, mục lục, hồ sơ, văn bản, thống kê | Báo cáo độc giả và phiếu | Toàn bộ | – | – |
| Xuất, nhập XML | Có | – | – | – | – | – |
| Sao lưu, kiểm tra, khôi phục | Có | – | – | – | Có | – |
| Người dùng, nhóm cán bộ, phân quyền | Có (chỉ quản trị viên, không giao được) | – | – | – | – | – |
| Nhật ký, giám sát | Có | – | – | – | – | – |
| Thiết lập hệ thống, thông tin đơn vị, cơ cấu tổ chức | Có | – | Xem thông tin đơn vị | Xem | – | – |

Phạm vi phông mặc định: cán bộ chưa được giao phạm vi xem và sửa mọi phông; báo cáo, tìm kiếm, cây biên mục và kiểm tra toàn vẹn chỉ tính các phông
trong phạm vi của người đang xem.

Độc giả chỉ thấy hồ sơ và văn bản **đã công bố** (không "Nháp", không "Đã tiêu hủy"), không vượt mức mật, và chỉ thuộc phông *Công khai* hoặc phông được
**cấp phép** còn hiệu lực cho nhóm hoặc cho riêng họ; phông *Nội bộ* không bao giờ mở cho độc giả. Mọi API kiểm quyền lại phía máy chủ; ẩn nút trên
giao diện chỉ là tiện lợi.

## 5. Kịch bản trình diễn

### Pha A – Hai giao diện và tài khoản (6 phút)

1. `Administrator` vào `/dashboard`: tổng quan, thanh bên theo quyền. Vào **Quản trị → Người dùng**, tạo `bienmuc.demo` (vai trò Biên mục viên) → hiện liên kết đặt mật khẩu một lần.
2. Mở liên kết ở cửa sổ ẩn danh, đặt mật khẩu → vào thẳng `/dashboard`; thanh bên chỉ có phần Biên mục, Danh mục. Mở lại liên kết cũ: báo đã dùng.
3. Quay lại tài khoản quản trị: thử tự khóa hoặc tự bỏ nhóm quyền quản trị của mình → bị từ chối; tạo **Nhóm cán bộ** cấp một nhóm quyền cho nhiều người.
4. Mở `/gioi-thieu` (không đăng nhập): trang công khai của đơn vị, lãnh đạo, cơ cấu, liên hệ.

**Kết quả mong đợi:** mỗi vai trò thấy menu riêng; liên kết đặt mật khẩu chỉ dùng một lần; không ai tự khóa mình.

### Pha B – Danh mục và biên mục (12 phút)

Thực hiện bằng `bienmuc.demo`.

1. **Danh mục**: sửa một mục ở *Cơ quan lưu trữ*, tạo từ điển nhiều cấp ở *Từ điển nhập nhanh* (cùng một giá trị dưới hai cha khác nhau), cây *Kho lưu trữ* (kho → phòng → giá → hộp).
2. **Biên mục** (`/dashboard/bien-muc`): dựng cây Phông → Khối → Mục lục → Hồ sơ; mở một hồ sơ, **tải lên nhiều tệp cùng lúc** (mỗi tệp có tiến độ riêng, mỗi tệp thành một văn bản).
3. Mở một văn bản: xem trước PDF/ảnh/văn bản, mã SHA-256, trạng thái xử lý nền; sửa mô tả (trường *Cơ quan ban hành* gợi ý theo từ điển); in phiếu mô tả hồ sơ và mục lục hồ sơ.
4. **Tìm kiếm** (`/dashboard/tim-kiem`): tìm cơ bản theo từ trong nội dung (có làm nổi từ khóa), tìm nâng cao theo phông, loại tệp, khoảng ngày; lưu bộ lọc; Ctrl+K.
5. Thử xóa một mục lục còn hồ sơ → bị từ chối; chuyển một hồ sơ sang mục lục khác → số văn bản và vị trí của các văn bản con cập nhật theo.

**Kết quả mong đợi:** cấp bậc luôn nhất quán; số liệu tự cập nhật; không xóa được cha còn con.

### Pha C – Độc giả đăng ký, tra cứu và độ mật (10 phút)

1. Ẩn danh mở `/dang-ky`, đăng ký một độc giả. Không có thông báo nào lộ email đã tồn tại hay chưa.
2. `phongdoc.demo`: **Độc giả → Đăng ký độc giả**, duyệt → hiện **liên kết đặt mật khẩu một lần** (không cần email). Độc giả đặt mật khẩu và vào `/portal`.
3. Độc giả tìm một từ có trong PDF (tìm theo nội dung). Văn bản mức *Mật* **không** hiện. Thử mở thẳng địa chỉ của văn bản mật → báo như không tồn tại.
4. Quản trị viên (`admin.demo`): **Độc giả → Nhóm độc giả**, nâng *mức mật tối đa* của nhóm → độc giả tìm lại và thấy.
5. **Cấp phép phông.** Độc giả chỉ thấy `P-2024` (*Công khai*); trang *Tài khoản* liệt kê đúng một phông. `phongdoc.demo` mở **Danh sách độc giả** → độc giả đó
   → *Phông được cấp phép riêng*, thêm `P-2025` với *Đến ngày* sau một tháng → độc giả tìm thấy hồ sơ của `P-2025`; trang *Tài khoản* ghi hạn. Ở
   **Danh mục → Phông lưu trữ** → `P-2025`, khung *Độc giả được khai thác* liệt kê cấp phép vừa tạo, người cấp và ngày cấp.
6. Đặt `P-2025` là *Nội bộ* → độc giả không còn thấy phông này dù vẫn còn cấp phép; đặt lại *Theo cấp phép* → thấy lại.

**Kết quả mong đợi:** danh sách, tìm kiếm, xem trước, tải tệp và truy cập địa chỉ trực tiếp đều theo cùng một chính sách; phông chưa cấp phép
và phông nội bộ không lộ ra ở đâu.

### Pha D – Phiếu sử dụng, sao chụp, lãnh đạo duyệt, trả (12 phút)

1. Độc giả: ở kết quả tìm kiếm bấm **Thêm vào phiếu** cho vài hồ sơ và văn bản (phiếu nháp phía máy chủ là giỏ), mở phiếu, chọn mục đích, **Gửi**. Làm tương tự cho phiếu sao chụp.
2. `phongdoc.demo`: `/dashboard/doc-gia/phieu-su-dung`, hàng đợi *Chờ tiếp nhận* có số đếm trên thanh bên; mở phiếu, **quyết định từng mục** (đồng ý hoặc từ chối kèm lý do).
3. Phiếu có mục mức *Mật* tự chuyển sang *Chờ lãnh đạo duyệt*: `lanhdao.demo` duyệt các mục đó; có thể trả phiếu về phòng đọc.
4. Phòng đọc **giao** tài liệu (đặt hạn trả), **nhận trả** (ghi tình trạng từng mục), **gia hạn** một phiếu. In phiếu giao, phiếu lấy tài liệu, thẻ độc giả.
5. Thử vượt hạn mức (số mục/phiếu, số phiếu/ngày, có tài liệu quá hạn) → độc giả bị từ chối kèm lý do. Công việc hằng ngày đánh dấu phiếu quá hạn và nhắc độc giả.
6. Độc giả nhận **thông báo trong ứng dụng** (chuông) ở mỗi bước; gửi một **góp ý**, phòng đọc xử lý.
7. **Luật phiếu theo cấp phép.** Độc giả gửi phiếu có một hồ sơ của `P-2025`; trước khi duyệt, phòng đọc thu hồi cấp phép `P-2025` → bấm duyệt bị từ chối
   và thông báo nêu mục nào hết quyền. Cấp lại với *Đến ngày* gần: khi giao, **hạn trả** không vượt ngày đó.
8. Phiếu sao chụp có văn bản mức *Mật* → bị từ chối (mức *Mật* không *Cho phép sao chụp*); mỗi mục sao chụp ghi số bản, hình thức (bản giấy, bản số)
   và trang cần sao.
9. Phòng đọc lập phiếu hộ một độc giả không có tài khoản: mục thuộc phông độc giả đó chưa được cấp phép bị từ chối, dù cán bộ xem được phông đó.

**Kết quả mong đợi:** vòng đời đủ: nháp → chờ tiếp nhận → (chờ lãnh đạo) → đã duyệt → đang sử dụng → đã trả; quá hạn là cờ, không phải trạng thái.
Mỗi mục được kiểm theo quyền của độc giả của phiếu ở lúc gửi, lúc duyệt và lúc giao.

### Pha E – Báo cáo và xuất/nhập XML (8 phút)

Thực hiện bằng `admin.demo`.

1. `/dashboard/bao-cao`: báo cáo phông, mục lục, hồ sơ, văn bản; thống kê theo phông, năm, mức mật, loại hình, kho; báo cáo độc giả, phiếu quá hạn. Tải CSV/XLSX; **In** (có đầu đề đơn vị và chữ ký), PDF.
2. **Tổng kiểm kê** (`/dashboard/kiem-ke`): tạo kỳ kiểm kê, lấy số liệu hệ thống, nhập số đếm thực tế, xem chênh lệch, hoàn thành (khóa số liệu).
3. `/dashboard/trao-doi-du-lieu`: **Xuất** theo bộ lọc, chọn trường theo từng cấp, xem trước số lượng, tải XML (và XSD). **Nhập**: tải tệp lên, hệ thống phân tích và báo lỗi từng dòng, **chạy thử** (không ghi gì) rồi chạy thật; nhập lại cùng tệp không tạo thêm bản ghi.

**Kết quả mong đợi:** xuất/nhập chạy nền có tiến độ, theo quyền của người chạy; tệp độc hại (DTD, thực thể) bị từ chối.

### Pha F – Bảo quản (8 phút)

Thực hiện bằng `baoquan.demo`.

1. Sao lưu → **Sao lưu mới** (*Cả hai*): theo dõi tiến độ; lần thứ hai chỉ chép tệp mới. Mở bản kết xuất: **Kiểm tra bản sao lưu**, tải về.
2. Làm hỏng có chủ đích một tệp trên máy chủ (hoặc xóa nó), rồi Kiểm tra → **Kiểm tra mới** (*Tệp tài liệu*): phát hiện tệp mất và cho biết có bản sao lưu khôi phục được.
3. **Chuyển sang khôi phục**: đợt khôi phục đưa đúng tệp cũ về; chạy kiểm tra lại: sạch.
4. Khôi phục → bản sao lưu CSDL → **Khôi phục từ bản này…**: hiện hướng dẫn đã kiểm tra, **không** tự chạy.

**Giới hạn cần nêu:** khôi phục CSDL tự động tắt mặc định (cần `dm_allow_db_restore`, mật khẩu root và gõ lại tên site). Chi tiết: [SAO_LUU_KHOI_PHUC.md](SAO_LUU_KHOI_PHUC.md).

### Pha G – Quản trị, nhật ký, giám sát (4 phút)

Thực hiện bằng `admin.demo`.

1. **Thiết lập hệ thống**: sao lưu tự động, thời hạn giữ, chính sách mật khẩu, số lần đăng nhập sai.
2. **Nhật ký hệ thống**: lọc theo loại, người dùng, ngày; xem chi tiết một dòng; tải CSV. **Dọn dẹp**: xem trước số dòng, chỉ dòng cũ hơn 7 ngày, phải gõ lại số dòng để xác nhận (việc dọn cũng được ghi lại).
3. **Giám sát hệ thống**: dịch vụ, chỉ mục tìm kiếm, hàng đợi, đĩa, sao lưu gần nhất, người dùng.

### Pha H – Phân quyền cán bộ (10 phút)

Thực hiện bằng `admin.demo`, kiểm lại bằng `bienmuc.demo` ở một cửa sổ khác.

1. **Quản trị → Phân quyền** → nhóm *Biên mục viên*: bỏ quyền **Xóa** ở *Hồ sơ lưu trữ*, xem tóm tắt thay đổi, **Lưu thay đổi**. `bienmuc.demo` tải lại trang:
   nút xóa hồ sơ biến mất, gọi thẳng API xóa bị từ chối. Bấm **Khôi phục mặc định** → quyền xóa trở lại.
2. **Thêm nhóm quyền** "Biên mục phông 2025", *Bắt đầu từ quyền của nhóm* Biên mục viên; bỏ chức năng "Lập và hoàn thành tổng kiểm kê phông".
   Nhóm Quản trị viên hiện mọi ô đã chọn và không sửa được.
3. **Quản trị → Người dùng** → `bienmuc.demo` → *Phạm vi truy cập*: xem *Tất cả phông*, sửa *Chỉ các phông được chọn* = `P-2025`. Khung *Quyền thực tế*
   ghi phông được xem, phông được sửa, mức mật và chức năng sau khi gộp phạm vi riêng với các nhóm cán bộ. `bienmuc.demo`: vẫn thấy `P-2024` nhưng mọi ô sửa chỉ đọc; sửa, thêm được ở `P-2025`; chuyển
   một hồ sơ từ `P-2025` sang `P-2024` bị từ chối (cần quyền sửa cả hai phông).
4. Đổi tiếp phạm vi xem thành `P-2025`: `P-2024` biến mất khỏi cây biên mục, tìm kiếm và báo cáo của `bienmuc.demo`.
5. Đóng một hồ sơ (*Đã đóng*): `bienmuc.demo` thấy dải "Hồ sơ đã đóng" và không sửa được; `admin.demo` vẫn sửa được.
6. **Nhật ký hệ thống**: các dòng "Sửa nhóm quyền …", "Tạo nhóm quyền …" và "đổi phạm vi phông" ghi rõ ai đổi gì.

**Kết quả mong đợi:** thay đổi quyền có hiệu lực ngay, không cần khởi động lại; quản trị viên luôn giữ mọi quyền; mọi thay đổi đều có trong nhật ký.

## 6. Checklist nghiệm thu phân quyền

Thực hiện các phép thử âm sau (kết quả kỳ vọng ở cuối dòng); phần lớn đã có sẵn trong `scripts/e2e/e2e_http.py`:

- Độc giả không vào `/dashboard` (bị chuyển về `/portal`); cán bộ vẫn mở được `/portal` qua liên kết "Giao diện độc giả" nếu có hồ sơ độc giả.
- Độc giả nhóm thấp không thấy, không mở được hồ sơ/văn bản mức cao hơn, hồ sơ nháp và đã tiêu hủy; nhóm cao hơn thấy.
- Độc giả không gọi được API xuất/nhập XML, báo cáo, bảo quản, người dùng, nhật ký (HTTP 403).
- Biên mục viên không có menu Bảo quản và Quản trị; gọi trực tiếp API người dùng bị từ chối.
- Cán bộ phòng đọc không tạo/sửa phông, hồ sơ, văn bản; chỉ xem.
- Cán bộ bảo quản không thấy Người dùng và Nhật ký.
- Quản trị viên không tạo được tài khoản System Manager, không sửa/khóa/xóa Administrator, không tự khóa hoặc tự hạ quyền, luôn còn ít nhất một quản trị viên.
- Chỉ quản trị viên mở được **Phân quyền** và sửa phạm vi của người dùng; nhóm Quản trị viên không sửa, không xóa được; nhóm có sẵn không xóa được; nhóm
  còn người dùng hoặc còn được nhóm cán bộ cấp thì không xóa được.
- Cán bộ có phạm vi hẹp không thấy hồ sơ, văn bản của phông ngoài phạm vi ở danh sách, cây biên mục, tìm kiếm, báo cáo, xem trước, tải tệp; không sửa
  được phông chỉ được xem; không sao lưu CSDL, không tải bản sao lưu, không khôi phục CSDL.
- Hồ sơ, phông *Đã đóng* và hồ sơ *Đã tiêu hủy* chỉ sửa được bởi người có chức năng "Sửa hồ sơ, phông đã hoàn thành hoặc đã đóng".
- Độc giả không thấy phông *Theo cấp phép* chưa được cấp, phông có cấp phép đã hết hạn hoặc chưa tới ngày, và phông *Nội bộ*; không cho được tài liệu
  của các phông đó vào phiếu. Người không có chức năng "Cấp phép khai thác phông cho độc giả" không cấp hay thu hồi được.
- Không ai (kể cả quản trị viên) sửa hoặc xóa lẻ từng dòng nhật ký; chỉ có "Dọn dẹp" có kiểm soát.

## 7. Điểm cần xác nhận kỹ thuật trước khi nghiệm thu

1. MongoDB Atlas: nếu dùng, địa chỉ IP máy chủ đã được cho phép; nếu chưa, nêu rõ chế độ dự phòng đang chạy (xem Giám sát hệ thống).
2. Có sẵn một PDF không mật và một PDF mật để chứng minh lọc quyền.
3. Không chạy khôi phục CSDL trên môi trường có dữ liệu quan trọng; luôn tạo bản sao lưu trước.
4. Chưa có đăng nhập OTP (2FA) trên trang `/dang-nhap`; tài khoản bật 2FA dùng `/login` của Frappe.
