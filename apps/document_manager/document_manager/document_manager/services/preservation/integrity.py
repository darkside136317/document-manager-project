# -*- coding: utf-8 -*-
"""Integrity checks of the archive (module 7).

Three kinds of check, each producing findings (Integrity Check Item rows):

* database  — structure: orphans, hierarchy columns that disagree with their parent, counters, dates, duplicate keys,
              broken links, index state (aggregate SQL: one finding per rule with the count and a few samples);
* metadata  — what an electronic archive needs described (number, date, author, location...) (aggregate SQL, warnings);
* files     — every document one by one: the file is there, is the one that was uploaded (SHA-256), is not empty, fits its
              declared type, and its GridFS copy exists. A finding says whether a backup can restore it.

A run is paged and resumable (`phase` + `cursor`); only problems are stored, the counters count everything.
"""

import frappe
from frappe import _
from frappe.utils import cint, nowdate

from document_manager.document_manager.services.errors import log_exception
from document_manager.document_manager.services.preservation import filestore, runner, sources

JOB = "document_manager.document_manager.services.preservation.integrity.run"
DOCTYPE = "Integrity Check"
DB, META, FILES = "db", "meta", "files"
PHASES = {
    "Toàn bộ": (DB, META, FILES), "Cơ sở dữ liệu": (DB,), "Siêu dữ liệu": (META,), "Tệp tài liệu": (FILES,),
    "Checksum": (FILES,), "Liên kết file-metadata": (FILES,), "File bị thiếu": (FILES,),
}
# which per-file tests an (old or new) kind runs
FILE_TESTS = {
    "Toàn bộ": {"missing", "checksum", "empty", "type", "gridfs"}, "Tệp tài liệu": {"missing", "checksum", "empty", "type", "gridfs"},
    "Checksum": {"checksum"}, "File bị thiếu": {"missing", "gridfs"}, "Liên kết file-metadata": {"link"},
}

AF, AD, CT, RG, FO = "`tabArchival File`", "`tabArchive Document`", "`tabCatalog`", "`tabRecord Group`", "`tabFonds`"


def _check(code, severity, title, sql, scope=None, fixable=False):
    """`sql` selects the names of the offending records; `scope` is the column the fonds filter applies to."""
    return {"code": code, "severity": severity, "title": title, "sql": sql, "scope": scope, "fixable": fixable}


