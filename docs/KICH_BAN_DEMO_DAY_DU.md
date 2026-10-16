# Kịch bản demo đầy đủ – Document Manager

Kịch bản trình diễn **toàn bộ chức năng** của phần mềm theo *Phụ lục 03 – Danh sách tính năng phần mềm quản lý và khai thác hồ sơ số hóa*,
theo một mạch dữ liệu liền: dựng tài khoản → danh mục → biên mục → độc giả đăng ký, tra cứu → phiếu sử dụng, phiếu sao chụp, lãnh đạo duyệt →
báo cáo, kiểm kê → xuất, nhập XML → bảo quản → phân quyền, nhật ký, giám sát.

| | |
|---|---|
| Thời lượng | Bản đầy đủ khoảng **2 giờ** (mục 2). Bản rút gọn **30 phút** (mục 3) |
| Người trình bày | Một người điều khiển, nên có thêm một người hỗ trợ đổi cửa sổ trình duyệt |
| Đối chiếu yêu cầu | Mục 4: từng dòng của Phụ lục 03 → bước demo |
| Rủi ro, cách xử lý | Mục 5 (đọc trước buổi demo) |
| Nghiệm thu phân quyền | Mục 7 (phép thử âm), mục 8 (điểm cần xác nhận kỹ thuật) |

Quy ước: **A4** là mã bước; ★ là bước có trong bản rút gọn; *nghiêng* là tên menu, nút hoặc trường trên màn hình; "→" là bấm tiếp.
Đường dẫn tính từ địa chỉ của hệ thống, ví dụ `http://localhost:8888`.

---

## 0. Chuẩn bị trước buổi demo

### 0.1. Môi trường (làm trước 1 ngày, kiểm lại trước 30 phút)

Chạy trong thư mục `docker/`:

```bash
C="docker compose -f docker-compose.yml -f docker-compose.dev.yml"     # hoặc docker-compose.prod.yml
$C up -d
$C ps                                                                    # mọi dịch vụ Up
$C exec backend bench --site <site> scheduler status                     # phải là "enabled"; nếu không: enable-scheduler
$C restart queue-long queue-short scheduler                              # worker nạp mã mới nhất
$C exec backend bench --site <site> clear-cache
```

- Đăng nhập `Administrator`, mở *Quản trị → Giám sát hệ thống*: Meilisearch, hàng đợi, đĩa phải xanh. MinIO ghi "Kết nối thành công" nếu đã bật,
  hoặc "Đã tắt; tệp lưu trên Frappe" (mặc định `MINIO_MODE=disabled`): cả hai đều demo được, xem mục 5.
- Dọn dữ liệu thử còn sót: `scripts/e2e/accounts.py down` (xem đầu tệp).
- Nội dung trang công khai: `scripts/demo/seed_organization.py up` (dữ liệu mẫu, gỡ bằng `down`), rồi chỉnh tên đơn vị cho đúng buổi demo.

### 0.2. Trình duyệt

Phiên đăng nhập gắn với trình duyệt, nên cần **ba cửa sổ tách biệt**:

| Cửa sổ | Dùng cho | Gợi ý |
|---|---|---|
| **W1** | Quản trị viên, biên mục viên, phòng đọc, bảo quản (đăng xuất/đăng nhập lại khi đổi người) | Trình duyệt chính |
| **W2** | Độc giả, khách | Cửa sổ ẩn danh |
| **W3** | Lãnh đạo (và kiểm tra quyền của biên mục viên ở phần M) | Trình duyệt thứ hai hoặc một hồ sơ trình duyệt khác |

Phóng to 110–125% để người xem đọc được. Tắt thông báo hệ điều hành.

### 0.3. Tệp mẫu

Tạo bằng `python scripts/e2e/ui/make_sample_files.py <thư mục>` (hoặc dùng sẵn `scripts/e2e/ui/samples`):

| Tệp | Dùng ở | Ghi chú |
|---|---|---|
| `Quyet dinh 123 ve luu tru.pdf` | D4, D7, E4, G1, L3 | PDF có chữ; chứa từ hiếm **"zebra"** để demo tìm theo nội dung |
| `Bao cao nam 2020.pdf` | D4, D5, F1 | Sẽ đặt mức *Mật* |
| `Anh scan trang 1.png` | D4 | Ảnh: xem trước được, không tìm được theo nội dung (chưa có OCR) |
| `ghi chu.txt` | D4 | Định dạng không được nhận: chứng minh bị từ chối |

Nên có thêm 1–2 PDF thật của đơn vị (văn bản có chữ, không phải bản quét) để tăng tính thuyết phục.

### 0.4. Tài khoản demo

Tạo ở bước A4 (hoặc tạo sẵn cho bản rút gọn). Mật khẩu đặt qua liên kết dùng một lần.

| Tài khoản | Nhóm quyền | Vai trò trong kịch bản |
|---|---|---|
| `Administrator` | (quản trị kỹ thuật) | Khởi động, tạo tài khoản |
| `admin.demo@example.com` | Quản trị viên | Quản trị, phân quyền, báo cáo, XML |
| `bienmuc.demo@example.com` | Biên mục viên | Danh mục, biên mục, kiểm kê |
| `phongdoc.demo@example.com` | Cán bộ phòng đọc | Đăng ký, độc giả, phiếu, góp ý, cấp phép phông |
| `lanhdao.demo@example.com` | Lãnh đạo | Duyệt phiếu cần lãnh đạo |
| `baoquan.demo@example.com` | Cán bộ bảo quản | Sao lưu, kiểm tra, khôi phục |
| Nguyễn Văn An (`an.docgia@example.com`) | Độc giả, tự đăng ký | Tra cứu, phiếu, góp ý |
| Trần Thị Bình (không email) | Độc giả, lập tại quầy | Phiếu do cán bộ lập hộ |

### 0.5. Dữ liệu dùng trong kịch bản

| Loại | Giá trị nhập |
|---|---|
| Cơ quan lưu trữ | Trung tâm Lưu trữ lịch sử tỉnh |
| Phông | **P-2024** "Phông Ủy ban nhân dân tỉnh" – *Công khai*; **P-2025** "Phông Sở Nội vụ" – *Theo cấp phép* |
| Loại hình, nhóm tài liệu | Tài liệu hành chính; Văn bản quy phạm |
| Kho | Kho A (*Kho*) → Phòng 1 (*Phòng*) → Giá 01 (*Giá*) → Hộp 001 (*Hộp*) |
| Khung phân loại | 1. Tổng hợp → 1.1. Kế hoạch, báo cáo |
| Từ điển | "Cơ quan ban hành" (đơn cấp): UBND tỉnh, Sở Nội vụ. "Địa danh" (đa cấp): Tỉnh A → Huyện B; Tỉnh C → Huyện B |
| Khối, mục lục | HC – Khối tài liệu hành chính; ML-01 – Mục lục hồ sơ năm 2024 (trong P-2024); ML-02 (trong P-2025) |
| Hồ sơ | **HS-001** "Hồ sơ về công tác lưu trữ năm 2024" (P-2024, *Thường*, *Đã hoàn thành*); **HS-101** "Hồ sơ tổ chức bộ máy" (P-2025, *Đã hoàn thành*) |
| Văn bản | Từ 3 tệp mẫu trong HS-001; "Bao cao nam 2020" đặt mức *Mật*; HS-101 có ít nhất một văn bản PDF |

