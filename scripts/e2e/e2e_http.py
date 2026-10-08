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

    def raw(self, path, data=None):
        """(status, bytes, content type) of a GET (or form POST): for downloads."""
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        try:
            resp = self.opener.open(urllib.request.Request(BASE + path, data=body), timeout=120)
        except urllib.error.HTTPError as e:
            resp = e
        return resp.status, resp.read(), resp.headers.get("Content-Type", "")

    def upload(self, name, content, private=1):
        """Upload a file through Frappe's upload_file (multipart); returns (status, file_url)."""
        boundary = "----dm" + str(abs(hash(name)))[:10]
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="is_private"\r\n\r\n{private}\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
                "Content-Type: application/xml\r\n\r\n")
        body = head.encode() + content + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(BASE + "/api/method/upload_file", data=body, method="POST", headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}", "X-Frappe-CSRF-Token": self.csrf()})
        try:
            resp = self.opener.open(req, timeout=60)
        except urllib.error.HTTPError as e:
            resp = e
        try:
            return resp.status, json.loads(resp.read().decode()).get("message", {}).get("file_url", "")
        except ValueError:
            return resp.status, ""

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
                       ("cataloger", "e2e.cataloger@example.com"), ("preserver", "e2e.preserver@example.com"),
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
    status, _, location = c["admin"].request("/document_manager_settings")
    check("the old settings page forwards to the staff app", status == 301 and location == "/dashboard/quan-tri/thiet-lap-he-thong", f"{status} {location}")

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

    # --- admin endpoints (the XML exchange has its own checks below)
    check("reader cannot read service health", c["reader"].json(api + "admin.get_service_health")[0] == 403)
    status, body = c["admin"].json(api + "admin.get_service_health")
    check("admin reads service health", status == 200 and "meilisearch" in body.get("message", {}), str(status))

    reader_site(c, api)
    reader_management(c, api)
    reports_and_exchange(c, api)
    preservation_and_administration(c, api)

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


def wait_for(client, path, key="busy", attempts=60):
    """Poll a job until it is no longer busy (the queue worker runs it)."""
    import time

    job = {}
    for _ in range(attempts):
        job = client.json(path)[1].get("message", {})
        if job and not job.get(key):
            break
        time.sleep(1)
    return job