DB_CHECKS = [
    _check("ORPHAN_GROUP", "Lỗi", "Khối tài liệu không còn phông chứa nó",
           f"SELECT g.name FROM {RG} g LEFT JOIN {FO} f ON f.name = g.fonds WHERE f.name IS NULL", "g.fonds"),
    _check("ORPHAN_CATALOG", "Lỗi", "Mục lục không còn khối tài liệu chứa nó",
           f"SELECT c.name FROM {CT} c LEFT JOIN {RG} g ON g.name = c.record_group WHERE g.name IS NULL", "c.fonds"),
    _check("ORPHAN_FILE", "Lỗi", "Hồ sơ không còn mục lục chứa nó",
           f"SELECT a.name FROM {AF} a LEFT JOIN {CT} c ON c.name = a.catalog WHERE c.name IS NULL", "a.fonds"),
    _check("ORPHAN_DOCUMENT", "Lỗi", "Văn bản không còn hồ sơ chứa nó",
           f"SELECT d.name FROM {AD} d LEFT JOIN {AF} a ON a.name = d.archival_file WHERE a.name IS NULL", "d.fonds"),
    _check("HIERARCHY_FILE", "Lỗi", "Hồ sơ ghi phông hoặc khối khác với mục lục chứa nó",
           f"SELECT a.name FROM {AF} a JOIN {CT} c ON c.name = a.catalog WHERE a.fonds <> c.fonds OR a.record_group <> c.record_group", "a.fonds"),
    _check("HIERARCHY_DOCUMENT", "Lỗi", "Văn bản ghi phông, khối hoặc mục lục khác với hồ sơ chứa nó",
           f"SELECT d.name FROM {AD} d JOIN {AF} a ON a.name = d.archival_file "
           "WHERE d.fonds <> a.fonds OR d.record_group <> a.record_group OR d.catalog <> a.catalog", "d.fonds"),
    _check("BROKEN_LEVEL_FILE", "Lỗi", "Hồ sơ có mức độ mật không còn trong danh mục",
           f"SELECT a.name FROM {AF} a LEFT JOIN `tabConfidentiality Level` l ON l.name = a.confidentiality_level "
           "WHERE a.confidentiality_level IS NOT NULL AND a.confidentiality_level <> '' AND l.name IS NULL", "a.fonds"),
    _check("BROKEN_LEVEL_DOCUMENT", "Lỗi", "Văn bản có mức độ mật không còn trong danh mục",
           f"SELECT d.name FROM {AD} d LEFT JOIN `tabConfidentiality Level` l ON l.name = d.confidentiality_level "
           "WHERE d.confidentiality_level IS NOT NULL AND d.confidentiality_level <> '' AND l.name IS NULL", "d.fonds"),
    _check("COUNTER_FONDS", "Cảnh báo", "Số hồ sơ ghi ở phông khác số hồ sơ thực tế",
           f"SELECT f.name FROM {FO} f WHERE f.total_files <> (SELECT COUNT(*) FROM {AF} a WHERE a.fonds = f.name)", "f.name", True),
    _check("COUNTER_FILE", "Cảnh báo", "Số văn bản ghi ở hồ sơ khác số văn bản thực tế",
           f"SELECT a.name FROM {AF} a WHERE a.total_documents <> (SELECT COUNT(*) FROM {AD} d WHERE d.archival_file = a.name)",
           "a.fonds", True),
    _check("DATE_FILE", "Cảnh báo", "Hồ sơ có ngày kết thúc trước ngày bắt đầu",
           f"SELECT a.name FROM {AF} a WHERE a.start_date IS NOT NULL AND a.end_date IS NOT NULL AND a.end_date < a.start_date", "a.fonds"),
    _check("DATE_FONDS", "Cảnh báo", "Phông có năm kết thúc trước năm bắt đầu",
           f"SELECT f.name FROM {FO} f WHERE f.start_year > 0 AND f.end_year > 0 AND f.end_year < f.start_year", "f.name"),
    _check("DATE_FUTURE", "Cảnh báo", "Văn bản có ngày văn bản ở tương lai",
           f"SELECT d.name FROM {AD} d WHERE d.document_date > CURDATE() + INTERVAL 1 DAY", "d.fonds"),
    _check("DUPLICATE_FILE_NUMBER", "Cảnh báo", "Số hồ sơ trùng nhau trong cùng một mục lục",
           f"SELECT CONCAT(a.catalog, ' / ', a.file_number) FROM {AF} a WHERE a.file_number <> '' "
           "GROUP BY a.catalog, a.file_number HAVING COUNT(*) > 1", "a.fonds"),
    _check("DUPLICATE_DOCUMENT_NUMBER", "Cảnh báo", "Số văn bản trùng nhau trong cùng một hồ sơ",
           f"SELECT CONCAT(d.archival_file, ' / ', d.document_number) FROM {AD} d WHERE d.document_number <> '' "
           "GROUP BY d.archival_file, d.document_number HAVING COUNT(*) > 1", "d.fonds"),
    _check("NO_CHECKSUM", "Cảnh báo", "Văn bản có tệp nhưng chưa có mã kiểm (chưa được xử lý)",
           f"SELECT d.name FROM {AD} d WHERE d.file_attachment <> '' AND (d.checksum IS NULL OR d.checksum = '')", "d.fonds"),
    _check("INDEX_ERROR", "Cảnh báo", "Văn bản lập chỉ mục tìm kiếm bị lỗi",
           f"SELECT d.name FROM {AD} d WHERE d.search_index_status = 'Lỗi'", "d.fonds"),
]
META_CHECKS = [
    _check("META_FONDS_CODE", "Cảnh báo", "Phông chưa có mã phông", f"SELECT f.name FROM {FO} f WHERE f.fonds_code IS NULL OR f.fonds_code = ''", "f.name"),
    _check("META_CATALOG_NUMBER", "Cảnh báo", "Mục lục chưa có số mục lục", f"SELECT c.name FROM {CT} c WHERE c.catalog_number IS NULL OR c.catalog_number = ''", "c.fonds"),
    _check("META_FILE_NUMBER", "Cảnh báo", "Hồ sơ chưa có số hồ sơ", f"SELECT a.name FROM {AF} a WHERE a.file_number IS NULL OR a.file_number = ''", "a.fonds"),
    _check("META_FILE_DATES", "Cảnh báo", "Hồ sơ chưa có thời gian bắt đầu", f"SELECT a.name FROM {AF} a WHERE a.start_date IS NULL", "a.fonds"),
    _check("META_FILE_LOCATION", "Cảnh báo", "Hồ sơ chưa có vị trí lưu trữ (kho, giá, hộp)",
           f"SELECT a.name FROM {AF} a WHERE (a.storage_warehouse IS NULL OR a.storage_warehouse = '') "
           "AND (a.shelf_number IS NULL OR a.shelf_number = '') AND (a.box_number IS NULL OR a.box_number = '')", "a.fonds"),
    _check("META_FILE_EMPTY", "Cảnh báo", "Hồ sơ đã hoàn thành nhưng chưa có văn bản nào",
           f"SELECT a.name FROM {AF} a WHERE a.status = 'Đã hoàn thành' AND NOT EXISTS (SELECT 1 FROM {AD} d WHERE d.archival_file = a.name)", "a.fonds"),
    _check("META_DOCUMENT_NUMBER", "Cảnh báo", "Văn bản chưa có số văn bản", f"SELECT d.name FROM {AD} d WHERE d.document_number IS NULL OR d.document_number = ''", "d.fonds"),
    _check("META_DOCUMENT_DATE", "Cảnh báo", "Văn bản chưa có ngày văn bản", f"SELECT d.name FROM {AD} d WHERE d.document_date IS NULL", "d.fonds"),
    _check("META_DOCUMENT_AUTHOR", "Cảnh báo", "Văn bản chưa có tác giả, cơ quan ban hành", f"SELECT d.name FROM {AD} d WHERE d.author IS NULL OR d.author = ''", "d.fonds"),
    _check("META_DOCUMENT_FILE", "Cảnh báo", "Văn bản chưa có tệp tài liệu số",
           f"SELECT d.name FROM {AD} d WHERE (d.file_attachment IS NULL OR d.file_attachment = '') AND (d.gridfs_file_id IS NULL OR d.gridfs_file_id = '')", "d.fonds"),
]
CHECKS = {check["code"]: check for check in [*DB_CHECKS, *META_CHECKS]}


