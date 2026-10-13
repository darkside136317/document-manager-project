# Hướng dẫn triển khai sản xuất — Document Manager

## 1. Yêu cầu máy chủ

| Thành phần | Tối thiểu | Khuyến nghị (khoảng 1 triệu văn bản) |
|---|---|---|
| CPU | 2 lõi | 4 lõi trở lên |
| RAM | 4 GB | 8 GB trở lên (MariaDB và Meilisearch cần nhiều bộ nhớ) |
| Đĩa | 40 GB SSD | 200 GB SSD trở lên; tệp tài liệu và kho sao lưu tăng theo dữ liệu |
| Hệ điều hành | Ubuntu 22.04 / Debian 12 | Ubuntu 24.04 LTS |
| Docker | Engine 24, Compose v2 | Engine 27 |
| Mạng | Cổng 80/443 | Reverse proxy có TLS phía trước |

## 2. Chuẩn bị

```bash
curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER   # đăng nhập lại sau lệnh này
git clone <địa-chỉ-repo> /opt/docmanager && cd /opt/docmanager
```

### MongoDB Atlas (tùy chọn, khuyến nghị)

MongoDB GridFS giữ tệp gốc và bản xem trước. Không có nó, hệ thống vẫn chạy: tệp nằm ở thư mục riêng của Frappe và việc kiểm tra bản GridFS bị bỏ qua
(ghi thành một cảnh báo). Nếu dùng:

1. Tạo cluster (khu vực gần nhất, ví dụ Singapore), một người dùng cơ sở dữ liệu có quyền đọc/ghi.
2. **Network Access**: thêm địa chỉ IP của máy chủ. Quên bước này là nguyên nhân thường gặp của lỗi *SSL handshake failed* khi kết nối.
3. Lấy chuỗi kết nối `mongodb+srv://…` (Database → Connect → Drivers).

## 3. Cấu hình `.env`

```bash
cd /opt/docmanager/docker
cp .env.example .env
nano .env
```

| Biến | Cần làm |
|---|---|
| `FRAPPE_SITE_NAME` | Tên miền thật, ví dụ `luutru.coquan.gov.vn` (nginx dùng làm tên site) |
| `ADMIN_PASSWORD` | Mật khẩu của `Administrator`: `openssl rand -base64 24` |
| `MARIADB_ROOT_PASSWORD` | `openssl rand -base64 24` |
| `MONGODB_ATLAS_URI`, `MONGODB_DATABASE` | Chuỗi kết nối và tên cơ sở dữ liệu GridFS (mặc định `docmanager_files`) |
| `MEILISEARCH_MASTER_KEY` | `openssl rand -hex 16`; **bắt buộc đổi**, Meilisearch không công khai ra máy chủ |
| `GUNICORN_WORKERS` / `GUNICORN_THREADS` | Khoảng `2 × số lõi + 1` tiến trình |
| `HTTP_PUBLISH_PORT` | Cổng nginx công bố (mặc định `80` ở chế độ production) |
| `CLIENT_MAX_BODY_SIZE` | Giới hạn tải lên của nginx, đặt `200m`; giới hạn tệp của ứng dụng là 100 MB |

Không đưa `.env` vào git.

## 4. Build image và khởi động

```bash
cd /opt/docmanager/docker
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend   # có tầng Node: chạy vitest và build giao diện cán bộ
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose logs -f create-site   # chờ xong (2–5 phút): tạo site, cài ERPNext và document_manager
docker compose ps
```

`create-site` chạy `bench new-site` với `--install-app document_manager`; ứng dụng tự gieo vai trò, mức độ mật, workflow, thông báo, nhóm độc giả
mặc định và các giá trị mặc định của thiết lập (`setup/install.py`). **Không cần cài ứng dụng hay chạy migrate bằng tay** ở lần đầu.

Kiểm tra: `https://<tên-miền>/gioi-thieu` (trang công khai) và `https://<tên-miền>/dang-nhap`; cán bộ đăng nhập rồi vào `/dashboard`.

## 5. Cấu hình sau cài đặt

1. Đăng nhập `Administrator`, vào **Quản trị → Người dùng**, tạo tài khoản cho cán bộ (vai trò: Quản trị tài liệu, Biên mục viên, Cán bộ phòng đọc, Lãnh đạo,
   Cán bộ bảo quản). Hệ thống đưa một liên kết đặt mật khẩu dùng một lần: gửi cho người dùng, không cần email. Liên kết hết hạn sau 72 giờ.
2. **Quản trị → Thông tin đơn vị** và **Cơ cấu tổ chức**: nội dung hiện ở các trang công khai.
3. **Quản trị → Thiết lập hệ thống**: lịch sao lưu tự động, thời hạn giữ bản sao lưu và nhật ký, chính sách mật khẩu, số lần đăng nhập sai.
4. **Độc giả → Thiết lập độc giả** và **Nhóm độc giả**: hạn mức phiếu, gia hạn, nhắc hạn, đăng ký tự do hay phải duyệt.
5. **Quản trị → Giám sát hệ thống**: kiểm tra Meilisearch, MongoDB, hàng đợi, đĩa và lần sao lưu gần nhất đều xanh.

## 6. TLS và reverse proxy

nginx trong compose lắng nghe HTTP. Đặt phía trước một reverse proxy có TLS (Nginx, Traefik hoặc Caddy). Với Nginx ngoài Docker:

```nginx
server {
    listen 80;
    server_name luutru.coquan.gov.vn;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name luutru.coquan.gov.vn;
    ssl_certificate     /etc/letsencrypt/live/luutru.coquan.gov.vn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/luutru.coquan.gov.vn/privkey.pem;

    client_max_body_size 200m;
    proxy_read_timeout 300;

    location / {
        proxy_pass http://127.0.0.1:80;      # HTTP_PUBLISH_PORT
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 7. Sao lưu

Hệ thống tự sao lưu: bật **Sao lưu tự động** trong Thiết lập hệ thống (tần suất ngày/tuần/tháng; có thể gồm cả tệp). Công việc chạy từ bộ lập lịch hằng ngày
và hàng đợi `long`, nên `scheduler` và `queue-long` phải chạy. Bản sao lưu nằm ở `sites/<site>/private/backups` (cơ sở dữ liệu) và
`sites/<site>/private/dm-backup-store` (kho tệp theo nội dung).

**Hai thư mục này cùng volume với site, nên không thay thế được bản sao lưu ra ngoài máy chủ.** Hãy sao chép định kỳ ra nơi khác
(rsync, restic, snapshot đĩa). MongoDB Atlas bản M10 trở lên tự sao lưu; bản miễn phí thì phải làm tay.

Vận hành, kiểm tra và khôi phục: xem [SAO_LUU_KHOI_PHUC.md](SAO_LUU_KHOI_PHUC.md).

## 8. Cập nhật phiên bản

```bash
cd /opt/docmanager && git pull
cd docker
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose exec backend bench --site <tên-site> migrate
docker compose exec backend bench --site <tên-site> clear-cache
```

Hoặc kéo image đã phát hành bởi CI (`ghcr.io/<chủ-repo>/docmanager-custom`) và đổi `image:` trong `docker-compose.prod.yml`.
Sau mỗi lần cập nhật, **khởi động lại `queue-long`, `queue-short` và `scheduler`** (`up -d` làm việc này khi image đổi): worker chỉ nạp mã mới khi khởi động.

Bản có chỉ mục mới (G9) tạo thêm hai chỉ mục kép trên `tabArchive Document` và `tabArchival File` ở lần `migrate` đầu. MariaDB xây chỉ mục phụ ở chế độ
trực tuyến (vẫn đọc và ghi được), nhưng trên kho cỡ một triệu văn bản việc này tốn thời gian và I/O: nên làm ngoài giờ cao điểm.

## 9. Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp và cách xử lý |
|---|---|
| `create-site` quá thời gian | Thiếu RAM; xem `docker compose logs create-site` |
| Giám sát báo MongoDB "Không kết nối" | IP máy chủ chưa có trong Network Access của Atlas, hoặc URI sai; hệ thống vẫn chạy ở chế độ dự phòng |
| Meilisearch 401 | `MEILISEARCH_MASTER_KEY` ở `.env` và trong site config khác nhau; chạy lại `configurator` |
| Tìm kiếm chỉ ra kết quả cũ | Chỉ mục chưa kịp cập nhật (khoảng 15 giây sau khi lưu); xem `queue-long` |
| Sao lưu, kiểm tra không chạy | `scheduler` hoặc `queue-long` không chạy: `docker compose ps`, `docker compose logs queue-long` |
| Trang trắng sau cập nhật | `bench --site <site> clear-cache`, rồi tải lại bằng Ctrl+F5 |
| HTTP 500 khi nhiều người cùng ghi | Kiểm tra `docker/mariadb/my_custom.cnf` còn `innodb_snapshot_isolation=OFF` |
| Redis dừng, trang báo 502 | `docker compose up -d` rồi `docker compose restart frontend` |
| Tìm văn bản báo "mất quá nhiều thời gian" | Meilisearch đang hỏng nên hệ thống tìm bằng cơ sở dữ liệu; sửa Meilisearch hoặc thu hẹp điều kiện tìm |
