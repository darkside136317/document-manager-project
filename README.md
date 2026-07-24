# Document Manager — Hệ thống Quản lý & Khai thác Hồ sơ Lưu trữ Số hóa

> Phần mềm quản lý và khai thác hồ sơ, tài liệu lưu trữ số hóa quy mô lớn, xây dựng trên nền tảng **Frappe/ERPNext**, triển khai bằng **Docker**.

## Tổng quan

Hệ thống phục vụ **quản lý và khai thác hồ sơ, tài liệu lưu trữ số hóa** (PDF, DOCX, XLSX, ảnh scan...) cho đơn vị lưu trữ (trung tâm lưu trữ, thư viện, cơ quan nhà nước). Thiết kế cho quy mô **1 triệu+ tài liệu**, nhiều người dùng đồng thời.

### 2 nhóm người dùng
- **Cán bộ nghiệp vụ** (nội bộ): biên mục, quản lý danh mục, thống kê báo cáo, bảo quản dữ liệu, quản trị hệ thống
- **Độc giả** (bên ngoài): tra cứu, tìm kiếm, gửi yêu cầu sử dụng/sao chụp tài liệu qua cổng thông tin trực tuyến

### 8 phân hệ nghiệp vụ
1. **Khai thác trực tuyến** — Cổng thông tin cho độc giả
2. **Biên mục tài liệu** — CRUD cấu trúc phân cấp 5 tầng
3. **Danh mục tài liệu** — Master data dùng chung
4. **Thống kê, Báo cáo** — Query/Script Reports
5. **Xuất/Nhập dữ liệu** — Export/Import XML
6. **Quản lý độc giả** — Phiếu yêu cầu, workflow duyệt
7. **Bảo quản tài liệu** — Sao lưu, kiểm tra, khôi phục
8. **Quản trị hệ thống** — Người dùng, phân quyền, nhật ký

## Kiến trúc

```
User (Cán bộ / Độc giả) → Nginx → Frappe Backend
                                      │
                                      ├──▸ MariaDB (metadata)
                                      ├──▸ Redis (cache + queue)
                                      ├──▸ Worker (extract text, preview, backup)
                                      ├──▸ MongoDB Atlas GridFS (lưu file gốc + preview)
                                      └──▸ Meilisearch (full-text search)
```

### Mô hình dữ liệu phân cấp

```
Phông lưu trữ (Fonds)
   └── Khối tài liệu (Record Group)
         └── Mục lục tài liệu (Catalog)
               └── Hồ sơ lưu trữ (Archival File)
                     └── Văn bản/tài liệu (Archive Document)
```

## Yêu cầu hệ thống

- Docker Engine 24+ & Docker Compose v2
- Tối thiểu 4GB RAM (khuyến nghị 8GB+)
- 20GB+ dung lượng đĩa cho dữ liệu
- Tài khoản MongoDB Atlas (free tier hoặc paid)

## Hướng dẫn cài đặt

### 1. Clone repository

```bash
git clone <your-repo-url>
cd document-manager-project
```

### 2. Cấu hình môi trường

```bash
cp docker/.env.example docker/.env
# Sửa docker/.env với các giá trị thực tế (mật khẩu, keys...)
```

### 3. Khởi động Docker

```bash
cd docker
docker compose up -d
```

### 4. Chờ site được tạo

```bash
# Theo dõi log tạo site
docker compose logs -f create-site

# Sau khi site tạo xong, truy cập:
# Frappe Desk: http://localhost:8080
# Meilisearch: http://localhost:7700
```

### 5. Đăng nhập Admin

- **URL**: http://localhost:8080
- **User**: Administrator
- **Password**: giá trị `ADMIN_PASSWORD` trong `.env`

## Cấu trúc thư mục

```
document-manager-project/
├── docker/
│   ├── docker-compose.yml    # Docker Compose đầy đủ services
│   ├── .env.example          # Template biến môi trường
│   └── .env                  # (gitignored) biến môi trường thực
├── apps/
│   └── document_manager/     # Custom Frappe app
│       ├── document_manager/
│       │   ├── document_manager/
│       │   │   ├── doctype/  # Tất cả Doctype
│       │   │   ├── report/   # Query/Script Reports
│       │   │   ├── api/      # Custom API endpoints
│       │   │   ├── services/ # Background workers, S3, Search
│       │   │   └── www/      # Portal pages cho độc giả
│       │   ├── hooks.py      # Frappe hooks configuration
│       │   ├── patches.txt   # Database migration patches
│       │   └── modules.txt   # Module registration
│       ├── setup.py
│       └── requirements.txt
├── docs/
│   └── build-log/            # Build documentation
│       └── 00-tong-quan-tien-do.md
├── .gitignore
└── README.md
```

## Tiến độ xây dựng

Xem chi tiết tại: [docs/build-log/00-tong-quan-tien-do.md](docs/build-log/00-tong-quan-tien-do.md)

## Quy tắc Git

- **Branch**: `main` → `develop` → `feature/<tên-tính-năng>`
- **Commit**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`)
- **Không commit**: `sites/`, `.env`, `node_modules/`

## License

MIT