Cho bản rút gọn: dựng sẵn toàn bộ dữ liệu ở bảng này và các tài khoản ở 0.4 từ hôm trước.

### 0.6. Diễn tập

Chạy toàn bộ kịch bản một lần trên đúng máy demo, rồi xóa dữ liệu diễn tập (mục 6) hoặc dựng lại site. Đăng ký độc giả bị giới hạn 10 lần/giờ mỗi IP:
nếu diễn tập nhiều lần, chạy `accounts.py up` (xóa bộ đếm giới hạn) hoặc chờ một giờ.

---

## 1. Tổng quan mạch demo

| Phần | Nội dung | Tài khoản | Cửa sổ | Phút |
|---|---|---|---|---|
| A | Khởi động, thiết lập, người dùng, đổi mật khẩu | Administrator, admin.demo | W1, W2 | 10 |
| B | Trang công khai của đơn vị | khách | W2 | 3 |
| C | Danh mục dùng chung | bienmuc.demo / admin.demo | W1 | 10 |
| D | Biên mục: khối, mục lục, hồ sơ, văn bản, tệp, in, tìm kiếm | bienmuc.demo | W1 | 15 |
| E | Độc giả: đăng ký, duyệt, quản lý, tra cứu, phân quyền, cấp phép phông, mẫu phiếu, thiết lập | khách, phongdoc, admin, An | W1, W2 | 15 |
| F | Phiếu yêu cầu sử dụng: giỏ, gửi, duyệt từng mục, lãnh đạo, giao, gia hạn, trả, in | An, phongdoc, lanhdao | W1–W3 | 15 |
| G | Phiếu sao chụp | An, phongdoc, lanhdao | W1–W3 | 7 |
| H | Góp ý, thông báo, tài khoản độc giả | An, phongdoc | W1, W2 | 4 |
| I | Báo cáo, thống kê, tổng kiểm kê | admin.demo, bienmuc.demo | W1 | 10 |
| K | Xuất, nhập XML | admin.demo | W1 | 8 |
| L | Sao lưu, kiểm tra toàn vẹn, khôi phục | baoquan.demo | W1 | 12 |
| M | Phân quyền cán bộ, phạm vi phông, nhật ký, giám sát | admin.demo, bienmuc.demo | W1, W3 | 10 |

---

## 2. Kịch bản chi tiết

### Phần A – Khởi động và quản trị tài khoản (10 phút)

**A1 ★ Hai giao diện.** W1: mở `/dang-nhap`, đăng nhập `Administrator` → hệ thống tự vào `/dashboard`.
Giới thiệu *Tổng quan* (số liệu kho tài liệu, văn bản cập nhật gần đây, danh mục dùng chung) và thanh bên chia theo phân hệ.
- *Mong đợi:* cán bộ vào ứng dụng `/dashboard`; độc giả sẽ vào `/portal` (phần E). Thanh bên chỉ hiện những gì người dùng được phép.

**A2 Cấu hình tham số hệ thống.** *Quản trị → Thiết lập hệ thống*: sao lưu tự động (tần suất, gồm tệp, thời hạn giữ, số bản tối thiểu), kiểm tra toàn vẹn tự động,
thời hạn giữ nhật ký, bật nhật ký, chính sách độ mạnh mật khẩu, số lần đăng nhập sai và thời gian khóa → *Lưu thiết lập*.

**A3 Thông tin đơn vị.** *Quản trị → Thông tin đơn vị*: giới thiệu, lãnh đạo (bảng), liên hệ → sửa một dòng, lưu.
*Quản trị → Cơ cấu tổ chức*: cây phòng ban, thêm một đơn vị con.
- *Mong đợi:* nội dung hiện ngay ở trang công khai (B1).

**A4 ★ Thêm người dùng.** *Quản trị → Người dùng → Thêm người dùng*: tạo 5 tài khoản ở 0.4, chọn nhóm quyền tương ứng ở mục *Vai trò* → *Tạo*.
- *Mong đợi:* mỗi tài khoản nhận một **liên kết đặt mật khẩu dùng một lần** (hiện đúng một lần, hiệu lực 72 giờ) để chuyển cho người dùng; không cần email.
  Chép liên kết của `bienmuc.demo` cho A7.

**A5 Tìm, sửa, khóa, xóa người dùng.** Ô *Tìm theo tên, email, điện thoại…*; lọc *Mọi vai trò / Mọi nhóm / Mọi tình trạng*. Mở một người: sửa điện thoại → *Lưu*;
*Khóa* rồi *Mở khóa*; tạo thêm một tài khoản thừa rồi *Xóa*.
- *Mong đợi:* tài khoản đã có dữ liệu thì không xóa được, hệ thống đề nghị khóa thay vì xóa.

**A6 Quản lý người dùng theo nhóm.** *Quản trị → Nhóm cán bộ → Thêm nhóm* "Tổ biên mục": *Vai trò cấp cho các thành viên* = Biên mục viên, thêm thành viên → *Lưu*.
- *Mong đợi:* thành viên tự có nhóm quyền của nhóm; lọc *Nhóm* ở màn hình Người dùng thấy họ.

**A7 Liên kết một lần, đổi mật khẩu.** W2: mở liên kết của `bienmuc.demo`, đặt mật khẩu → vào `/dashboard`, thanh bên chỉ có Biên mục, Danh mục, Báo cáo, Tổng kiểm kê.
Mở lại liên kết cũ → báo đã dùng. Menu tài khoản (góc trên phải) → *Đổi mật khẩu* (mật khẩu hiện tại, mật khẩu mới, nhập lại). Đăng xuất W2.

**A8 Rào chắn.** W1 (`Administrator` hoặc `admin.demo`): mở chính tài khoản mình, thử *Khóa* hoặc bỏ nhóm *Quản trị viên* → bị từ chối.
- *Mong đợi:* không ai tự khóa, tự hạ quyền; luôn còn ít nhất một quản trị viên; không tạo được tài khoản System Manager từ ứng dụng.

### Phần B – Trang công khai (3 phút)

**B1 ★** W2 (chưa đăng nhập): `/gioi-thieu` (trang chủ), `/lanh-dao`, `/co-cau`, `/lien-he`, `/huong-dan`.
- *Mong đợi:* nội dung lấy từ A3; có nút *Đăng nhập*, *Đăng ký*; giao diện dùng được trên điện thoại (thu nhỏ cửa sổ để minh họa).

### Phần C – Danh mục dùng chung (10 phút, `bienmuc.demo` hoặc `admin.demo`)

Mọi danh mục dùng chung một kiểu màn hình: danh sách có tìm, *Thêm mới*, biểu mẫu bên phải với *Lưu*, *Xóa*.

**C1 Cơ quan lưu trữ.** *Danh mục → Cơ quan lưu trữ → Thêm mới* "Trung tâm Lưu trữ lịch sử tỉnh"; sửa địa chỉ; tạo một mục thử rồi xóa.

**C2 ★ Phông lưu trữ.** *Danh mục → Phông lưu trữ → Thêm mới* P-2024 và P-2025 (0.5): tên, mã, cơ quan, năm, loại hình, nhóm, khung phân loại.
Giới thiệu hai trường mới: *Chế độ khai thác* (Công khai / Theo cấp phép / Nội bộ; phông mới mặc định *Theo cấp phép*) và *Cho phép sao chụp*.
Đặt P-2024 *Công khai*, giữ P-2025 *Theo cấp phép*.

