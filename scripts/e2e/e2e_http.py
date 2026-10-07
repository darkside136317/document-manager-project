"""HTTP end-to-end checks against a running stack (default http://localhost:8888).

Prepare accounts first (see accounts.py), then:  DM_E2E_PASSWORD=... python scripts/e2e/e2e_http.py [base_url]
Every check prints PASS/FAIL; the exit code is the number of failures.
"""
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8888").rstrip("/")
PASSWORD = os.environ.get("DM_E2E_PASSWORD") or sys.exit("Set DM_E2E_PASSWORD to the value used for accounts.py")
failures = 0


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), NoRedirect)

    def request(self, path, data=None, method=None):
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(BASE + path, data=body, method=method)
        try:
            resp = self.opener.open(req, timeout=60)
        except urllib.error.HTTPError as e:
            resp = e
        raw = resp.read().decode("utf-8", "replace")
        return resp.status, raw, resp.headers.get("Location", "")

    def json(self, path, data=None):
        status, raw, _ = self.request(path, data)
        try:
            return status, json.loads(raw)
        except ValueError:
            return status, {}

    def post_json(self, path, data, csrf=""):
        """POST a JSON body (what the reader site's script sends); returns (status, parsed JSON)."""
        req = urllib.request.Request(BASE + path, data=json.dumps(data).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf})
        try:
            resp = self.opener.open(req, timeout=60)
        except urllib.error.HTTPError as e:
            resp = e
        raw = resp.read().decode("utf-8", "replace")
        try:
            return resp.status, json.loads(raw)
        except ValueError:
            return resp.status, {}

    def login(self, email):
        status, _ = self.json("/api/method/login", {"usr": email, "pwd": PASSWORD})
        return status == 200


def check(name, ok, detail=""):
    global failures
    failures += 0 if ok else 1
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def clients():
    out = {}
    for key, email in (("reader", "e2e.reader@example.com"), ("noprofile", "e2e.noprofile@example.com"),
                       ("officer", "e2e.officer@example.com"), ("admin", "e2e.admin@example.com")):
        c = Client()
        check(f"login {key}", c.login(email))
        out[key] = c
    out["guest"] = Client()
    return out


def main():
    c = clients()
    api = "/api/method/document_manager.document_manager.api."

    # --- pages and gates
    check("guest /portal redirects to login", c["guest"].request("/portal")[0] in (301, 302, 303))
    check("reader /portal 200", c["reader"].request("/portal")[0] == 200)
    status, _, location = c["reader"].request("/dashboard")
    check("reader /dashboard redirected away", status in (301, 302, 303) and "dashboard" not in location, location)
    check("officer /dashboard 200", c["officer"].request("/dashboard")[0] == 200)
    check("admin readers form 200", c["admin"].request("/readers/form")[0] == 200)
    check("admin settings page 200", c["admin"].request("/document_manager_settings")[0] == 200)

    # --- search
    for key in ("reader", "officer", "admin"):
        status, body = c[key].json(api + "search.search_documents?query=a")
        check(f"{key} search_documents", status == 200 and "data" in body.get("message", {}), str(status))
        status, body = c[key].json(api + "search.search_archival_files?query=a")
        check(f"{key} search_archival_files", status == 200 and "total" in body.get("message", {}), str(status))
    check("no-profile reader cannot search", c["noprofile"].json(api + "search.search_documents?query=a")[0] == 403)
    check("guest cannot search", c["guest"].json(api + "search.search_documents?query=a")[0] in (401, 403))

    # --- data exposure through the generic resource API
    status, body = c["noprofile"].json("/api/resource/Archive%20Document?limit_page_length=5")
    check("no-profile reader sees no documents via /api/resource", status in (200, 403) and not body.get("data"), str(body)[:120])
    status, body = c["reader"].json("/api/resource/Archival%20File?fields=[\"name\",\"status\"]&limit_page_length=500")
    check("reader sees no draft files via /api/resource",
          status == 200 and all(r.get("status") != "Nháp" for r in body.get("data", [])), str(body)[:160])

    # --- XML and admin endpoints
    for key in ("reader", "noprofile", "guest"):
        status, _ = c[key].json(api.replace("api.", "services.xml_handler.export_xml") + "?doctype=Archival%20File")
        check(f"{key} cannot export XML", status in (401, 403), str(status))
    status, body = c["admin"].json(api.replace("api.", "services.xml_handler.export_xml") + "?doctype=Fonds")
    check("admin can export XML", status == 200 and "xml_content" in body.get("message", {}), str(status))
    check("reader cannot read service health", c["reader"].json(api + "admin.get_service_health")[0] == 403)
    status, body = c["admin"].json(api + "admin.get_service_health")
    check("admin reads service health", status == 200 and "meilisearch" in body.get("message", {}), str(status))

    reader_site(c, api)

    print(f"\n{failures} failure(s)")
    return failures


