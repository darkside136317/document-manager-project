"""HTTP end-to-end checks against a running stack (default http://localhost:8888).

Prepare accounts first (see accounts.py), then:  DM_E2E_PASSWORD=... python scripts/e2e/e2e_http.py [base_url]
Every check prints PASS/FAIL; the exit code is the number of failures.
"""
import http.cookiejar
import json
import os
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

    print(f"\n{failures} failure(s)")
    return failures


if __name__ == "__main__":
    sys.exit(main())
