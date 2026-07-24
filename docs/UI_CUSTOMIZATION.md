# Tùy biến giao diện Document Manager

Giao diện được chia thành hai lớp độc lập:

- `public/css/theme-tokens.css`: màu sắc, font, bo góc và độ đổ bóng.
- `public/css/document-manager-ui.css`: component dùng chung cho Desk, Workspace và Portal.

## Đổi nhận diện nhanh

Chỉ sửa các biến trong `theme-tokens.css`, ưu tiên:

```css
--dm-primary
--dm-primary-hover
--dm-accent
--dm-brand-navy
--dm-brand-gradient
--dm-font-sans
--dm-radius-md
```

Không đặt màu cố định trong page mới. Component phải sử dụng biến `--dm-*` để khi
khách hàng gửi Figma mới chỉ cần thay token, không sửa logic tìm kiếm, preview hoặc API.

Sau khi sửa theme, chạy build image và `bench --site <site> clear-cache`, sau đó tải lại
trình duyệt bằng `Ctrl + Shift + R`.