**C3 Loại hình, nhóm tài liệu.** *Loại hình tài liệu*: thêm "Tài liệu hành chính"; *Nhóm tài liệu*: thêm "Văn bản quy phạm".

**C4 Kho, giá, hộp.** *Kho, giá, hộp lưu trữ*: dạng cây. Thêm Kho A (*Loại* = Kho) → Phòng 1 (Phòng) → Giá 01 (Giá) → Hộp 001 (Hộp), sức chứa, vị trí.
- *Mong đợi:* hồ sơ chọn được hộp ở D3; đáp ứng "tính chất tài liệu như giá, hộp".

**C5 Mức độ mật.** *Mức độ mật*: 4 mức gieo sẵn (Thường, Mật, Tối mật, Tuyệt mật) với *thứ tự ưu tiên*, *Cần lãnh đạo duyệt*, *Cho phép sao chụp*.
- *Mong đợi:* mặc định chỉ mức Thường cho sao chụp; từ mức Mật trở lên cần lãnh đạo duyệt khi độc giả mượn.

**C6 Khung phân loại hồ sơ.** Cây "1. Tổng hợp" → "1.1. Kế hoạch, báo cáo".

**C7 Từ điển đơn cấp, đa cấp.** *Loại từ điển*: thêm "Cơ quan ban hành" và "Địa danh" (đánh dấu *Từ điển đa cấp*).
*Từ điển nhập nhanh*: thêm "UBND tỉnh", "Sở Nội vụ" vào "Cơ quan ban hành"; thêm Tỉnh A → Huyện B và Tỉnh C → Huyện B vào "Địa danh".
- *Mong đợi:* cùng một giá trị đứng được dưới hai cha khác nhau; giá trị "Cơ quan ban hành" được gợi ý khi nhập văn bản (D5).

**C8 Ràng buộc.** Thử xóa mức mật *Thường* hoặc một phông đang có khối → bị từ chối, thông báo nêu bản ghi đang dùng.

### Phần D – Biên mục (15 phút, `bienmuc.demo`)

**D1 ★ Khối tài liệu.** *Biên mục → Biên mục hồ sơ, văn bản*: cây phông bên trái. Chọn P-2024 → *Thêm khối tài liệu* "HC" → *Lưu*; chọn khối → *Sửa* đổi tên → *Lưu*.
Tạo một khối thử rồi xóa (nút *Xóa* trong biểu mẫu).

**D2 ★ Mục lục tài liệu.** Chọn khối HC → *Thêm mục lục* "ML-01 – Mục lục hồ sơ năm 2024" (số, năm bắt đầu, kết thúc) → *Lưu*; *Sửa* năm; tạo một mục lục thử rồi xóa.
Làm tương tự ML-02 trong một khối của P-2025.

**D3 ★ Hồ sơ lưu trữ.** Chọn ML-01 → *Thêm hồ sơ*: HS-001 (số, tiêu đề, ngày bắt đầu, kết thúc, mức *Thường*, loại hình, nhóm, khung phân loại, kho *Hộp 001*, giá, hộp,
trạng thái *Đã hoàn thành*) → *Lưu* → mở trang hồ sơ. *Sửa hồ sơ* → đổi số trang → *Lưu*. Tạo HS-101 trong ML-02. Tạo một hồ sơ thử rồi xóa.
- *Mong đợi:* phông, khối tự điền theo mục lục; danh sách hồ sơ bên phải cây có tìm và sắp xếp.

**D4 ★ Thêm văn bản bằng tải tệp.** Trang HS-001 → *Tải tệp lên*: chọn cùng lúc ba tệp mẫu (0.3). Thử thêm `ghi chu.txt`.
- *Mong đợi:* mỗi tệp có tiến độ riêng và thành một văn bản; `.txt` bị từ chối (chỉ nhận pdf, docx, xlsx, doc, xls, jpg, png, tif; tối đa 100 MB).
  Khoảng 15 giây sau, trạng thái xử lý chuyển *Đã lập chỉ mục tìm kiếm*.

**D5 Sửa, thêm, xóa văn bản.** Mở văn bản "Quyet dinh 123": xem trước PDF ngay trên trang, *SHA-256*, *Trích xuất nội dung* (đoạn chữ lấy từ tệp),
*Đã lưu kho an toàn* (nếu đã bật MinIO). Sửa *Số, ký hiệu* "123/QĐ-UBND", ngày, *Tác giả, cơ quan ban hành* (gõ "UB" → gợi ý từ từ điển C7) → *Lưu*.
Mở "Bao cao nam 2020" → mức mật *Mật* → *Lưu*. Ở trang hồ sơ → *Thêm văn bản* (không tệp) → lưu → mở → *Xóa*.
- *Mong đợi:* xem trước ảnh PNG cũng được; *Tải tệp gốc*, *Xử lý lại tệp* có sẵn.

**D6 In ấn.** Trang hồ sơ → *In*: phiếu mô tả hồ sơ và mục lục văn bản trong hồ sơ (hiển thị tên mẫu "Archival File Standard", "Archival File Contents", xem mục 5),
mở bản xem in hoặc *PDF*. Trang văn bản → *In phiếu*.

**D7 ★ Tìm kiếm cơ bản và nâng cao.** *Biên mục → Tìm kiếm*:
- **Hồ sơ**: gõ "lưu trữ" (cơ bản); *Nâng cao*: phông P-2024, khối, mục lục, mức mật, trạng thái, kho, *Bắt đầu từ ngày / đến ngày* → *Áp dụng*.
- **Văn bản**: gõ **"zebra"** → tìm thấy "Quyet dinh 123" (từ này chỉ có trong *nội dung* tệp, không có trong tiêu đề), từ khóa được làm nổi;
  *Nâng cao*: *Tác giả, cơ quan ban hành*, *Văn bản từ ngày / đến ngày*, *Loại tệp*, *Mức độ mật*.
- *Lưu bộ lọc* và mở lại; nhấn **Ctrl+K** ở bất kỳ đâu để tìm nhanh hồ sơ, văn bản, màn hình.

**D8 Quy tắc của cây.** Thử xóa ML-01 (còn hồ sơ) → bị từ chối. Sửa HS-001 chuyển sang mục lục khác rồi chuyển lại → văn bản đi theo (mở một văn bản xem phông, mục lục).

### Phần E – Độc giả (15 phút)

**E1 ★ Đăng ký.** W2 (khách): `/dang-ky` → nhập Nguyễn Văn An, email `an.docgia@example.com`, điện thoại, cơ quan → *Gửi đăng ký*.
- *Mong đợi:* thông báo chung, không tiết lộ email đã tồn tại hay chưa.

**E2 ★ Duyệt đăng ký, đăng nhập.** W1 (`phongdoc.demo`): *Độc giả → Đăng ký độc giả* (số đếm trên thanh bên) → *Mở* đơn của An → chọn *Nhóm độc giả* → *Duyệt*.
- *Mong đợi:* tạo hồ sơ độc giả, tài khoản và **liên kết đặt mật khẩu dùng một lần**. W2: mở liên kết, đặt mật khẩu → `/dang-nhap` → vào `/portal`.
  Thử mở `/dashboard` bằng tài khoản độc giả → bị chuyển về `/portal`.

