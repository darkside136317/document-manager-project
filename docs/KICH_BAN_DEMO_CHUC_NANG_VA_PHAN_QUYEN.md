# Kịch bản demo chức năng và phân quyền

## 1. Mục đích và phạm vi

Kịch bản dùng để demo và nghiệm thu **Document Manager** theo một luồng nghiệp vụ xuyên suốt: quản trị viên dựng tài khoản, biên mục viên biên mục tài liệu số,
độc giả đăng ký và khai thác, phòng đọc và lãnh đạo xử lý phiếu, cán bộ bảo quản sao lưu và kiểm tra, quản trị viên giám sát.

Thời lượng gợi ý: **60 phút**. Mọi thao tác thực hiện trên site đã cài ứng dụng `document_manager` (xem [DEPLOYMENT.md](DEPLOYMENT.md)).
Ánh xạ từng bước tới yêu cầu của Phụ lục 03: [TRACEABILITY.md](TRACEABILITY.md).

> Trước buổi demo: worker (`queue-long`, `queue-short`, `scheduler`), Redis, MariaDB và Meilisearch đang chạy. MongoDB Atlas là tùy chọn: nếu không kết nối, mọi thứ
> vẫn chạy và màn hình **Giám sát hệ thống** ghi rõ trạng thái đó. Trích xuất nội dung và lập chỉ mục mất khoảng 15 giây sau khi lưu một tệp.

## 2. Tài khoản

Tạo bằng `Administrator` ở **Quản trị → Người dùng → Thêm người dùng**; mỗi tài khoản nhận một liên kết đặt mật khẩu dùng một lần (hiện đúng một lần, gửi cho người dùng).

| Tài khoản gợi ý | Vai trò | Dùng để demo |
|---|---|---|
| `admin.demo` | Quản trị tài liệu | Quản trị, thiết lập, xuất/nhập, báo cáo, sao lưu và mọi quyền nghiệp vụ |
| `bienmuc.demo` | Biên mục viên | Danh mục, biên mục, tổng kiểm kê |
| `phongdoc.demo` | Cán bộ phòng đọc | Độc giả, phiếu sử dụng và sao chụp, góp ý |
| `lanhdao.demo` | Lãnh đạo | Xem toàn bộ dữ liệu và báo cáo; duyệt phiếu cần lãnh đạo |
| `baoquan.demo` | Cán bộ bảo quản | Sao lưu, kiểm tra toàn vẹn, khôi phục |
| độc giả | Đăng ký ở `/dang-ky` | Tra cứu và gửi phiếu (không cần tạo tay) |

## 3. Dữ liệu chuẩn bị

Do `bienmuc.demo` hoặc `admin.demo` nhập qua giao diện (hoặc nhập một tệp XML mẫu ở **Xuất, nhập dữ liệu**):

1. **Danh mục**: cơ quan lưu trữ, mức độ mật (đã gieo sẵn *Thường*, *Mật*, *Tối mật*, *Tuyệt mật*), kho/giá/hộp, loại hình, nhóm tài liệu, khung phân loại, từ điển "Cơ quan ban hành".
2. **Biên mục**: Phông `P-2024` → Khối `HC` → Mục lục `ML-01` → Hồ sơ `HS-001 – Hồ sơ công tác năm 2024`.
3. **Văn bản** của `HS-001`: một văn bản mức *Thường* và một mức *Mật* (tải PDF có chữ để thử tìm theo nội dung).
4. **Giới thiệu đơn vị**: `scripts/demo/seed_organization.py up` gieo nội dung mẫu cho các trang công khai (đây là dữ liệu mẫu; `down` gỡ đi), hoặc nhập ở **Quản trị → Thông tin đơn vị**.

## 4. Ma trận phân quyền thực tế

Màn hình **Quản trị → Phân quyền vai trò** hiển thị ma trận này trực tiếp từ cấu hình thật (quyền theo từng loại dữ liệu). Tóm tắt:

