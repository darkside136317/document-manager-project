# Kịch bản demo chức năng và phân quyền

## 1. Mục đích và phạm vi

Kịch bản này dùng để demo và nghiệm thu ứng dụng **Document Manager** theo một luồng nghiệp vụ xuyên suốt: cán bộ chuẩn bị dữ liệu, biên mục tài liệu số, độc giả tra cứu/gửi yêu cầu, phòng đọc xử lý yêu cầu, cán bộ bảo quản vận hành sao lưu và quản trị viên giám sát hệ thống.

Thời lượng gợi ý: **45–60 phút**. Mọi thao tác thực hiện trên site Frappe đã cài ứng dụng `document_manager`.

> Lưu ý: đây là kịch bản theo chức năng hiện có trong mã nguồn. Các tác vụ nền (trích xuất nội dung, lập chỉ mục, sao lưu, kiểm tra toàn vẹn) cần worker/Redis và các kết nối MongoDB GridFS, Meilisearch được cấu hình hoạt động trước khi demo.

## 2. Tài khoản và dữ liệu chuẩn bị

Tạo các tài khoản thử nghiệm, mỗi tài khoản chỉ gán đúng một vai trò dưới đây (ngoài các role Frappe mặc định cần thiết):

| Mã tài khoản | Vai trò | Mục đích demo |
|---|---|---|
| `admin.demo` | Document Admin | Quản trị dữ liệu, cấu hình, xuất/nhập, báo cáo và toàn quyền nghiệp vụ |
| `cataloger.demo` | Cataloger | Tạo, cập nhật, xóa dữ liệu biên mục |
| `readingroom.demo` | Reading Room Officer | Quản lý độc giả và xử lý yêu cầu khai thác/sao chụp |
| `preservation.demo` | Preservation Officer | Sao lưu, kiểm tra toàn vẹn, lập đợt khôi phục |
| `reader.demo` | Reader | Tra cứu trên cổng và gửi yêu cầu |

Thiết lập dữ liệu mẫu trước buổi demo:

1. Cơ quan lưu trữ: `TTLT-DEMO` – Trung tâm Lưu trữ Demo.
2. Mức độ mật, theo thứ tự ưu tiên: `Thường` (1), `Hạn chế` (2), `Mật` (3).
3. Kho lưu trữ: `KHO-01`; Loại tài liệu: `Quyết định`; Nhóm tài liệu: `Hành chính`; một bảng phân loại và vài từ điển nhập nhanh.
4. Phông `P-2024` → Khối `HC` → Mục lục `ML-01` → Hồ sơ `HS-001 – Hồ sơ công tác năm 2024`.
5. Hai văn bản thuộc `HS-001`: `QD-001` ở mức `Thường` và `QD-MAT-001` ở mức `Mật`. Đính kèm ít nhất một PDF có thể trích xuất nội dung.
6. Tạo hồ sơ Reader liên kết với `reader.demo`, đặt `max_confidentiality_priority = 1` để chỉ đọc dữ liệu mức `Thường`.

## 3. Ma trận phân quyền thực tế

Ký hiệu: **C** tạo, **R** xem, **U** sửa, **D** xóa, **S** submit, **H** hủy/amend, **P** in, **X/I** xuất/nhập.

| Nhóm dữ liệu/chức năng | Document Admin | Cataloger | Reading Room Officer | Preservation Officer | Reader |
|---|---|---|---|---|---|
| Phông, khối, mục lục, hồ sơ, văn bản | CRUD; Admin có P/X/I ở các DocType chính | CRUD hồ sơ/văn bản/mục lục/khối; không xóa Phông | R | – | R, bị lọc theo độ mật |
| Cơ quan, bảng phân loại, nhóm/loại tài liệu, từ điển | CRUD; P/X/I | CRUD, trừ xóa ở một số danh mục | R ở danh mục được cấp | – | – |
| Mức độ mật | CRUD; P/X/I | R | R | – | – |
| Kho lưu trữ | CRUD; P/X/I | CRU, không xóa | R | R | – |
| Độc giả và thiết lập độc giả | CRUD; P/X/I | – | CRU, không xóa Reader | – | chỉ sửa hồ sơ Reader của mình; không tạo |
| Phiếu yêu cầu khai thác/sao chụp | CRUD, S/H/P/X | – | CRU, S/H/P | – | CRU, S; không hủy/amend/xóa |
| Phản hồi độc giả | CRUD | – | RU | – | CRU, không xóa |
| Sao lưu, kiểm tra toàn vẹn, khôi phục | CRUD | – | – | CRU, không xóa | – |
| Thiết lập hệ thống, thông tin tổ chức, nhật ký | CRUD thiết lập/thông tin; R/X nhật ký | – | R thông tin tổ chức; RU thiết lập độc giả | – | R thông tin tổ chức |
| Báo cáo và export/import XML | Toàn quyền báo cáo; XML cho Phông/Khối/Mục lục/Hồ sơ/Văn bản | theo quyền đọc/tác nghiệp | theo quyền đọc | – | không có export/import |

