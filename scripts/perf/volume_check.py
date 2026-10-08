"""Volume check: fill a scratch site with about a million documents and time the hot paths of the app.

Never run it on the live site: it refuses any site whose name does not start with "perf". Create the scratch site once
(separate database), from the `sites` directory of the backend container:

    bench new-site perfdm.localhost --db-root-username root --db-root-password <root password> \
        --admin-password perf --mariadb-user-host-login-scope='%' --install-app document_manager

The script comes in on stdin, the first argument is the step:

    docker compose exec -T -w /home/frappe/frappe-bench/sites backend \
        /home/frappe/frappe-bench/env/bin/python - seed    < scripts/perf/volume_check.py   # fills the tables (resumable)
    ... python - measure < scripts/perf/volume_check.py   # timings of API and service calls, EXPLAIN of the slow SQL
    ... python - reset   < scripts/perf/volume_check.py   # empties the seeded tables again

Environment: DM_PERF_SITE (default perfdm.localhost), DM_PERF_SCALE (1 = 1,000,000 documents; 0.1 for a quick try),
DM_PERF_SLOW_MS (default 300: a query slower than this is explained).

Reading the result: "best" is the fastest of three runs (warm buffer pool), "n" the number of SQL statements. A page of a list
should answer in well under a second at the full scale; the integrity checks and the statistics reports are background or
on-demand work and may take seconds, but must not take minutes.
"""
import os
import statistics
import sys
import time

import frappe

SITE = os.environ.get("DM_PERF_SITE", "perfdm.localhost")
SCALE = float(os.environ.get("DM_PERF_SCALE", "1"))
SLOW_MS = float(os.environ.get("DM_PERF_SLOW_MS", "300"))
STEP = sys.argv[-1]
if not SITE.startswith("perf"):
    sys.exit(f"{SITE}: refusing to run on a site whose name does not start with 'perf'")


def scaled(base: int) -> int:
    return max(1, int(base * SCALE))


