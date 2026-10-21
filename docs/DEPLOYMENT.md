# Hướng dẫn triển khai sản xuất — Document Manager

## 1. Yêu cầu máy chủ

| Thành phần | Tối thiểu | Khuyến nghị (khoảng 1 triệu văn bản) |
|---|---|---|
| CPU | 2 lõi | 4 lõi trở lên |
| RAM | 4 GB | 8 GB trở lên (MariaDB và Meilisearch cần nhiều bộ nhớ) |
| Đĩa | 40 GB SSD | Tính theo dung lượng tệp thực tế: 1 triệu tệp, trung bình 1 MB/tệp cần khoảng 1 TB chỉ cho tệp gốc; cộng chỗ cho MariaDB, chỉ mục và dung lượng trống vận hành |
| Hệ điều hành | Ubuntu 22.04 / Debian 12 | Ubuntu 24.04 LTS |
| Docker / Python | Engine 24, Compose v2, Python 3 | Engine 27, Python 3 |
| Mạng | Cổng 80/443 | Reverse proxy có TLS phía trước |

## 2. Chuẩn bị

```bash
curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER   # đăng nhập lại sau lệnh này
git clone <địa-chỉ-repo> /opt/docmanager && cd /opt/docmanager
```

Khách hàng cần trỏ bản ghi DNS **A** của hostname dùng cho ứng dụng (ví dụ `hoso.abc.com.vn`) tới IP public của máy chủ.
Tên này phải được chọn trước khi tạo site lần đầu. Trên máy chủ chỉ mở cổng 80/443 cho reverse proxy; cổng SSH nên giới hạn theo IP quản trị.

### Nơi lưu tệp trên production

ERPNext/Frappe vẫn lưu tệp tải lên trong `sites/<site>/private/files` thuộc Docker volume `${DATA_VOLUME_PREFIX}_sites`.
Mặc định `MINIO_MODE=disabled`: Frappe lưu một bản tệp riêng tư trên volume `${DATA_VOLUME_PREFIX}_sites`.
Khi bật MinIO, Document Manager ghi thêm bản đối tượng của tài liệu lưu trữ. Ở chế độ `auto`, MinIO Community dùng volume
`${DATA_VOLUME_PREFIX}_minio`; ở chế độ `manual`, đối tượng nằm trên máy chủ MinIO đã có theo `MINIO_ENDPOINT`.
Nếu MinIO và Frappe dùng cùng SSD, hai bản tệp sẽ cùng chiếm dung lượng; MinIO không tự chuyển attachment ERPNext ra khỏi SSD.
MariaDB dùng volume `${DATA_VOLUME_PREFIX}_db_data`. Không đổi `DATA_VOLUME_PREFIX` sau khi tạo site vì Compose sẽ gắn volume mới trống.