def reports_and_exchange(c, api):
    """Module 4 (reports) and module 5 (XML exchange): who may use them, and a real export, upload and dry run."""
    # --- the report catalogue follows the user's rights
    slugs = {}
    for key in ("admin", "leader", "officer", "cataloger"):
        status, body = c[key].json(api + "reports.list_reports")
        slugs[key] = {r["slug"] for g in body.get("message", []) for r in g["reports"]}
        check(f"{key} lists reports", status == 200 and len(slugs[key]) >= 6, f"{status} {len(slugs[key])}")
    check("admin and leader see every report", slugs["admin"] == slugs["leader"] and len(slugs["admin"]) >= 11, str(slugs["admin"]))
    check("the officer has the reader reports, not the inventory", "doc-gia" in slugs["officer"] and "tong-kiem-ke" not in slugs["officer"])
    check("the cataloger has the archive reports, not the reader ones", "phong" in slugs["cataloger"] and "doc-gia" not in slugs["cataloger"])
    for key in ("reader", "noprofile", "guest"):
        for endpoint in ("reports.list_reports", "reports.run_report?slug=phong", "reports.download_report?slug=phong",
                         "reports.print_report?slug=phong"):
            check(f"{key} cannot {endpoint.split('?')[0]}", c[key].json(api + endpoint)[0] in (401, 403))
    check("the cataloger cannot run a reader report", c["cataloger"].json(api + "reports.run_report?slug=doc-gia")[0] == 403)
    check("an unknown report is a 404", c["admin"].json(api + "reports.run_report?slug=khong-co")[0] == 404)

    # --- every report runs on the live data
    for slug in sorted(slugs["admin"]):
        status, body = c["admin"].json(api + f"reports.run_report?slug={slug}&page_size=5")
        result = body.get("message", {})
        check(f"report {slug} runs", status == 200 and isinstance(result.get("rows"), list) and "columns" in result, f"{status} {str(body)[:160]}")
    status, body = c["admin"].json(api + "reports.run_report?slug=ho-so&page_size=2&page=1")
    check("a paged report pages", status == 200 and len(body["message"]["rows"]) <= 2 and body["message"]["paged"])
    bad = urllib.parse.quote(json.dumps({"status": "x"}))
    check("a bad filter value is refused", c["admin"].json(api + f"reports.run_report?slug=ho-so&filters={bad}")[0] in (400, 417))

    # --- output files
    status, content, kind = c["officer"].raw(api + "reports.download_report?slug=phong&format=xlsx")
    check("xlsx download", status == 200 and content[:2] == b"PK" and "spreadsheet" in kind, f"{status} {kind}")
    status, content, kind = c["officer"].raw(api + "reports.download_report?slug=phong&format=csv")
    check("csv download carries the BOM", status == 200 and content.startswith(b"\xef\xbb\xbf") and "csv" in kind, f"{status} {kind}")
    status, content, kind = c["officer"].raw(api + "reports.print_report?slug=thong-ke-phong")
    check("printable page has the signature block", status == 200 and "html" in kind and "Người lập biểu".encode() in content, f"{status} {kind}")
    status, content, kind = c["officer"].raw(api + "reports.print_report?slug=phong&format=pdf")
    check("pdf printout", status == 200 and content[:4] == b"%PDF", f"{status} {kind}")
    check("a download refuses an unknown format", c["admin"].json(api + "reports.download_report?slug=phong&format=exe")[0] in (400, 417))

    # --- pages and old addresses
    for key in ("admin", "leader", "officer", "cataloger"):
        check(f"{key} opens the report hub", c[key].request("/dashboard/bao-cao")[0] == 200)
    check("reader does not get the staff app", c["reader"].request("/dashboard/bao-cao")[0] in (301, 302, 303))
    status, _, location = c["officer"].request("/reports/thong_ke_tai_lieu")
    check("old report page forwards to the report", status == 301 and location == "/dashboard/bao-cao/thong-ke-phong", f"{status} {location}")
    status, _, location = c["guest"].request("/reports/thong_ke_khai_thac")
    check("old usage report forwards too", status == 301 and location == "/dashboard/bao-cao/thong-ke-phieu", f"{status} {location}")
    check("a staff user opens the exchange page", c["admin"].request("/dashboard/trao-doi-du-lieu")[0] == 200)

    # --- who may exchange XML
    for key in ("officer", "leader", "cataloger", "reader", "noprofile", "guest"):
        for endpoint in ("exchange.capabilities", "exchange.list_jobs", "exchange.download_schema", "exchange.preview_export?level=Fonds"):
            check(f"{key} cannot {endpoint.split('?')[0]}", c[key].json(api + endpoint)[0] in (401, 403))
        status, _ = c[key].post_json(api + "exchange.start_export", {"level": "Fonds"})
        check(f"{key} cannot start an export", status in (401, 403), str(status))
        status, _ = c[key].post_json(api + "exchange.analyze_import", {"file_url": "/private/files/x.xml"})
        check(f"{key} cannot analyse an upload", status in (401, 403), str(status))
    status, body = c["admin"].json(api + "exchange.capabilities")
    check("admin reads the exchange capabilities", status == 200 and len(body["message"]["levels"]) == 5, str(status))
    status, content, kind = c["admin"].raw(api + "exchange.download_schema")
    check("the XSD downloads", status == 200 and b"ArchiveExchange" in content and b"<xs:schema" in content, f"{status} {kind}")
    status, body = c["admin"].post_json(api + "exchange.start_export", {"level": "Fonds", "filters": {"query": "e2e-khong-co-phong-nay"}})
    check("an export that finds nothing is refused", status in (400, 417), str(status))
    status, body = c["admin"].post_json(api + "exchange.start_export", {"level": "Fonds", "fields": {"Fonds": ["owner"]}})
    check("an export of a field outside the format is refused", status in (400, 417), str(status))

    # --- a real export through the queue, and what comes back
    status, body = c["admin"].post_json(api + "exchange.start_export", {"level": "Fonds", "include_children": 0})
    job = body.get("message", {})
    check("an export is queued", status == 200 and job.get("status") in ("Chờ xử lý", "Đang xử lý", "Hoàn thành"), f"{status} {str(body)[:200]}")
    name = job.get("name", "")
    finished = wait_for(c["admin"], api + f"exchange.get_job?job={name}")
    check("the worker finishes the export", finished.get("status") in ("Hoàn thành", "Hoàn thành có lỗi") and finished.get("has_result"), str(finished)[:200])
    status, xml, kind = c["admin"].raw(api + f"exchange.download?job={name}")
    check("the export downloads as XML", status == 200 and xml.startswith(b"<?xml") and b"<ArchiveExchange" in xml, f"{status} {kind}")
    check("it holds no storage or system field", not any(x in xml for x in (b"gridfs", b"content_text", b"<owner>", b"<name>")))
    check("an officer cannot download it", c["officer"].json(api + f"exchange.download?job={name}")[0] in (401, 403))

    status, url = c["admin"].upload("e2e-export.xml", xml)
    check("the file uploads as private", status == 200 and url.startswith("/private/files/"), f"{status} {url}")
    status, body = c["admin"].post_json(api + "exchange.analyze_import", {"file_url": url})
    analysed = body.get("message", {})
    check("the uploaded file is analysed and valid", status == 200 and analysed.get("valid") and analysed["job"]["analysis"]["total"] >= 0, str(body)[:200])
    upload_job = (analysed.get("job") or {}).get("name", "")
    status, body = c["admin"].post_json(api + "exchange.start_import", {"job": upload_job, "dry_run": 1})
    check("a dry run is queued", status == 200 and body.get("message", {}).get("dry_run") == 1, str(body)[:200])
    dry = wait_for(c["admin"], api + f"exchange.get_job?job={upload_job}")
    check("the dry run finishes without errors and creates nothing", dry.get("status") == "Hoàn thành" and dry.get("created") == 0 and dry.get("failed") == 0, str(dry)[:240])
    check("its summary says it was a rehearsal", "Chạy thử" in dry.get("summary", ""), dry.get("summary", ""))

    # --- hostile and malformed uploads
    head = b'<?xml version="1.0"?>'
    hostile = (
        ("an entity declaration", head + b'<!DOCTYPE d [<!ENTITY a "b">]><ArchiveExchange version="1.0">&a;</ArchiveExchange>'),
        ("another root element", head + b'<Other version="1.0"/>'),
        ("an invalid date", head + b'<ArchiveExchange version="1.0"><Fonds><fonds_name>x</fonds_name><RecordGroup>'
                                  b"<group_title>g</group_title><Catalog><catalog_title>c</catalog_title><ArchivalFile><file_title>f</file_title>"
                                  b"<start_date>05/03/1995</start_date></ArchivalFile></Catalog></RecordGroup></Fonds></ArchiveExchange>"),
    )
    for label, content in hostile:
        status, url = c["admin"].upload("e2e-bad.xml", content)
        status, body = c["admin"].post_json(api + "exchange.analyze_import", {"file_url": url})
        refused = status in (400, 417) or (status == 200 and body.get("message", {}).get("valid") is False)
        check(f"{label} is refused", refused, f"{status} {str(body)[:160]}")
    status, url = c["admin"].upload("e2e-note.txt", b'<ArchiveExchange version="1.0"/>')
    check("only .xml files are read", c["admin"].post_json(api + "exchange.analyze_import", {"file_url": url})[0] in (400, 417))
    status, url = c["admin"].upload("e2e-public.xml", b'<ArchiveExchange version="1.0"/>', private=0)
    check("a public file is not read", c["admin"].post_json(api + "exchange.analyze_import", {"file_url": url})[0] in (403, 417))
    for finished_job in (name, upload_job):
        if finished_job:
            c["admin"].post_json(api + "exchange.delete_job", {"job": finished_job})


