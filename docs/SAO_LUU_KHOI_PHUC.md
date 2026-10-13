# Sao lưu, kiểm tra toàn vẹn và khôi phục

Dành cho cán bộ bảo quản và quản trị viên. Các màn hình nằm ở menu **Bảo quản** của ứng dụng cán bộ:
`/dashboard/bao-quan/sao-luu`, `/dashboard/bao-quan/kiem-tra`, `/dashboard/bao-quan/khoi-phuc`.
Quyền: Quản trị tài liệu và Cán bộ bảo quản.

## 1. Hệ thống giữ những gì, ở đâu

| Thứ cần giữ | Cách giữ | Nơi lưu (trong volume `sites`) |
|---|---|---|
| Cơ sở dữ liệu (siêu dữ liệu, phiếu, nhật ký, người dùng) | Bản kết xuất `.sql.gz` của `bench backup`, ghi lại dung lượng và mã SHA-256 | `sites/<site>/private/backups/` |
| Tệp tài liệu số | **Kho theo nội dung**: mỗi tệp là một đối tượng đặt tên theo SHA-256, một bảng kê (`manifests/<mã-đợt>.jsonl`) cho từng đợt | `sites/<site>/private/dm-backup-store/` |

Kho tệp lưu **một bản duy nhất cho mỗi nội dung**: đợt sau chỉ chép tệp mà kho chưa có (sao lưu tăng dần), nên sao lưu hằng ngày rẻ. Nếu một tệp nguồn đã
bị đổi hoặc hỏng (mã SHA-256 không khớp với siêu dữ liệu), hệ thống **không chép** nó vào kho và báo lỗi cho tài liệu đó, để bản tốt đã có không bị đè bằng bản xấu.

> Cả hai thư mục nằm cùng ổ với dữ liệu thật. Chúng chống được lỗi phần mềm và thao tác nhầm, **không chống được mất ổ đĩa hay máy chủ**. Hãy sao chép
> chúng ra ngoài máy chủ theo lịch (xem [DEPLOYMENT.md](DEPLOYMENT.md) mục 7).

## 2. Sao lưu

**Chạy tay:** Sao lưu → **Sao lưu mới**, chọn loại (*Cơ sở dữ liệu*, *Tệp tài liệu* hoặc *Cả hai*), có thể giới hạn theo phông. Đợt chạy nền; ngăn kéo chi tiết cho
tiến độ từng tệp. Có thể **Dừng** và **Chạy tiếp**: đợt tiếp tục từ chỗ dừng chứ không chép lại từ đầu.

**Tự động:** Quản trị → Thiết lập hệ thống: *Bật sao lưu tự động*, *Tần suất* (hằng ngày, tuần, tháng), *Sao lưu cả tệp tài liệu*. Bộ lập lịch kiểm tra mỗi ngày và chỉ bắt đầu
khi đã đến hạn và không có đợt nào đang chạy. Cần `scheduler` và `queue-long` đang chạy.

**Dọn bản cũ:** nút **Dọn bản cũ** xóa các đợt quá *Giữ backup (ngày)*, nhưng **luôn giữ** *Luôn giữ tối thiểu* đợt thành công mới nhất (mặc định 3), và chỉ xóa các tệp trong kho không
còn đợt nào tham chiếu.

**Tải về:** trong ngăn kéo của một đợt có bản kết xuất cơ sở dữ liệu, nút tải về trả tệp `.sql.gz` hoặc bảng kê; mỗi lần tải được ghi nhật ký.
Nên **Kiểm tra bản sao lưu** (đọc lại và so SHA-256) trước khi tin vào nó.

Một đợt có thể kết thúc là *Thành công*, *Một phần* (ví dụ cơ sở dữ liệu tốt nhưng vài tệp nguồn bị hỏng) hoặc *Lỗi*; đọc "Ghi chú" của đợt để biết tài liệu nào.

## 3. Kiểm tra toàn vẹn

Kiểm tra → **Kiểm tra mới**. Loại kiểm tra:

| Loại | Kiểm tra gì |
|---|---|
| Cơ sở dữ liệu | Liên kết mồ côi (khối không có phông, hồ sơ không có mục lục, văn bản không có hồ sơ…), cấp bậc sai, mức mật đã bị xóa khỏi danh mục, bộ đếm sai, ngày tháng sai, số trùng, văn bản có tệp mà chưa có mã kiểm, lỗi lập chỉ mục |
| Siêu dữ liệu | Thứ một kho lưu trữ điện tử cần mô tả: mã phông, số mục lục, số hồ sơ, thời gian, vị trí lưu trữ, số/ngày/tác giả văn bản, tệp số |
| Tệp tài liệu | Từng tệp: còn không, đúng mã SHA-256, đúng loại (so với nội dung thật), không rỗng, còn bản GridFS |
| Toàn bộ | Cả ba |

Kết quả là danh sách **phát hiện**, mỗi phát hiện có mức (Lỗi hoặc Cảnh báo), mã lỗi, tài liệu liên quan, và với lỗi tệp có cho biết **một bản sao lưu có khôi phục được không**.
Một phát hiện có thể **Bỏ qua** (và Mở lại). Với lỗi *Sai bộ đếm*, nút **Sửa bộ đếm** tính lại từ dữ liệu thật.

