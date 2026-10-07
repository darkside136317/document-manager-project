import frappe


def execute():
    """`Reader.reader_group` was free text and `max_confidentiality_priority` the only control.

    Turn every distinct free-text group into a Reader Group (clearance = the highest one among
    its members) and give group-less readers the default group. A reader keeps a personal
    override only where their stored clearance differs from their group's.
    """
    from document_manager.document_manager.setup.install import ensure_default_reader_group

    default = ensure_default_reader_group()
    default_priority = frappe.db.get_value("Reader Group", default, "max_confidentiality_priority") or 1

    readers = frappe.get_all("Reader", fields=["name", "reader_group", "max_confidentiality_priority"],
                             limit_page_length=0)
    members = {}
    for reader in readers:
        label = (reader.reader_group or "").strip()[:140]
        if label.lower() in ("none", "null"):  # the old form saved a template "None" for a blank group
            label = ""
        members.setdefault(label, []).append(reader)

    for label, group_readers in members.items():
        if not label:
            group, priority = default, default_priority
        else:
            priority = max(int(r.max_confidentiality_priority or 1) for r in group_readers)
            group = label if frappe.db.exists("Reader Group", label) else frappe.get_doc({
                "doctype": "Reader Group", "group_name": label, "is_active": 1,
                "max_confidentiality_priority": priority,
                "description": "Tạo tự động từ nhóm độc giả nhập tay trước đây",
            }).insert(ignore_permissions=True).name
            priority = frappe.db.get_value("Reader Group", group, "max_confidentiality_priority") or priority
        for reader in group_readers:
            own = int(reader.max_confidentiality_priority or 1)
            frappe.db.set_value("Reader", reader.name, {
                "reader_group": group,
                "max_confidentiality_priority": 0 if own == priority else own,
            }, update_modified=False)