Quy tắc bảo mật bổ sung: nhân sự nội bộ (bốn role nghiệp vụ, System Manager, Administrator) xem được mọi mức độ mật. Reader chỉ thấy **Hồ sơ lưu trữ** và **Văn bản/tài liệu** có ưu tiên mức mật không vượt `max_confidentiality_priority` trong hồ sơ Reader.

## 4. Kịch bản trình diễn

### Pha A – Đăng nhập và tổng quan (3 phút)

1. Đăng nhập bằng `admin.demo`, mở workspace **Document Manager**.
2. Giới thiệu dashboard và các nhóm: Biên mục, Độc giả & khai thác, Bảo quản, Danh mục, Thống kê, Quản trị.
3. Mở **Thông tin tổ chức** để chứng minh thông tin giới thiệu/liên hệ có thể quản lý và Reader chỉ được xem.
4. Đăng xuất và đăng nhập nhanh bằng `reader.demo`: xác nhận đây là tài khoản portal, không có Desk; menu portal gồm Tìm kiếm, Phiếu yêu cầu, Phiếu sao chụp và Góp ý.

**Kết quả mong đợi:** giao diện/đường dẫn khả dụng khác nhau theo role.

### Pha B – Chuẩn hóa danh mục và biên mục (12 phút)

Thực hiện bằng `cataloger.demo`.

1. Vào **Cơ quan lưu trữ**, **Bảng phân loại**, **Nhóm tài liệu**, **Loại tài liệu**, **Kho lưu trữ**, **Từ điển nhập nhanh**; tạo hoặc sửa một giá trị minh họa. Với từ điển, minh họa nhập nhanh từ khóa hay lặp lại.
2. Mở **Mức độ mật**: chỉ cho thấy quyền xem của Cataloger. Chuyển sang `admin.demo`, tạo/sửa mức `Hạn chế` hoặc `Mật` để chứng minh đây là danh mục quản trị.
3. Với Cataloger, tạo chuỗi dữ liệu 5 tầng: **Phông → Khối tài liệu → Mục lục → Hồ sơ lưu trữ → Văn bản/tài liệu**.
4. Khi tạo Hồ sơ, chọn phông/khối/mục lục, kho lưu trữ, mức độ mật, thời gian tài liệu. Khi tạo Văn bản, đính kèm PDF, điền số/ngày văn bản, tác giả, loại tệp, số trang và mức độ mật.
5. Lưu văn bản, chờ worker xử lý. Mở lại để chỉ ra tệp đính kèm, checksum SHA-256, phiên bản, trạng thái lập chỉ mục và nội dung được trích xuất (nếu dịch vụ đã hoàn tất).
6. Tìm kiếm từ List View theo mã/tên hồ sơ và văn bản; in hồ sơ hoặc văn bản bằng `admin.demo` để minh họa mẫu in chuẩn.

**Kết quả mong đợi:** dữ liệu liên kết đúng cấp cha–con; số lượng văn bản của hồ sơ và tổng hồ sơ của phông được cập nhật tự động; Cataloger có thể xóa văn bản/hồ sơ/mục lục/khối nhưng không xóa Phông.

### Pha C – Tra cứu, preview và kiểm tra độ mật (8 phút)

Thực hiện bằng `reader.demo`.