Chế độ `disabled` không chạy MinIO, không khởi tạo bucket hoặc sao chép tệp. Chế độ `auto` chạy MinIO một node, tạo bucket riêng tư `documents`, tài khoản ứng dụng và quyền chỉ với bucket đó. Không công bố cổng
9000/9001 ra Internet. Chế độ `manual` kết nối MinIO có sẵn, không khởi chạy máy chủ MinIO và không tạo tài khoản, bucket hoặc policy.
Tài khoản ứng dụng cấp sẵn phải có quyền `ListBucket`, `GetObject`, `PutObject`, `DeleteObject` trên bucket đó.
[MinIO Community](https://github.com/minio/minio/blob/master/docs/distributed/README.md) có hỗ trợ cụm nhiều node;
có thể dùng cụm này qua chế độ `manual`. Khi đổi nơi lưu đối tượng đã có, cần chuyển dữ liệu trước khi đổi endpoint.
[MinIO AIStor Free](https://docs.min.io/aistor/operations/licenses/) là sản phẩm khác, giới hạn một node.
Repository Community đã lưu trữ ở chế độ chỉ đọc; cần theo dõi rủi ro bảo mật của release cố định trước khi vận hành dài hạn.
Trường dữ liệu `gridfs_file_id` vẫn giữ tên cũ để tương thích các site đã tạo; đối tượng mới có mã bắt đầu bằng `minio:`.

## 3. Cấu hình môi trường production

```bash
cd /opt/docmanager/docker
cp .env.prod.example .env.prod
chmod 600 .env.prod
nano .env.prod
cd ..
python3 scripts/validate_prod_env.py docker/.env.prod
```

Dev dùng `.env.dev` (từ `.env.dev.example`); production dùng `.env.prod`. Mọi lệnh Compose production bên dưới đều truyền
`--env-file .env.prod`. Không chép `.env.dev` từ máy lập trình lên server và không đưa tệp chứa mật khẩu vào Git.

| Biến | Cần làm |
|---|---|
| `FRAPPE_SITE_NAME` | Đúng hostname khách hàng đã trỏ DNS, ví dụ `hoso.abc.com.vn`; cũng là tên site Frappe |
| `PUBLIC_URL` | `https://` + `FRAPPE_SITE_NAME`, ví dụ `https://hoso.abc.com.vn` |
| `COMPOSE_PROJECT_NAME`, `DATA_VOLUME_PREFIX` | Tên riêng cho từng khách hàng trên cùng host; thay cả hai giá trị mẫu, tách container, network và volume dữ liệu |
| `DATA_ROOT` | Thư mục dữ liệu trên host, ví dụ `/srv/docmanager`; để trống nếu muốn dùng Docker volume thông thường |
| `ADMIN_PASSWORD`, `MARIADB_ROOT_PASSWORD`, `MEILISEARCH_MASTER_KEY` | Ba giá trị ngẫu nhiên **khác nhau**, mỗi giá trị có thể tạo bằng `openssl rand -hex 24` |
| `MINIO_MODE`, `COMPOSE_PROFILES` | Mặc định `disabled`/rỗng để chỉ dùng Frappe; `auto`/`auto` để tự chạy MinIO; `manual`/rỗng để kết nối MinIO có sẵn |
| `MINIO_ENDPOINT`, `MINIO_BUCKET` | `disabled`: endpoint rỗng; `auto`: `http://minio:9000` và `documents`; `manual`: URL nội bộ/TLS và tên bucket đã tạo |
| `MINIO_APP_ACCESS_KEY`, `MINIO_APP_SECRET_KEY` | Ở `auto`, tạo hai giá trị riêng tối thiểu 24 ký tự; ở `manual`, dùng khóa đã cấp từ MinIO có sẵn (tối thiểu 8 ký tự) và cấp quyền cho bucket |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Chỉ cần ở `auto`: hai giá trị ngẫu nhiên khác nhau, tối thiểu 24 ký tự; ở `manual` và `disabled` để trống |
| `GUNICORN_WORKERS` / `GUNICORN_THREADS` | Khoảng `2 × số lõi + 1` tiến trình |
| `HTTP_PUBLISH_PORT` | `127.0.0.1:8080`: chỉ reverse proxy trên cùng máy truy cập được, không mở HTTP trực tiếp ra Internet |
| `CLIENT_MAX_BODY_SIZE` | Giới hạn tải lên của nginx, đặt `200m`; giới hạn tệp của ứng dụng là 100 MB |

Tên volume của dev mặc định là `docmanager_*`. `DATA_VOLUME_PREFIX` production phải khác, và phải giữ nguyên qua các lần cập nhật;
đổi giá trị này sẽ khiến Compose gắn vào volume trống. Đổi `FRAPPE_SITE_NAME` sau khi tạo site cũng không tự đổi tên site cũ.
Khi đặt `DATA_ROOT`, tạo trước các thư mục `db-data`, `redis-queue`, `sites`, `logs`, `meilisearch` và `minio` bên dưới thư mục này.
Production nạp thêm `docker-compose.prod.bind.yml`: các volume dữ liệu vẫn được Docker khởi tạo nhưng nội dung nằm trực tiếp trong
`DATA_ROOT` trên host. Giữ nguyên `DATA_ROOT` sau lần chạy đầu; đổi đường dẫn sẽ gắn vào thư mục dữ liệu khác.
Các dịch vụ chạy liên tục, gồm Redis, dùng chính sách `restart: always`; Docker và reverse proxy trên host cũng cần được bật
tự khởi động bằng systemd để web hoạt động trở lại sau reboot.
Với `disabled`, giữ bốn khóa MinIO và `MINIO_ENDPOINT` rỗng như tệp mẫu. Để bật `auto`, đặt `MINIO_MODE=auto`,
`COMPOSE_PROFILES=auto`, `MINIO_ENDPOINT=http://minio:9000`, `MINIO_BUCKET=documents` và điền bốn khóa MinIO.
Để bật `manual`, dùng cấu hình dưới đây. Mọi lệnh production phải chạy qua `scripts/prod_compose.py` để chỉ nạp
Compose overlay MinIO khi chế độ này được bật.

Ở chế độ `manual`, endpoint phải truy cập được từ các container qua mạng Docker. Nếu MinIO có sẵn chạy trên cùng host, dùng `MINIO_ENDPOINT=http://host.docker.internal:9000`; production overlay đã ánh xạ host gateway cho các tiến trình ứng dụng, kiểm tra bucket và chuyển dữ liệu. Giới hạn cổng 9000 bằng firewall. Dùng HTTPS khi kết nối qua mạng không tin cậy.
Kiểm tra bucket và quyền của tài khoản ứng dụng trước khi triển khai; `minio-init` sẽ thử liệt kê, ghi, đọc và xóa một đối tượng
kiểm tra rồi mới cho ứng dụng khởi động, nhưng không tạo hay sửa tài khoản, bucket hoặc policy trên MinIO có sẵn.

Ví dụ các dòng MinIO trong `.env.prod` khi dùng máy chủ có sẵn:

```dotenv
MINIO_MODE=manual
COMPOSE_PROFILES=
MINIO_ENDPOINT=https://minio.internal.example:9000
MINIO_BUCKET=existing-documents
MINIO_ROOT_USER=
MINIO_ROOT_PASSWORD=
MINIO_APP_ACCESS_KEY=<access-key-đã-cấp>
MINIO_APP_SECRET_KEY=<secret-key-đã-cấp>
```

Nếu đổi một site đang chạy từ `auto` sang `manual`, sao chép toàn bộ đối tượng sang bucket mới và kiểm tra chúng trước khi
đổi endpoint. Sau khi chạy `up -d --remove-orphans`, kiểm tra container MinIO cũ đã dừng; nếu còn chạy, dùng
`docker compose --profile auto --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.prod.minio.yml stop minio`.
Đổi biến môi trường không tự chuyển dữ liệu. Nếu đổi từ `auto` hoặc `manual` về `disabled`, xác nhận tệp Frappe còn đọc được
trước khi tắt MinIO; các tài liệu chỉ còn bản MinIO sẽ không mở được khi MinIO tắt.

## 4. Build image và khởi động

```bash
cd /opt/docmanager/docker
python3 ../scripts/prod_compose.py config -q
python3 ../scripts/prod_compose.py build
python3 ../scripts/prod_compose.py up -d --remove-orphans
python3 ../scripts/prod_compose.py logs -f create-site
python3 ../scripts/prod_compose.py ps -a
python3 ../scripts/prod_compose.py exec backend bench --site <tên-site> enable-scheduler
```

Thiếu lệnh `enable-scheduler` thì sao lưu tự động, cờ quá hạn, nhắc hạn và kiểm tra toàn vẹn hằng tuần không chạy.

`create-site` chỉ chạy `bench new-site` khi site chưa tồn tại; ở lần chạy lại nó kiểm tra site rồi bỏ qua. Ứng dụng tự gieo vai trò,
mức độ mật, workflow, thông báo, nhóm độc giả mặc định và thiết lập (`setup/install.py`). **Không cần cài ứng dụng hay chạy migrate bằng tay** ở lần đầu.

Nếu bật `auto` hoặc `manual`, chạy `python3 ../scripts/prod_compose.py logs minio-init minio-backfill`.
Ở `auto`, `minio-init` tạo bucket và tài khoản tự động, lặp lại an toàn khi cập nhật. Ở `manual`, nó chỉ kiểm tra bucket bằng
khóa ứng dụng. `minio-backfill` đưa các tệp riêng tư đã có lên MinIO;
chỉ sau khi hoàn tất backend và worker mới khởi động. Nếu tệp cũ chỉ còn trong GridFS mà không có bản Frappe trên SSD,
bước này dùng `MONGODB_ATLAS_URI` và `MONGODB_DATABASE` cũ trong `.env.prod` để đọc và khôi phục bản Frappe. Giữ hai biến cũ
chỉ trong lần chuyển dữ liệu; sau khi `minio-backfill` thành công có thể xóa chúng. Nếu không còn URI hoặc tệp không đọc được,
bước này dừng và nêu tên các tài liệu cần phục hồi trước khi gỡ MongoDB.

Kiểm tra: `https://<tên-miền>/gioi-thieu` (trang công khai) và `https://<tên-miền>/dang-nhap`; cán bộ đăng nhập rồi vào `/dashboard`.

## 5. Cấu hình sau cài đặt

1. Đăng nhập `Administrator`, vào **Quản trị → Người dùng**, tạo tài khoản cho cán bộ và gán nhóm quyền (có sẵn: Quản trị viên, Biên mục viên, Cán bộ phòng đọc,
   Lãnh đạo, Cán bộ bảo quản; sửa hoặc thêm nhóm ở **Quản trị → Phân quyền**). Hệ thống đưa một liên kết đặt mật khẩu dùng một lần: gửi cho người dùng, không cần email. Liên kết hết hạn sau 72 giờ.
2. **Quản trị → Thông tin đơn vị** và **Cơ cấu tổ chức**: nội dung hiện ở các trang công khai.
3. **Quản trị → Thiết lập hệ thống**: lịch sao lưu tự động, thời hạn giữ bản sao lưu và nhật ký, chính sách mật khẩu, số lần đăng nhập sai.
4. **Độc giả → Thiết lập độc giả** và **Nhóm độc giả**: hạn mức phiếu, gia hạn, nhắc hạn, đăng ký tự do hay phải duyệt.
5. **Quản trị → Giám sát hệ thống**: kiểm tra Meilisearch, hàng đợi, đĩa và lần sao lưu gần nhất; MinIO hiện "Đã tắt" khi dùng mặc định, hoặc "Kết nối được" khi đã bật.

## 6. TLS và reverse proxy

nginx trong compose chỉ lắng nghe trên `127.0.0.1:8080` của host. Đặt reverse proxy có TLS (Nginx, Traefik hoặc Caddy)
phía trước. Với Nginx ngoài Docker trên cùng máy, thay `hoso.abc.com.vn` dưới đây bằng `FRAPPE_SITE_NAME` thật và cấp chứng chỉ TLS:

Nếu truy cập trực tiếp qua EIP, đặt `FRAPPE_SITE_NAME` bằng IP và `PUBLIC_URL=https://<IP>` trước khi tạo site. Chứng chỉ
Let's Encrypt cho IP chỉ có hiệu lực khoảng 6 ngày, nên cần Certbot hỗ trợ chứng chỉ IP và gia hạn tự động; mở inbound TCP
80/443 trên security group. Đặt `/docs` và `/docs/dang-nhap` chuyển hướng đến `/dang-nhap` trong server HTTPS để có
đường vào trang đăng nhập. Các trang ứng dụng tiếp tục dùng đường dẫn gốc như `/dashboard` và `/portal`.

```nginx
server {
    listen 80;
    server_name hoso.abc.com.vn;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name hoso.abc.com.vn;
    ssl_certificate     /etc/letsencrypt/live/hoso.abc.com.vn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/hoso.abc.com.vn/privkey.pem;

    client_max_body_size 200m;
    proxy_read_timeout 300;

    location / {
        proxy_pass http://127.0.0.1:8080;    # HTTP_PUBLISH_PORT
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;  # websocket (/socket.io)
        proxy_set_header Connection "upgrade";
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
(rsync, restic, snapshot đĩa). Ở chế độ `auto`, dữ liệu MinIO của stack này nằm ở volume `${DATA_VOLUME_PREFIX}_minio`;
ở `manual`, dữ liệu nằm trên máy chủ MinIO đã cấu hình.

Vận hành, kiểm tra và khôi phục: xem [SAO_LUU_KHOI_PHUC.md](SAO_LUU_KHOI_PHUC.md).

## 8. Cập nhật phiên bản

```bash
cd /opt/docmanager && git pull
cd docker
python3 ../scripts/prod_compose.py build
python3 ../scripts/prod_compose.py up -d --remove-orphans
python3 ../scripts/prod_compose.py exec backend bench --site <tên-site> migrate
python3 ../scripts/prod_compose.py exec backend bench --site <tên-site> clear-cache
```

Hoặc kéo image đã phát hành bởi CI (`ghcr.io/<chủ-repo>/docmanager-custom`) và đổi `image:` trong `docker-compose.prod.yml`.
Sau mỗi lần cập nhật, **khởi động lại `queue-long`, `queue-short` và `scheduler`** (`up -d` làm việc này khi image đổi): worker chỉ nạp mã mới khi khởi động.

Bản có chỉ mục mới (G9) tạo thêm hai chỉ mục kép trên `tabArchive Document` và `tabArchival File` ở lần `migrate` đầu. MariaDB xây chỉ mục phụ ở chế độ
trực tuyến (vẫn đọc và ghi được), nhưng trên kho cỡ một triệu văn bản việc này tốn thời gian và I/O: nên làm ngoài giờ cao điểm.

## 9. Xử lý sự cố

Trong các lệnh dưới đây, đặt `C="python3 ../scripts/prod_compose.py"`
khi đang ở thư mục `docker/`.

| Triệu chứng | Nguyên nhân thường gặp và cách xử lý |
|---|---|
| `create-site` quá thời gian | Thiếu RAM; xem `$C logs create-site` |
| `minio-init` không hoàn tất | Xem `$C logs minio-init`; ở `auto` kiểm tra thêm `$C logs minio` và bốn giá trị khóa; ở `manual` kiểm tra endpoint, bucket, quyền và kết nối mạng |
| `minio-backfill` không hoàn tất | Xem `$C logs minio-backfill`; giữ URI MongoDB cũ trong `.env.prod` khi tệp chỉ còn trong GridFS, hoặc phục hồi tệp Frappe trước khi gỡ MongoDB |
| Giám sát báo MinIO "Không kết nối" khi đã bật | Kiểm tra endpoint, bucket và tài khoản ứng dụng; ở `auto` xem thêm `$C ps minio` và `$C logs minio` |
| Meilisearch 401 | `MEILISEARCH_MASTER_KEY` ở `.env.prod` và trong site config khác nhau; chạy lại `configurator` |
| Tìm kiếm chỉ ra kết quả cũ | Chỉ mục chưa kịp cập nhật (khoảng 15 giây sau khi lưu); xem `queue-long` |
| Sao lưu, kiểm tra không chạy | `scheduler` hoặc `queue-long` không chạy: `$C ps`, `$C logs queue-long` |
| Trang trắng sau cập nhật | `bench --site <site> clear-cache`, rồi tải lại bằng Ctrl+F5 |
| HTTP 500 khi nhiều người cùng ghi | Kiểm tra `docker/mariadb/my_custom.cnf` còn `innodb_snapshot_isolation=OFF` |
| Redis dừng, trang báo 502 | `$C up -d` rồi `$C restart frontend` |
| Tìm văn bản báo "mất quá nhiều thời gian" | Meilisearch đang hỏng nên hệ thống tìm bằng cơ sở dữ liệu; sửa Meilisearch hoặc thu hẹp điều kiện tìm |

## 10. Tích hợp AI số hóa với PDFluent

Tính năng mặc định **tắt**. Bật `Số hóa` trong **Quản trị → Thiết lập hệ thống** sau khi hai hệ thống đã kết nối. Chỉ quản trị viên cấu hình tên, thứ tự và chế độ hiển thị của các trường tại **Quản trị → Cấu hình trường dữ liệu**. Các trường thuộc cây Phông → Khối → Mục lục → Hồ sơ → Văn bản được đánh dấu `Số hóa` hoặc `Cả hai` tạo thành schema bất biến của từng job.

### Cấu hình dev trên cùng máy

Trong `docker/.env.dev`, đặt `PDFLUENT_API_URL=http://host.docker.internal:8000`, `PDFLUENT_API_KEY` là khóa bắt đầu bằng `sk_live_` (ít nhất 24 ký tự), và `AI_CALLBACK_API_KEY` là một khóa ngẫu nhiên riêng. Compose dev ánh xạ `host.docker.internal` cho backend và worker gửi job. PDFluent phải lắng nghe trên `0.0.0.0:8000` để nhận kết nối từ container.

Trong `.env` của PDFluent, đặt `ERP_INTEGRATION_API_KEY` bằng `PDFLUENT_API_KEY`, `ERP_NOTIFICATION_MODE=frappe_callback`, `ERP_CALLBACK_API_KEY` bằng `AI_CALLBACK_API_KEY`, và `ERP_CALLBACK_URL=http://localhost:8888/api/method/document_manager.document_manager.api.ai_integration.receive_status` khi PDFluent chạy trực tiếp trên máy host. Địa chỉ callback phải truy cập được từ nơi chạy worker PDFluent. Sau khi điền env, chạy lại ERP `configurator`, khởi động lại API/worker PDFluent, rồi chạy migration hai bên như hướng dẫn dưới đây. Giữ các khóa ngoài Git.

Nếu chưa chạy PDFluent, để trống ba biến AI trong `docker/.env.dev` và giữ chế độ số hóa tắt; các chức năng khai thác hiện tại vẫn hoạt động.

Trong `.env.prod` của ERP, đặt `PDFLUENT_API_URL` là URL FastAPI mà container ERP truy cập được, `PDFLUENT_API_KEY` là khóa dạng `sk_live_...`, và `AI_CALLBACK_API_KEY` là một khóa ngẫu nhiên khác. Nếu PDFluent chạy trên cùng server, dùng `http://host.docker.internal:8000`; `docker-compose.prod.yml` đã ánh xạ tên này cho backend và `queue-long`. Giới hạn cổng PDFluent bằng firewall. Nếu chạy trên server khác, dùng URL mạng riêng hoặc HTTPS. Chạy lại `configurator` để ghi các giá trị vào Frappe site config. Không đặt hai khóa trong mã nguồn.

Trong `.env` của PDFluent, đặt `ERP_INTEGRATION_API_KEY` bằng `PDFLUENT_API_KEY`, `ERP_NOTIFICATION_MODE=frappe_callback`, `ERP_CALLBACK_API_KEY` bằng `AI_CALLBACK_API_KEY`, và `ERP_CALLBACK_URL` bằng URL đầy đủ của Frappe:

```text
https://<domain-erp>/api/method/document_manager.document_manager.api.ai_integration.receive_status
```

Chạy Alembic migration của PDFluent và `bench --site <site> migrate` của ERP trước khi khởi động lại API/worker. PDFluent cần worker Celery trên hàng đợi `summarize` và `maintenance`, cùng Celery Beat. Nếu tắt callback, cán bộ có thể dùng **Làm mới trạng thái AI** để lấy JSON và đồng bộ job; nếu bật callback, Frappe nhận các sự kiện theo thứ tự và gửi thông báo cho người duyệt.

Job hiện nhận tối đa 100 văn bản có tệp PDF, PNG, JPG/JPEG hoặc WebP. Các định dạng Office/TIFF cần chuyển sang PDF trước khi bóc tách. Kết quả AI luôn gắn với mã văn bản ERP, phiên bản và SHA-256 nguồn; người có quyền duyệt xác nhận từng trường trước khi dữ liệu được ghi vào hồ sơ.
