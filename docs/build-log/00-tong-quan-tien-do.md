# Tổng quan Tiến độ — Document Manager

> Cập nhật lần cuối: 2026-07-08

## Tổng quan

| # | Giai đoạn | Trạng thái | Build-log |
|---|-----------|------------|-----------|
| 0 | Hạ tầng Docker & Cấu trúc Project | ✅ Đã xong | *(xem bên dưới)* |
| 1 | Danh mục dùng chung (Master Data) | 🔲 Chưa bắt đầu | [01-danh-muc-dung-chung.md](01-danh-muc-dung-chung.md) |
| 2 | Mô hình phân cấp 5 tầng | 🔲 Chưa bắt đầu | [02-mo-hinh-phan-cap.md](02-mo-hinh-phan-cap.md) |
| 3 | Biên mục tài liệu | 🔲 Chưa bắt đầu | [03-bien-muc.md](03-bien-muc.md) |
| 4 | Phân quyền (RBAC) | 🔲 Chưa bắt đầu | [04-phan-quyen.md](04-phan-quyen.md) |
| 5 | Search Pipeline (Meilisearch + MinIO) | 🔲 Chưa bắt đầu | [05-search-pipeline.md](05-search-pipeline.md) |
| 6 | Khai thác trực tuyến & Quản lý Độc giả | 🔲 Chưa bắt đầu | [06-khai-thac-truc-tuyen.md](06-khai-thac-truc-tuyen.md) |
| 7 | Thống kê & Báo cáo | 🔲 Chưa bắt đầu | [07-thong-ke-bao-cao.md](07-thong-ke-bao-cao.md) |
| 8 | Xuất/Nhập XML | 🔲 Chưa bắt đầu | [08-xuat-nhap.md](08-xuat-nhap.md) |
| 9 | Bảo quản tài liệu | 🔲 Chưa bắt đầu | [09-bao-quan.md](09-bao-quan.md) |
| 10 | Quản trị hệ thống | 🔲 Chưa bắt đầu | [10-quan-tri-he-thong.md](10-quan-tri-he-thong.md) |
| 11 | Git, Deploy & Tối ưu vận hành | 🔲 Chưa bắt đầu | [11-git-deploy.md](11-git-deploy.md) |

---

## Giai đoạn 0: Hạ tầng Docker & Cấu trúc Project

### Mục tiêu
Thiết lập cấu trúc thư mục project, Docker Compose đầy đủ services, và Frappe app skeleton.

### Đã hoàn thành
1. **Docker Compose** (`docker/docker-compose.yml`) — 14 services:
   - Frappe: backend, frontend (nginx), websocket, configurator, create-site, queue-long, queue-short, scheduler
   - Database: MariaDB 11.8
   - Cache/Queue: Redis 7 (cache + queue riêng)
   - Search: Meilisearch v1.12
   - Storage: MinIO (S3-compatible) + minio-init (tạo bucket)

2. **Biến môi trường** (`docker/.env.example`) — template cho DB, Redis, MinIO, Meilisearch, Nginx

3. **Frappe App Skeleton** (`apps/document_manager/`):
   - `setup.py`, `requirements.txt` (boto3, meilisearch, pdfplumber, python-docx, openpyxl)
   - `hooks.py` — cấu hình app với các hooks placeholder (sẽ activate từng giai đoạn)
   - Package structure: `doctype/`, `report/`, `api/`, `services/`

4. **Project files**: `README.md`, `.gitignore`, `docs/build-log/`

### Quyết định kỹ thuật
- **Meilisearch** thay vì Elasticsearch: nhẹ hơn (~50MB RAM vs 2GB+), Docker image nhỏ, API đơn giản, hỗ trợ tiếng Việt tốt
- **MinIO** self-hosted: S3-compatible, không phụ thuộc cloud vendor, có Console UI quản lý
- **Redis 7** (thay vì 6.2 của pwd.yml gốc): bản LTS mới hơn, hiệu năng tốt hơn
- **Volumes named riêng** (prefix `docmanager_`): tách biệt để backup độc lập

### Việc cần làm tiếp
→ Giai đoạn 1: Tạo Doctype danh mục dùng chung (Master Data)
