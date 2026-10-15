# Định dạng trao đổi dữ liệu XML (Phụ lục 03, phân hệ 5)

Màn hình **Trao đổi dữ liệu → Xuất, nhập XML** (`/dashboard/trao-doi-du-lieu`) dành cho người có chức năng **Xuất dữ liệu XML** hoặc **Nhập dữ liệu XML** (mặc định: Quản trị viên; giao thêm ở Quản trị → Phân quyền).
Lược đồ XSD chính thức được sinh từ danh sách trường của hệ thống và tải ở `/api/method/document_manager.document_manager.api.exchange.download_schema`
(nút "Lược đồ XSD" trên màn hình). Tệp nhập được kiểm tra bằng đúng XSD này.

## Cấu trúc

Dữ liệu là một cây theo đúng thứ bậc lưu trữ: **Phông › Khối tài liệu › Mục lục › Hồ sơ › Văn bản**.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ArchiveExchange version="1.0" exported_at="2026-10-08T09:30:00" source="docmanager.yourdomain.com" level="Archival File">
  <Fonds ref="true">                       <!-- cấp trên của dữ liệu xuất: chỉ mang các trường khóa -->
    <fonds_name>Phông Công ty ABC</fonds_name><fonds_code>ABC</fonds_code><archival_agency>Trung tâm lưu trữ</archival_agency>
    <RecordGroup ref="true">
      <group_title>Khối tài liệu hành chính</group_title><group_code>HC</group_code>
      <Catalog ref="true">
        <catalog_title>Mục lục 2020</catalog_title><catalog_number>ML-2020</catalog_number>
        <ArchivalFile>
          <file_title>Hồ sơ hội nghị</file_title><file_number>01</file_number><start_date>2020-03-04</start_date>
          <ArchiveDocument><document_title>Quyết định 123</document_title><document_number>123/QĐ</document_number></ArchiveDocument>
        </ArchivalFile>
      </Catalog>
    </RecordGroup>
  </Fonds>
</ArchiveExchange>
```

| Phần tử | DocType | Trường khóa (nhận ra bản ghi) | Trường luôn dùng khi tạo mới (và có trong phần tử `ref`) |
|---|---|---|---|
| `Fonds` | Fonds | `fonds_code`, nếu không có thì `fonds_name` | tên, mã, `archival_agency` |
| `RecordGroup` | Record Group | `group_code`, nếu không có thì `group_title` | tiêu đề, mã |
| `Catalog` | Catalog | `catalog_number`, nếu không có thì `catalog_title` | tiêu đề, số |
| `ArchivalFile` | Archival File | `file_number`, nếu không có thì `file_title` | tiêu đề, số |
| `ArchiveDocument` | Archive Document | `document_number`, nếu không có thì `document_title` | tiêu đề, số |

* Mỗi phần tử con của một cấp là một **trường** (tên phần tử = tên trường trong DocType). Thứ tự trường theo XSD, mọi trường đều tùy chọn.
  Danh sách trường của từng cấp xem ở màn hình xuất hoặc trong XSD. Ngày dạng `YYYY-MM-DD`, số nguyên và số thực dạng thường, giá trị chọn phải thuộc danh sách của trường.
* Giá trị ở các trường liên kết (cơ quan lưu trữ, mức độ mật, loại hình, kho…) là **tên** bản ghi danh mục; danh mục phải có sẵn trên hệ thống nhận
  (hoặc bật "Tạo danh mục còn thiếu": chỉ tạo cơ quan lưu trữ, loại hình, nhóm tài liệu — **không bao giờ tạo mức độ mật**).
* `ref="true"` đánh dấu phần tử chỉ để chỉ chỗ đặt dữ liệu (cấp trên của cấp được xuất). Khi nhập: tìm thấy thì dùng, không thấy thì tạo từ các trường khóa.
* Tệp tài liệu số (PDF, ảnh…), nội dung văn bản trích xuất, mã định danh lưu trữ và các cột hệ thống **không** nằm trong tệp.

## Xuất

1. Chọn cấp dữ liệu và đặt điều kiện tìm kiếm (cùng bộ lọc với màn hình tìm kiếm), tùy chọn "Kèm cả dữ liệu cấp dưới".
2. "Xem trước số lượng" cho biết số bản ghi mỗi cấp (tối đa 100.000 bản ghi một tệp).
3. Chọn các trường đưa vào tệp (trường khóa luôn có), bấm "Xuất XML": việc chạy nền, theo dõi ở thẻ kết quả, tải tệp khi xong.
   Việc xuất đọc dữ liệu bằng quyền của người xuất.

## Nhập

1. Tải tệp lên: hệ thống kiểm tra mã hóa UTF-8, **không chấp nhận DOCTYPE/ENTITY**, đúng lược đồ XSD, rồi cho xem số bản ghi và các trường có trong tệp.
2. Chọn cách nhập: **Chỉ thêm mới** (bản ghi đã có được giữ nguyên) hoặc **Thêm mới và cập nhật** (cập nhật theo các trường đã chọn), và các trường cần nhập.
3. **Chạy thử** thực hiện đúng quy trình nhập nhưng hoàn tác ở cuối: không ghi gì. Sau đó **Nhập dữ liệu**.
4. Mỗi bản ghi đi qua kiểm tra và phân quyền của DocType (quyền của người nhập). Bản ghi lỗi được ghi vào nhật ký của lượt (kèm vị trí trong cây) và nhánh con của nó bị bỏ qua; các bản ghi khác vẫn được nhập.
   Một lúc chỉ chạy một lượt nhập thật.

Lịch sử các lượt xuất, nhập (kèm tệp, tổng kiểm SHA-256 và nhật ký lỗi) xem ở thẻ **Lịch sử**; mọi lượt được ghi vào nhật ký hệ thống ("Xuất XML", "Nhập XML").
