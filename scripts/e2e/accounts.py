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
frappe.db.commit()
print(mode, "ok:", ", ".join(ACCOUNTS))
