# -*- coding: utf-8 -*-
"""Import: walk an exchange file top-down and add or update the records it describes, as the user who asked.

* a node is matched by its business key inside its parent (the code, else the title), never by record name;
* only the fields the user chose are written, and only fields of the exchange format (no mass assignment);
* every record goes through the DocType's own validation and permissions (`insert` / `save`, no
  `ignore_permissions`); a record that fails is logged and its subtree skipped, the rest carries on;
* a dry run does exactly the same inside a transaction that is rolled back at the end.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, strip_html

from document_manager.document_manager.services.exchange import jobs, schema, xmlio

MODE_INSERT, MODE_UPSERT = "Chỉ thêm mới", "Thêm mới và cập nhật"
MODES = (MODE_INSERT, MODE_UPSERT)
# Catalogues that may be created from a name alone when the file mentions one the site lacks. Confidentiality
# levels are deliberately not here: creating one would make up a security level.
SAFE_MASTERS = {"Archival Agency": "agency_name", "Document Type Category": "type_name", "Document Group": "group_name"}
COMMIT_EVERY = 200
PROGRESS_EVERY = 25


class Run:
    def __init__(self, job, options: dict, total: int):
        self.job = job
        self.mode = options.get("mode") or MODE_INSERT
        self.dry = bool(cint(options.get("dry_run")))
        self.create_masters = bool(cint(options.get("create_masters")))
        asked = options.get("fields") or {}
        self.selected = {level.doctype: set(asked.get(level.doctype, level.fields)) & set(level.fields) for level in schema.LEVELS}
        self.kinds = {level.doctype: {s["fieldname"]: s for s in schema.field_specs(level)} for level in schema.LEVELS}
        self.total = total
        self.processed = 0
        self.rows: list[dict] = []
        self.counts = {level.doctype: {"created": 0, "updated": 0, "unchanged": 0, "exists": 0, "failed": 0, "skipped": 0,
                                       "refs": 0} for level in schema.LEVELS}
        self.masters = 0

    def log(self, severity: str, level: schema.Level, path: str, message: str) -> None:
        if len(self.rows) < jobs.MAX_LOG_ROWS:
            self.rows.append({"severity": severity, "level": level.label, "path": path[:500], "message": message[:1000]})

    @property
    def totals(self) -> dict:
        return {k: sum(c[k] for c in self.counts.values()) for k in ("created", "updated", "unchanged", "exists", "failed", "skipped")}

    def tick(self) -> None:
        self.processed += 1
        if self.processed % PROGRESS_EVERY == 0:
            jobs.check_cancel(self.job.name)
            jobs.set_progress(self.job.name, processed=self.processed, total=self.total, **self.totals)
        if not self.dry and self.processed % COMMIT_EVERY == 0:
            frappe.db.commit()


# --- values ---------------------------------------------------------------------------------------------------------

def coerce(spec: dict, text: str):
    kind = spec["kind"]
    if kind == "int":
        return cint(text) if text else 0
    if kind == "float":
        return flt(text) if text else 0.0
    if kind == "date":
        return text or None
    if kind == "link":
        return text or None
    return text


def same(spec: dict, current, new) -> bool:
    kind = spec["kind"]
    if kind == "int":
        return cint(current) == cint(new)
    if kind == "float":
        return abs(flt(current) - flt(new)) < 1e-9
    if kind == "date":
        return (getdate(current) if current else None) == (getdate(new) if new else None)
    return (current or "") == (new or "")


def readable(error: Exception) -> str:
    """The message of a failed record for the log; a permission error carries its words in a flag, not in itself."""
    text = strip_html(str(error)).strip()
    if not text and isinstance(error, frappe.PermissionError):
        text = strip_html(str(frappe.flags.pop("error_message", "") or "")) or _("Bạn không có quyền ghi dữ liệu này")
    return (text or error.__class__.__name__).replace("\n", " ")[:600]


# --- one node ---------------------------------------------------------------------------------------------------------

def find(level: schema.Level, parent: str | None, values: dict) -> str | None:
    """The record this node stands for inside `parent`: by code, else by title (a record without a code)."""
    scope = {level.parent_field: parent} if level.parent_field else {}
    code, title = values.get(level.code), values.get(level.title)
    attempts = []
    if code:
        attempts.append({**scope, level.code: code})
        attempts.append({**scope, level.title: title, level.code: ["is", "not set"]})
    else:
        attempts.append({**scope, level.title: title})
    for filters in attempts:
        names = frappe.get_all(level.doctype, filters=filters, pluck="name", page_length=2)
        if len(names) > 1:
            frappe.throw(_("Có nhiều {0} trùng khóa “{1}” trong cùng một cấp cha").format(level.label.lower(), code or title))
        if names:
            return names[0]
    return None


def ensure_masters(run: Run, level: schema.Level, data: dict) -> None:
    for name, spec in run.kinds[level.doctype].items():
        target = spec["options"] if spec["kind"] == "link" else None
        value = data.get(name)
        if value and target in SAFE_MASTERS and not frappe.db.exists(target, value):
            frappe.get_doc({"doctype": target, SAFE_MASTERS[target]: value}).insert()
            run.masters += 1


def create(run: Run, level: schema.Level, parent: str | None, values: dict, ref: bool) -> str:
    wanted = set(level.required) | (set() if ref else run.selected[level.doctype])
    data = {"doctype": level.doctype}
    if level.parent_field:
        data[level.parent_field] = parent
    for name in level.fields:
        if name in values and name in wanted:
            data[name] = coerce(run.kinds[level.doctype][name], values[name])
    if run.create_masters:
        ensure_masters(run, level, data)
    doc = frappe.get_doc(data)
    doc.insert()
    return doc.name


def update(run: Run, level: schema.Level, name: str, values: dict) -> bool:
    doc = frappe.get_doc(level.doctype, name)
    changes = {}
    for field in level.fields:
        if field in values and field in run.selected[level.doctype]:
            spec = run.kinds[level.doctype][field]
            new = coerce(spec, values[field])
            if not same(spec, doc.get(field), new):
                changes[field] = new
    if not changes:
        return False
    if run.create_masters:
        ensure_masters(run, level, changes)
    doc.update(changes)
    doc.save()
    return True


def subtree_size(element) -> int:
    return sum(1 for e in element.iter() if e.tag in schema.BY_ELEMENT)


def process(run: Run, index: int, element, parent: str | None, trail: str) -> None:
    level = schema.LEVELS[index]
    counts = run.counts[level.doctype]
    values = xmlio.values_of(element, level)
    ref = xmlio.is_ref(element)
    key = xmlio.key_of(level, values) or "?"
    path = f"{trail} › {level.label} {key}" if trail else f"{level.label} {key}"
    savepoint = f"xn{index}"
    frappe.db.savepoint(savepoint)
    name = None
    try:
        if not values.get(level.title):
            frappe.throw(_("Thiếu {0}").format(frappe.get_meta(level.doctype).get_field(level.title).label))
        name = find(level, parent, values)
        if name:
            if ref:
                counts["refs"] += 1
            elif run.mode == MODE_UPSERT:
                counts["updated" if update(run, level, name, values) else "unchanged"] += 1
            else:
                counts["exists"] += 1
        else:
            name = create(run, level, parent, values, ref)
            counts["created"] += 1
            counts["refs"] += 1 if ref else 0
    except Exception as e:
        frappe.db.rollback(save_point=savepoint)
        frappe.local.message_log = []
        counts["failed"] += 1
        below = subtree_size(element) - 1
        if below:
            run.counts[schema.LEVELS[min(index + 1, len(schema.LEVELS) - 1)].doctype]["skipped"] += below
        run.log("Lỗi", level, path, readable(e) + (_(" — bỏ qua {0} bản ghi con").format(below) if below else ""))
        for _i in range(subtree_size(element)):
            run.tick()
        return
    run.tick()
    for child in xmlio.children_of(element, index):
        process(run, index + 1, child, name, path)


# --- the run ------------------------------------------------------------------------------------------------------------

def run_import(job) -> None:
    options = jobs.options_of(job)
    root = xmlio.parse(jobs.read_source(job))
    problems = xmlio.validate(root)
    if problems:
        return jobs.finish(job, jobs.FAILED, _("Tệp không đúng lược đồ: {0}").format(problems[0]),
                           rows=[{"severity": "Lỗi", "level": "", "path": "", "message": p} for p in problems])
    analysis = xmlio.analyze(root)
    run = Run(job, options, analysis["total"])
    jobs.set_progress(job.name, phase=_("Đang chạy thử") if run.dry else _("Đang nhập"), processed=0, total=run.total)
    previous = frappe.flags.in_import
    frappe.flags.in_import = True  # the audit trail records the import itself, not every record in it
    frappe.db.savepoint("exchange_run")
    try:
        for top in xmlio.children_of(root, -1):
            process(run, 0, top, None, "")
    finally:
        frappe.flags.in_import = previous
    if run.dry:
        frappe.db.rollback(save_point="exchange_run")
        frappe.db.after_commit.reset()  # nothing queued by the rolled-back records may run
        frappe.db.before_commit.reset()
    else:
        frappe.db.commit()
    totals = run.totals
    verb = _("Chạy thử (không ghi dữ liệu): sẽ") if run.dry else _("Đã")
    summary = _("{0} thêm {1}, cập nhật {2}, không đổi {3}, đã có {4}, lỗi {5}").format(
        verb, totals["created"], totals["updated"], totals["unchanged"], totals["exists"], totals["failed"])
    if run.masters:
        summary += _(", tạo {0} mục danh mục").format(run.masters)
    status = jobs.DONE_WITH_ERRORS if totals["failed"] else jobs.DONE
    jobs.finish(job, status, summary, result={"levels": run.counts, "masters": run.masters, "dry_run": run.dry}, rows=run.rows,
                processed=run.processed, total=run.total, created=totals["created"], updated=totals["updated"],
                skipped=totals["unchanged"] + totals["exists"] + totals["skipped"], failed=totals["failed"])
