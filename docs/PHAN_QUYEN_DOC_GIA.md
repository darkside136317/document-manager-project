# Phân quyền: độc giả và cán bộ

Nguồn quy tắc duy nhất: `document_manager/policy.py` (`get_access`, `get_reader_scope`, `reader_scope_of`). Danh sách, kiểm tra
từng bản ghi, tìm kiếm (cơ sở dữ liệu và Meilisearch), báo cáo, xem/tải tệp và phiếu đều dùng cùng một kết quả.

## 1. Độc giả

### Phông nào độc giả được khai thác

Mỗi phông có một **chế độ khai thác** (màn hình Phông lưu trữ):

| Chế độ | Ai khai thác được |
|---|---|
| **Công khai** | Mọi độc giả đã được duyệt |
| **Theo cấp phép** (mặc định cho phông mới) | Chỉ độc giả hoặc nhóm độc giả được cấp phép phông đó |
| **Nội bộ** | Chỉ cán bộ; không mở cho độc giả, kể cả khi đã cấp phép |

Phông độc giả được dùng = các phông **công khai** ∪ phông **cấp cho nhóm** của họ ∪ phông **cấp riêng** cho họ, chỉ tính cấp phép còn
hiệu lực (trong khoảng *Từ ngày* – *Đến ngày*), không bao giờ gồm phông nội bộ. Khi một phông được cấp nhiều lần, cấp phép dài nhất có hiệu lực.

| Cấp ở đâu | Màn hình | Ghi chú |
|---|---|---|
| Cho cả nhóm | Độc giả → Nhóm độc giả → *Phông được cấp phép cho cả nhóm* | Mọi thành viên của nhóm |
| Cho một người | Độc giả → Danh sách độc giả → *Phông được cấp phép riêng* | Cộng thêm vào phông của nhóm |
| Xem ai được khai thác một phông | Danh mục → Phông lưu trữ → mở phông → *Độc giả được khai thác* | Chỉ xem |

Cấp hoặc thu hồi cần chức năng **"Cấp phép khai thác phông cho độc giả"** (mặc định: Quản trị viên, Cán bộ phòng đọc). Mỗi dòng ghi người cấp
và ngày cấp. Độc giả được nhắc trong ứng dụng 7 ngày trước khi một cấp phép riêng hết hạn. Trang *Tài khoản* của độc giả liệt kê các phông
họ đang được khai thác và hạn của từng phông.

### Mức mật và chức năng

Quyền của độc giả còn gồm **mức mật tối đa** và **các chức năng** của nhóm (tìm kiếm, xem trước, tải tệp gốc, lập phiếu sử dụng, lập phiếu
sao chụp, gửi góp ý). Mức mật riêng của độc giả (`0` = theo nhóm) do quản trị viên đặt. Độc giả không có hồ sơ đang hoạt động, hoặc thuộc
nhóm bị khóa, không đọc được gì.

### Độc giả không bao giờ thấy

- Hồ sơ **Nháp** hoặc **Đã tiêu hủy** và văn bản bên trong.
- Tài liệu có mức mật cao hơn mức của họ, hoặc không có mức mật.
- Tài liệu của phông chưa được cấp phép hoặc phông nội bộ.
- Nội dung trích xuất (`content_text`): tìm kiếm chỉ trả đoạn trích ngắn.

### Luật của phiếu sử dụng và phiếu sao chụp

1. Mỗi mục trong phiếu được kiểm theo **quyền của độc giả của phiếu**, tính từ hồ sơ độc giả, bất kể ai lập phiếu (kể cả cán bộ lập hộ cho
   độc giả không có tài khoản, và cán bộ có hồ sơ độc giả tự lập phiếu cho mình).
2. Quyền được kiểm lại khi **duyệt** và khi **giao tài liệu**: cấp phép đã hết hạn hoặc bị thu hồi thì không duyệt, không giao được; thông báo
   nêu rõ mục nào.
3. **Hạn trả** không vượt quá ngày hết hạn của cấp phép phông; gia hạn dừng ở ngày đó.
4. **Phiếu sao chụp** chỉ nhận tài liệu của phông *Cho phép sao chụp* và ở mức mật *Cho phép sao chụp* (mặc định: chỉ mức "Thường").
   Mỗi mục ghi số bản, hình thức (bản giấy, bản số) và trang cần sao.

## 2. Cán bộ

| Lớp | Quyết định gì | Ở đâu |
|---|---|---|
| **Nhóm quyền** | Được làm gì với từng loại dữ liệu (xem, thêm, sửa, xóa, duyệt, in, xuất, chỉ bản ghi của mình, trường nhạy cảm) và dùng chức năng nào | Quản trị → Phân quyền |
| **Phạm vi phông** | Được xem phông nào, được sửa phông nào, mức mật cao nhất được xem | Quản trị → Người dùng → *Phạm vi truy cập*; hoặc Nhóm cán bộ (cộng dồn) |
| **Khóa theo trạng thái** | Hồ sơ hoặc phông *Đã đóng*, hồ sơ *Đã tiêu hủy*: chỉ người có chức năng "Sửa hồ sơ, phông đã hoàn thành hoặc đã đóng" mới sửa, thêm, xóa được | Tự động |

- **Quản trị viên** (nhóm Quản trị viên, System Manager) luôn có mọi quyền, mọi chức năng, mọi phông; nhóm này không sửa được.
- Cán bộ không có phạm vi riêng và không thuộc nhóm cán bộ nào cấp phạm vi: xem và sửa được mọi phông, như trước. Thuộc nhóm cán bộ có
  phạm vi: khai thác các phông của nhóm; có thêm phạm vi riêng thì hai phạm vi cộng dồn.
- Chuyển hồ sơ, mục lục, khối sang phông khác cần quyền sửa **cả hai** phông.
- Sao lưu cơ sở dữ liệu, tải bản sao lưu, dọn bản cũ, khôi phục cơ sở dữ liệu và kiểm tra toàn bộ kho chứa dữ liệu của mọi phông: chỉ cán bộ được
  xem tất cả các phông mới dùng được.
- Trường nhạy cảm (mức độ mật của hồ sơ và văn bản, tình trạng và thời hạn bảo quản): theo cột "Trường nhạy cảm" của nhóm quyền
  (mặc định: Quản trị viên và Biên mục viên).

## 3. Nhật ký

Mọi thay đổi trên các DocType nghiệp vụ, đổi nhóm quyền, đổi phạm vi của người dùng, đăng nhập, đăng xuất, xem và tải tài liệu được ghi vào
**Business Activity Log** (nếu bật). Không vai trò nào được sửa hay xóa lẻ dòng nhật ký; dọn nhật ký chỉ qua chức năng có kiểm soát.