1. Mở `/search`, tìm `công tác` hoặc một từ có trong PDF đã trích xuất. Minh họa tìm toàn văn.
2. Thử bộ lọc: phông, mức độ mật, loại tệp; thay đổi sắp xếp và chuyển trang nếu có đủ dữ liệu.
3. Trên một kết quả mức `Thường`, chọn **Xem trước**. Minh họa PDF/ảnh hiển thị trực tiếp hoặc nội dung trích xuất với tệp chưa hỗ trợ preview; mở chi tiết và tải tệp nếu được phép.
4. Tìm `QD-MAT-001`. Xác nhận không xuất hiện với Reader ưu tiên 1.
5. Dùng `admin.demo` mở cùng văn bản để xác nhận cán bộ nội bộ vẫn thấy được. Tăng `max_confidentiality_priority` của Reader lên 3, đăng nhập lại Reader và tìm lại để xác nhận quyền được mở rộng.

**Kết quả mong đợi:** cả danh sách, tìm kiếm toàn văn, preview/tải tệp và truy cập trực tiếp đều tuân theo độ mật.

### Pha D – Yêu cầu khai thác, sao chụp và phản hồi (12 phút)

1. Với `reader.demo`, tạo **Phiếu yêu cầu khai thác**, thêm Hồ sơ/Văn bản mức `Thường` vào bảng chi tiết, lưu và **Submit**. Trạng thái chuyển thành `Chờ duyệt`.
2. Tạo **Phiếu yêu cầu sao chụp**, thêm văn bản, điền yêu cầu sao chụp, Submit. Trạng thái cũng là `Chờ duyệt`.
3. Gửi một **Phản hồi độc giả** để minh họa kênh góp ý.
4. Đăng nhập `readingroom.demo`: mở danh sách Reader để tìm/cập nhật độc giả; mở hai phiếu đang chờ.
5. Duyệt phiếu khai thác: thao tác **Approve**, kiểm tra `approved_by`, `approved_date`, trạng thái `Đã duyệt`; sau khi hoàn trả, chọn **Mark returned** để thành `Đã trả`.
6. Duyệt phiếu sao chụp: **Approve**, sau khi cấp bản sao chọn **Mark completed** để thành `Đã hoàn thành`. Tạo thêm một phiếu và **Reject**, nhập lý do để minh họa nhánh từ chối.
7. Mở phản hồi độc giả và trả lời bằng `readingroom.demo`; Reader mở lại để xem phản hồi.
8. Mở mẫu in của phiếu bằng `readingroom.demo` hoặc `admin.demo`.

**Kết quả mong đợi:** Reader tạo/submit được yêu cầu của mình nhưng không được xóa, hủy hoặc amend; Reading Room Officer xử lý vòng đời yêu cầu nhưng không xóa yêu cầu; Admin có toàn quyền.

### Pha E – Báo cáo, export/import XML (6 phút)

Thực hiện bằng `admin.demo`.

1. Mở **Thống kê tài liệu**, lọc theo phông/kho/loại tài liệu và chạy báo cáo. Chỉ ra các tổng số và biểu đồ.
2. Mở **Thống kê khai thác**, lọc khoảng thời gian để xem yêu cầu khai thác/sao chụp theo trạng thái và biểu đồ.
3. Xuất dữ liệu XML cho lần lượt một trong các loại được hỗ trợ: `Fonds`, `Record Group`, `Catalog`, `Archival File`, `Archive Document`; chọn bộ trường cần xuất nếu gọi qua API.
4. Nhập lại một XML thử nghiệm với bản ghi mới; kiểm tra job nền và log. Nhập lại lần hai với `update_existing = false` để minh họa bỏ qua trùng; chỉ dùng `update_existing = true` khi chủ trì demo đã xác nhận dữ liệu được phép cập nhật.

**Kết quả mong đợi:** XML export/import chỉ hỗ trợ năm DocType trên; import chạy nền, không chờ trực tiếp trên trình duyệt.

### Pha F – Bảo quản, kiểm tra toàn vẹn và khôi phục (6 phút)

Thực hiện bằng `preservation.demo`.

