# Tùy biến giao diện Document Manager

Có hai giao diện, dùng chung **một bộ token nhận diện**:

| Giao diện | Công nghệ | Nơi định nghĩa kiểu |
|---|---|---|
| Cán bộ (`/dashboard`) | Vue 3 + Tailwind (`apps/document_manager/frontend`) | `frontend/src/styles/app.css` (thành phần và chế độ tối), màu lấy từ token qua `frontend/tailwind.config.js` |
| Độc giả (`/portal`, trang công khai) | Jinja + Alpine | `public/css/dm-reader.css` (thành phần), khung ở `templates/reader/base.html` |

Token nằm ở `apps/document_manager/document_manager/public/css/theme-tokens.css`; cả hai giao diện nạp tệp này, và Tailwind đọc màu từ các biến `--dm-*`.
Ứng dụng **không** chèn kiểu hay script nào vào các trang của Frappe (`/login`, Desk).

## Đổi nhận diện nhanh

Chỉ sửa các biến trong `theme-tokens.css`, ưu tiên:

```css
--dm-primary        --dm-primary-hover   --dm-primary-soft
--dm-accent         --dm-brand-navy      --dm-brand-gradient
--dm-radius-md      (xem tệp để biết các biến chữ và khoảng cách)
```

Cả hai giao diện có chế độ **tối**: bảng màu tối được khai báo lại dưới `html[data-theme="dark"]` (cán bộ: `frontend/src/styles/app.css`; độc giả: `public/css/dm-reader.css`).
Độc giả theo cài đặt hệ thống (`prefers-color-scheme`) cho đến khi họ bấm nút đổi giao diện, lựa chọn được nhớ trong trình duyệt. Đổi màu chủ đạo thì kiểm tra cả hai chế độ.

Nguyên tắc: không đặt màu cố định trong trang hoặc thành phần mới; dùng biến `--dm-*` (hoặc lớp Tailwind đã ánh xạ tới biến), để khi có bản thiết kế mới chỉ cần thay token,
không phải sửa logic tìm kiếm, xem trước hay API.

## Áp dụng thay đổi

- Môi trường phát triển: giao diện độc giả đổi ngay (tải lại bằng Ctrl+F5); giao diện cán bộ được `staff-ui` build lại sau vài giây.
- Sản xuất: build lại image (`docker compose … build backend`; tầng Node build giao diện cán bộ), `up -d`, rồi `bench --site <site> clear-cache`.

## Tên đơn vị, biểu trưng và nội dung công khai

Không nằm trong mã: nhập ở **Quản trị → Thông tin đơn vị** (tên, giới thiệu, lãnh đạo, giờ mở cửa, liên hệ) và **Cơ cấu tổ chức**; các trang `/gioi-thieu`, `/lanh-dao`, `/co-cau`, `/lien-he`
lấy từ đó. Đầu và cuối các bản in (phiếu, báo cáo) cấu hình ở **Độc giả → Mẫu phiếu, mẫu đăng ký** và theo thông tin đơn vị.
