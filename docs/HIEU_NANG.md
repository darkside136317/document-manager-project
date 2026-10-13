# Hiệu năng ở quy mô một triệu văn bản

Tài liệu này ghi lại cách đo, kết quả đo và những gì đã làm để ứng dụng dùng được khi kho có khoảng **một triệu văn bản**. Số đo lấy từ
`scripts/perf/volume_check.py`, chạy trên một site thử riêng (không phải site thật).

## 1. Cách đo

- Site thử `perfdm.localhost` (cơ sở dữ liệu riêng), tạo bằng `bench new-site … --install-app document_manager`; script từ chối chạy trên site có tên không bắt đầu bằng `perf`.
- Dữ liệu sinh bằng SQL (`seq_1_to_N` của MariaDB), thời điểm sửa (`modified`) rải ngẫu nhiên trong một năm và không liên quan tới cấp bậc, để các truy vấn sắp xếp theo `modified`
  không được "ưu ái":

  | Bảng | Số dòng | Dữ liệu | Chỉ mục |
  |---|---|---|---|
  | Archive Document | 1.000.000 | 448 MB | 422 MB |
  | Business Activity Log | 1.000.000 | 181 MB | 223 MB |
  | Archival File | 200.000 | 51 MB | 81 MB |
  | Usage Request | 100.000 | 15 MB | 27 MB |
  | Reader | 20.000 | 4 MB | 7 MB |

  (cùng 20 phông, 400 khối, 4.000 mục lục).
- Máy đo: máy phát triển (Docker Desktop trên Windows), MariaDB 11.8 với `innodb_buffer_pool_size = 1G` — **nhỏ hơn dữ liệu**, nên đây là kịch bản khắt khe;
  máy chủ thật nên có bộ nhớ đệm lớn hơn (xem mục 5).
- Mỗi phép đo chạy ba lần và lấy lần nhanh nhất ("best"). Truy vấn chậm hơn 300 ms được `EXPLAIN`.

Chạy lại:

```bash
# một lần: tạo site thử (xem đầu file scripts/perf/volume_check.py)
docker compose exec -T -w /home/frappe/frappe-bench/sites backend /home/frappe/frappe-bench/env/bin/python - seed    < scripts/perf/volume_check.py
docker compose exec -T -w /home/frappe/frappe-bench/sites backend /home/frappe/frappe-bench/env/bin/python - measure < scripts/perf/volume_check.py
# DM_PERF_SCALE=0.1 để thử nhanh với 100.000 văn bản; bước "reset" xóa dữ liệu đã gieo
```

## 2. Kết quả

Thời gian của một lời gọi API hoặc dịch vụ (đã gồm phân quyền của Frappe), ở một triệu văn bản.

### Dùng hằng ngày: dưới một giây

| Thao tác | Thời gian |
|---|---|
| Danh sách văn bản của một hồ sơ hoặc một mục lục | 6–12 ms |
| Danh sách hồ sơ của một mục lục | 3–5 ms |
| Cây biên mục: phông / khối / mục lục | 100 / 13 / 4 ms |
| Danh sách văn bản mới nhất, trang 1 (đếm 947.000 dòng) | ~380 ms |
| Danh sách văn bản, trang 5.000 (phân trang sâu) | ~950 ms |
| Hàng đợi phiếu, số đếm trên thanh bên | 60 ms |
| Thanh bên (boot) | 40 ms |
| Tìm hồ sơ theo tên, độc giả | 0,3–0,9 s |
| Độc giả tìm văn bản theo phông (có điều kiện quyền) | 0,3 s |
| Tổng quan (9 số đếm) | ~0,8 s |
| Nhật ký: trang mới nhất; lọc theo loại, 1 tháng | 0,2–0,3 s |
| Nhật ký: tìm chữ (cửa sổ 30 ngày) | ~0,35 s |
| Giám sát hệ thống | ~1 s |

### Báo cáo (theo yêu cầu, có thể vài giây)

| Báo cáo | Thời gian | Ghi chú |
|---|---|---|
| Hồ sơ, mục lục, độc giả, thống kê theo phông, thống kê phiếu, phiếu quá hạn | 0,3–1,2 s | |
| Văn bản, **một phông** | 1,2 s | cách dùng thông thường |
| Phông lưu trữ (đếm và cộng dung lượng toàn bộ văn bản) | 4–5 s | quét cả bảng văn bản |
| Văn bản, **không lọc** (sắp xếp 947.000 dòng theo tên phông) | 9 s | nên chọn phông hoặc năm |

### Kiểm tra toàn vẹn (công việc nền)

Hai mươi bảy phép kiểm tra cơ sở dữ liệu và siêu dữ liệu cộng lại khoảng **15 giây**; mỗi phép từ 1 ms đến 2 s. (Phần kiểm tra từng tệp chạy theo trang và tỉ lệ với số tệp.)

### Điều đã được sửa nhờ phép đo

| Vấn đề phát hiện | Trước | Sau | Cách sửa |
|---|---|---|---|
| Kiểm tra "số văn bản trùng trong một hồ sơ" | 27,4 s | 0,8 s | chỉ mục kép `(archival_file, document_number)` |
| Kiểm tra "số hồ sơ trùng trong một mục lục" | 8,4 s | 0,2 s | chỉ mục kép `(catalog, file_number)` |
| Tìm chữ trong nhật ký | 9,0 s | 0,35 s | không ghi ngày thì chỉ tìm 30 ngày gần nhất (màn hình nói rõ), đếm có trần |
| Đếm số hồ sơ/phông trên cây biên mục | 0,42 s | 0,1 s | không sắp xếp theo `modified` trong truy vấn gộp |
| Màn hình giám sát | 6 s | ~1 s | kết quả thăm dò Meilisearch/MongoDB được nhớ 20–60 giây; dung lượng thư mục tệp đo trong nền thay vì quét thư mục ngay trong lời gọi |
| MongoDB hỏng làm mỗi lời gọi chờ 5 giây | 5 s/lần | tức thì trong 30 giây sau lần lỗi | nhớ lần lỗi gần nhất |
| Ô tìm của danh sách văn bản/hồ sơ | quét cả cột liên kết | chỉ tiêu đề, số, tác giả | `search_fields` riêng cho các màn hình lớn |

## 3. Cái gì chậm theo bản chất, và đã được chặn thế nào

Tìm chuỗi con (`LIKE '%chữ%'`) không dùng được chỉ mục B-tree: với từ hiếm phải quét cả bảng (3–5 s ở một triệu văn bản).

- **Đường chính của tìm văn bản là Meilisearch**, không bị ảnh hưởng. Cơ sở dữ liệu chỉ phục vụ **dự phòng khi Meilisearch hỏng** và các điều kiện nâng cao theo
  tiêu đề, số, tác giả.
- Mọi truy vấn quét kiểu này chạy trong **trần thời gian 8 giây** (`max_statement_time` của MariaDB, `services/queries.bounded_scan`): quá hạn thì người dùng nhận
  thông báo "Tìm kiếm mất quá nhiều thời gian. Hãy nhập từ khóa cụ thể hơn hoặc thu hẹp theo phông, hồ sơ, năm", và máy chủ không bị một vài truy vấn như vậy chiếm hết kết nối.
- **Tổng số kết quả có trần 10.000** (hiện "10.000+"), và một trang chưa đầy thì chính nó là tổng (không đếm lần hai).
- Trong nhật ký, tìm chữ không ghi ngày chỉ nhìn 30 ngày gần nhất; muốn tìm xa hơn, chọn "Từ ngày".

Trong số đo cuối, các dòng sau vẫn dài hơn một giây: tìm văn bản theo chữ bằng cơ sở dữ liệu với từ hiếm (4–8 s hoặc bị cắt ở 8 s), tìm nâng cao theo tác giả và khoảng ngày (1,2–1,7 s),
báo cáo phông (4 s) và báo cáo văn bản không lọc (9 s), xem trước dọn nhật ký (3 s, gom theo loại trên cả bảng).

## 4. Những gì chưa làm (có chủ đích)

- **FULLTEXT trên cơ sở dữ liệu** để thay đường dự phòng: chỉ mục toàn văn InnoDB chỉ thấy dữ liệu đã commit, ngữ nghĩa theo từ chứ không theo chuỗi con, và chỉ đáng làm nếu
  đường dự phòng trở thành đường chính.
- **Chỉ mục phủ cho báo cáo phông** (`fonds`, `file_size_kb`): có thể giảm đáng kể 4 s của báo cáo này (chưa đo), đổi lại tốn dung lượng và chậm ghi; chưa cần khi báo cáo chạy theo yêu cầu.
- **Bộ nhớ đệm cho số đếm tổng quan**: 0,8 s ở một triệu văn bản, chấp nhận được.

## 5. Khuyến nghị vận hành khi kho lớn

- `innodb_buffer_pool_size` bằng 50–70% RAM của máy chạy MariaDB (ví dụ 4–5 GB trên máy 8 GB); tệp `docker/mariadb/my_custom.cnf` mặc định đặt 1 GB cho máy phát triển.
  Dữ liệu cùng chỉ mục của văn bản và hồ sơ trong kho thử là khoảng 1 GB, của nhật ký khoảng 0,4 GB.
- Giữ `slow_query_log` bật (đã bật, ngưỡng 2 giây) và xem định kỳ.
- Dọn nhật ký theo thời hạn giữ (Thiết lập hệ thống → Giữ log) để bảng nhật ký không lớn vô hạn.
- Meilisearch cần RAM riêng (`MEILI_MAX_INDEXING_MEMORY`); lập chỉ mục lại toàn bộ một triệu văn bản là việc nền dài.
- Sau khi nâng cấp lên bản có chỉ mục kép, chạy `bench migrate` ngoài giờ cao điểm.