**E3 Danh sách độc giả.** W1: *Độc giả → Danh sách độc giả*: tìm "An"; *Thêm mới* Trần Thị Bình tại quầy (không email) → *Lưu*; sửa số giấy tờ.
Khung *Truy cập trực tuyến* → *Tạo tài khoản và cấp liên kết* (cho độc giả muốn dùng trực tuyến). *In thẻ độc giả* / *PDF*. Tạo một độc giả thử rồi xóa.

**E4 ★ Độc giả tra cứu (nhóm mặc định).** W2 (An): `/portal` – *Tra cứu tài liệu*.
- Hồ sơ: *Tiêu đề hồ sơ* "lưu trữ"; *Tìm nâng cao*: *Phông*, *Số, ký hiệu hồ sơ*, *Thời gian bắt đầu từ… đến*.
- Văn bản: *Từ khóa* "zebra" (*tìm theo cả nội dung văn bản*); *Tìm nâng cao*: *Tác giả, cơ quan ban hành*, *Ngày văn bản*, *Loại tệp*; sắp xếp.
- Mở HS-001 (danh sách văn bản trong hồ sơ) → mở văn bản → *Bản xem trước*.
- *Mong đợi:* chỉ thấy phông P-2024 (công khai); **không** thấy văn bản *Mật* "Bao cao nam 2020" và không thấy HS-101 của P-2025.
  Dán thẳng địa chỉ của văn bản Mật (lấy từ W1) → báo như không tồn tại.

**E5 ★ Phân quyền độc giả theo nhóm quyền, nhóm chức năng.** W1 (`admin.demo`): *Độc giả → Nhóm độc giả*: mở "Độc giả mặc định" giới thiệu *Mức mật tối đa*,
6 chức năng (tìm kiếm, xem trước, tải tệp gốc, lập phiếu sử dụng, lập phiếu sao chụp, gửi góp ý), *Cách duyệt phiếu*, hạn mức riêng.
*Thêm mới* nhóm "Nghiên cứu viên" mức mật tối đa 2 → *Lưu*. Mở độc giả An → chuyển sang nhóm "Nghiên cứu viên" → *Lưu*.
- *Mong đợi:* W2 tìm lại → thấy văn bản *Mật*. (Có thể bỏ chức năng *tải tệp gốc* của nhóm để thấy nút tải biến mất.)

**E6 ★ Cấp phép khai thác phông.** W1 (`phongdoc.demo`): mở độc giả An → bảng *Phông được cấp phép riêng* → thêm P-2025, *Đến ngày* = 3 ngày sau → *Lưu*.
- *Mong đợi:* W2 thấy HS-101; trang *Tài khoản* của An ghi "Phông được khai thác" kèm hạn. W1: *Danh mục → Phông lưu trữ* → P-2025 → khung
  *Độc giả được khai thác* ghi cấp phép vừa tạo, người cấp, ngày cấp. Đặt P-2025 *Nội bộ* → W2 không còn thấy (dù vẫn còn cấp phép); đặt lại *Theo cấp phép*.

**E7 Mẫu phiếu, mẫu đăng ký.** *Độc giả → Mẫu phiếu, mẫu đăng ký*: mở "Mẫu mặc định — Phiếu yêu cầu sử dụng" → *Thêm dòng* ở *Mục đích*: "Nghiên cứu luận văn" → *Lưu*.
Giới thiệu mẫu *Phiếu sao chụp* và *Đăng ký độc giả* (trường thêm trên biểu mẫu đăng ký).
- *Mong đợi:* mục đích mới hiện trên phiếu của độc giả ở F1.

**E8 Tham số phục vụ độc giả.** *Độc giả → Thiết lập độc giả*: số phiếu mỗi ngày, số mục mỗi phiếu, số phiếu đang mở, số ngày giữ tài liệu, số lần và số ngày gia hạn,
nhắc trước hạn, chặn khi có tài liệu quá hạn, cho tự đăng ký, phải duyệt → *Lưu thiết lập*.

### Phần F – Phiếu yêu cầu sử dụng (15 phút)

**F1 ★ Độc giả lập và gửi phiếu.** W2 (An): ở kết quả tìm, *Thêm vào phiếu sử dụng* cho HS-001, văn bản "Bao cao nam 2020" (Mật) và HS-101 (P-2025).
Nút đổi thành *✓ Đã có trong phiếu sử dụng*: bấm lần nữa thì mở phiếu, không thêm trùng.
Mở phiếu (biểu tượng giỏ / *Phiếu sử dụng*): mỗi mục ghi số, phông, mức mật; dòng *Mỗi phiếu tối đa …* cho biết hạn mức trước khi gửi.
Chọn mục đích "Nghiên cứu luận văn" (E7, nút được đánh dấu), ghi chú: bản nháp **tự lưu** sau khoảng một giây ("Đã lưu tự động lúc …"), tải lại trang vẫn còn.
Bỏ một mục; bỏ mục cuối cùng thì hệ thống hỏi trước khi hủy bản nháp → *Gửi yêu cầu*.
Mở `/portal/phieu`: danh sách phiếu, lọc trạng thái, xem chi tiết.
- *Mong đợi:* phiếu nháp được giữ trên máy chủ (đổi máy vẫn còn); vượt hạn mức (E8) thì bị từ chối kèm lý do.

**F2 ★ Phòng đọc tiếp nhận, quyết định từng mục.** W1 (`phongdoc.demo`): *Khai thác tài liệu → Phiếu yêu cầu sử dụng* (số đếm trên thanh bên). Các tab:
*Chờ tiếp nhận, Chờ lãnh đạo duyệt, Đã duyệt, Đang sử dụng, Quá hạn, Đã đóng, Nháp, Tất cả*. Tìm theo số phiếu hoặc tên độc giả. Mở phiếu của An:
duyệt HS-001 và HS-101 (hoặc *Duyệt tất cả*), mục Mật để lãnh đạo → *Chuyển lãnh đạo* (quyết định từng dòng được lưu cùng lúc).
Dòng gợi ý dưới các nút giải thích vì sao không có *Duyệt*; dòng chưa quyết định ghi "sẽ được duyệt cùng phiếu".
- *Mong đợi:* phiếu có tài liệu mật thì phòng đọc **không** tự *Duyệt* được, chỉ *Chuyển lãnh đạo* (theo *Cách duyệt phiếu* của nhóm và cờ *Cần lãnh đạo duyệt* của mức mật).

**F3 ★ Lãnh đạo duyệt.** W3 (`lanhdao.demo`): tab *Chờ lãnh đạo duyệt* → mở phiếu → quyết định mục Mật (đồng ý hoặc từ chối kèm lý do) → *Lưu quyết định* → *Duyệt*.
Giới thiệu thêm *Trả lại phòng đọc*.

**F4 ★ Giao, gia hạn, nhận trả, in.** W1 (`phongdoc.demo`): tab *Đã duyệt* → mở phiếu → *Giao tài liệu*.
- *Mong đợi:* *Hạn trả* = ngày giao + số ngày giữ, nhưng **không vượt ngày hết hạn cấp phép P-2025** (3 ngày, E6).

Menu *In* → *In phiếu*, *In phiếu lấy tài liệu* (có vị trí kho của từng hồ sơ), mỗi mục có *PDF*. Tab *Đang sử dụng* → *Gia hạn*.
- *Mong đợi:* với phiếu này hệ thống **từ chối gia hạn** vì hạn trả đã chạm ngày hết cấp phép P-2025 ("Quyền khai thác phông của độc giả hết hạn ngày …").
  Đây là quy tắc, nên nói trước. Muốn minh họa gia hạn thành công, dùng phiếu chỉ có tài liệu P-2024 (phiếu của Trần Thị Bình ở F5 sau khi duyệt và giao).

*Nhận trả*: ghi tình trạng từng mục → *Xác nhận đã nhận trả* → phiếu *Đã trả*. Mở *Lịch sử xử lý* của phiếu: ai làm gì, lúc nào.

**F5 Cán bộ lập, sửa, xóa phiếu hộ độc giả.** W1: *Lập phiếu cho độc giả* → chọn Trần Thị Bình (hiện nhóm, phông được khai thác, lưu ý nếu có tài liệu quá hạn)
→ chọn mục đích gợi ý → *Thêm hồ sơ* / *Thêm văn bản* (mỗi dòng hiện tiêu đề, số, phông) → *Lưu nháp*.
Tab *Nháp* → mở → sửa ghi chú → xóa nháp. Lập lại → thử thêm HS-101 → dòng đó tô đỏ ngay "Không lập được: độc giả không được khai thác…" và nút gửi bị khóa (Bình chưa được cấp phép P-2025,
dù cán bộ xem được) → bỏ mục đó → *Gửi duyệt*.
- *Mong đợi:* mỗi mục được kiểm theo quyền của **độc giả của phiếu**, không theo quyền của cán bộ lập phiếu.

Tiếp tục với phiếu này: phiếu chỉ có tài liệu mức *Thường* nên phòng đọc tự *Duyệt* được (không qua lãnh đạo) → *Giao tài liệu* → *Gia hạn* → hạn trả được cộng thêm
số ngày gia hạn (E8).

**F6 (tùy chọn) Thu hồi cấp phép giữa chừng.** An gửi một phiếu có HS-101; phòng đọc xóa dòng cấp phép P-2025 của An rồi bấm duyệt → bị chặn, thông báo nêu mục nào hết quyền.

**F7 Quá hạn.** Giới thiệu tab *Quá hạn* và công việc hằng ngày: đánh dấu phiếu quá hạn, nhắc độc giả trước hạn; quá hạn là cờ, không phải trạng thái.
(Muốn thấy dữ liệu thật ở tab này cần phiếu đã quá hạn từ hôm trước, xem mục 5.)

**F8 Độc giả theo dõi.** W2: chuông thông báo có tin ở mỗi bước (tiếp nhận, duyệt, giao, trả); `/portal/phieu/<số phiếu>` thấy kết quả từng mục, hạn trả.
Độc giả *Hủy phiếu* được khi phiếu chưa ai quyết định.

### Phần G – Phiếu sao chụp (7 phút)

**G1 ★ Độc giả lập phiếu sao chụp.** W2 (An): *Thêm vào phiếu sao chụp* cho văn bản "Quyet dinh 123" → mở *Phiếu sao chụp*: *Số bản* 2, *Hình thức* *Bản số*,
*Trang* "1–2", mục đích → *Gửi yêu cầu*. Thử thêm văn bản *Mật* vào phiếu sao chụp → bị từ chối.
- *Mong đợi:* chỉ sao chụp được tài liệu của phông *Cho phép sao chụp* và mức mật *Cho phép sao chụp* (mặc định chỉ *Thường*).

**G2 ★ Duyệt và hoàn thành.** W1 (`phongdoc.demo`): *Khai thác tài liệu → Phiếu sao chụp* → mở → quyết định mục → *Lưu quyết định* → *Chuyển lãnh đạo*.
W3 (`lanhdao.demo`): *Duyệt*. W1: *Hoàn thành* → *In phiếu* / *PDF*. Thêm: *Lập phiếu cho độc giả* (phiếu sao chụp), sửa và xóa nháp, tìm phiếu.

### Phần H – Góp ý, thông báo, tài khoản độc giả (4 phút)

**H1 Tiếp nhận góp ý.** W2 (An): `/portal/gop-y` → *Gửi góp ý mới* (tiêu đề, nội dung). W1 (`phongdoc.demo`): *Khai thác tài liệu → Góp ý của độc giả* → mở →
*Phản hồi cho độc giả* → gửi. W2: thấy *Phản hồi của đơn vị* và thông báo trên chuông.

**H2 Tài khoản độc giả.** W2: `/portal/tai-khoan`: sửa thông tin liên hệ → *Lưu thông tin*; *Đổi mật khẩu*; xem *Quyền khai thác của bạn* (nhóm, chức năng) và
*Phông được khai thác* kèm hạn. `/portal/thong-bao`: toàn bộ thông báo, đánh dấu đã đọc.

### Phần I – Báo cáo, thống kê, tổng kiểm kê (10 phút)

**I1 ★ Báo cáo kho tài liệu.** W1 (`admin.demo`): *Thống kê, báo cáo → Báo cáo, thống kê*. Lần lượt:
*Báo cáo phông lưu trữ*, *Báo cáo mục lục tài liệu*, *Báo cáo hồ sơ lưu trữ*, *Báo cáo văn bản, tài liệu* (lọc theo phông),
*Thống kê hồ sơ, tài liệu theo phông* (có biểu đồ), *Thống kê theo loại hình tài liệu, kho lưu trữ*.
Với một báo cáo: *Bộ lọc* → *CSV*, *Excel*, *In* (có đầu đề đơn vị và chữ ký), *PDF*.
- *Mong đợi:* số liệu khớp với dữ liệu vừa nhập ở phần D.

**I2 Báo cáo độc giả.** *Báo cáo độc giả*, *Thống kê phiếu yêu cầu của độc giả*, *Phiếu đang sử dụng và quá hạn*, *Hồ sơ, văn bản được khai thác nhiều* → *In*.

**I3 ★ Tổng kiểm kê phông.** W1 (`bienmuc.demo`): *Thống kê, báo cáo → Tổng kiểm kê phông → Thêm mới* (tên kỳ, ngày) → *Lưu* → *Lập danh sách phông*
(lấy số liệu hệ thống từng phông) → nhập số đếm thực tế → xem chênh lệch → *Hoàn thành kiểm kê* → *In biên bản* / *Xem báo cáo*.
- *Mong đợi:* kỳ đã hoàn thành bị khóa số liệu; chỉ quản trị viên *Mở lại* được (đăng nhập `admin.demo` để minh họa).

### Phần K – Xuất, nhập dữ liệu XML (8 phút, `admin.demo`)

**K1 ★ Tìm kiếm và kết xuất XML.** *Trao đổi dữ liệu → Xuất, nhập XML* → phần xuất:
*1. Chọn dữ liệu cần xuất* (cấp *Hồ sơ*, phông P-2024, khoảng năm) → *2. Kết quả tìm kiếm* (số bản ghi sẽ xuất) →
*3. Chọn các trường đưa vào tệp* (bỏ vài trường) → xuất → tải tệp XML ở *Lịch sử xuất, nhập XML*. *Tải lược đồ XSD*.
- *Mong đợi:* tệp là cây Phông › Khối › Mục lục › Hồ sơ (cấp trên chỉ mang trường khóa), chạy nền có tiến độ.

