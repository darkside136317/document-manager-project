"""Fill the public pages of the reader site with sample content (unit profile, leaders, structure).

Everything is fictional: replace it from the staff area (Desk: Organization Info / Organization Unit).
Run inside the backend container, from the sites directory (the script comes in on stdin):

    docker compose exec -T -w /home/frappe/frappe-bench/sites backend \
        /home/frappe/frappe-bench/env/bin/python - up   < scripts/demo/seed_organization.py
    docker compose exec -T -w /home/frappe/frappe-bench/sites backend \
        /home/frappe/frappe-bench/env/bin/python - down < scripts/demo/seed_organization.py

`up` only writes the fields that are still empty, so a profile an administrator filled in is never
overwritten; `down` removes the sample units and clears the fields `up` filled.
"""
import sys

import frappe

SITE = "docmanager.yourdomain.com"
PROFILE = {
    "org_name": "Trung tâm Lưu trữ Lịch sử",
    "org_type": "Đơn vị sự nghiệp công lập",
    "tagline": "Gìn giữ ký ức, mở rộng tri thức: tra cứu hồ sơ và tài liệu lưu trữ ngay trên trình duyệt của bạn.",
    "address": "12 Phố Ví Dụ, Quận Mẫu, Hà Nội",
    "phone": "024 3999 0000",
    "fax": "024 3999 0001",
    "email": "phongdoc@example.org",
    "website": "https://example.org",
    "reading_room_hours": "Thứ Hai – Thứ Sáu: 8:00 – 11:30, 13:30 – 16:30\nThứ Bảy: 8:00 – 11:30 (hẹn trước)",
    "introduction": "<p>Trung tâm bảo quản và tổ chức khai thác tài liệu lưu trữ có giá trị lịch sử, văn hóa. "
                    "Độc giả có thể tra cứu hồ sơ, văn bản đã được số hóa và gửi yêu cầu sử dụng hoặc sao chụp trực tuyến.</p>"
                    "<p>Đây là nội dung <strong>mẫu</strong>: hãy thay bằng giới thiệu thật của đơn vị.</p>",
    "leadership_info": "<p>Ban lãnh đạo Trung tâm gồm Giám đốc và các Phó Giám đốc phụ trách từng mảng nghiệp vụ.</p>",
    "org_structure": "<p>Trung tâm gồm các phòng chuyên môn, phối hợp từ thu thập, chỉnh lý đến bảo quản và phục vụ độc giả.</p>",
    "reader_guide": "<ul><li>Xuất trình giấy tờ tùy thân khi đến phòng đọc.</li><li>Không mang đồ uống, thức ăn vào khu vực đọc.</li>"
                    "<li>Giữ gìn tài liệu, không tự ý sao chụp khi chưa được duyệt.</li></ul>",
}
LEADERS = [
    ("Nguyễn Văn An", "Giám đốc", "Phụ trách chung, công tác tổ chức và hợp tác."),
    ("Trần Thị Bình", "Phó Giám đốc", "Phụ trách chỉnh lý, biên mục và số hóa tài liệu."),
    ("Lê Minh Châu", "Phó Giám đốc", "Phụ trách bảo quản và khai thác, phục vụ độc giả."),
]
UNITS = [  # (name, parent, head, position, description)
    ("Phòng Hành chính – Tổng hợp", None, "Phạm Thu Dung", "Trưởng phòng", "Văn thư, tổ chức, kế toán và quản trị."),
    ("Phòng Chỉnh lý và Biên mục", None, "Hoàng Văn Em", "Trưởng phòng", "Chỉnh lý, xác định giá trị và lập công cụ tra cứu."),
    ("Tổ Số hóa", "Phòng Chỉnh lý và Biên mục", "Vũ Thị Giang", "Tổ trưởng", "Quét, xử lý ảnh và nhập siêu dữ liệu."),
    ("Phòng Bảo quản", None, "Đặng Quốc Huy", "Trưởng phòng", "Kho, vệ sinh, tu bổ và kiểm tra tình trạng tài liệu."),
    ("Phòng Đọc và Khai thác", None, "Bùi Lan Hương", "Trưởng phòng", "Tiếp nhận độc giả, duyệt phiếu và phục vụ tài liệu."),
]

mode = sys.argv[-1]
frappe.init(site=SITE)
frappe.connect()
frappe.set_user("Administrator")

if mode == "up":
    info = frappe.get_doc("Organization Info")
    for field, value in PROFILE.items():
        if not info.get(field):
            info.set(field, value)
    if not info.leaders:
        for order, (name, position, bio) in enumerate(LEADERS, start=1):
            info.append("leaders", {"full_name": name, "position": position, "bio": bio, "display_order": order, "is_visible": 1})
    info.save(ignore_permissions=True)
    for order, (name, parent, head, position, description) in enumerate(UNITS, start=1):
        if not frappe.db.exists("Organization Unit", name):
            frappe.get_doc({"doctype": "Organization Unit", "unit_name": name, "parent_organization_unit": parent,
                            "head_name": head, "head_position": position, "description": description,
                            "display_order": order, "is_visible": 1}).insert(ignore_permissions=True)
else:
    for name, *_ in reversed(UNITS):
        if frappe.db.exists("Organization Unit", name):
            frappe.delete_doc("Organization Unit", name, force=True, ignore_permissions=True)
    info = frappe.get_doc("Organization Info")
    for field, value in PROFILE.items():
        if info.get(field) == value:
            info.set(field, None)
    info.set("leaders", [row for row in info.leaders if row.full_name not in {l[0] for l in LEADERS}])
    info.flags.ignore_mandatory = True
    info.save(ignore_permissions=True)
frappe.db.commit()
print(mode, "ok")