1. Tạo **Đợt sao lưu**, chọn `Cơ sở dữ liệu`, `Tệp tài liệu` hoặc `Cả hai`, sau đó bấm **Run backup**. Theo dõi `Đang chạy` → `Thành công/Lỗi`, thời gian hoàn thành, đường dẫn và dung lượng sao lưu.
2. Tạo **Kiểm tra toàn vẹn**, chọn `Checksum`, `File bị thiếu`, `Liên kết file-metadata` hoặc `Toàn bộ`; chạy kiểm tra. Mở lại bản ghi để xem tổng số đã kiểm tra, lỗi phát hiện và chi tiết lỗi.
3. Tạo **Đợt khôi phục**, chọn đợt sao lưu nguồn, chạy để thể hiện cơ chế điều phối và trạng thái job.
4. Dùng Admin mở cùng màn hình để chứng minh Admin cũng có toàn quyền; Cataloger/Reader không thấy quyền thao tác.

**Giới hạn cần nêu khi demo:** mã hiện tại chỉ ghi nhận tác vụ khôi phục CSDL và yêu cầu thực hiện restore thực tế thủ công qua `bench restore`; không tuyên bố đã tự động khôi phục dữ liệu CSDL.

### Pha G – Quản trị, cấu hình và nhật ký (4 phút)

Thực hiện bằng `admin.demo` hoặc `System Manager` cho phần được Frappe cấp role chuẩn.

1. Mở **Document Manager Settings**, điền/cập nhật cấu hình MongoDB GridFS và Meilisearch, bấm kiểm tra kết nối MongoDB/Meilisearch.
2. Bật/tắt lịch kiểm tra toàn vẹn tự động. Nêu lịch cron hiện cấu hình: Chủ nhật, 02:00.
3. Mở **Reader Settings** để kiểm tra tham số khai thác độc giả; `readingroom.demo` được cập nhật thiết lập này nhưng không tạo bản ghi mới.
4. Mở **Nhật ký nghiệp vụ**, tìm theo loại hoạt động/thời gian, export nếu dùng Admin/System Manager; kiểm tra tác vụ dọn log định kỳ.
5. Trong quản trị chuẩn Frappe, minh họa tạo người dùng, gán role và đổi mật khẩu (đây là chức năng nền tảng của Frappe, không phải DocType riêng của ứng dụng).

## 5. Checklist nghiệm thu phân quyền

Thực hiện tối thiểu các phép thử âm sau trước khi kết thúc:

- Reader ưu tiên 1 không thấy hoặc không mở được Hồ sơ/Văn bản mức `Mật`; Reader ưu tiên 3 mở được.
- Cataloger không có quyền xóa Phông, không sửa Mức độ mật và không vận hành Sao lưu.
- Reading Room Officer không tạo/sửa Phông, Hồ sơ hay Văn bản; chỉ đọc chúng.
- Preservation Officer không biên mục hay xử lý phiếu yêu cầu.
- Reader không vào Desk, không export/import XML, không xóa/hủy/amend phiếu.
- Admin có quyền tạo/sửa/xóa toàn bộ DocType ứng dụng, vận hành bảo quản, cấu hình và export/import tại các DocType đã hỗ trợ.

## 6. Điểm cần xác nhận kỹ thuật trước khi nghiệm thu

1. Dịch vụ MongoDB, Meilisearch, Redis và worker hoạt động; nếu không, upload vẫn có thể lưu metadata nhưng preview, toàn văn, chỉ mục hoặc tác vụ nền có thể không hoàn tất.
2. Kiểm tra có bản PDF mẫu không mật và một bản mật để chứng minh chính xác lọc quyền.
3. Không chạy khôi phục trên môi trường demo có dữ liệu quan trọng; tạo backup trước mọi thử nghiệm.
4. Các phương thức duyệt/từ chối/hoàn tất phiếu hiện được khai báo là API document method. Khi nghiệm thu bảo mật, cần kiểm tra chúng từ phiên Reader bằng kiểm thử API trực tiếp, không chỉ kiểm tra nút giao diện; nếu Reader có thể gọi trực tiếp phương thức đổi trạng thái, cần bổ sung kiểm tra role phía máy chủ trước khi đưa production.

