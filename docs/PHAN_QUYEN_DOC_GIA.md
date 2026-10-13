# Phân quyền khai thác của độc giả

Nguồn quy tắc duy nhất: `document_manager/policy.py` (`get_reader_scope`). Truy vấn danh sách, kiểm tra từng bản ghi, API tìm kiếm, bộ lọc Meilisearch, xem/tải tệp và phiếu đều dùng cùng một kết quả.

## Một độc giả được làm gì

Quyền của độc giả = **nhóm độc giả** của họ, cộng (nếu có) **mức mật riêng**.

| Thành phần | Ở đâu | Ý nghĩa |
|---|---|---|
| Nhóm độc giả | `Reader Group` (Desk: `/app/reader-group`) | Mức mật tối đa, phạm vi phông, các chức năng được dùng |
| Nhóm mặc định | Nhóm có `Nhóm mặc định` = 1 | Độc giả chưa có nhóm sẽ vào nhóm này (luôn có đúng một) |
| Mức mật riêng | `Reader.max_confidentiality_priority` | `0` = theo nhóm; số > 0 ghi đè mức mật của nhóm cho riêng người đó |

Chức năng của nhóm: tìm kiếm, xem trước, tải tệp gốc, lập phiếu yêu cầu sử dụng, lập phiếu sao chụp, gửi góp ý. Phạm vi phông: tất cả, hoặc chỉ các phông được liệt kê (áp dụng cho cả Phông, Khối, Mục lục, Hồ sơ, Văn bản).

Độc giả **không có hồ sơ đang hoạt động**, hoặc thuộc nhóm bị khóa, không đọc được gì (kể cả khi gọi thẳng `/api/resource/...`).

## Độc giả không bao giờ thấy

- Hồ sơ ở trạng thái **Nháp** hoặc tình trạng tiêu hủy **Đã tiêu hủy**, và các văn bản bên trong. Cán bộ cần đổi trạng thái hồ sơ sang *Đang xử lý* hoặc *Đã hoàn thành* để công bố.
- Tài liệu có mức mật cao hơn mức của họ, hoặc không có mức mật (xử lý theo hướng chặn).
- Nội dung trích xuất (`content_text`): kết quả tìm kiếm chỉ trả đoạn trích ngắn.

Đổi mức mật, vị trí (mục lục, khối, phông) của một hồ sơ sẽ cập nhật ngay các văn bản bên trong và đưa chúng vào hàng đợi lập lại chỉ mục.

## Ai được đổi quyền

- Tạo và sửa thông tin độc giả: Quản trị tài liệu, Cán bộ phòng đọc.
- Đổi **nhóm** và **mức mật riêng** (trường permlevel 1): chỉ Quản trị tài liệu. Cán bộ phòng đọc sửa các trường này sẽ bị bỏ qua.
- Tạo, sửa, xóa nhóm độc giả: Quản trị tài liệu, System Manager.
- Cán bộ phòng đọc vẫn lập phiếu hộ độc giả bất kể nhóm của độc giả đó có cho phép hay không.

## Nhật ký

Mọi thay đổi trên các DocType nghiệp vụ (tạo, sửa — kèm đổi trạng thái/mức mật/nhóm cũ → mới, xóa), đăng nhập, đăng xuất, xem và tải tài liệu được ghi vào **Business Activity Log** theo cấu hình `Bật Business Activity Log`. Nhật ký không ghi giá trị của các trường thông thường. Không vai trò nào được tạo, sửa hay xóa dòng nhật ký bằng quyền DocType; việc dọn nhật ký chạy theo lô qua tác vụ hằng ngày (giữ `Giữ log (ngày)` ngày).
