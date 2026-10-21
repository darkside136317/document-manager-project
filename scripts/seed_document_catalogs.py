"""Add the initial Vietnamese document type, group, and classification master data.

Run inside a Frappe container with its working directory set to bench/sites:
    python seed_document_catalogs.py <site-name>

Existing records are preserved. A name/code collision with different values aborts
the transaction so an administrator can resolve it explicitly.
"""

from __future__ import annotations

import sys


DOCUMENT_TYPES = (
    ("DOC01", "Văn bản hành chính"),
    ("DOC02", "Văn bản quy phạm pháp luật"),
    ("DOC03", "Hồ sơ pháp lý doanh nghiệp"),
    ("DOC04", "Hợp đồng"),
    ("DOC05", "Tài liệu tư pháp"),
    ("DOC06", "Giấy tờ cá nhân"),
    ("DOC07", "Hồ sơ hộ tịch"),
    ("DOC08", "Hồ sơ đất đai và bất động sản"),
    ("DOC09", "Hồ sơ xây dựng"),
    ("DOC10", "Tài liệu kỹ thuật"),
    ("DOC11", "Tài liệu an toàn lao động"),
    ("DOC12", "Tài liệu kế toán"),
    ("DOC13", "Hóa đơn và chứng từ thuế"),
    ("DOC14", "Tài liệu ngân hàng"),
    ("DOC15", "Hồ sơ nhân sự"),
    ("DOC16", "Tài liệu bảo hiểm"),
    ("DOC17", "Hồ sơ y tế"),
    ("DOC18", "Tài liệu giáo dục"),
    ("DOC19", "Tài liệu nghiên cứu"),
    ("DOC20", "Đơn từ và biểu mẫu"),
    ("DOC21", "Văn bản viết tay"),
    ("DOC22", "Hồ sơ đấu thầu"),
    ("DOC23", "Tài liệu mua sắm"),
    ("DOC24", "Tài liệu logistics và xuất nhập khẩu"),
    ("DOC25", "Tài liệu vận tải"),
    ("DOC26", "Hồ sơ giáo dục hành chính"),
    ("DOC27", "Tài liệu thương mại"),
    ("DOC28", "Tài liệu quản trị doanh nghiệp"),
    ("DOC29", "Tài liệu công nghệ thông tin"),
    ("DOC30", "Tài liệu lưu trữ lịch sử"),
    ("DOC31", "Tài liệu có bảng biểu"),
    ("DOC32", "Tài liệu có con dấu và chữ ký"),
    ("DOC33", "Tài liệu đa ngôn ngữ"),
    ("DOC34", "Tài liệu ảnh và bản scan"),
    ("DOC35", "Bản đồ và sơ đồ"),
    ("DOC36", "Tài liệu khác"),
)

DOCUMENT_GROUPS = (
    ("ADMIN", "Văn bản hành chính"),
    ("LEGAL", "Pháp luật và pháp lý"),
    ("ENTERPRISE", "Hồ sơ doanh nghiệp"),
    ("CONTRACT", "Hợp đồng và thỏa thuận"),
    ("IDENTITY", "Giấy tờ định danh cá nhân"),
    ("CIVIL", "Hộ tịch và dân sự"),
    ("LAND", "Đất đai và bất động sản"),
    ("CONSTRUCTION", "Xây dựng và công trình"),
    ("ENGINEERING", "Kỹ thuật và công nghệ"),
    ("SAFETY", "An toàn lao động và môi trường"),
    ("FINANCE", "Tài chính và kế toán"),
    ("TAX", "Thuế và hóa đơn"),
    ("BANKING", "Ngân hàng và tín dụng"),
    ("HR", "Nhân sự và lao động"),
    ("INSURANCE", "Bảo hiểm"),
    ("HEALTHCARE", "Y tế và sức khỏe"),
    ("EDUCATION", "Giáo dục và đào tạo"),
    ("RESEARCH", "Nghiên cứu khoa học"),
    ("APPLICATION", "Đơn từ và biểu mẫu"),
    ("HANDWRITTEN", "Tài liệu viết tay"),
    ("PROCUREMENT", "Mua sắm và cung ứng"),
    ("TENDER", "Đấu thầu"),
    ("LOGISTICS", "Logistics và xuất nhập khẩu"),
    ("TRANSPORT", "Giao thông và vận tải"),
    ("SALES", "Kinh doanh và thương mại"),
    ("MANAGEMENT", "Quản trị doanh nghiệp"),
    ("IT", "Công nghệ thông tin"),
    ("ARCHIVE", "Hồ sơ lưu trữ"),
    ("EDUCATIONAL_ADMIN", "Hồ sơ hành chính giáo dục"),
    ("DRAWING", "Bản vẽ, bản đồ và sơ đồ"),
    ("MULTILINGUAL", "Tài liệu đa ngôn ngữ"),
    ("OTHER", "Tài liệu khác"),
)