**K2 ★ Nhập XML, chọn trường đưa vào cơ sở dữ liệu.** Mở tệp vừa xuất, sửa tiêu đề một hồ sơ và thêm một hồ sơ mới (hoặc dùng tệp mẫu chuẩn bị sẵn).
Phần nhập: *1. Chọn tệp XML* → *2. Nội dung tệp* (số bản ghi, cấp, nguồn, phiên bản lược đồ) → *3. Cách nhập*: bật *Chạy thử*, tùy chọn *Tạo danh mục còn thiếu*
→ *4. Chọn các trường đưa vào cơ sở dữ liệu* → *Nhập dữ liệu*. Xem kết quả từng dòng, rồi chạy lại không chọn *Chạy thử*.
- *Mong đợi:* chạy thử không ghi gì; nhập thật cập nhật hồ sơ đã có, thêm hồ sơ mới; **nhập lại cùng tệp không tạo bản ghi trùng**.
  Tệp có khai báo `DOCTYPE`/`ENTITY` hoặc sai lược đồ bị từ chối kèm số dòng. *Xóa lượt này* trong lịch sử.

### Phần L – Bảo quản (12 phút, `baoquan.demo`)

**L1 ★ Sao lưu.** *Bảo quản → Sao lưu → Sao lưu mới*: *Sao lưu gì* = *Cả hai* (cơ sở dữ liệu và tệp), *Ghi chú* → *Bắt đầu*. Theo dõi tiến độ. Mở đợt:
*Kiểm tra bản sao lưu*, *Tải về*, *Tải bảng kê (manifest)*, SHA-256. Chạy *Sao lưu mới* lần hai → chỉ chép tệp mới.
Giới thiệu *Dừng* / *Chạy tiếp*, *Xóa* đợt, *Dọn bản cũ* (theo thời hạn giữ, không xuống dưới số bản tối thiểu), *Sao lưu theo lịch* (A2).
- *Mong đợi:* đợt kết thúc *Thành công*; đáp ứng cả "sao lưu cơ sở dữ liệu phần mềm" của phân hệ Quản trị.

**L2 ★ Kiểm tra cơ sở dữ liệu.** *Bảo quản → Kiểm tra toàn vẹn → Kiểm tra mới*: *Loại kiểm tra* = *Cơ sở dữ liệu* (rồi *Siêu dữ liệu*) → *Bắt đầu*.
- *Mong đợi:* danh sách phát hiện theo mức (Lỗi, Cảnh báo), lọc theo mức, trạng thái xử lý; với lỗi bộ đếm có nút *Sửa bộ đếm*.

**L3 ★ Kiểm tra từng tài liệu, chuyển sang khôi phục.** Người hỗ trợ làm hỏng có chủ đích một tệp trên máy chủ (đã có trong bản sao lưu L1):

```bash
$C exec backend bash -c 'ls sites/<site>/private/files | grep -i quyet'            # tìm đúng tên tệp
$C exec backend bash -c 'echo hong >> "sites/<site>/private/files/<tên tệp>"'      # thay đổi nội dung → sai SHA-256
```

*Kiểm tra mới* → *Tệp tài liệu* → *Bắt đầu*.
- *Mong đợi:* phát hiện tệp có mã băm không khớp, cột *Phục hồi được*; nút **Chuyển sang khôi phục (1 tài liệu có thể phục hồi)**.

**L4 ★ Khôi phục tài liệu theo đợt.** Bấm *Chuyển sang khôi phục* → đợt khôi phục được tạo và chạy → tệp gốc trở về; *Kiểm tra mới* (*Tệp tài liệu*) lần nữa → sạch.
Giới thiệu *Khôi phục → Khôi phục tài liệu* (nhập mã các văn bản cần khôi phục, mỗi dòng một mã).

**L5 Khôi phục cơ sở dữ liệu.** *Bảo quản → Khôi phục* (hoặc mở một đợt sao lưu có bản CSDL) → *Khôi phục từ bản này…*.
- *Mong đợi:* hệ thống hiện **hướng dẫn và lệnh đã kiểm tra**, không tự chạy. Chỉ khi máy chủ bật `dm_allow_db_restore` mới có ô *Gõ tên site* để cho phép tự khôi phục.
  Giải thích lý do: khôi phục CSDL ghi đè toàn bộ dữ liệu, cần người có thẩm quyền trên máy chủ.

### Phần M – Phân quyền cán bộ, nhật ký, giám sát (10 phút)

**M1 ★ Nhóm quyền sửa được.** W1 (`admin.demo`): *Quản trị → Phân quyền* → nhóm *Biên mục viên*: ma trận *loại dữ liệu × thao tác* (Xem, Thêm, Sửa, Xóa, Duyệt, In, Xuất,
Chỉ của mình, Trường nhạy cảm) và danh sách chức năng. Bỏ ô *Xóa* ở *Hồ sơ lưu trữ* → *Lưu thay đổi* (hộp xác nhận tóm tắt thay đổi).
W3: đăng nhập `bienmuc.demo`, mở HS-001 → nút xóa đã mất. W1: *Khôi phục mặc định*. *Thêm nhóm quyền* "Biên mục phông 2025", *Bắt đầu từ quyền của nhóm* Biên mục viên.
- *Mong đợi:* thay đổi có hiệu lực ngay; nhóm *Quản trị viên* luôn đủ quyền và không sửa được; nhóm có sẵn không xóa được.

**M2 Phạm vi phông của cán bộ.** *Quản trị → Người dùng* → `bienmuc.demo` → *Phạm vi truy cập*: *Phông được xem* = Tất cả phông, *Phông được sửa* = chỉ P-2025 → *Lưu*.
Khung *Quyền thực tế* ghi kết quả. W3 (bienmuc): HS-001 (P-2024) chỉ đọc; HS-101 (P-2025) sửa được. Đặt lại như cũ.

**M3 Khóa theo trạng thái.** W1: đặt HS-001 trạng thái *Đã đóng*. W3 (bienmuc): HS-001 có dải "Hồ sơ đã đóng", không sửa, không thêm văn bản được. W1 đặt lại *Đã hoàn thành*.

**M4 ★ Nhật ký hệ thống.** *Quản trị → Nhật ký hệ thống*: lọc *Loại thao tác*, *Người dùng*, *Từ ngày / Đến ngày*, *Tìm trong nội dung*; mở một dòng xem chi tiết;
*Tải CSV*. Chỉ ra các dòng của buổi demo: đăng nhập, tạo hồ sơ, xem/tải văn bản, sửa nhóm quyền, đổi phạm vi phông.
*Dọn dẹp*: chọn *Xóa các dòng trước ngày* → *Xem trước* (số dòng theo loại) → xác nhận bằng cách gõ lại số dòng.
- *Mong đợi:* không ai sửa hay xóa lẻ từng dòng; chỉ xóa được dòng cũ hơn 7 ngày; việc dọn cũng được ghi lại.

