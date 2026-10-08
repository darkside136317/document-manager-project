"""Create or remove the throw-away accounts used by e2e_http.py.

Run inside the backend container, from the sites directory (script comes in on stdin).
The password comes from DM_E2E_PASSWORD (any strong value; the accounts are deleted by `down`):

    docker compose exec -T -e DM_E2E_PASSWORD -w /home/frappe/frappe-bench/sites backend \
        /home/frappe/frappe-bench/env/bin/python - up   < scripts/e2e/accounts.py
    docker compose exec -T -e DM_E2E_PASSWORD -w /home/frappe/frappe-bench/sites backend \
        /home/frappe/frappe-bench/env/bin/python - down < scripts/e2e/accounts.py
"""
import os
import sys

import frappe

SITE = "docmanager.yourdomain.com"
PASSWORD = os.environ.get("DM_E2E_PASSWORD") or sys.exit("Set DM_E2E_PASSWORD (pass it with `exec -e DM_E2E_PASSWORD`)")
ACCOUNTS = {  # email: (roles, user type, reader profile?)
    "e2e.reader@example.com": (["Reader"], "Website User", True),
    "e2e.noprofile@example.com": (["Reader"], "Website User", False),
    "e2e.officer@example.com": (["Reading Room Officer"], "System User", False),
    "e2e.leader@example.com": (["Archive Leader"], "System User", False),
    "e2e.cataloger@example.com": (["Cataloger"], "System User", False),
    "e2e.preserver@example.com": (["Preservation Officer"], "System User", False),
    "e2e.admin@example.com": (["Document Admin"], "System User", False),
}

mode = sys.argv[-1]
frappe.init(site=SITE)
frappe.connect()
frappe.set_user("Administrator")

def purge_reader(email):
    """A reader account and everything that points at it (slips, feedback, notifications)."""
    reader = frappe.db.get_value("Reader", {"user": email})
    if reader:
        for doctype in ("Usage Request", "Copy Request", "Reader Feedback"):
            for name in frappe.get_all(doctype, filters={"reader": reader}, pluck="name"):
                doc = frappe.get_doc(doctype, name)
                if doc.docstatus == 1:
                    doc.flags.ignore_permissions = True
                    doc.cancel()
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        frappe.delete_doc("Reader", reader, force=True, ignore_permissions=True)
    frappe.db.delete("Notification Log", {"for_user": email})
    for name in frappe.get_all("Reader Registration", filters={"email": email}, pluck="name"):
        frappe.delete_doc("Reader Registration", name, force=True, ignore_permissions=True)
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, force=True, ignore_permissions=True)


def purge_archive():
    """Archive data and groups the browser flows create carry the prefix "E2E-" (children are removed first)."""
    from document_manager.document_manager.services.preservation import backup, filestore

    # restores first: a backup that a restore batch still points at is not deleted
    for doctype, item, link in (("Restore Batch", "Restore Batch Item", "restore"), ("Integrity Check", "Integrity Check Item", "check"),
                                ("Backup Batch", "Backup Batch Item", "batch")):
        for name in frappe.get_all(doctype, filters={"owner": ["like", "e2e.%@example.com"]}, pluck="name"):
            if doctype == "Backup Batch":
                backup.delete_batch(name)
                continue
            for row in frappe.get_all(item, filters={link: name}, pluck="name"):
                frappe.delete_doc(item, row, force=True, ignore_permissions=True)
            frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
    filestore.collect_garbage(keep_batches=set(frappe.get_all("Backup Batch", pluck="name")), min_age=0)
    for name in frappe.get_all("Staff Group", filters={"group_name": ["like", "E2E-%"]}, pluck="name"):
        frappe.delete_doc("Staff Group", name, force=True, ignore_permissions=True)
    for name in frappe.get_all("Inventory Check", filters={"check_title": ["like", "E2E-%"]}, pluck="name"):
        frappe.delete_doc("Inventory Check", name, force=True, ignore_permissions=True)
    for name in frappe.get_all("Data Exchange Job", filters={"owner": ["like", "e2e.%@example.com"]}, pluck="name"):
        frappe.delete_doc("Data Exchange Job", name, force=True, ignore_permissions=True)
    for doctype, field in (("Archive Document", "document_title"), ("Archival File", "file_title"), ("Catalog", "catalog_title"),
                           ("Record Group", "group_title"), ("Fonds", "fonds_name"), ("Archival Agency", "agency_name"),
                           ("Confidentiality Level", "level_name"), ("Reader Group", "group_name"), ("Document Type Category", "type_name"),
                           ("Document Group", "group_name")):
        for name in frappe.get_all(doctype, filters={field: ["like", "E2E-%"]}, pluck="name"):
            frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
    for name in frappe.get_all("Reader", filters={"full_name": ["like", "E2E-%"]}, pluck="name"):
        frappe.delete_doc("Reader", name, force=True, ignore_permissions=True)


# readers created by the browser flows (reader.mjs registers e2e.newreader.<n>@example.com)
for email in frappe.get_all("User", filters={"name": ["like", "e2e.%@example.com"]}, pluck="name"):
    purge_reader(email)
for name in frappe.get_all("Reader Registration", filters={"email": ["like", "e2e.%@example.com"]}, pluck="name"):
    frappe.delete_doc("Reader Registration", name, force=True, ignore_permissions=True)

for email, (roles, user_type, profile) in ACCOUNTS.items():
    reader = frappe.db.get_value("Reader", {"user": email})
    if reader:
        frappe.delete_doc("Reader", reader, force=True, ignore_permissions=True)
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, force=True, ignore_permissions=True)
    if mode != "up":
        continue
    user = frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0],
                           "send_welcome_email": 0, "user_type": user_type, "new_password": PASSWORD,
                           "roles": [{"role": r} for r in roles]})
    user.flags.no_welcome_mail = True
    user.insert(ignore_permissions=True)
    if profile:
        frappe.get_doc({"doctype": "Reader", "full_name": "E2E Reader", "user": email, "email": email,
                        "is_active": 1}).insert(ignore_permissions=True)
purge_archive()  # after the readers: their slips point at the files
frappe.db.delete("Business Activity Log", {"reference_doctype": "E2E-LOG"})
if mode == "up":  # old rows for the clean-up flow (admin.mjs): far older than anything the site has logged
    for n in range(3):
        frappe.get_doc({"doctype": "Business Activity Log", "activity_type": "Xem", "reference_doctype": "E2E-LOG", "reference_name": f"OLD-{n}",
                        "user": "Administrator", "timestamp": "2020-01-15 12:00:00", "description": f"E2E old log row {n}"}).insert(ignore_permissions=True)
frappe.cache.delete_keys("rl:*")  # the sign-up and password endpoints are rate limited per IP: a rerun starts fresh
frappe.db.commit()
print(mode, "ok:", ", ".join(ACCOUNTS))
