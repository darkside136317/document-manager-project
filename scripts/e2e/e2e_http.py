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

    def csrf(self):
        """The CSRF token of this session (what the pages hand to their scripts); empty for a guest."""
        if getattr(self, "_csrf", None) is None:
            self._csrf = ""
            for path in ("/portal", "/dashboard"):
                found = re.search(r'"csrf(?:_token)?":\s*"([^"]+)"', self.request(path)[1])
                if found:
                    self._csrf = found.group(1)
                    break
        return self._csrf

    def post_json(self, path, data, csrf=None):
        """POST a JSON body (what the reader site's script sends); returns (status, parsed JSON)."""
        csrf = self.csrf() if csrf is None else csrf
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
                       ("officer", "e2e.officer@example.com"), ("leader", "e2e.leader@example.com"),
                       ("admin", "e2e.admin@example.com")):
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
    status, _, location = c["admin"].request("/readers/form")
    check("admin's old readers form forwards to the staff app", status == 302 and location == "/dashboard/doc-gia/doc-gia", f"{status} {location}")
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
    reader_management(c, api)

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


def reader_management(c, api):
    """The reading room's slip queues, the leader's limits, reader administration and the old staff pages."""
    # the old staff pages forward to the staff app, readers to their own pages, guests sign in first
    for old, reader_to, staff_to in (("/usage_requests", "/portal/phieu", "/dashboard/doc-gia/phieu-su-dung"),
                                     ("/copy_requests", "/portal/sao-chep", "/dashboard/doc-gia/phieu-sao-chup"),
                                     ("/reader_feedbacks", "/portal/gop-y", "/dashboard/doc-gia/gop-y"),
                                     ("/readers", "/portal", "/dashboard/doc-gia/doc-gia"),
                                     ("/reader_settings", "/portal", "/dashboard/doc-gia/thiet-lap-doc-gia")):
        status, _, location = c["officer"].request(old)
        check(f"officer {old} -> staff app", status == 302 and location == staff_to, f"{status} {location}")
        status, _, location = c["reader"].request(old)
        check(f"reader {old} -> reader site", status == 302 and location == reader_to, f"{status} {location}")
        status, _, location = c["guest"].request(old)
        check(f"guest {old} -> sign in", status == 302 and location.startswith("/dang-nhap"), f"{status} {location}")
    status, _, location = c["leader"].request("/usage_requests?name=UR-00001")
    check("an old slip address keeps the slip name", status == 302 and location == "/dashboard/doc-gia/phieu-su-dung/UR-00001", f"{status} {location}")
    check("leader opens the staff app", c["leader"].request("/dashboard")[0] == 200)
    check("leader's /portal is the reader site, not an error", c["leader"].request("/portal")[0] == 200)

    # who may read the queues
    read_endpoints = ("slips.queue_summary", "slips.queue_badges", "slips.list_slips?kind=usage", "slips.list_slips?kind=copy&view=tat_ca",
                      "feedback.list_feedback")
    for endpoint in read_endpoints:
        for key in ("officer", "leader", "admin"):
            status, body = c[key].json(api + endpoint)
            check(f"{key} {endpoint}", status == 200 and "message" in body, str(status))
        for key in ("reader", "noprofile", "guest"):
            check(f"{key} cannot {endpoint}", c[key].json(api + endpoint)[0] in (401, 403))
    status, body = c["leader"].json(api + "slips.queue_summary")
    summary = body.get("message", {})
    check("the leader's queue offers the leader tab", "cho_lanh_dao" in summary.get("usage", {}), str(summary)[:160])
    check("the leader's default tab is the leader's", summary.get("default_view") == "cho_lanh_dao", str(summary)[:160])
    status, body = c["officer"].json(api + "slips.list_slips?kind=copy&page_size=100000")
    check("page size is capped", status == 200 and len(body.get("message", {}).get("rows", [])) <= 100, str(status))

    # the decisions are POST only and the reader cannot reach them
    for endpoint, data in (("slips.decide_items", {"kind": "usage", "name": "UR-00001", "decisions": "[]"}),
                           ("slips.receive_return", {"name": "UR-00001"}), ("slips.renew", {"name": "UR-00001"}),
                           ("slips.delete_draft", {"kind": "usage", "name": "UR-00001"})):
        check(f"{endpoint} refuses GET", c["officer"].json(api + endpoint + "?" + urllib.parse.urlencode(data))[0] in (403, 405))
        for key in ("reader", "noprofile", "guest"):
            status, _ = c[key].post_json(api + endpoint, data)
            check(f"{key} cannot {endpoint}", status in (401, 403), str(status))
    check("the leader cannot hand documents back", c["leader"].post_json(api + "slips.receive_return", {"name": "UR-00001"})[0] == 403)
    check("the leader cannot renew", c["leader"].post_json(api + "slips.renew", {"name": "UR-00001"})[0] == 403)
    status, _ = c["officer"].json(api + "slips.get_slip?kind=usage&name=UR-NOPE")
    check("an unknown slip is a clean error", status in (404, 417), str(status))
    check("a reader's card and slips are staff only",
          all(c[k].json(api + "slips.reader_slips?reader=RD-1")[0] in (401, 403) for k in ("reader", "noprofile", "guest")))

    # reader administration: staff read, the leader cannot write, nobody outside the staff touches it
    check("the leader reads the readers list", c["leader"].json(api + "crud.get_list?doctype=Reader")[0] == 200)
    status, _ = c["leader"].post_json(api + "crud.save", {"doctype": "Reader", "values": {"full_name": "E2E-x", "email": "e2e.x@example.com"}})
    check("the leader cannot create a reader", status in (403, 417), str(status))
    for key in ("reader", "noprofile", "guest"):
        check(f"{key} cannot read the readers list", c[key].json(api + "crud.get_list?doctype=Reader")[0] in (401, 403))
        check(f"{key} cannot read the request templates", c[key].json(api + "crud.get_list?doctype=Request%20Template")[0] in (401, 403))
        status, _ = c[key].post_json(api + "registration.issue_reader_access", {"reader": "RD-1"})
        check(f"{key} cannot issue online access", status in (401, 403), str(status))
    status, _ = c["leader"].post_json(api + "registration.issue_reader_access", {"reader": "RD-1"})
    check("the leader cannot issue online access", status == 403, str(status))
    check("issue_reader_access refuses GET", c["admin"].json(api + "registration.issue_reader_access?reader=RD-1")[0] in (403, 405))
    status, body = c["admin"].json(api + "crud.get?doctype=Reader%20Settings&name=Reader%20Settings")
    check("admin reads the reader settings as a form", status == 200 and "max_open_requests" in body.get("message", {}), str(status))
    status, _ = c["leader"].post_json(api + "crud.save", {"doctype": "Reader Settings", "values": {"renewal_days": 3}, "name": "Reader Settings"})
    check("the leader may read the reader settings but not change them", status in (403, 417), str(status))
    status, body = c["admin"].json(api + "boot.get_staff_boot")
    check("the staff boot lists the reader screens", status == 200 and body.get("message", {}).get("readers"), str(status))
    status, body = c["leader"].json(api + "boot.get_staff_boot")
    boot = body.get("message", {})
    check("the leader's boot lists the reader settings read-only",
          status == 200 and all(not e["permissions"]["write"] for e in boot.get("settings", [])), str(boot.get("settings"))[:160])

    # printing a slip needs the right to read it
    for key in ("guest", "reader", "noprofile"):
        status, _, _ = c[key].request("/printview?doctype=Usage%20Request&name=UR-00001")
        check(f"{key} cannot print someone else's slip", status in (302, 401, 403, 404), str(status))


if __name__ == "__main__":
    sys.exit(main())
