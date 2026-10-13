# Document Manager

Phần mềm quản lý và khai thác hồ sơ, tài liệu lưu trữ số hóa cho đơn vị lưu trữ (trung tâm lưu trữ, thư viện, cơ quan nhà nước).
Xây dựng thành một ứng dụng **Frappe v16** tên `document_manager`, triển khai bằng **Docker**, thiết kế cho kho khoảng **một triệu văn bản**.

Phần mềm đáp ứng đủ tám phân hệ của *Phụ lục 03 – Danh sách tính năng phần mềm quản lý và khai thác hồ sơ số hóa*.

---

## Mục lục

- [Hai giao diện](#hai-giao-diện)
- [Chức năng theo phân hệ](#chức-năng-theo-phân-hệ)
- [Vai trò người dùng](#vai-trò-người-dùng)
- [Kiến trúc](#kiến-trúc)
- [Chạy thử trên máy](#chạy-thử-trên-máy)
- [Triển khai sản xuất](#triển-khai-sản-xuất)
- [Cấu hình](#cấu-hình)
- [Kiểm thử](#kiểm-thử)
- [Hiệu năng](#hiệu-năng)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Giới hạn đã biết](#giới-hạn-đã-biết)
- [Tài liệu](#tài-liệu)

---

## Hai giao diện

| | Cán bộ | Độc giả |
|---|---|---|
| Địa chỉ | `/dashboard` | `/portal` và các trang công khai `/gioi-thieu`, `/lanh-dao`, `/co-cau`, `/lien-he`, `/huong-dan` |
| Đăng nhập | `/dang-nhap` (dùng chung) | `/dang-nhap`, đăng ký tại `/dang-ky` |
| Công nghệ | Ứng dụng một trang Vue 3 + Vite + Tailwind (`apps/document_manager/frontend`) | Jinja + Alpine.js, dựng phía máy chủ, ưu tiên điện thoại |

Cả hai dùng chung một bộ màu (`public/css/theme-tokens.css`), có giao diện sáng/tối, dùng được trên điện thoại và không tải gì từ CDN.
Độc giả không vào được `/dashboard`; mọi API đều kiểm quyền lại phía máy chủ.

## Chức năng theo phân hệ

| # | Phân hệ | Nội dung chính | Màn hình |
|---|---|---|---|
| 1 | **Khai thác trực tuyến** | Trang giới thiệu đơn vị, lãnh đạo, cơ cấu, liên hệ; đăng ký (có duyệt), đăng nhập, quên mật khẩu; tìm hồ sơ và văn bản cơ bản/nâng cao (cả theo nội dung tệp); "Thêm vào phiếu" ngay từ kết quả; phiếu sử dụng, phiếu sao chụp; góp ý; thông báo trong ứng dụng | `/portal`, `/portal/phieu`, `/portal/sao-chep`, `/portal/gop-y`, `/portal/tai-khoan` |
| 2 | **Biên mục** | Cây Phông → Khối → Mục lục → Hồ sơ → Văn bản; thêm, sửa, xóa có luật (không xóa cha còn con, chuyển hồ sơ thì văn bản đi theo); tải nhiều tệp cùng lúc; xem trước PDF/ảnh; in phiếu mô tả, mục lục hồ sơ; tìm kiếm nâng cao, bộ lọc đã lưu, Ctrl+K | `/dashboard/bien-muc`, `/dashboard/tim-kiem` |
| 3 | **Danh mục** | Cơ quan lưu trữ, phông, loại hình, nhóm tài liệu, kho/phòng/giá/hộp, mức độ mật, khung phân loại, từ điển nhập nhanh một cấp và nhiều cấp | `/dashboard/danh-muc/...` |
| 4 | **Thống kê, báo cáo** | 11 báo cáo (phông, mục lục, hồ sơ, văn bản, thống kê theo phông/loại hình/kho, độc giả, phiếu, quá hạn…); tải CSV, XLSX; in có đầu đề đơn vị, PDF; tổng kiểm kê phông | `/dashboard/bao-cao`, `/dashboard/kiem-ke` |
| 5 | **Xuất, nhập XML** | Xuất theo bộ lọc với trường chọn theo từng cấp; nhập có phân tích, chạy thử, nhật ký từng dòng; lược đồ XSD tải được; chống tệp độc hại | `/dashboard/trao-doi-du-lieu` |
| 6 | **Quản lý độc giả** | Độc giả và nhóm quyền (mức mật, phạm vi phông, tính năng, hạn mức); hàng đợi phiếu; quyết định từng mục; lãnh đạo duyệt tài liệu mật; giao, nhận trả, gia hạn, quá hạn; mẫu phiếu và mẫu đăng ký; in phiếu, thẻ độc giả | `/dashboard/doc-gia/...` |
| 7 | **Bảo quản** | Sao lưu cơ sở dữ liệu và tệp (tăng dần, mã SHA-256, theo lịch); kiểm tra toàn vẹn cơ sở dữ liệu, siêu dữ liệu và từng tệp; khôi phục tệp theo đợt từ kết quả kiểm tra; khôi phục cơ sở dữ liệu có kiểm soát | `/dashboard/bao-quan/sao-luu`, `kiem-tra`, `khoi-phuc` |
| 8 | **Quản trị** | Người dùng (liên kết đặt mật khẩu dùng một lần), nhóm cán bộ, ma trận phân quyền, nhật ký (lọc, CSV, dọn có kiểm soát), giám sát hệ thống, thiết lập hệ thống, thông tin đơn vị | `/dashboard/quan-tri/...` |

## Vai trò người dùng

| Vai trò | Làm được gì |
|---|---|
| **Quản trị tài liệu** (`Document Admin`) | Mọi nghiệp vụ, người dùng, thiết lập, xuất/nhập XML, sao lưu, nhật ký |
| **Biên mục viên** (`Cataloger`) | Danh mục, biên mục, tổng kiểm kê; báo cáo về kho tài liệu |
| **Cán bộ phòng đọc** (`Reading Room Officer`) | Độc giả, đăng ký, phiếu sử dụng và sao chụp, góp ý; báo cáo độc giả |
| **Lãnh đạo** (`Archive Leader`) | Xem toàn bộ dữ liệu và báo cáo; duyệt phiếu có tài liệu cần lãnh đạo duyệt |
| **Cán bộ bảo quản** (`Preservation Officer`) | Sao lưu, kiểm tra toàn vẹn, khôi phục |
| **Độc giả** (`Reader`) | Tra cứu trong phạm vi nhóm quyền, gửi phiếu, góp ý |

Bảo vệ: quản trị viên không tạo được tài khoản System Manager, không tự khóa hay tự hạ quyền mình, và hệ thống luôn giữ ít nhất một quản trị viên.
Độc giả chỉ thấy tài liệu đã công bố (không "Nháp", không "Đã tiêu hủy"), không vượt mức mật và phạm vi phông của nhóm.

## Kiến trúc

```
Trình duyệt ─▶ nginx (frontend) ─▶ gunicorn (backend: Frappe + document_manager)
                                      │
                                      ├─▶ MariaDB 11.8           siêu dữ liệu, phiếu, nhật ký
                                      ├─▶ Redis                  bộ nhớ đệm, hàng đợi
                                      ├─▶ worker long/short, scheduler
                                      │      trích xuất văn bản, lập chỉ mục, sao lưu, kiểm tra, xuất/nhập XML
                                      ├─▶ Meilisearch            tìm toàn văn (dự phòng bằng MariaDB khi hỏng)
                                      └─▶ MongoDB Atlas GridFS   tệp gốc và bản xem trước (tùy chọn)
```

Nguyên tắc:

- **Một nguồn chính sách cho độc giả** (`policy.get_reader_scope`): dùng chung cho truy vấn SQL, `has_permission`, tìm kiếm, tải tệp và phiếu.
- **API mỏng, nghiệp vụ trong `services/`**: `api/*.py` chỉ kiểm quyền và đầu vào. Màn hình danh mục dùng API chung (`api/crud.py`, `api/meta.py`), chỉ mở các DocType đã đăng ký trong `constants.py` và để Frappe tự kiểm quyền, ràng buộc, liên kết.
- **Việc dài chạy nền** có tiến độ, dừng và chạy tiếp được: sao lưu, kiểm tra, khôi phục, xuất/nhập.
- **Mọi thao tác quan trọng được ghi nhật ký** (`services/audit.py`).

## Chạy thử trên máy

Yêu cầu: Docker Engine 24+ với Compose v2, Docker được cấp ít nhất 8 GB RAM.

```bash
git clone <địa-chỉ-repo> document-manager-project
cd document-manager-project/docker
cp .env.example .env      # điền mật khẩu và khóa (xem mục Cấu hình)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
docker compose logs -f create-site      # lần đầu: tạo site, cài ứng dụng (vài phút)
```

Mở **http://localhost:8888** (cổng `HTTP_PUBLISH_PORT`):

- `http://localhost:8888/gioi-thieu`: trang công khai;
- `http://localhost:8888/dang-nhap`: đăng nhập `Administrator` với mật khẩu `ADMIN_PASSWORD`, rồi vào `/dashboard`.

Ở chế độ phát triển, mã nguồn được gắn thẳng vào container: sửa Python, mẫu trang hay DocType có hiệu lực sau vài giây
(trình theo dõi `dev-watcher` tự chạy `migrate` khi cần), giao diện cán bộ được dịch vụ `staff-ui` build lại tự động.

Một số lệnh hay dùng (chạy trong thư mục `docker/`):

```bash
C="docker compose -f docker-compose.yml -f docker-compose.dev.yml"
$C ps                                                  # trạng thái dịch vụ
$C logs -f dev-watcher                                 # lỗi migrate nếu có
$C restart queue-long queue-short scheduler            # sau khi thêm tệp Python mới
$C exec backend bench --site <site> migrate
```

Nếu Redis bị dừng và trang báo lỗi 502: `$C up -d` rồi `docker restart docker-frontend-1`.

## Triển khai sản xuất

```bash
cd docker
cp .env.example .env    # tên miền thật, mật khẩu mạnh, khóa Meilisearch mới
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose logs -f create-site
```

Image có tầng Node: chạy kiểm thử giao diện và build giao diện cán bộ, nên máy chủ không cần cài Node.
Site mới tự gieo vai trò, mức độ mật, workflow, nhóm độc giả mặc định và giá trị mặc định của thiết lập; không cần cài ứng dụng bằng tay.
Đặt một reverse proxy có TLS phía trước nginx của compose, và sao chép định kỳ thư mục sao lưu ra ngoài máy chủ.

Cập nhật phiên bản: `git pull`, build lại, `up -d`, rồi `bench --site <site> migrate`. CI phát hành sẵn image lên GHCR khi push lên `main` hoặc tag `v*`.

## Cấu hình

Biến môi trường trong `docker/.env`:

| Biến | Ý nghĩa |
|---|---|
| `FRAPPE_SITE_NAME` | Tên site, cũng là tên miền |
| `ADMIN_PASSWORD` | Mật khẩu `Administrator` |
| `MARIADB_ROOT_PASSWORD` | Mật khẩu root MariaDB |
| `MONGODB_ATLAS_URI`, `MONGODB_DATABASE` | GridFS cho tệp (tùy chọn) |
| `MEILISEARCH_HOST`, `MEILISEARCH_MASTER_KEY` | Máy tìm kiếm toàn văn; khóa bắt buộc đổi |
| `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT` | Số tiến trình web |
| `HTTP_PUBLISH_PORT`, `CLIENT_MAX_BODY_SIZE`, `PROXY_READ_TIMEOUT` | nginx |

Tùy chọn trong `site_config.json` của site:

| Khóa | Ý nghĩa |
|---|---|
| `dm_allow_db_restore` | `1` cho phép hệ thống tự khôi phục cơ sở dữ liệu (mặc định tắt: chỉ hiện hướng dẫn đã kiểm tra) |
| `dm_db_root_password` | Mật khẩu root dùng khi tự khôi phục (hoặc biến môi trường `DB_ROOT_PASSWORD`) |

Thiết lập nghiệp vụ nằm trên giao diện: **Quản trị → Thiết lập hệ thống** (sao lưu tự động, thời hạn giữ, chính sách mật khẩu, số lần đăng nhập sai)
và **Độc giả → Thiết lập độc giả** (hạn mức phiếu, gia hạn, nhắc hạn, đăng ký).

## Kiểm thử

| Lớp | Quy mô | Cách chạy |
|---|---|---|
| Python (Frappe) | 426 test, 19 module | `docker compose exec backend bench --site <site> run-tests --app document_manager --module document_manager.tests.test_<tên>` |
| Giao diện cán bộ (vitest) | 185 test | `cd apps/document_manager/frontend && npm test` |
| HTTP đầu-cuối | 497 kiểm tra, gồm ma trận quyền của mọi API | `DM_E2E_PASSWORD=… python scripts/e2e/e2e_http.py` |
| Trình duyệt (Playwright) | 8 luồng, 126 bước | `scripts/e2e/ui/<luồng>.mjs` |
| Hiệu năng | 1 triệu văn bản | `scripts/perf/volume_check.py` trên một site thử riêng |

Kiểm thử đầu-cuối cần tài khoản thử: `scripts/e2e/accounts.py up` trước, `down` sau (xem đầu tệp).

CI (`.github/workflows/ci.yml`): kiểm tra tĩnh (biên dịch, ruff, JSON, cú pháp JS, compose) → vitest và build giao diện →
build image, tạo site mới sạch, `migrate`, chạy toàn bộ 19 module Python → phát hành image lên GHCR.

## Hiệu năng

Đo trên site thử với 1.000.000 văn bản, 200.000 hồ sơ và 1.000.000 dòng nhật ký:

| Loại thao tác | Thời gian |
|---|---|
| Danh sách theo hồ sơ/mục lục, cây biên mục, hàng đợi phiếu, thanh bên | dưới 0,15 s |
| Danh sách văn bản mới nhất, tìm hồ sơ, tổng quan, nhật ký, giám sát | 0,3–1 s |
| Báo cáo theo phông | khoảng 1 s; báo cáo toàn kho không lọc 4–9 s |
| 27 phép kiểm tra toàn vẹn (chạy nền) | khoảng 15 s |

Tìm theo chữ bằng cơ sở dữ liệu (chỉ dùng khi Meilisearch hỏng) có trần 8 giây và tổng số kết quả có trần 10.000.
Khi kho lớn, nên đặt `innodb_buffer_pool_size` bằng 50–70% RAM của máy chạy MariaDB (`docker/mariadb/my_custom.cnf`).

## Cấu trúc thư mục

```
document-manager-project/
├── apps/document_manager/
│   ├── frontend/                   giao diện cán bộ (Vue 3): src/pages, src/components, src/lib, tests
│   └── document_manager/
│       ├── hooks.py, patches.txt
│       ├── public/                 css, js (giao diện độc giả), staff/ (kết quả build, không đưa vào git)
│       ├── templates/              khung trang độc giả, mẫu in
│       ├── www/                    trang độc giả và trang công khai
│       ├── patches/                di chuyển dữ liệu khi nâng cấp
│       ├── tests/                  kiểm thử Python
│       └── document_manager/
│           ├── doctype/            44 DocType
│           ├── api/                API cho hai giao diện (kiểm quyền)
│           ├── services/           nghiệp vụ: archive, search, reports, exchange, preservation, audit…
│           ├── setup/              gieo dữ liệu cho site mới và sau mỗi lần migrate
│           └── constants.py, permissions.py, policy.py
├── docker/                         Dockerfile, compose (cơ sở, dev, prod), cấu hình MariaDB, trình theo dõi dev
├── scripts/
│   ├── e2e/                        tài khoản thử, kiểm tra HTTP, luồng trình duyệt
│   ├── perf/volume_check.py        đo hiệu năng ở quy mô lớn
│   └── demo/seed_organization.py   nội dung mẫu cho trang giới thiệu đơn vị
└── .github/workflows/ci.yml
```

## Giới hạn đã biết

- **MongoDB Atlas là tùy chọn**: khi không kết nối được (thường do IP máy chủ chưa được cho phép trong Atlas), tệp được giữ ở thư mục riêng của Frappe và việc kiểm tra bản GridFS ghi cảnh báo.
- **Chưa có OTP (2FA)** trên trang `/dang-nhap`; tài khoản bật 2FA đăng nhập qua `/login` của Frappe.
- **Lược đồ XML là lược đồ nội bộ** (có XSD tải được), chưa theo một XSD chính thức.
- **Khôi phục cơ sở dữ liệu tự động tắt mặc định**; xem mục Cấu hình.
- **Độc giả chỉ yêu cầu được tài liệu họ đã xem được**; chưa có cấp quyền xem có thời hạn cho tài liệu vượt mức.
- **ERPNext vẫn nằm trong image** dù ứng dụng không dùng.

## Tài liệu

Tài liệu chi tiết bằng tiếng Việt trong thư mục `docs/`:

| Tệp | Nội dung |
|---|---|
| `DEPLOYMENT.md` | Triển khai sản xuất, TLS, cập nhật, xử lý sự cố |
| `KICH_BAN_DEMO_CHUC_NANG_VA_PHAN_QUYEN.md` | Kịch bản demo và danh sách nghiệm thu phân quyền |
| `UI_CUSTOMIZATION.md` | Đổi nhận diện giao diện |
| `TRACEABILITY.md` | Từng dòng của Phụ lục 03 → màn hình, API, kiểm thử |
| `SAO_LUU_KHOI_PHUC.md` | Vận hành sao lưu, kiểm tra toàn vẹn, khôi phục |
| `HIEU_NANG.md` | Cách đo và kết quả ở một triệu văn bản |
| `DEV_WORKFLOW.md` | Quy trình phát triển và CI/CD |
| `PHAN_QUYEN_DOC_GIA.md`, `XML_SCHEMA.md` | Phân quyền độc giả; lược đồ XML |
| `BAO_CAO_REFACTOR.md` | Báo cáo quá trình tái cấu trúc |