**M5 Giám sát hệ thống.** *Quản trị → Giám sát hệ thống*: dịch vụ (cơ sở dữ liệu, Redis, Meilisearch, MinIO), chỉ mục tìm kiếm, công việc nền,
dung lượng lưu trữ, sao lưu và kiểm tra gần nhất, người dùng và nhật ký → *Làm mới*.

**Kết thúc (2 phút).** Quay lại *Tổng quan*: số liệu đã thay đổi theo buổi demo. Tóm tắt 8 phân hệ, mời đặt câu hỏi.

---

## 3. Bản rút gọn 30 phút

Điều kiện: dữ liệu ở 0.5 và tài khoản ở 0.4 đã dựng sẵn; các tệp đã tải lên và lập chỉ mục.

| # | Bước | Nội dung chính | Phút |
|---|---|---|---|
| 1 | A1, B1 | Hai giao diện, trang công khai | 2 |
| 2 | A4 | Thêm người dùng, liên kết một lần | 2 |
| 3 | C2 | Phông và chế độ khai thác | 1 |
| 4 | D1–D3 | Cây biên mục: thêm khối, mục lục, hồ sơ | 3 |
| 5 | D4, D7 | Tải nhiều tệp; tìm "zebra" theo nội dung, tìm nâng cao | 3 |
| 6 | E1, E2, E4 | Độc giả đăng ký, được duyệt, tra cứu: không thấy tài liệu mật | 3 |
| 7 | E5, E6 | Nâng nhóm độc giả, cấp phép phông: thấy thêm | 2 |
| 8 | F1–F4 | Phiếu sử dụng: gửi, duyệt từng mục, lãnh đạo duyệt, giao, trả, in | 5 |
| 9 | G1 | Phiếu sao chụp, quy tắc sao chụp tài liệu mật | 1 |
| 10 | I1, I3 | Báo cáo (In, Excel), tổng kiểm kê | 2 |
| 11 | K1 | Xuất XML có chọn trường | 1 |
| 12 | L1, L3, L4 | Sao lưu, phát hiện tệp hỏng, khôi phục | 3 |
| 13 | M1, M4 | Sửa nhóm quyền có hiệu lực ngay; nhật ký | 2 |

---

## 4. Đối chiếu Phụ lục 03 → bước demo

| Phân hệ | Tính năng | Bước |
|---|---|---|
| **1. Khai thác trực tuyến** | Giao diện khai thác trực tuyến cho độc giả và người dùng được cấp quyền | A1, B1, E4 |
| | Giới thiệu đơn vị, lãnh đạo, cơ cấu tổ chức, liên hệ | A3, B1 |
| | Tìm kiếm hồ sơ lưu trữ cơ bản và nâng cao | E4 |
| | Tìm kiếm văn bản, tài liệu cơ bản và nâng cao | E4 |
| | Đăng ký, đăng nhập của độc giả | E1, E2 |
| | Quản lý danh mục, chi tiết phiếu yêu cầu sử dụng của độc giả | F1, F8 |
| | Đưa hồ sơ, văn bản vào phiếu yêu cầu sử dụng | F1 |
| | Gửi phiếu yêu cầu sử dụng cho phòng đọc | F1 |
| | Quản lý danh mục, chi tiết phiếu sao chụp | G1 |
| | Đưa hồ sơ, văn bản vào phiếu sao chụp | G1 |
| | Gửi phiếu sao chụp cho phòng đọc | G1 |
| | Tiếp nhận góp ý của độc giả | H1 |
| **2. Biên mục** | Nghiệp vụ biên mục, cập nhật, quản lý thông tin tài liệu | D1–D8 |
| | Thêm mới, sửa, xóa khối tài liệu | D1 |
| | Thêm mới, sửa, xóa mục lục tài liệu | D2 |
| | Thêm mới, sửa, xóa hồ sơ lưu trữ | D3 |
| | Tìm kiếm cơ bản, nâng cao hồ sơ lưu trữ | D7 |
| | Thêm mới, sửa, xóa văn bản trong hồ sơ | D4, D5 |
| | In ấn, tìm kiếm cơ bản và nâng cao tài liệu | D6, D7 |
| **3. Danh mục** | Hệ thống danh mục dùng chung | C1–C8 |
| | Cơ quan lưu trữ | C1 |
| | Phông lưu trữ | C2 |
| | Loại hình tài liệu | C3 |
| | Nhóm tài liệu | C3 |
| | Kho lưu trữ | C4 |
| | Tính chất tài liệu: giá, hộp, hồ sơ, mức độ mật | C4, C5, D3 |
| | Khung phân loại hồ sơ | C6 |
| | Từ điển nhập nhanh | C7, D5 |
| | Từ điển đơn cấp và đa cấp | C7 |
| **4. Thống kê, báo cáo** | Báo cáo phông lưu trữ | I1 |
| | Báo cáo mục lục tài liệu | I1 |
| | Báo cáo hồ sơ lưu trữ | I1 |
| | Báo cáo văn bản, tài liệu | I1 |
| | Thống kê hồ sơ, tài liệu theo phông | I1 |
| | Thống kê theo loại hình tài liệu, kho lưu trữ | I1 |
| | Tổng kiểm kê phông | I3 |
| **5. Xuất, nhập dữ liệu** | Tìm kiếm và kết xuất dữ liệu ra XML | K1 |
| | Nhập dữ liệu từ XML | K2 |
| | Lựa chọn các trường dữ liệu đưa vào cơ sở dữ liệu | K1 (bước 3), K2 (bước 4) |
| **6. Quản lý độc giả** | Danh sách độc giả: thêm, sửa, xóa, tìm kiếm | E3 |
| | Phân quyền độc giả theo nhóm quyền, nhóm chức năng | E5, E6 |
| | Quản lý phiếu yêu cầu sử dụng | F2–F4 |
| | Thêm mới, sửa, xóa, tìm kiếm phiếu yêu cầu sử dụng | F2 (tìm), F5 |
| | Đưa hồ sơ, văn bản vào phiếu yêu cầu sử dụng | F1, F5 |
| | Lãnh đạo duyệt hồ sơ, văn bản trong phiếu yêu cầu sử dụng | F3 |
| | Trả hồ sơ, tài liệu cho người dùng sau khi được phê duyệt | F4 |
| | Quản lý phiếu sao chụp | G2 |
| | Thêm mới, sửa, xóa, tìm kiếm phiếu sao chụp | G2 |
| | Đưa hồ sơ, văn bản vào phiếu sao chụp | G1, G2 |
| | Lãnh đạo duyệt hồ sơ, văn bản trong phiếu sao chụp | G2 |
| | Báo cáo, thống kê, in ấn thông tin độc giả và phiếu | E3 (thẻ), F4 (phiếu), G2, I2 |
| | Cấu hình mẫu phiếu yêu cầu, mẫu đăng ký | E7 |
| | Cấu hình tham số phục vụ độc giả khai thác | E8 |
| **7. Bảo quản** | Sao lưu cơ sở dữ liệu tài liệu lưu trữ | L1 |
| | Sao lưu tệp tài liệu | L1 |
| | Thêm mới, sửa, xóa đợt sao lưu | L1 |
| | Kiểm tra cơ sở dữ liệu tài liệu lưu trữ | L2 |
| | Kiểm tra từng tài liệu để phát hiện lỗi, dữ liệu không đáp ứng nghiệp vụ | L2 (*Siêu dữ liệu*), L3 |
| | Chuyển sang khôi phục khi phát hiện lỗi | L3 |
| | Khôi phục cơ sở dữ liệu | L5 |
| | Khôi phục tài liệu bị lỗi theo đợt | L4 |
| **8. Quản trị hệ thống** | Cấu hình tham số hệ thống | A2 |
| | Quản lý người sử dụng theo nhóm: thêm, sửa, xóa, tìm kiếm | A4, A5, A6 |
| | Phân quyền theo vai trò quản trị, tác nghiệp, nhóm quyền khác | A4, M1, M2, M3 |
| | Sao lưu, khôi phục cơ sở dữ liệu phần mềm | L1, L5 |
| | Quản lý nhật ký hệ thống | M4 |
| | Tìm kiếm và dọn dẹp nhật ký | M4 |
| | Đổi mật khẩu | A7, H2 |
| | Thông tin đơn vị: giới thiệu, cơ cấu tổ chức, liên hệ | A3 |
| *Bổ sung* | Thông báo trong ứng dụng, giám sát hệ thống, Ctrl+K, phạm vi phông, khóa theo trạng thái | F8, H2, M5, D7, M2, M3 |

