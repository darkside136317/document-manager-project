# Quy trình phát triển và build tự động

Có hai lớp tự động:

| Khi nào | Cơ chế | Kết quả |
|---|---|---|
| Đang phát triển trên máy | `docker/docker-compose.dev.yml` | Sửa file là chạy ngay, không cần build image |
| Push lên GitHub | `.github/workflows/ci.yml` | Kiểm tra, chạy test, build và đẩy image lên GHCR |

## 1. Phát triển cục bộ (hot reload)

Chạy từ thư mục `docker/`:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml up -d --no-build
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml restart frontend websocket
```

Mã nguồn `apps/document_manager` được bind-mount vào backend, **frontend (nginx phục vụ JS/CSS)**, worker, scheduler và dịch vụ `dev-watcher`. Sau khi lưu file, vài giây sau thay đổi có hiệu lực:

| Bạn sửa | Điều gì tự xảy ra |
|---|---|
| File `.py` | gunicorn `--reload` nạp lại; worker và scheduler được `dev/autoreload.py` khởi động lại |
| `templates/`, `www/*.html`, `public/` (JS, CSS) | `dev-watcher` xóa website cache; thư mục `public` đã là liên kết trực tiếp tới assets |
| DocType, Workflow (`setup_workflows.py`), `hooks.py`, patch, Print Format, Report JSON | `dev-watcher` chạy `bench migrate` rồi xóa cache |
| Giao diện cán bộ `/dashboard` (Vue) trong `apps/document_manager/frontend/src` | dịch vụ `staff-ui` chạy `vite build --watch`: build lại sau 2–5 giây, nhấn F5 để xem |

Xem nhật ký của watcher, nơi báo lỗi migrate nếu có:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml logs -f dev-watcher
```

Nếu migrate lỗi, sửa file rồi lưu lại, watcher sẽ chạy lại.

Chạy test trong container (tên module là `document_manager.tests.test_<tên>`, nằm ở `apps/document_manager/document_manager/tests/`):

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml exec backend bench --site <tên-site> run-tests --app document_manager --module document_manager.tests.test_request_workflow
```

Đừng chạy hai lượt test cùng lúc trên một site (dùng chung cơ sở dữ liệu), và chờ `dev-watcher` migrate xong sau khi sửa DocType hoặc `hooks.py`.
Sau khi **thêm file Python mới** hoặc đổi mã mà worker đang giữ (`services/`), khởi động lại worker cho chắc:
`docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml restart queue-long queue-short scheduler`.

Giao diện cán bộ (Vue 3 + Vite + Tailwind, thư mục `apps/document_manager/frontend`):

```bash
cd apps/document_manager/frontend
npm install          # lần đầu
npm test             # 184 bài kiểm thử đơn vị (vitest + jsdom)
npm run build        # ra document_manager/public/staff (đã được .gitignore)
```

Trong chế độ dev, dịch vụ `staff-ui` tự `npm ci` (modules nằm trong volume `staff-ui-node-modules`, không đụng thư mục trên máy) rồi build lại mỗi khi sửa. Trang `www/dashboard.py` đọc `public/staff/.vite/manifest.json` để nạp đúng file JS/CSS đã băm tên. Image Docker build giao diện ở stage `staff-ui` (có chạy `npm test`), nên không cần Node trên máy chủ.

Lưu ý:

- Sau khi chuyển từ chế độ prod sang dev lần đầu, tạo lại `frontend` (`up -d --force-recreate frontend`) rồi hard refresh trình duyệt (Ctrl+F5): nginx chỉ gửi `ETag`/`Last-Modified` nên trình duyệt có thể giữ bản JS cũ.

- Chế độ dev không có giới hạn bộ nhớ và `restart: always` của `docker-compose.prod.yml`. Không dùng cho sản xuất.
- Thêm thư viện Python mới (`requirements.txt`) hoặc đổi `Dockerfile` vẫn cần build lại image: `docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml build backend`.
- Trên Windows, inotify không hoạt động với bind mount nên các script dùng polling (độ trễ 1–3 giây).

## 2. CI/CD trên GitHub

`ci.yml` chạy cho mỗi push, pull request và có thể chạy tay (`workflow_dispatch`):

1. **static**: biên dịch Python, ruff (chỉ lỗi thật), kiểm tra JSON, cú pháp JS, tính hợp lệ của các file compose.
   **frontend**: `npm ci`, vitest, `vite build` cho giao diện cán bộ.
2. **test**: build image, tạo site mới sạch (ERPNext + document_manager) trong Docker, chạy `bench migrate` (site mới phải tự gieo dữ liệu) rồi chạy toàn bộ 19 module test Python.
3. **publish**: chỉ khi push lên `main` hoặc tag `v*` và test đã đạt. Đẩy image lên `ghcr.io/<chủ-repo>/docmanager-custom` với các tag: phiên bản ERPNext, `latest`, `sha-<mã commit>`, và tên tag git.

Triển khai bản mới lên máy chủ:

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml exec backend bench --site <tên-site> migrate
```

Để compose dùng image từ GHCR, đổi `image:` của các dịch vụ trong `docker-compose.prod.yml` thành `ghcr.io/<chủ-repo>/docmanager-custom:${ERPNEXT_VERSION}`.

Thêm test mới: đặt file `test_*.py` vào `apps/document_manager/document_manager/tests/` và thêm một dòng `run-tests --module ...` vào bước **Run tests** của `ci.yml`.

## 3. Kiểm tra trên stack đang chạy

| Công cụ | Dùng để | Cách chạy |
|---|---|---|
| `scripts/e2e/accounts.py` | Tạo/xóa tài khoản và dữ liệu thử (`up` / `down`); cần mật khẩu trong `DM_E2E_PASSWORD` | `docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml exec -T -e DM_E2E_PASSWORD -w /home/frappe/frappe-bench/sites backend /home/frappe/frappe-bench/env/bin/python - up < ../scripts/e2e/accounts.py` |
| `scripts/e2e/e2e_http.py` | Gần 500 kiểm tra HTTP: ma trận quyền của mọi API, địa chỉ cũ, tệp độc hại | `DM_E2E_PASSWORD=… python scripts/e2e/e2e_http.py [địa-chỉ]` |
| `scripts/e2e/ui/*.mjs` | Tám luồng trình duyệt (Playwright): reader, catalogues, cataloguing, slips, reports, exchange, preservation, admin | `cd scripts/e2e/ui && npm ci && DM_E2E_PASSWORD=… OUT_DIR=out SAMPLES_DIR=samples PW_CHANNEL=msedge node <luồng>.mjs` (tệp mẫu: `python make_sample_files.py samples`) |
| `scripts/perf/volume_check.py` | Đo hiệu năng ở một triệu văn bản trên site thử riêng | xem [HIEU_NANG.md](HIEU_NANG.md) |

Luôn chạy `accounts.py down` sau khi thử xong. Luồng trình duyệt cần các worker đang chạy.

Mẹo trên Windows: Git Bash cần `MSYS_NO_PATHCONV=1` khi chạy `docker compose exec ... -w /đường/dẫn`; tránh `heredoc` nhiều dấu nháy, hãy ghi script ra file rồi chạy.

## 4. Kiến trúc mã nguồn trong một trang

- `api/*.py` là lớp mỏng: kiểm quyền (`assert_capability`, `is_staff`, `assert_feature`), kiểm tra đầu vào, rồi gọi `services/`. Không đặt nghiệp vụ trong `api/`.
- `services/` chứa nghiệp vụ; công việc nền dài đi qua `frappe.enqueue(..., enqueue_after_commit=True)` và có tiến độ, dừng/chạy tiếp.
- `constants.py` là danh sách duy nhất những DocType mà giao diện cán bộ được phép mở (`MASTERS`, `ARCHIVE_SCREENS`, `READER_SCREENS`, …), vai trò cán bộ và danh sách chức năng (`CAPABILITIES`).
- Chi tiết kiến trúc: [TAI_LIEU_KY_THUAT.md](TAI_LIEU_KY_THUAT.md).
- `policy.py` là điểm quyết định quyền duy nhất (`get_access`: quản trị viên, cán bộ, độc giả; phạm vi phông; chức năng); `permissions.py` chỉ nối nó vào các hook của Frappe.
- Thêm một màn hình danh mục: thêm DocType, thêm một dòng vào `constants.py`, giao diện tự có danh sách, biểu mẫu, quyền.
- Giao diện cán bộ: trang ở `frontend/src/pages`, thành phần ở `components`, logic thuần ở `lib` (có vitest). Danh sách phải bỏ qua phản hồi cũ khi bộ lọc đổi (xem `UsersPage.vue`).
- Jinja của Frappe **không tự thoát HTML**: mọi mẫu trang độc giả phải bọc `{% autoescape true %}`.