| Nhóm chức năng | Quản trị tài liệu | Biên mục viên | Cán bộ phòng đọc | Lãnh đạo | Cán bộ bảo quản | Độc giả |
|---|---|---|---|---|---|---|
| Phông | Toàn quyền | Tạo, sửa (không xóa) | Xem | Xem | – | Xem phần được cấp |
| Khối, mục lục, hồ sơ, văn bản | Toàn quyền | Tạo, sửa, xóa | Xem | Xem | – | Xem phần được cấp |
| Tổng kiểm kê phông | Toàn quyền | Tạo, sửa (không xóa) | – | Xem | Xem | – |
| Danh mục chung (cơ quan, loại hình, nhóm, kho, từ điển…) | Toàn quyền | Tạo, sửa (từ điển: cả xóa) | Xem | Xem | Chỉ xem kho | – |
| Mức độ mật | Toàn quyền | Xem | Xem | Xem | – | – |
| Độc giả | Toàn quyền | – | Tạo, sửa | Xem | – | Sửa liên hệ của mình |
| Nhóm độc giả, mẫu phiếu | Toàn quyền | – | Xem | Xem | – | – |
| Đăng ký độc giả (hàng đợi duyệt) | Toàn quyền | – | Duyệt, từ chối | – | – | Gửi đăng ký |
| Phiếu sử dụng, phiếu sao chụp | Toàn quyền | – | Tiếp nhận, quyết định từng mục, giao, nhận trả, gia hạn | Duyệt phiếu cần lãnh đạo | – | Tạo, gửi, hủy phiếu của mình |
| Góp ý | Toàn quyền | – | Xử lý | Xem | – | Gửi |
| Thiết lập độc giả | Toàn quyền | – | Sửa | Xem | – | – |
| Báo cáo | Toàn bộ | Báo cáo phông, mục lục, hồ sơ, văn bản, thống kê | Báo cáo độc giả và phiếu | Toàn bộ | – | – |
| Xuất, nhập XML | Có | – | – | – | – | – |
| Sao lưu, kiểm tra, khôi phục | Có | – | – | – | Có | – |
| Người dùng, nhóm cán bộ, phân quyền, nhật ký, giám sát | Có | – | – | – | – | – |
| Thiết lập hệ thống, thông tin đơn vị, cơ cấu tổ chức | Có | – | Xem thông tin đơn vị | Xem | – | – |

Quy tắc chung: độc giả chỉ thấy hồ sơ và văn bản **đã công bố** (không "Nháp", không "Đã tiêu hủy"), không vượt mức mật của nhóm quyền, trong phạm vi phông của nhóm. Mọi API
kiểm quyền lại phía máy chủ; ẩn nút trên giao diện chỉ là tiện lợi.

## 5. Kịch bản trình diễn

### Pha A – Hai giao diện và tài khoản (6 phút)

1. `Administrator` vào `/dashboard`: tổng quan, thanh bên theo quyền. Vào **Quản trị → Người dùng**, tạo `bienmuc.demo` (vai trò Biên mục viên) → hiện liên kết đặt mật khẩu một lần.
2. Mở liên kết ở cửa sổ ẩn danh, đặt mật khẩu → vào thẳng `/dashboard`; thanh bên chỉ có phần Biên mục, Danh mục. Mở lại liên kết cũ: báo đã dùng.
3. Quay lại tài khoản quản trị: thử tự khóa hoặc tự bỏ vai trò quản trị của mình → bị từ chối; tạo **Nhóm cán bộ** cấp một vai trò cho nhiều người.
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
4. Quản trị viên (`admin.demo`): **Độc giả → Nhóm độc giả**, nâng *mức mật tối đa* của nhóm → độc giả tìm lại và thấy; thu hẹp *phạm vi phông* → thấy ít đi.

**Kết quả mong đợi:** danh sách, tìm kiếm, xem trước, tải tệp và truy cập địa chỉ trực tiếp đều theo cùng một chính sách.

