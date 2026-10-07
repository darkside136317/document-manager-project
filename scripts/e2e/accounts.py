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
frappe.cache.delete_keys("rl:*")  # the sign-up and password endpoints are rate limited per IP: a rerun starts fresh
frappe.db.commit()
print(mode, "ok:", ", ".join(ACCOUNTS))
