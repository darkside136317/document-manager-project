import frappe

def run():
    frappe.init(site="dm.localhost")
    frappe.connect()

    doc = frappe.get_doc('DocType', 'Archival File')
    fields = doc.fields

    has_disposal = any(f.fieldname == 'disposal_status' for f in fields)
    if not has_disposal:
        doc.append('fields', {
            'fieldname': 'section_disposal',
            'fieldtype': 'Section Break',
            'label': 'Quản lý Tiêu hủy'
        })
        doc.append('fields', {
            'fieldname': 'retention_years',
            'fieldtype': 'Int',
            'label': 'Thời hạn bảo quản (Năm)',
            'default': '0',
            'description': 'Số năm bảo quản kể từ ngày kết thúc hồ sơ'
        })
        doc.append('fields', {
            'fieldname': 'disposal_status',
            'fieldtype': 'Select',
            'label': 'Trạng thái Tiêu hủy',
            'options': 'Bình thường\nCảnh báo tiêu hủy\nĐã tiêu hủy',
            'default': 'Bình thường'
        })
        
        doc.save()
        frappe.db.commit()
        print("Added disposal fields to Archival File")
    else:
        print("Fields already exist")

if __name__ == "__main__":
    run()