CLASSIFICATION_SCHEMES = (
    ("ADMIN", "Khung phân loại hồ sơ hành chính"),
    ("LEGAL", "Khung phân loại hồ sơ pháp lý"),
    ("ORG", "Khung phân loại hồ sơ tổ chức và doanh nghiệp"),
    ("PERSONNEL", "Khung phân loại hồ sơ nhân sự"),
    ("FINANCE", "Khung phân loại hồ sơ tài chính và kế toán"),
    ("TAX", "Khung phân loại hồ sơ thuế"),
    ("CONTRACT", "Khung phân loại hồ sơ hợp đồng"),
    ("PROCUREMENT", "Khung phân loại hồ sơ mua sắm và cung ứng"),
    ("TENDER", "Khung phân loại hồ sơ đấu thầu"),
    ("SALES", "Khung phân loại hồ sơ kinh doanh và bán hàng"),
    ("CUSTOMER", "Khung phân loại hồ sơ khách hàng"),
    ("SUPPLIER", "Khung phân loại hồ sơ nhà cung cấp"),
    ("PROJECT", "Khung phân loại hồ sơ dự án"),
    ("CONSTRUCTION", "Khung phân loại hồ sơ xây dựng và công trình"),
    ("ENGINEERING", "Khung phân loại hồ sơ kỹ thuật"),
    ("ASSET", "Khung phân loại hồ sơ tài sản và thiết bị"),
    ("OPERATION", "Khung phân loại hồ sơ vận hành"),
    ("SAFETY", "Khung phân loại hồ sơ an toàn lao động"),
    ("ENVIRONMENT", "Khung phân loại hồ sơ môi trường"),
    ("QUALITY", "Khung phân loại hồ sơ quản lý chất lượng"),
    ("LAND", "Khung phân loại hồ sơ đất đai và bất động sản"),
    ("CIVIL", "Khung phân loại hồ sơ hộ tịch và dân sự"),
    ("HEALTHCARE", "Khung phân loại hồ sơ y tế"),
    ("EDUCATION", "Khung phân loại hồ sơ giáo dục và đào tạo"),
    ("INSURANCE", "Khung phân loại hồ sơ bảo hiểm"),
    ("BANKING", "Khung phân loại hồ sơ ngân hàng và tín dụng"),
    ("LOGISTICS", "Khung phân loại hồ sơ logistics và xuất nhập khẩu"),
    ("TRANSPORT", "Khung phân loại hồ sơ giao thông và vận tải"),
    ("IT", "Khung phân loại hồ sơ công nghệ thông tin"),
    ("MEETING", "Khung phân loại hồ sơ hội họp và điều hành"),
    ("ARCHIVE", "Khung phân loại hồ sơ lưu trữ"),
    ("CORRESPONDENCE", "Khung phân loại hồ sơ văn thư và công văn"),
    ("RESEARCH", "Khung phân loại hồ sơ nghiên cứu khoa học"),
    ("COMPLIANCE", "Khung phân loại hồ sơ tuân thủ và kiểm toán"),
    ("OTHER", "Khung phân loại hồ sơ khác"),
)


def seed_category(frappe, doctype, name_field, code_field, entries, defaults):
    if len(set(entries)) != len(entries) or len({code for code, _ in entries}) != len(entries):
        raise ValueError(f"Duplicate entries in {doctype} seed")
    existing = frappe.get_all(
        doctype, fields=["name", name_field, code_field], limit_page_length=0
    )
    by_name = {}
    by_code = {}
    for row in existing:
        name = row[name_field]
        if name in by_name:
            raise ValueError(f"Duplicate existing {doctype} name: {name}")
        by_name[name] = row
        code = row[code_field]
        if not code:
            continue
        if code in by_code:
            raise ValueError(f"Duplicate existing {doctype} code: {code}")
        by_code[code] = row

    created = updated = kept = 0
    for code, name in entries:
        code_row = by_code.get(code)
        name_row = by_name.get(name)
        if code_row and code_row[name_field] != name:
            raise ValueError(f"{doctype} code {code} already belongs to {code_row[name_field]}")
        if name_row and name_row[code_field] not in (None, "", code):
            raise ValueError(f"{doctype} name {name} already has code {name_row[code_field]}")
        if code_row or (name_row and name_row[code_field] == code):
            kept += 1
        elif name_row:
            frappe.db.set_value(doctype, name_row.name, code_field, code)
            updated += 1
        else:
            frappe.get_doc({
                "doctype": doctype, name_field: name, code_field: code, **defaults,
            }).insert(ignore_permissions=True)
            created += 1
    return created, updated, kept


def main(site):
    import frappe

    frappe.init(site=site)
    frappe.connect()
    try:
        for doctype, name_field, code_field, entries, defaults in (
            ("Document Type Category", "type_name", "type_code", DOCUMENT_TYPES, {"is_active": 1}),
            ("Document Group", "group_name", "group_code", DOCUMENT_GROUPS, {"is_active": 1}),
            ("Classification Scheme", "scheme_name", "scheme_code", CLASSIFICATION_SCHEMES, {"is_group": 1}),
        ):
            created, updated, kept = seed_category(
                frappe, doctype, name_field, code_field, entries, defaults
            )
            print(f"{doctype}: created={created}, updated={updated}, kept={kept}")
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python seed_document_catalogs.py <site-name>")
    main(sys.argv[1])
