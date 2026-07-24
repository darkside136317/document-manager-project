# 🚀 Hướng dẫn Triển khai Production — Document Manager

## Yêu cầu Server

| Thành phần | Tối thiểu | Khuyến nghị |
|-----------|----------|-------------|
| **CPU** | 2 cores | 4+ cores |
| **RAM** | 4 GB | 8+ GB |
| **Disk** | 40 GB SSD | 100+ GB SSD |
| **OS** | Ubuntu 22.04+ / Debian 12+ | Ubuntu 24.04 LTS |
| **Docker** | Docker Engine 24+ | Docker Engine 27+ |
| **Network** | Port 80/443 mở | Reverse proxy (Traefik/Nginx) |

---

## Bước 1: Chuẩn bị Server

```bash
# 1.1 — Cài Docker Engine + Docker Compose v2
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Logout rồi login lại

# 1.2 — Kiểm tra
docker --version        # >= 24.0
docker compose version  # >= 2.20

# 1.3 — Clone project lên server
git clone <your-repo-url> /opt/docmanager
cd /opt/docmanager
```

---

## Bước 2: Cấu hình MongoDB Atlas

### 2.1 — Tạo tài khoản MongoDB Atlas
1. Truy cập https://www.mongodb.com/atlas
2. Đăng ký tài khoản → Tạo **Organization** → **Project**

### 2.2 — Tạo Cluster
1. **Database** → **Build a Database**
2. Chọn **M0 Free** (512MB) hoặc **M10+** (production)
3. Region: **Singapore** (gần VN nhất)
4. Cluster Name: `docmanager-cluster`

### 2.3 — Tạo Database User
1. **Security** → **Database Access** → **Add New Database User**
2. Username: `docmanager_user`, Password: strong password
3. Role: **Read and write to any database**

### 2.4 — Whitelist IP
1. **Security** → **Network Access** → **Add IP Address**
2. Nhập IP server cụ thể (hoặc `0.0.0.0/0` cho dev)

### 2.5 — Lấy Connection String
1. **Database** → **Connect** → **Drivers** → **Python**
2. Copy connection string dạng:
```
mongodb+srv://docmanager_user:<password>@cluster.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

---

## Bước 3: Tạo file .env

```bash
cd /opt/docmanager/docker
cp .env.production .env
nano .env
```

Các giá trị BẮT BUỘC thay đổi:

| Biến | Hành động |
|------|----------|
| `FRAPPE_SITE_NAME` | Domain thực (ví dụ: `luutru.coquan.gov.vn`) |
| `ADMIN_PASSWORD` | `openssl rand -base64 24` |
| `MARIADB_ROOT_PASSWORD` | `openssl rand -base64 24` |
| `MONGODB_ATLAS_URI` | Connection string từ Bước 2.5 |
| `MEILISEARCH_MASTER_KEY` | `openssl rand -hex 16` |
| `GUNICORN_WORKERS` | `2 × CPU cores + 1` |

---

## Bước 4: Build Docker Image

```bash
cd /opt/docmanager

docker build \
  -t docmanager-custom:v16.26.2 \
  --build-arg ERPNEXT_VERSION=v16.26.2 \
  -f docker/Dockerfile .

docker images | grep docmanager
```

---

## Bước 5: Khởi động hệ thống

```bash
cd /opt/docmanager/docker

# Khởi động (base + production override)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Xem logs — chờ create-site hoàn thành (~2-5 phút)
docker compose logs -f create-site

# Kiểm tra services
docker compose ps
```

---

## Bước 6: Cài đặt App

```bash
# Vào container backend
docker compose exec backend bash

# Cài app
bench --site docmanager.yourdomain.com install-app document_manager

# Migrate
bench --site docmanager.yourdomain.com migrate

exit
```

---

## Bước 7: Cấu hình Services trong Frappe

```bash
# MongoDB Atlas
docker compose exec backend bench --site <site> set-config \
  mongodb_atlas_uri "mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority"

docker compose exec backend bench --site <site> set-config \
  mongodb_database "docmanager_files"

# Meilisearch
docker compose exec backend bench --site <site> set-config \
  meilisearch_host "http://meilisearch:7700"

docker compose exec backend bench --site <site> set-config \
  meilisearch_master_key "YOUR_MEILI_MASTER_KEY"
```

---

## Bước 8: Cấu hình SSL

### Option A: Nginx bên ngoài Docker

```nginx
server {
    listen 80;
    server_name docmanager.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name docmanager.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/docmanager.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/docmanager.yourdomain.com/privkey.pem;

    client_max_body_size 100m;
    proxy_read_timeout 300;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Cài Let's Encrypt:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d docmanager.yourdomain.com
```

---

## Bước 9: Kiểm tra

1. Truy cập `https://docmanager.yourdomain.com` → Login Administrator
2. **Setup > Document Manager Settings** → Test MongoDB + Meilisearch connections
3. Tạo test: Fonds → Record Group → Catalog → Archival File → Archive Document (upload PDF)
4. Kiểm tra: text extraction (`docker compose logs queue-long`), search index, portal `/search`

---

## Bước 10: Backup tự động

```bash
# Crontab — backup lúc 2:00 AM hàng ngày
crontab -e

# Thêm dòng:
0 2 * * * cd /opt/docmanager/docker && docker compose exec -T backend bench --site <site> backup --with-files >> /var/log/docmanager-backup.log 2>&1
```

MongoDB Atlas M10+: tự động backup. M0 Free: backup thủ công qua Atlas UI.

---

## Troubleshooting

| Vấn đề | Giải pháp |
|--------|----------|
| `create-site` timeout | Tăng RAM, xem: `docker compose logs create-site` |
| MongoDB refused | Kiểm tra IP whitelist Atlas, URI trong site_config |
| Meilisearch 401 | Kiểm tra master_key khớp giữa compose và site_config |
| Text extract không chạy | `docker compose logs queue-long` |
| Trang trắng | `docker compose exec backend bench --site <site> clear-cache` |

---

## Cập nhật

```bash
git pull origin main
docker build -t docmanager-custom:v16.26.2 -f docker/Dockerfile .
cd docker
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose exec backend bench --site <site> migrate
docker compose exec backend bench --site <site> clear-cache
```