### Pha D – Phiếu sử dụng, sao chụp, lãnh đạo duyệt, trả (12 phút)

1. Độc giả: ở kết quả tìm kiếm bấm **Thêm vào phiếu** cho vài hồ sơ và văn bản (phiếu nháp phía máy chủ là giỏ), mở phiếu, chọn mục đích, **Gửi**. Làm tương tự cho phiếu sao chụp.
2. `phongdoc.demo`: `/dashboard/doc-gia/phieu-su-dung`, hàng đợi *Chờ tiếp nhận* có số đếm trên thanh bên; mở phiếu, **quyết định từng mục** (đồng ý hoặc từ chối kèm lý do).
3. Phiếu có mục mức *Mật* tự chuyển sang *Chờ lãnh đạo duyệt*: `lanhdao.demo` duyệt các mục đó; có thể trả phiếu về phòng đọc.
4. Phòng đọc **giao** tài liệu (đặt hạn trả), **nhận trả** (ghi tình trạng từng mục), **gia hạn** một phiếu. In phiếu giao, phiếu lấy tài liệu, thẻ độc giả.
5. Thử vượt hạn mức (số mục/phiếu, số phiếu/ngày, có tài liệu quá hạn) → độc giả bị từ chối kèm lý do. Công việc hằng ngày đánh dấu phiếu quá hạn và nhắc độc giả.
6. Độc giả nhận **thông báo trong ứng dụng** (chuông) ở mỗi bước; gửi một **góp ý**, phòng đọc xử lý.

**Kết quả mong đợi:** vòng đời đủ: nháp → chờ tiếp nhận → (chờ lãnh đạo) → đã duyệt → đang sử dụng → đã trả; quá hạn là cờ, không phải trạng thái.

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
4. **Phân quyền vai trò**: ma trận quyền theo loại dữ liệu.

## 6. Checklist nghiệm thu phân quyền

Thực hiện các phép thử âm sau (kết quả kỳ vọng ở cuối dòng); phần lớn đã có sẵn trong `scripts/e2e/e2e_http.py`:

- Độc giả không vào `/dashboard` (bị chuyển về `/portal`); cán bộ vẫn mở được `/portal` qua liên kết "Giao diện độc giả" nếu có hồ sơ độc giả.
- Độc giả nhóm thấp không thấy, không mở được hồ sơ/văn bản mức cao hơn, hồ sơ nháp và đã tiêu hủy; nhóm cao hơn thấy.
- Độc giả không gọi được API xuất/nhập XML, báo cáo, bảo quản, người dùng, nhật ký (HTTP 403).
- Biên mục viên không có menu Bảo quản và Quản trị; gọi trực tiếp API người dùng bị từ chối.
- Cán bộ phòng đọc không tạo/sửa phông, hồ sơ, văn bản; chỉ xem.
- Cán bộ bảo quản không thấy Người dùng và Nhật ký.
- Quản trị viên không tạo được tài khoản System Manager, không sửa/khóa/xóa Administrator, không tự khóa hoặc tự hạ quyền, luôn còn ít nhất một quản trị viên.
- Không ai (kể cả quản trị viên) sửa hoặc xóa lẻ từng dòng nhật ký; chỉ có "Dọn dẹp" có kiểm soát.

## 7. Điểm cần xác nhận kỹ thuật trước khi nghiệm thu

1. MongoDB Atlas: nếu dùng, địa chỉ IP máy chủ đã được cho phép; nếu chưa, nêu rõ chế độ dự phòng đang chạy (xem Giám sát hệ thống).
2. Có sẵn một PDF không mật và một PDF mật để chứng minh lọc quyền.
3. Không chạy khôi phục CSDL trên môi trường có dữ liệu quan trọng; luôn tạo bản sao lưu trước.
4. Chưa có đăng nhập OTP (2FA) trên trang `/dang-nhap`; tài khoản bật 2FA dùng `/login` của Frappe.