---

## 5. Lưu ý, rủi ro và cách xử lý khi demo

| Tình huống | Cách xử lý |
|---|---|
| Menu *In* ở trang hồ sơ hiện tên mẫu tiếng Anh ("Archival File Standard", "Archival File Contents") | Giới thiệu là "phiếu mô tả hồ sơ" và "mục lục văn bản trong hồ sơ"; nội dung bản in bằng tiếng Việt |
| Không có nút in riêng cho một mục lục | Dùng *Báo cáo mục lục tài liệu* → *In* (I1); danh sách hồ sơ của một mục lục: *Báo cáo hồ sơ lưu trữ* lọc theo mục lục → *In* |
| Ảnh hoặc PDF bản quét không tìm được theo nội dung | Bản cài hiện chưa có OCR; demo tìm theo nội dung bằng PDF có chữ (`Quyet dinh 123…`, từ "zebra") |
| Tìm ngay sau khi tải tệp không ra | Chờ khoảng 15 giây đến khi trang hồ sơ ghi *Đã lập chỉ mục tìm kiếm*; nếu lâu: kiểm tra `queue-long` đang chạy |
| Tìm văn bản báo "mất quá nhiều thời gian" | Meilisearch không hoạt động nên hệ thống tìm bằng cơ sở dữ liệu; kiểm tra Giám sát, khởi động lại `meilisearch` |
| Giám sát ghi MinIO "Đã tắt; tệp lưu trên Frappe" | MinIO là tùy chọn: tệp vẫn lưu trên volume của Frappe và hệ thống chạy đủ; nói rõ bản lưu đối tượng chỉ có khi bật MinIO |
| Giám sát báo lỗi MinIO | Đã bật MinIO nhưng không kết nối được: kiểm tra dịch vụ `minio`, bucket và khóa `MINIO_APP_*` trong `.env` |
| *Duyệt* không hiện với phòng đọc | Phiếu có tài liệu cần lãnh đạo (đúng thiết kế): dùng *Chuyển lãnh đạo*; hoặc chưa *Lưu quyết định* cho các mục |
| Không có dữ liệu ở tab *Quá hạn* | Cờ quá hạn do công việc hằng ngày đặt; muốn có dữ liệu thì tạo phiếu giao từ trước buổi demo vài ngày, hoặc chỉ giới thiệu |
| Sao lưu theo lịch, nhắc hạn không chạy | Bộ lập lịch của site chưa bật: `bench --site <site> enable-scheduler` (0.1) |
| *Gia hạn* bị từ chối | Phiếu đã gia hạn tối đa số lần, hoặc hạn trả đã chạm ngày hết cấp phép phông (F4): đúng quy tắc; dùng phiếu khác để minh họa |
| *Dọn dẹp* nhật ký báo 0 dòng | Site mới chưa có dòng cũ hơn 7 ngày; giải thích quy tắc, chỉ demo bước *Xem trước* |
| Đăng ký độc giả bị từ chối vì quá nhiều lần | Giới hạn 10 lần/giờ mỗi IP; chạy `accounts.py up` để xóa bộ đếm, hoặc đổi mạng |
| Lãnh đạo và phòng đọc dùng chung cửa sổ, bị đăng xuất lẫn nhau | Dùng cửa sổ W3 riêng (trình duyệt hoặc hồ sơ trình duyệt khác) |
| L3 không phát hiện lỗi | Phải chạy *Sao lưu* (L1) **trước** khi làm hỏng tệp, và chọn đúng *Tệp tài liệu*; kiểm tra đã sửa đúng tệp |
| Thao tác không có hiệu lực ngay sau khi cập nhật mã | `bench --site <site> clear-cache`, khởi động lại worker, nhấn Ctrl+F5 |

Câu hỏi thường gặp nên chuẩn bị: dữ liệu mật được bảo vệ thế nào (phần E, M); sao lưu nằm ở đâu và có đưa ra ngoài máy chủ không
([SAO_LUU_KHOI_PHUC.md](SAO_LUU_KHOI_PHUC.md)); hiệu năng ở một triệu văn bản ([HIEU_NANG.md](HIEU_NANG.md)); triển khai
([TAI_LIEU_KY_THUAT.md](TAI_LIEU_KY_THUAT.md), mục 13).

---

## 6. Dọn dẹp sau demo

- Xóa dữ liệu demo nếu cần dùng lại site: phiếu, độc giả, hồ sơ, văn bản, danh mục đã tạo (xóa từ dưới lên: văn bản → hồ sơ → mục lục → khối → phông), các tài khoản `*.demo`.
  Cách nhanh nhất trên máy demo riêng: dựng lại site (`$C down -v` rồi `up -d`; **xóa toàn bộ dữ liệu**, xem [TAI_LIEU_KY_THUAT.md](TAI_LIEU_KY_THUAT.md) mục 13.7).
- Gỡ nội dung mẫu trang công khai: `scripts/demo/seed_organization.py down`.
- Trả lại các thiết lập đã đổi trong buổi demo (Thiết lập hệ thống, Thiết lập độc giả, chế độ phông, phạm vi phông của `bienmuc.demo`, nhóm quyền đã khôi phục mặc định).
- Xóa tệp mẫu tải về máy (XML đã xuất, PDF đã in) nếu chứa dữ liệu thật của đơn vị.

---

## 7. Checklist nghiệm thu phân quyền

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

## 8. Điểm cần xác nhận kỹ thuật trước khi nghiệm thu

1. MinIO: nếu bật (`auto` hoặc `manual`), Giám sát ghi "Kết nối thành công" và cổng 9000/9001 không công bố ra Internet; nếu không bật, nêu rõ tệp chỉ có bản trên volume của Frappe (xem [DEPLOYMENT.md](DEPLOYMENT.md)).
2. Có sẵn một PDF không mật và một PDF mật để chứng minh lọc quyền.
3. Không chạy khôi phục CSDL trên môi trường có dữ liệu quan trọng; luôn tạo bản sao lưu trước.
4. Chưa có đăng nhập OTP (2FA) trên trang `/dang-nhap`; tài khoản bật 2FA dùng `/login` của Frappe.