# --- aggregate (SQL) checks -------------------------------------------------------------------------------------------

def run_sql_check(check: dict, fonds: str | None, today=None) -> tuple[int, list[str]]:
    """(how many records offend, a few of their names)."""
    sql = check["sql"]
    params = {}
    if fonds and check["scope"]:
        # the rule's own conditions go in brackets: "a OR b AND scope" would not mean "(a OR b) AND scope"
        head, rest = sql.split(" WHERE ", 1)
        conditions, group, tail = rest.partition(" GROUP BY ")
        sql = f"{head} WHERE ({conditions}) AND {check['scope']} = %(fonds)s{group}{tail}"
        params["fonds"] = fonds
    total = frappe.db.sql(f"SELECT COUNT(*) FROM ({sql}) t", params)[0][0] or 0
    samples = [r[0] for r in frappe.db.sql(f"{sql} LIMIT 5", params)] if total else []
    return cint(total), samples


def describe_finding(check: dict, count: int, samples: list[str]) -> str:
    text = _(check["title"]) + f": {count}"
    return text + (f" (ví dụ: {', '.join(str(s) for s in samples)})" if samples else "")


def run_sql_phase(doc, checks: list, findings: runner.Findings) -> None:
    for check in checks:
        runner.check_cancel(DOCTYPE, doc.name)
        count, samples = run_sql_check(check, doc.fonds)
        if not count:
            continue
        findings.add(check["severity"], describe_finding(check, count, samples), None, code=check["code"],
                     restorable=0)
        frappe.db.commit()


# --- per-document file checks --------------------------------------------------------------------------------------

def backup_index() -> dict:
    """{document: sha256} of the newest backup that holds each document's file (the files a restore could bring back)."""
    index = {}
    batches = frappe.get_all("Backup Batch", filters={"status": ["in", ["Thành công", "Một phần"]],
                                                       "backup_type": ["in", ["Tệp tài liệu", "Cả hai"]]},
                             pluck="name", order_by="completed_at desc")
    for batch in batches:
        for entry in filestore.read_manifest(batch):
            if entry.get("document") not in index and filestore.has(entry.get("sha256")):
                index[entry["document"]] = entry["sha256"]
    return index


