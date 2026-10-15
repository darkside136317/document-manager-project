import frappe


def execute():
    """Existing sites, once: fonds open by licence, copies of confidential levels refused, and a reader group that used to
    see "every fonds" keeps exactly the fonds it saw, as explicit grants (a fonds created later needs its own grant)."""
    frappe.db.sql("update `tabFonds` set access_mode = 'Theo cấp phép' where ifnull(access_mode, '') = ''")
    frappe.db.sql("update `tabConfidentiality Level` set allow_copy = 0 where priority >= 2")
    if not frappe.db.has_column("Reader Group", "fonds_scope"):
        return
    fonds = frappe.get_all("Fonds", filters={"access_mode": ["!=", "Nội bộ"]}, pluck="name", limit_page_length=0)
    today = frappe.utils.nowdate()
    for group in frappe.db.sql_list("select name from `tabReader Group` where ifnull(fonds_scope, 'Tất cả phông') = 'Tất cả phông'"):
        doc = frappe.get_doc("Reader Group", group)
        have = {row.fonds for row in doc.fonds_scopes}
        for name in fonds:
            if name not in have:
                doc.append("fonds_scopes", {"fonds": name, "granted_on": today, "note": "Chuyển từ \"Tất cả phông\""})
        doc.flags.ignore_permissions = True
        doc.save()
        frappe.db.sql("update `tabReader Group` set fonds_scope = 'Chỉ các phông được chọn' where name = %s", group)