FONDS, GROUPS, CATALOGS = scaled(20), scaled(400), scaled(4000)
FILES, DOCS, LOGS, READERS, USAGE = scaled(200_000), scaled(1_000_000), scaled(1_000_000), scaled(20_000), scaled(100_000)
GROUPS_PER_FONDS = max(1, GROUPS // FONDS)
CATALOGS_PER_GROUP = max(1, CATALOGS // GROUPS)
FILES_PER_CATALOG = max(1, FILES // CATALOGS)
DOCS_PER_FILE = max(1, DOCS // FILES)

frappe.init(site=SITE)
frappe.connect()
frappe.set_user("Administrator")
from document_manager.document_manager.services import lifecycle as lc  # noqa: E402  (needs the site)


def pad(prefix: str, expr: str) -> str:
    return f"concat('{prefix}', lpad({expr}, 8, '0'))"


LEVEL = "case when seq mod 100 < 90 then 'Thường' when seq mod 100 < 98 then 'Mật' else 'Tối mật' end"
# `modified` spread over a year in an order unrelated to the hierarchy: with one shared timestamp every query that sorts by
# `modified` looks perfect to the optimizer and the numbers would flatter the application
SCATTER = "date_sub(now(), interval (seq * 7919) mod 31536000 second)"
DAY = "date_add('1990-01-01', interval (seq * 7) mod 13000 day)"
TABLES = {
    # doctype: (rows, {column: sql expression over `seq`})
    "Fonds": (FONDS, {
        "fonds_name": "concat('Phông thử nghiệm ', seq)", "fonds_code": "concat('PF', seq)", "start_year": "1990", "end_year": "2025",
        "total_files": str(FILES // FONDS)}),
    "Record Group": (GROUPS, {
        "group_title": "concat('Khối tài liệu ', seq)", "group_code": "concat('RG', seq)", "fonds": pad("PF-", f"1 + (seq - 1) div {GROUPS_PER_FONDS}")}),
    "Catalog": (CATALOGS, {
        "catalog_title": "concat('Mục lục ', seq)", "catalog_number": "seq",
        "record_group": pad("RG-", f"1 + (seq - 1) div {CATALOGS_PER_GROUP}"),
        "fonds": pad("PF-", f"1 + (seq - 1) div {CATALOGS_PER_GROUP * GROUPS_PER_FONDS}")}),
    "Archival File": (FILES, {
        "file_title": "concat('Hồ sơ về việc phê duyệt kế hoạch số ', seq)", "file_number": f"seq mod {FILES_PER_CATALOG} + 1",
        "catalog": pad("CT-", f"1 + (seq - 1) div {FILES_PER_CATALOG}"),
        "record_group": pad("RG-", f"1 + (seq - 1) div {FILES_PER_CATALOG * CATALOGS_PER_GROUP}"),
        "fonds": pad("PF-", f"1 + (seq - 1) div {FILES_PER_CATALOG * CATALOGS_PER_GROUP * GROUPS_PER_FONDS}"),
        "status": "if(seq mod 10 = 0, 'Nháp', 'Đã hoàn thành')", "start_date": DAY, "end_date": f"date_add({DAY}, interval 30 day)",
        "total_documents": str(DOCS_PER_FILE), "total_pages": "seq mod 400", "confidentiality_level": LEVEL}),
    "Archive Document": (DOCS, {
        "document_title": "concat('Quyết định số ', seq, ' về việc phê duyệt kế hoạch công tác năm ', 1990 + seq mod 36)",
        "document_number": "concat(seq mod 5000, '/QĐ-UBND')", "author": "concat('Ủy ban nhân dân cấp ', seq mod 200)",
        "document_date": DAY, "file_type": "case when seq mod 10 < 7 then 'pdf' when seq mod 10 < 9 then 'docx' else 'jpg' end",
        "search_index_status": "if(seq mod 20 = 0, 'Chưa index', 'Đã index')", "checksum": "md5(seq)",
        "file_attachment": "concat('/private/files/doc', seq, '.pdf')", "content_text": "concat('Nội dung văn bản số ', seq, ' của ủy ban nhân dân')",
        "archival_file": pad("AF-", f"1 + (seq - 1) div {DOCS_PER_FILE}"),
        "catalog": pad("CT-", f"1 + (seq - 1) div {DOCS_PER_FILE * FILES_PER_CATALOG}"),
        "record_group": pad("RG-", f"1 + (seq - 1) div {DOCS_PER_FILE * FILES_PER_CATALOG * CATALOGS_PER_GROUP}"),
        "fonds": pad("PF-", f"1 + (seq - 1) div {DOCS_PER_FILE * FILES_PER_CATALOG * CATALOGS_PER_GROUP * GROUPS_PER_FONDS}"),
        "confidentiality_level": LEVEL}),
    "Business Activity Log": (LOGS, {
        "activity_type": "elt(1 + seq mod 6, 'Xem', 'Tạo mới', 'Cập nhật', 'Tìm kiếm', 'Đăng nhập', 'Tải xuống')",
        "reference_doctype": "'Archive Document'", "reference_name": pad("AD-", f"1 + seq mod {DOCS}"),
        "user": "elt(1 + seq mod 4, 'Administrator', 'perf.officer@example.com', 'perf.reader@example.com', 'perf.cataloger@example.com')",
        "timestamp": "date_add(date_sub(now(), interval seq mod 700 day), interval seq mod 86400 second)",
        "description": "concat('Xem văn bản ', seq)"}),
    "Reader": (READERS, {
        "full_name": "concat('Độc giả thử nghiệm ', seq)", "email": "concat('doc.gia.', seq, '@example.com')", "is_active": "1",
        "id_number": "lpad(seq, 12, '0')"}),
    "Usage Request": (USAGE, {
        "reader": pad("RD-", f"1 + seq mod {READERS}"), "request_date": "date_sub(curdate(), interval seq mod 500 day)", "docstatus": "1",
        "workflow_state": f"elt(1 + seq mod 10, '{lc.STATE_PENDING}', '{lc.STATE_LEADER}', '{lc.STATE_APPROVED}', '{lc.STATE_IN_USE}', "
                          f"'{lc.STATE_IN_USE}', '{lc.STATE_RETURNED}', '{lc.STATE_RETURNED}', '{lc.STATE_RETURNED}', '{lc.STATE_REJECTED}', "
                          f"'{lc.STATE_RETURNED}')",
        "purpose": "'Nghiên cứu'", "due_date": "date_add(curdate(), interval seq mod 30 day)", "is_overdue": "if(seq mod 50 = 0, 1, 0)"}),
}
NAME = {"Fonds": "PF-", "Record Group": "RG-", "Catalog": "CT-", "Archival File": "AF-", "Archive Document": "AD-",
        "Business Activity Log": "LG-", "Reader": "RD-", "Usage Request": "UR-"}
CHUNK = 100_000


def seed() -> None:
    for doctype, (rows, columns) in TABLES.items():
        table = f"`tab{doctype}`"
        have = frappe.db.sql(f"select count(*) from {table}")[0][0]
        if have >= rows:
            print(f"{doctype}: {have} rows, nothing to add", flush=True)
            continue
        stored = {c: e for c, e in columns.items() if c != "docstatus"}
        modified = SCATTER if doctype in ("Archive Document", "Archival File", "Usage Request", "Business Activity Log") else "now()"
        names = ", ".join(stored)
        values = ", ".join(stored.values())
        docstatus = columns.get("docstatus", "0")
        started = time.time()
        for start in range(have + 1, rows + 1, CHUNK):
            end = min(rows, start + CHUNK - 1)
            frappe.db.sql(
                f"insert into {table} (name, creation, modified, modified_by, owner, docstatus, idx, {names}) "
                f"select {pad(NAME[doctype], 'seq')}, {modified}, {modified}, 'Administrator', 'Administrator', {docstatus}, 0, {values} "
                f"from seq_{start}_to_{end}")
            frappe.db.commit()
        print(f"{doctype}: {rows} rows in {time.time() - started:.0f} s", flush=True)
    for email, role in (("perf.reader@example.com", "Reader"), ("perf.officer@example.com", "Reading Room Officer"),
                        ("perf.cataloger@example.com", "Cataloger")):
        if not frappe.db.exists("User", email):
            user = frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0,
                                   "user_type": "Website User" if role == "Reader" else "System User",
                                   "roles": [{"role": role}]}).insert(ignore_permissions=True)
            user.db_set("enabled", 1)
    if not frappe.db.exists("Reader", {"user": "perf.reader@example.com"}):
        frappe.get_doc({"doctype": "Reader", "full_name": "Perf Reader", "user": "perf.reader@example.com",
                        "email": "perf.reader@example.com", "is_active": 1}).insert(ignore_permissions=True)
    frappe.db.commit()
    for doctype in TABLES:
        frappe.db.sql(f"analyze table `tab{doctype}`")
    print("analysed", flush=True)


# --- measuring ------------------------------------------------------------------------------------------------------------

SLOW: list = []
STATEMENTS = [0]
_original_sql = frappe.db.sql


def _traced(query, *args, **kwargs):
    started = time.perf_counter()
    try:
        return _original_sql(query, *args, **kwargs)
    finally:
        elapsed = (time.perf_counter() - started) * 1000
        STATEMENTS[0] += 1
        if elapsed >= SLOW_MS and str(query).lstrip().lower().startswith(("select", "with")):
            SLOW.append((elapsed, str(query), args[0] if args else kwargs.get("values")))


def timed(label, fn, repeat=3):
    runs, shown = [], None
    for _ in range(repeat):
        SLOW.clear()
        STATEMENTS[0] = 0
        started = time.perf_counter()
        try:
            fn()
        except Exception as exc:  # a failing call is a result too
            print(f"{label:62} ERROR {type(exc).__name__}: {str(exc)[:80]}", flush=True)
            return None
        runs.append((time.perf_counter() - started) * 1000)
        shown = (STATEMENTS[0], list(SLOW))
    best = min(runs)
    flag = "  <-- slow" if best > 1000 else ""
    print(f"{label:62} best {best:8.0f} ms   median {statistics.median(runs):8.0f} ms   n={shown[0]:<3}{flag}", flush=True)
    return label, best, shown[1]


def explain(entries) -> None:
    done = set()
    for label, best, slow in entries:
        for elapsed, query, values in sorted(slow, key=lambda s: -s[0])[:2]:
            key = " ".join(query.split())[:200]
            if key in done:
                continue
            done.add(key)
            print(f"\n[{label}] {elapsed:.0f} ms\n  {' '.join(query.split())[:500]}")
            try:
                for row in _original_sql("explain " + query, values, as_dict=True):
                    print("   ", {k: row[k] for k in ("table", "type", "key", "rows", "Extra") if row.get(k) is not None})
            except Exception as exc:
                print("    (explain failed:", str(exc)[:100], ")")


def measure() -> None:
    from document_manager.document_manager.api import archive, boot, crud, dashboard, logs, slips, users
    from document_manager.document_manager.api import admin as admin_api
    from document_manager.document_manager.services import reports, search_service
    from document_manager.document_manager.services.preservation import integrity

    frappe.db.sql = _traced
    results = []

    def case(label, fn):
        results.append(timed(label, fn))

    sample_catalog, sample_group, sample_fonds = "CT-00001234", "RG-00000077", "PF-00000005"

    print(f"\n== staff ({DOCS:,} documents, {FILES:,} files, {LOGS:,} log rows)\n")
    frappe.set_user("Administrator")
    case("crud list: documents, newest, page 1", lambda: crud.get_list("Archive Document", page=1))
    case("crud list: documents, page 5000 (deep paging)", lambda: crud.get_list("Archive Document", page=5000, page_size=20))
    case("crud list: documents of one file", lambda: crud.get_list("Archive Document", filters={"archival_file": "AF-00012345"}))
    case("crud list: documents of one catalog, page 3", lambda: crud.get_list("Archive Document", filters={"catalog": sample_catalog}, page=3))
    case("crud list: documents, text search 'Quyết định số 5000'", lambda: crud.get_list("Archive Document", search="Quyết định số 5000"))
    case("crud list: files of one catalog", lambda: crud.get_list("Archival File", filters={"catalog": sample_catalog}))
    case("crud list: files, text search", lambda: crud.get_list("Archival File", search="kế hoạch số 777"))
    case("slips: queue of usage requests (waiting)", lambda: slips.list_slips("usage", "cho_tiep_nhan"))
    case("slips: queue of usage requests, text search", lambda: slips.list_slips("usage", "cho_tiep_nhan", search="RD-00000077"))
    case("slips: queue 'all', page 400", lambda: slips.list_slips("usage", "tat_ca", page=400))
    case("slips: counters of the queue tabs", lambda: slips.queue_summary())
    case("slips: sidebar counters", lambda: slips.queue_badges())
    case("tree: fonds", lambda: archive.get_tree())
    case("tree: groups of a fonds", lambda: archive.get_tree("Fonds", sample_fonds))
    case("tree: catalogs of a group", lambda: archive.get_tree("Record Group", sample_group))
    case("overview (dashboard counters)", lambda: dashboard.get_workspace_summary())
    case("sidebar (boot)", lambda: boot.build_boot())
    case("search documents: 'quyết định 5000' (database fallback)", lambda: search_service._search_documents_db({"query": "quyết định 5000"}, 1, 20))
    case("search documents: advanced, author + date range", lambda: search_service.search_documents(
        {"author": "cấp 12", "date_from": "2005-01-01", "date_to": "2006-01-01"}))
    case("search files: title", lambda: search_service.search_files({"file_title": "kế hoạch số 123"}))
    case("search files: fonds + date range", lambda: search_service.search_files(
        {"fonds": sample_fonds, "start_date_from": "2000-01-01", "start_date_to": "2001-01-01"}))
    case("log list: newest page", lambda: logs.list_logs())
    case("log list: one type, last month", lambda: logs.list_logs(activity_type="Xem", date_from=frappe.utils.add_days(frappe.utils.nowdate(), -30)))
    case("log list: text search", lambda: logs.list_logs(search="văn bản 77777"))
    case("log purge preview (older than 400 days)", lambda: logs.preview_purge(frappe.utils.add_days(frappe.utils.nowdate(), -400)))
    case("users list", lambda: users.list_users())
    case("monitor", lambda: admin_api.monitor())

    print("\n== reports\n")
    for slug in sorted(reports.REPORTS):
        case(f"report {slug}", lambda slug=slug: reports.run(slug, {}, 1, 20))
    case("report van-ban, one fonds (the way it is used)", lambda: reports.run("van-ban", {"fonds": sample_fonds}, 1, 20))
    case("report ho-so, one fonds", lambda: reports.run("ho-so", {"fonds": sample_fonds}, 1, 20))

    print("\n== readers (policy conditions in every query)\n")
    frappe.set_user("perf.reader@example.com")
    case("reader: search documents 'quyết định 5000' (database)", lambda: search_service._search_documents_db({"query": "quyết định 5000"}, 1, 20))
    case("reader: search documents of one fonds", lambda: search_service.search_documents({"fonds": sample_fonds}, page=2))
    case("reader: search documents, author + date range", lambda: search_service.search_documents(
        {"author": "cấp 12", "date_from": "2005-01-01", "date_to": "2006-01-01"}))
    case("reader: search files, title", lambda: search_service.search_files({"file_title": "kế hoạch số 123"}))
    case("reader: search files of one catalog", lambda: search_service.search_files({"catalog": sample_catalog}))
    frappe.set_user("Administrator")

    print("\n== integrity checks (background job)\n")
    for check in [*integrity.DB_CHECKS, *integrity.META_CHECKS]:
        results.append(timed(f"check {check['code']}", lambda check=check: integrity.run_sql_check(check, None), repeat=1))

    frappe.db.sql = _original_sql
    explain([r for r in results if r])


if STEP == "reset":  # empties the seeded tables (the scratch site only)
    for _doctype in TABLES:
        frappe.db.sql(f"truncate table `tab{_doctype}`")
    print("tables emptied")
elif STEP == "seed":
    seed()
elif STEP == "measure":
    measure()
else:
    sys.exit("usage: python - reset|seed|measure < volume_check.py")