def check_file(row, tests: set, available: dict, mongo: bool) -> list[tuple]:
    """Problems of one document's file: [(code, severity, message, restorable)]."""
    out = []
    restorable = row.name in available
    url, gridfs_id = row.get("file_attachment") or "", row.get("gridfs_file_id") or ""
    if not (url or gridfs_id):
        return out
    content = sources.read_disk(url) if url else None
    if "link" in tests:
        if url and not gridfs_id and mongo:
            out.append(("GRIDFS_NOT_STORED", "Cảnh báo", _("Có tệp đính kèm nhưng chưa có bản trên MongoDB (GridFS)"), restorable or content is not None))
        if gridfs_id and not url:
            out.append(("NO_ATTACHMENT", "Cảnh báo", _("Có bản trên GridFS nhưng không còn tệp đính kèm"), True))
        return out
    if url and content is None:
        if "missing" in tests:
            fallback = restorable or bool(gridfs_id and sources.gridfs_exists(gridfs_id))
            out.append(("FILE_MISSING", "Lỗi", _("Không còn tệp trên máy chủ (đường dẫn {0})").format(url), fallback))
    elif content is not None:
        if "empty" in tests and not content:
            out.append(("FILE_EMPTY", "Lỗi", _("Tệp rỗng (0 byte)"), restorable))
        if "checksum" in tests and row.get("checksum") and content and sources.sha256(content) != row.checksum:
            out.append(("CHECKSUM", "Lỗi", _("Mã kiểm SHA-256 của tệp khác với mã đã ghi khi tải lên: tệp đã bị thay đổi hoặc hỏng"), restorable))
        if "type" in tests and content and sources.matches_type(row.get("file_type"), content) is False:
            out.append(("TYPE_MISMATCH", "Cảnh báo", _("Nội dung tệp không đúng loại {0} đã khai báo").format(row.file_type), False))
    if "gridfs" in tests and gridfs_id and mongo and sources.gridfs_exists(gridfs_id) is False:
        out.append(("GRIDFS_MISSING", "Lỗi", _("Không còn bản của tệp trên MongoDB (GridFS)"), content is not None or restorable))
    return out


def run_files_phase(doc, findings: runner.Findings, notes: list) -> None:
    tests = FILE_TESTS.get(doc.check_type, FILE_TESTS["Toàn bộ"])
    sources.forget_probe()
    mongo, reason = sources.mongo_available()
    if not mongo and ({"gridfs", "link"} & tests):
        findings.add("Cảnh báo", _("Không kết nối được MongoDB ({0}): bỏ qua kiểm tra bản trên GridFS").format(reason or "?"), None, code="MONGO_DOWN")
        notes.append("MongoDB không kết nối được: chỉ kiểm tra tệp trên máy chủ.")
    available = backup_index() if ({"missing", "checksum", "empty"} & tests) else {}
    filters = [["fonds", "=", doc.fonds]] if doc.fonds else []
    or_filters = [["file_attachment", "!=", ""], ["gridfs_file_id", "!=", ""]]
    cursor = doc.cursor or ""
    checked = cint(doc.total_checked)
    while True:
        rows = frappe.get_all("Archive Document", filters=[*filters, ["name", ">", cursor]] if cursor else filters,
                              or_filters=or_filters, order_by="name asc", page_length=runner.PAGE,
                              fields=["name", "file_attachment", "gridfs_file_id", "checksum", "file_type"])
        if not rows:
            break
        for row in rows:
            for code, severity, message, restorable in check_file(row, tests, available, mongo):
                findings.add(severity, message, row.name, code=code, restorable=1 if restorable else 0)
        checked += len(rows)
        cursor = rows[-1].name
        doc.db_set({"cursor": cursor, "total_checked": checked, "errors_found": findings.errors,
                    "warnings_found": findings.warnings}, update_modified=False)
        frappe.db.commit()
        runner.check_cancel(DOCTYPE, doc.name)


# --- the job --------------------------------------------------------------------------------------------------------