def preservation_and_administration(c, api):
    """Module 7 (preservation) and module 8 (administration): who may use them, the guards, and the old addresses."""
    import time

    outsiders = ("officer", "leader", "cataloger", "reader", "noprofile", "guest")
    # --- preservation: administrators and preservation officers only
    for key in outsiders:
        for endpoint in ("preservation.overview", "preservation.list_jobs?kind=backup", "preservation.get_job?kind=backup&name=BK-x",
                         "preservation.download_backup?name=BK-x", "preservation.list_findings?check=IC-x"):
            check(f"{key} cannot {endpoint.split('?')[0]}", c[key].json(api + endpoint)[0] in (401, 403))
        for endpoint, data in (("start_backup", {}), ("start_check", {}), ("start_restore", {"documents": ["x"]}), ("fix_counters", {}),
                               ("run_retention", {}), ("delete_job", {"kind": "backup", "name": "BK-x"}), ("prepare_db_restore", {"source_backup": "BK-x"}),
                               ("run_restore", {"name": "RS-x", "confirm_site": "x"})):
            status, _ = c[key].post_json(api + f"preservation.{endpoint}", data)
            check(f"{key} cannot {endpoint}", status in (401, 403), str(status))
    for key in ("admin", "preserver"):
        status, body = c[key].json(api + "preservation.overview")
        check(f"{key} reads the preservation overview", status == 200 and {"settings", "site"} <= set(body.get("message", {})), f"{status} {str(body)[:160]}")
        for kind in ("backup", "integrity", "restore"):
            status, body = c[key].json(api + f"preservation.list_jobs?kind={kind}")
            check(f"{key} lists {kind} jobs", status == 200 and "data" in body.get("message", {}), f"{status} {str(body)[:120]}")
    check("an unknown kind of job is refused", c["admin"].json(api + "preservation.list_jobs?kind=bogus")[0] in (400, 417))
    for name in ("../../../etc/passwd", "..%2f..%2fsites%2fcommon_site_config.json", "BK-khong-co"):
        status, _, _ = c["admin"].raw(api + f"preservation.download_backup?name={name}")
        check(f"a backup download of {name[:22]} is refused", status in (400, 403, 404, 417), str(status))
    check("a restore of nothing is refused", c["admin"].post_json(api + "preservation.start_restore", {})[0] in (400, 417))
    status, body = c["admin"].post_json(api + "preservation.run_restore", {"name": "RS-khong-co", "confirm_site": "x"})
    check("a database restore needs an existing batch and the site name", status in (400, 404, 417), f"{status} {str(body)[:120]}")

    # --- administration: administrators only
    for key in ("preserver", *outsiders):
        for endpoint in ("users.list_users", "users.roles_info", "users.role_matrix", "users.get_user?name=e2e.admin@example.com",
                         "logs.list_logs", "logs.filter_options", "logs.download_logs", "logs.preview_purge?before=2020-01-01", "admin.monitor"):
            check(f"{key} cannot {endpoint.split('?')[0]}", c[key].json(api + endpoint)[0] in (401, 403))
        for endpoint, data in (("users.save_user", {"values": {"email": "e2e.nobody@example.com", "first_name": "X", "roles": ["Cataloger"]}}),
                               ("users.set_enabled", {"name": "e2e.cataloger@example.com", "enabled": 0}),
                               ("users.issue_password_link", {"name": "e2e.cataloger@example.com"}),
                               ("users.delete_user", {"name": "e2e.cataloger@example.com"}),
                               ("logs.purge", {"before": "2020-01-01", "confirm_count": 1})):
            status, _ = c[key].post_json(api + endpoint, data)
            check(f"{key} cannot {endpoint}", status in (401, 403), str(status))
    check("every account is still enabled after those attempts", all(
        c["admin"].json(api + f"users.get_user?name={e}")[1].get("message", {}).get("enabled") == 1
        for e in ("e2e.cataloger@example.com", "e2e.officer@example.com")))

    status, body = c["admin"].json(api + "users.list_users?page_size=200")
    rows = body.get("message", {}).get("data", [])
    names = {r["name"] for r in rows}
    check("the user list holds staff", status == 200 and {"e2e.admin@example.com", "e2e.cataloger@example.com", "e2e.preserver@example.com"} <= names, f"{status} {len(rows)}")
    check("it holds no reader, no system account", not ({"e2e.reader@example.com", "e2e.noprofile@example.com", "Administrator", "Guest"} & names), str(sorted(names))[:200])
    check("the one asking is marked", any(r["name"] == "e2e.admin@example.com" and r["is_me"] for r in rows))
    status, body = c["admin"].json(api + "users.roles_info")
    roles = {r["role"] for r in body.get("message", [])}
    check("the roles offered are the five staff roles", status == 200 and roles == {"Document Admin", "Cataloger", "Reading Room Officer", "Archive Leader", "Preservation Officer"}, str(roles))
    status, body = c["admin"].json(api + "users.role_matrix")
    sections = {s["section"] for s in body.get("message", {}).get("sections", [])}
    check("the role matrix has its sections", status == 200 and {"Biên mục", "Danh mục", "Bảo quản", "Quản trị"} <= sections, str(sections))

    # --- the guards that keep an administrator from locking everyone out or raising themselves
    attempts = (
        ("creating a System Manager", "users.save_user", {"values": {"email": "e2e.sm@example.com", "first_name": "X", "roles": ["System Manager"]}}),
        ("creating an Administrator", "users.save_user", {"values": {"email": "e2e.adm@example.com", "first_name": "X", "roles": ["Administrator"]}}),
        ("editing Administrator", "users.save_user", {"values": {"first_name": "Hacked"}, "name": "Administrator"}),
        ("locking Administrator", "users.set_enabled", {"name": "Administrator", "enabled": 0}),
        ("deleting Administrator", "users.delete_user", {"name": "Administrator"}),
        ("a password link for Administrator", "users.issue_password_link", {"name": "Administrator"}),
        ("editing a reader's account", "users.save_user", {"values": {"first_name": "Hacked"}, "name": "e2e.reader@example.com"}),
        ("deleting a reader's account", "users.delete_user", {"name": "e2e.reader@example.com"}),
        ("locking oneself", "users.set_enabled", {"name": "e2e.admin@example.com", "enabled": 0}),
        ("deleting oneself", "users.delete_user", {"name": "e2e.admin@example.com"}),
        ("demoting oneself", "users.save_user", {"values": {"roles": ["Cataloger"]}, "name": "e2e.admin@example.com"}),
        ("a made-up email", "users.save_user", {"values": {"email": "not-an-email", "first_name": "X", "roles": ["Cataloger"]}}),
        ("an existing email", "users.save_user", {"values": {"email": "e2e.cataloger@example.com", "first_name": "X", "roles": ["Cataloger"]}}),
        ("a clean-up of recent days", "logs.purge", {"before": time.strftime("%Y-%m-%d"), "confirm_count": 1}),
    )
    for label, endpoint, data in attempts:
        status, _ = c["admin"].post_json(api + endpoint, data)
        check(f"{label} is refused", status in (400, 403, 404, 417), str(status))
    check("the administrator is still themselves", c["admin"].json(api + "users.get_user?name=e2e.admin@example.com")[1]["message"]["roles"] == ["Document Admin"])
    status, body = c["admin"].json(api + "logs.preview_purge?before=2020-01-01")
    check("a clean-up preview counts without deleting", status == 200 and "total" in body.get("message", {}), f"{status} {str(body)[:120]}")
    check("a clean-up needs the count back", c["admin"].post_json(api + "logs.purge", {"before": "2020-01-01", "confirm_count": 10 ** 9})[0] in (400, 417))

    # --- a real account: created with a one-time link, edited, locked and removed
    email = f"e2e.http{int(time.time()) % 100000}@example.com"
    status, body = c["admin"].post_json(api + "users.save_user", {"values": {"email": email, "first_name": "Http", "roles": ["Cataloger", "Preservation Officer"]}})
    made = body.get("message", {})
    check("an account is created with its roles and a one-time link", status == 200 and made.get("name") == email and made.get("set_password_path", "").startswith("/dat-mat-khau?key="), f"{status} {str(body)[:200]}")
    check("the new account has the roles asked for", sorted(made.get("roles", [])) == ["Cataloger", "Preservation Officer"], str(made.get("roles")))
    status, body = c["admin"].post_json(api + "users.save_user", {"values": {"roles": ["Reading Room Officer"]}, "name": email})
    check("its roles are replaced", status == 200 and body["message"]["roles"] == ["Reading Room Officer"], f"{status} {str(body)[:160]}")
    status, body = c["admin"].json(api + f"users.list_users?search={email}&role=Reading%20Room%20Officer")
    check("the list finds it by search and role", status == 200 and [r["name"] for r in body["message"]["data"]] == [email], f"{status} {str(body)[:160]}")
    status, body = c["admin"].post_json(api + "users.set_enabled", {"name": email, "enabled": 0})
    check("it is locked", status == 200 and body["message"]["enabled"] == 0, f"{status} {str(body)[:120]}")
    check("a locked account gets no password link", c["admin"].post_json(api + "users.issue_password_link", {"name": email})[0] in (400, 417))
    status, body = c["admin"].post_json(api + "users.set_enabled", {"name": email, "enabled": 1})
    check("it is unlocked", status == 200 and body["message"]["enabled"] == 1)
    status, body = c["admin"].post_json(api + "users.issue_password_link", {"name": email})
    check("a new link can be issued", status == 200 and "/dat-mat-khau?key=" in body.get("message", {}).get("set_password_path", ""), f"{status} {str(body)[:120]}")
    status, body = c["admin"].post_json(api + "users.delete_user", {"name": email})
    check("an account never used is deleted", status == 200 and body["message"]["name"] == email, f"{status} {str(body)[:160]}")
    check("and is gone", c["admin"].json(api + f"users.get_user?name={email}")[0] == 404)

    # --- the log and the monitor
    kind_param = urllib.parse.quote("Quản lý người dùng")
    status, content, kind = c["admin"].raw(api + f"logs.download_logs?activity_type={kind_param}")
    check("the log downloads as CSV with the BOM", status == 200 and content.startswith(b"\xef\xbb\xbf") and "csv" in kind, f"{status} {kind}")
    status, body = c["admin"].json(api + f"logs.list_logs?activity_type={kind_param}&page_size=5")
    check("the log is filtered by type", status == 200 and body["message"]["total"] >= 1 and all(r["activity_type"] == "Quản lý người dùng" for r in body["message"]["data"]), f"{status} {str(body)[:160]}")
    check("a page of the log is capped", len(c["admin"].json(api + "logs.list_logs?page_size=100000")[1]["message"]["data"]) <= 200)
    status, body = c["admin"].json(api + "admin.monitor")
    check("the monitor gathers the state of the system", status == 200 and {"services", "documents", "jobs", "storage", "users", "backups", "log"} <= set(body.get("message", {})), f"{status} {str(body)[:160]}")

    # --- pages and the old addresses
    for path, target in (("/backup_batches", "/dashboard/bao-quan/sao-luu"), ("/integrity_checks", "/dashboard/bao-quan/kiem-tra"),
                         ("/restore_batches", "/dashboard/bao-quan/khoi-phuc"), ("/business_activity_log", "/dashboard/quan-tri/nhat-ky"),
                         ("/document_manager_settings", "/dashboard/quan-tri/thiet-lap-he-thong")):
        status, _, location = c["admin"].request(path)
        check(f"{path} forwards to the staff app", status == 301 and location == target, f"{status} {location}")
    for key, path in (("admin", "/dashboard/quan-tri/nguoi-dung"), ("admin", "/dashboard/quan-tri/nhat-ky"), ("admin", "/dashboard/bao-quan/kiem-tra"),
                      ("preserver", "/dashboard/bao-quan/sao-luu"), ("cataloger", "/dashboard/quan-tri/nguoi-dung")):
        check(f"{key} opens {path}", c[key].request(path)[0] == 200)  # the shell loads; the data calls above enforce the rights
    check("a reader does not get the staff app", c["reader"].request("/dashboard/quan-tri/nguoi-dung")[0] in (301, 302, 303))
    check("a guest does not get the staff app", c["guest"].request("/dashboard/bao-quan/sao-luu")[0] in (301, 302, 303))


if __name__ == "__main__":
    sys.exit(main())