Kiểm tra tệp cho cả kho tính được bằng cách chạy theo trang, dừng và chạy tiếp được. Khi MongoDB không kết nối, phần GridFS bị bỏ qua và có một cảnh báo "Không kết nối MongoDB".

Có thể bật **Kiểm tra tự động** (hằng tuần).

## 4. Khôi phục tệp tài liệu

Cách thường dùng: mở một đợt kiểm tra có lỗi tệp → **Chuyển sang khôi phục (n tài liệu có thể phục hồi)**. Hệ thống tạo một **đợt khôi phục** gồm các tài liệu đó.
Cách khác: Khôi phục → **Khôi phục tài liệu**, dán tên các văn bản (mỗi dòng một tên) và có thể chọn đợt sao lưu nguồn; để trống thì lấy bản mới nhất có tệp của từng tài liệu.

Khi chạy, mỗi tài liệu được xử lý riêng:

- bản trong kho được đọc và so SHA-256 (một bản hỏng bị từ chối), ghi lại **đúng từng byte** lên máy chủ, rồi đọc lại và so một lần nữa; nếu tài liệu có bản GridFS đã mất thì tải lên lại;
- nếu bản ghi tệp của Frappe đã mất, nó được tạo lại;
- tài liệu không có trong bản sao lưu nào, hoặc bản sao lưu cũng hỏng, được báo **lỗi riêng**, không ảnh hưởng tài liệu khác và không ghi gì lên chúng;
- các phát hiện của tài liệu được đánh dấu *Đã khôi phục*.

Đợt khôi phục có tiến độ, dừng/chạy tiếp được, và kết thúc *Thành công*, *Một phần* hoặc *Lỗi*.

## 5. Khôi phục cơ sở dữ liệu

Khôi phục cơ sở dữ liệu **thay toàn bộ dữ liệu hiện tại** bằng bản sao lưu: mọi thứ nhập sau thời điểm sao lưu sẽ mất. Vì vậy hệ thống mặc định **không tự làm**.

Cách làm mặc định (hướng dẫn đã kiểm tra):

1. Sao lưu → mở một đợt có bản cơ sở dữ liệu → **Kiểm tra bản sao lưu** (đọc lại và so SHA-256).
2. **Khôi phục từ bản này…**: hệ thống tạo một đợt khôi phục ở trạng thái *Chưa chạy*, kiểm tra lại bản sao lưu và hiện các lệnh cần chạy trên máy chủ:

   ```bash
   bench --site <site> set-maintenance-mode on
   bench --site <site> --force restore <đường-dẫn-tệp-sql.gz> --db-root-password <mật-khẩu-root>
   bench --site <site> migrate
   bench --site <site> set-maintenance-mode off
   ```

3. Quản trị viên chạy các lệnh đó (trong container `backend`), đăng nhập, chạy một đợt **Kiểm tra toàn vẹn** và kiểm tra lại dữ liệu.

Tự chạy (tùy chọn, chỉ khi site đã cho phép): trong `site_config.json` đặt `"dm_allow_db_restore": 1` và mật khẩu root MariaDB (`"dm_db_root_password"`, hoặc biến môi trường
`DB_ROOT_PASSWORD` của container). Khi đó, ở đợt khôi phục chuẩn bị sẵn bấm **Chạy khôi phục** và **gõ lại đúng tên site** để xác nhận. Hệ thống bật chế độ bảo trì,
chạy `restore` rồi `migrate`, và **luôn tắt chế độ bảo trì khi xong hoặc khi lỗi**. Một bản kết xuất hỏng kết thúc ở *Lỗi* mà không chạy gì.

Nên tập khôi phục ít nhất một lần trên bản sao của môi trường, trước khi cần đến nó.

## 6. Việc hằng ngày nên làm

| Tần suất | Việc |
|---|---|
| Hằng ngày | Màn hình **Giám sát hệ thống**: "Sao lưu gần nhất" xanh, không có đợt lỗi |
| Hằng tuần | Xem kết quả **Kiểm tra tự động**; xử lý hoặc bỏ qua các phát hiện mới |
| Hằng tháng | **Kiểm tra bản sao lưu** của đợt mới nhất; sao chép `private/backups` và `private/dm-backup-store` ra ngoài máy chủ; kiểm tra dung lượng đĩa |
| Hằng quý | Tập khôi phục trên môi trường thử |

## 7. Khi có sự cố

| Tình huống | Làm gì |
|---|---|
| Đợt sao lưu treo ở "Đang chạy" | Sau 6 giờ không có tiến triển, hệ thống coi là treo và cho phép xóa hoặc chạy lại; kiểm tra `queue-long` |
| "Tệp nguồn đã thay đổi (không khớp mã kiểm)" | Tệp trên đĩa khác với mã đã ghi; **không** bị chép vào kho. Tìm nguyên nhân (ổ đĩa, sửa tay) rồi khôi phục tệp đó từ đợt cũ tốt |
| "Không kết nối MongoDB" | Kiểm tra danh sách IP của Atlas và `MONGODB_ATLAS_URI`; phần còn lại của kiểm tra vẫn chạy |
| Cần lấy lại một tài liệu bị xóa nhầm | Khôi phục tệp chỉ gắn lại **tệp** của tài liệu còn tồn tại; bản ghi đã bị xóa phải nhập lại (xuất/nhập XML) hoặc khôi phục cơ sở dữ liệu |