def create(check_type: str = "Toàn bộ", fonds: str | None = None, trigger: str = "Thủ công", user: str | None = None):
    initiated = frappe.session.user if user is None else (user or None)
    doc = frappe.get_doc({"doctype": DOCTYPE, "check_type": check_type, "fonds": fonds or None, "trigger": trigger,
                          "initiated_by": initiated})
    doc.insert(ignore_permissions=True)
    return doc


def start(doc) -> None:
    doc.db_set({"status": "Đang chờ", "completed_at": None}, update_modified=False)
    runner.enqueue(JOB, doc.name, timeout=4 * 3600)


def run(name: str) -> None:
    """Worker: run the phases the kind asks for, record the findings, say how it ended."""
    doc = frappe.get_doc(DOCTYPE, name)
    if doc.status not in ("Đang chờ", "Đang chạy", "Lỗi", "Đã hủy"):
        return
    runner.mark_running(doc, phase="")
    if not doc.cursor:  # a fresh run: nothing from an earlier attempt stays
        for item in frappe.get_all("Integrity Check Item", filters={"check": name}, pluck="name"):
            frappe.delete_doc("Integrity Check Item", item, force=True, ignore_permissions=True)
        doc.db_set({"total_checked": 0, "errors_found": 0, "warnings_found": 0}, update_modified=False)
    frappe.db.commit()
    findings = runner.Findings("Integrity Check Item", "check", name)
    findings.errors, findings.warnings = (cint(doc.errors_found), cint(doc.warnings_found)) if doc.cursor else (0, 0)
    notes = []
    try:
        phases = PHASES.get(doc.check_type, (FILES,))
        for phase in phases:
            doc.db_set("phase", {DB: "Cơ sở dữ liệu", META: "Siêu dữ liệu", FILES: "Tệp tài liệu"}[phase], update_modified=False)
            if phase == DB:
                run_sql_phase(doc, DB_CHECKS, findings)
            elif phase == META:
                run_sql_phase(doc, META_CHECKS, findings)
            else:
                run_files_phase(doc, findings, notes)
        if findings.truncated:
            notes.append(f"Chỉ lưu {runner.MAX_ITEMS} dòng phát hiện đầu tiên.")
        status = "Phát hiện lỗi" if findings.errors else "Hoàn thành"
        doc.reload()
        summary = _("Đã kiểm tra {0} tài liệu: {1} lỗi, {2} cảnh báo").format(cint(doc.total_checked), findings.errors, findings.warnings)
        runner.finish(doc, status, errors_found=findings.errors, warnings_found=findings.warnings, summary=summary,
                      error_details="\n".join(notes), phase="", cursor="")
    except runner.Cancelled:
        frappe.db.rollback()
        runner.finish(doc, "Đã hủy", error_details="Đã dừng theo yêu cầu.")
    except Exception as e:
        frappe.db.rollback()
        log_exception("Integrity Check", f"Check {name} failed")
        runner.finish(doc, "Lỗi", error_details=runner.explain(e))
    frappe.db.commit()
    doc.reload()
    runner.notify(doc, _("Kiểm tra {0}: {1}").format(doc.name, doc.status))


def schedule_integrity_check() -> str | None:
    """Weekly job (hooks): a full check when the settings ask for it."""
    if not runner.settings().auto_integrity_check or runner.is_active(DOCTYPE):
        return None
    doc = create("Toàn bộ", trigger="Theo lịch", user="")
    start(doc)
    return doc.name


def fix_counters() -> dict:
    """Recompute the counters kept on fonds (files) and files (documents) from the actual records."""
    frappe.db.sql(f"UPDATE {FO} f SET f.total_files = (SELECT COUNT(*) FROM {AF} a WHERE a.fonds = f.name) "
                  f"WHERE f.total_files <> (SELECT COUNT(*) FROM {AF} a WHERE a.fonds = f.name)")
    fonds = frappe.db.sql("SELECT ROW_COUNT()")[0][0] or 0
    frappe.db.sql(f"UPDATE {AF} a SET a.total_documents = (SELECT COUNT(*) FROM {AD} d WHERE d.archival_file = a.name) "
                  f"WHERE a.total_documents <> (SELECT COUNT(*) FROM {AD} d WHERE d.archival_file = a.name)")
    files = frappe.db.sql("SELECT ROW_COUNT()")[0][0] or 0
    return {"fonds": cint(fonds), "files": cint(files), "on": nowdate()}