def reader_site(c, api):
    """Public pages, the reader area's gates, redirects and the sign-up / account endpoints."""
    for path in ("/", "/gioi-thieu", "/lanh-dao", "/co-cau", "/lien-he", "/huong-dan", "/dang-nhap", "/dang-ky", "/quen-mat-khau"):
        status, body, _ = c["guest"].request(path)
        check(f"guest {path} 200 and its own document", status == 200 and "<!DOCTYPE html>" in body and "frappe.ready" not in body, str(status))
    check("an unknown set-password link is explained", "không hợp lệ" in c["guest"].request("/dat-mat-khau?key=nope")[1])

    for path in ("/portal", "/portal/phieu", "/portal/sao-chep", "/portal/gop-y", "/portal/tai-khoan", "/portal/thong-bao"):
        status, _, location = c["guest"].request(path)
        check(f"guest {path} -> 302 to sign in", status == 302 and location.startswith("/dang-nhap?redirect-to="), f"{status} {location}")
    for path in ("/portal/phieu", "/portal/sao-chep", "/portal/gop-y", "/portal/tai-khoan", "/portal/thong-bao"):
        check(f"reader {path} 200", c["reader"].request(path)[0] == 200)
    check("reader /portal/ho-so/<missing> 404", c["reader"].request("/portal/ho-so/AF-99999")[0] == 404)
    check("officer /portal 200 (staff may use the reader site)", c["officer"].request("/portal")[0] == 200)
    status, _, location = c["reader"].request("/usage_requests")
    check("reader's old slip page -> new page", status == 302 and location == "/portal/phieu", f"{status} {location}")
    status, _, location = c["guest"].request("/portal_document?name=DOC-000001")
    check("old document viewer address redirects", status == 301 and location.startswith("/portal/van-ban"), f"{status} {location}")

    # sign-up endpoints: POST only, honeypot, officers only for the queue
    register = api + "registration.register_reader"
    check("sign-up refuses GET", c["guest"].json(register + "?full_name=x&email=a@b.vn")[0] in (403, 405))
    status, body = c["guest"].post_json(register, {"full_name": "Bot", "email": "bot@example.com", "website": "http://spam.example"})
    check("honeypot answers like a real sign-up", status == 200 and body.get("message", {}).get("status") == "pending", str(status))
    status, body = c["guest"].post_json(register, {"full_name": "x", "email": "not-an-email"})
    check("invalid email is refused", status in (400, 417), str(status))
    for key in ("reader", "noprofile", "guest"):
        check(f"{key} cannot list registrations", c[key].json(api + "registration.list_registrations")[0] in (401, 403))
        check(f"{key} cannot read the reader groups", c[key].json(api + "registration.reader_groups")[0] in (401, 403))
    status, body = c["officer"].json(api + "registration.list_registrations?status=M%E1%BB%9Bi")
    check("officer lists the queue", status == 200 and "rows" in body.get("message", {}), str(status))
    check("the honeypot request was not queued",
          not any(r["email"] == "bot@example.com" for r in body.get("message", {}).get("rows", [])))

    # a wrong current password is a message and the reader stays signed in
    csrf = re.search(r'"csrf": "([^"]+)"', c["reader"].request("/portal")[1])
    status, body = c["reader"].post_json(api + "account.change_password", {"old_password": "wrong", "new_password": "Whatever!12345"}, csrf.group(1) if csrf else "")
    check("wrong current password is refused (417)", status == 417, str(status))
    check("...and the reader is still signed in", c["reader"].request("/portal/tai-khoan")[0] == 200)
    status, body = c["reader"].post_json(api + "basket.add_to_basket", {"kind": "file", "name": "AF-99999", "target": "usage"}, csrf.group(1) if csrf else "")
    check("a missing file cannot be added to the basket", status in (403, 404, 417), str(status))
    check("guest cannot use the basket", c["guest"].post_json(api + "basket.add_to_basket", {"kind": "file", "name": "x", "target": "usage"})[0] in (401, 403))


if __name__ == "__main__":
    sys.exit(main())
