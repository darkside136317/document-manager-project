"""Seed fictional archive data for the local development UI and user guide.

Run from the repository root (the site is deliberately fixed to docmanager.local):

    cd docker
    docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml \
      exec -T -w /home/frappe/frappe-bench/sites backend \
      /home/frappe/frappe-bench/env/bin/python - up < ../scripts/demo/seed_user_guide.py

Use ``down`` instead of ``up`` to remove only the records created by this script.
The generated reader password is printed only when the account is first created.
"""

import secrets
import sys

import frappe

SITE = "docmanager.local"
PREFIX = "HD MẪU"
READER_EMAIL = "demo.reader@example.com"

ARCHIVES = [
    {
        "agency": "HD MẪU - Trung tâm Lưu trữ tỉnh Minh Hòa",
        "fonds": "HD MẪU - UBND tỉnh Minh Hòa",
        "code": "HD-UBND",
        "mode": "Công khai",
        "groups": [
            ("HD MẪU - Hành chính và tổ chức", "HD-HC", [
                ("HD MẪU - Công tác tổ chức 2023", "01", [
                    ("HD MẪU - Kế hoạch công tác năm 2023", "01", [
                        ("HD MẪU - Kế hoạch triển khai nhiệm vụ năm 2023", "KH-01/2023", "2023-01-10"),
                        ("HD MẪU - Thông báo lịch họp giao ban quý I", "TB-04/2023", "2023-02-01"),
                    ]),
                    ("HD MẪU - Tổng kết hoạt động năm 2023", "02", [
                        ("HD MẪU - Báo cáo kết quả hoạt động năm 2023", "BC-15/2023", "2023-12-15"),
                    ]),
                ]),
            ]),
            ("HD MẪU - Văn hóa và giáo dục", "HD-VH", [
                ("HD MẪU - Chương trình văn hóa 2024", "02", [
                    ("HD MẪU - Tổ chức ngày hội đọc sách 2024", "03", [
                        ("HD MẪU - Kế hoạch tổ chức ngày hội đọc sách", "KH-08/2024", "2024-03-05"),
                        ("HD MẪU - Thư mời tham gia ngày hội đọc sách", "TM-11/2024", "2024-03-12"),
                    ]),
                    ("HD MẪU - Hoạt động thư viện năm 2024", "04", [
                        ("HD MẪU - Báo cáo hoạt động thư viện", "BC-20/2024", "2024-12-10"),
                    ]),
                ]),
            ]),
        ],
    },
    {
        "agency": "HD MẪU - Sở Giáo dục Minh Hòa",
        "fonds": "HD MẪU - Sở Giáo dục Minh Hòa",
        "code": "HD-SGD",
        "mode": "Theo cấp phép",
        "groups": [
            ("HD MẪU - Kế hoạch đào tạo", "HD-DT", [
                ("HD MẪU - Kế hoạch năm học 2024", "01", [
                    ("HD MẪU - Kế hoạch bồi dưỡng giáo viên", "01", [
                        ("HD MẪU - Kế hoạch tập huấn giáo viên", "KH-02/2024", "2024-02-20"),
                    ]),
                ]),
            ]),
        ],
    },
]


def ensure(doctype, title_field, title, **values):
    name = frappe.db.get_value(doctype, {title_field: title}, "name")
    if name:
        return name
    return frappe.get_doc({"doctype": doctype, title_field: title, **values}).insert(ignore_permissions=True).name


def seed():
    if not frappe.db.exists("Confidentiality Level", "Thường"):
        ensure("Confidentiality Level", "level_name", "Thường", priority=1)
    counts = {"fonds": 0, "files": 0, "documents": 0}
    for entry in ARCHIVES:
        agency = ensure("Archival Agency", "agency_name", entry["agency"], is_active=1)
        fonds = ensure("Fonds", "fonds_name", entry["fonds"], archival_agency=agency,
                       fonds_code=entry["code"], access_mode=entry["mode"], status="Đã hoàn thành",
                       description="Dữ liệu giả phục vụ hướng dẫn sử dụng trên môi trường dev.")
        counts["fonds"] += 1
        for group_title, group_code, catalogs in entry["groups"]:
            group = ensure("Record Group", "group_title", group_title, fonds=fonds,
                           group_code=group_code, status="Đã hoàn thành")
            for catalog_title, catalog_code, files in catalogs:
                catalog = ensure("Catalog", "catalog_title", catalog_title, record_group=group,
                                 catalog_number=catalog_code)
                for file_title, file_number, documents in files:
                    archive_file = ensure("Archival File", "file_title", file_title, catalog=catalog,
                                          fonds=fonds, record_group=group, file_number=file_number,
                                          confidentiality_level="Thường", status="Đã hoàn thành",
                                          description="Hồ sơ minh họa. Không chứa tài liệu thật.")
                    counts["files"] += 1
                    for title, number, date in documents:
                        ensure("Archive Document", "document_title", title, archival_file=archive_file,
                               document_number=number, document_date=date, author=entry["agency"],
                               description="Bản ghi mô tả minh họa; chưa đính kèm tệp số.")
                        counts["documents"] += 1
    if not frappe.db.exists("User", READER_EMAIL):
        password = secrets.token_urlsafe(18)
        user = frappe.get_doc({"doctype": "User", "email": READER_EMAIL,
                               "first_name": "Lan", "last_name": "Độc giả Mẫu",
                               "user_type": "Website User", "send_welcome_email": 0,
                               "new_password": password, "roles": [{"role": "Reader"}]})
        user.flags.no_welcome_mail = True
        user.insert(ignore_permissions=True)
        print("Tài khoản độc giả mẫu:", READER_EMAIL)
        print("Mật khẩu dev (chỉ hiện lần đầu):", password)
    if not frappe.db.get_value("Reader", {"user": READER_EMAIL}, "name"):
        ensure("Reader", "full_name", "HD MẪU - Nguyễn Thị Lan", user=READER_EMAIL,
               email=READER_EMAIL, max_confidentiality_priority=1, is_active=1,
               organization="Trường THPT Minh Hòa", phone="0900000000")
    print("Đã bảo đảm dữ liệu mẫu:", counts)


def remove():
    reader = frappe.db.get_value("Reader", {"user": READER_EMAIL}, "name")
    if reader:
        frappe.delete_doc("Reader", reader, force=True, ignore_permissions=True)
    if frappe.db.exists("User", READER_EMAIL):
        frappe.delete_doc("User", READER_EMAIL, force=True, ignore_permissions=True)
    for doctype, field in [
        ("Archive Document", "document_title"), ("Archival File", "file_title"),
        ("Catalog", "catalog_title"), ("Record Group", "group_title"),
        ("Fonds", "fonds_name"), ("Archival Agency", "agency_name"),
    ]:
        for name in frappe.get_all(doctype, filters={field: ["like", PREFIX + "%"]}, pluck="name"):
            frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
    print("Đã xóa dữ liệu mẫu HD MẪU")


if __name__ == "__main__":
    mode = sys.argv[-1]
    if mode not in ("up", "down"):
        sys.exit("Dùng up hoặc down")
    frappe.init(site=SITE)
    frappe.connect()
    if frappe.local.site != SITE:
        sys.exit("Chỉ chạy cho docmanager.local")
    frappe.set_user("Administrator")
    try:
        (seed if mode == "up" else remove)()
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise
