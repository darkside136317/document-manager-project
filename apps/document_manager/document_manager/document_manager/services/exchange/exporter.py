# -*- coding: utf-8 -*-
"""Export: search the archive, choose the fields, write the matching records (with their ancestors, and optionally
everything below them) as one XML tree.

Everything is read through `frappe.get_list`, so the permission conditions of the user who asked apply, and only
the fields the exchange format lists leave the system (no extracted text, storage ids or system columns). The
file is written as a stream; a request is refused beyond `xmlio.MAX_NODES` records.
"""

import os
import tempfile
from datetime import date, datetime

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from document_manager.document_manager.services import search_service
from document_manager.document_manager.services.exchange import jobs, schema, xmlio
from document_manager.document_manager.services.reports.base import data, date as date_filter, link, select

PAGE = 5000
CHUNK = 500
FONDS_STATUS = ["Đang xử lý", "Đã hoàn thành", "Đã đóng"]
FILE_STATUS = ["Nháp", "Đang xử lý", "Đã hoàn thành", "Đã đóng"]
FILE_TYPES = ["PDF", "DOCX", "XLSX", "JPG", "PNG", "TIFF", "Khác"]

# The search of each level: the filters its screen offers (the `query` is the basic search, the rest the advanced).
FILTERS = {
    "Fonds": [data("query", "Tên hoặc mã phông"), link("archival_agency", "Cơ quan lưu trữ", "Archival Agency"),
              select("status", "Tình trạng", FONDS_STATUS)],
    "Record Group": [data("query", "Tên hoặc mã khối"), link("fonds", "Phông", "Fonds")],
    "Catalog": [data("query", "Tên hoặc số mục lục"), link("fonds", "Phông", "Fonds"),
                link("record_group", "Khối tài liệu", "Record Group", depends="fonds")],
    "Archival File": [data("query", "Số hoặc tiêu đề hồ sơ"), link("fonds", "Phông", "Fonds"),
                      link("record_group", "Khối tài liệu", "Record Group", depends="fonds"),
                      link("catalog", "Mục lục", "Catalog", depends="record_group"), select("status", "Tình trạng", FILE_STATUS),
                      link("confidentiality_level", "Mức độ mật", "Confidentiality Level"),
                      link("document_type_category", "Loại hình tài liệu", "Document Type Category"),
                      link("storage_warehouse", "Kho, giá, hộp", "Storage Warehouse"),
                      date_filter("start_date_from", "Hình thành từ ngày"), date_filter("start_date_to", "Hình thành đến ngày")],
    "Archive Document": [data("query", "Số, tiêu đề hoặc tác giả"), link("fonds", "Phông", "Fonds"),
                         link("record_group", "Khối tài liệu", "Record Group", depends="fonds"),
                         link("catalog", "Mục lục", "Catalog", depends="record_group"),
                         link("archival_file", "Hồ sơ", "Archival File", depends="catalog"),
                         data("author", "Tác giả, cơ quan ban hành"), select("file_type", "Loại tệp", FILE_TYPES),
                         link("confidentiality_level", "Mức độ mật", "Confidentiality Level"),
                         date_filter("date_from", "Văn bản từ ngày"), date_filter("date_to", "Văn bản đến ngày")],
}


def clean_params(doctype: str, raw) -> dict:
    """Keep the filters the level declares, stripped; anything else the client sends is dropped."""
    raw = frappe.parse_json(raw) if isinstance(raw, str) and raw else (raw or {})
    allowed = {spec["fieldname"] for spec in FILTERS[doctype]}
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in raw.items() if k in allowed and v not in (None, "")}


def conditions(doctype: str, params: dict) -> tuple[list, list | None]:
    """(filters, or_filters) for `get_list`, built by the same code as the search screens."""
    if doctype == "Archival File":
        return search_service.file_conditions(params)
    if doctype == "Archive Document":
        return search_service.document_conditions(params)
    filters = [[doctype, f, "=", params[f]] for f in ("archival_agency", "status", "fonds", "record_group") if f in params]
    level = schema.BY_DOCTYPE[doctype]
    or_filters = None
    if "query" in params:
        like = f"%{params['query']}%"
        or_filters = [[doctype, f, "like", like] for f in (level.title, level.code, "name")]
    return filters, or_filters


# --- reading the records -----------------------------------------------------------------------------------------------

def _columns(index: int, fields) -> list[str]:
    ancestors = [schema.LEVELS[i].link_field for i in range(index)]
    return list(dict.fromkeys(["name", *ancestors, *fields]))


def _fetch(index: int, filters, or_filters=None, fields=None, limit: int | None = None) -> list[dict]:
    """All records matching, paged by name (a stable order), as plain dicts; stops at `limit` records."""
    level = schema.LEVELS[index]
    columns = _columns(index, fields if fields is not None else level.fields)
    out, start = [], 0
    while True:
        page = frappe.get_list(level.doctype, filters=filters, or_filters=or_filters, fields=columns, order_by="name asc",
                               start=start, page_length=PAGE)
        out.extend(dict(row) for row in page)
        if limit is not None and len(out) > limit:
            return out
        if len(page) < PAGE:
            return out
        start += PAGE


def _by_names(index: int, names, fields=None) -> list[dict]:
    names = sorted(set(n for n in names if n))
    out = []
    for i in range(0, len(names), CHUNK):
        out.extend(_fetch(index, [[schema.LEVELS[index].doctype, "name", "in", names[i:i + CHUNK]]], fields=fields))
    return out


def _below(index: int, deeper: int, names, fields=None) -> list[dict]:
    """Records of level `deeper` that sit under the records `names` of level `index`."""
    link_field = schema.LEVELS[index].link_field
    names = sorted(names)
    out = []
    for i in range(0, len(names), CHUNK):
        out.extend(_fetch(deeper, [[schema.LEVELS[deeper].doctype, link_field, "in", names[i:i + CHUNK]]], fields=fields))
    return out


def count_matching(doctype: str, params: dict) -> tuple[int, list[str]]:
    """(how many records match, up to MAX_NODES + 1 of their names)."""
    filters, or_filters = conditions(doctype, params)
    names = frappe.get_list(doctype, filters=filters, or_filters=or_filters, pluck="name", order_by="name asc",
                            page_length=xmlio.MAX_NODES + 1)
    return len(names), names


def plan(doctype: str, raw_filters, include_children: bool) -> dict:
    """What an export would contain: records per level (the chosen level, its ancestors, what is below it)."""
    index = schema.index_of(doctype)
    params = clean_params(doctype, raw_filters)
    matched, names = count_matching(doctype, params)
    counts = {level.doctype: 0 for level in schema.LEVELS}
    counts[doctype] = matched
    ancestors = {level.doctype: 0 for level in schema.LEVELS}
    if names and index:
        rows = _by_names(index, names[: xmlio.MAX_NODES], fields=[])
        for above in range(index):
            ancestors[schema.LEVELS[above].doctype] = len({r[schema.LEVELS[above].link_field] for r in rows} - {None, ""})
    if include_children and names:
        for deeper in range(index + 1, len(schema.LEVELS)):
            counts[schema.LEVELS[deeper].doctype] = len(_below(index, deeper, names[: xmlio.MAX_NODES], fields=[]))
    total = sum(counts.values()) + sum(ancestors.values())
    return {"counts": counts, "ancestors": ancestors, "total": total, "too_many": total > xmlio.MAX_NODES,
            "limit": xmlio.MAX_NODES, "filters": params}


# --- building and writing the tree ---------------------------------------------------------------------------------------

def _value(row: dict, name: str) -> str:
    value = row.get(name)
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def chosen_fields(index: int, fields) -> list[str]:
    """The fields asked for at a level (all when none are named); the key fields always travel with a node."""
    level = schema.LEVELS[index]
    fields = frappe.parse_json(fields) if isinstance(fields, str) and fields else (fields or {})
    asked = fields.get(level.doctype)
    selected = [f for f in level.fields if asked is None or f in asked]
    return [f for f in level.fields if f in selected or f in schema.identity_fields(level)]


def build_tree(doctype: str, names: list[str], fields, include_children: bool) -> tuple[list[dict], dict, list[str]]:
    """The nodes ({ref, values, children}) of the fonds that hold the matching records, with counts and warnings."""
    index = schema.index_of(doctype)
    levels = schema.LEVELS
    rows = {i: {} for i in range(len(levels))}
    for row in _by_names(index, names, fields=chosen_fields(index, fields)):
        rows[index][row["name"]] = row
    if include_children:
        for deeper in range(index + 1, len(levels)):
            for row in _below(index, deeper, rows[index], fields=chosen_fields(deeper, fields)):
                rows[deeper][row["name"]] = row
    for above in range(index - 1, -1, -1):
        needed = {row[levels[above].link_field] for row in rows[index].values()}
        for row in _by_names(above, needed, fields=levels[above].required):
            rows[above][row["name"]] = row

    warnings, children = [], {i: {} for i in range(1, len(levels))}
    for i in range(1, len(levels)):
        parent_field = levels[i].parent_field
        for row in rows[i].values():
            parent = row.get(parent_field)
            if parent in rows[i - 1]:
                children[i].setdefault(parent, []).append(row)
            elif len(warnings) < jobs.MAX_LOG_ROWS:
                warnings.append(_("{0} {1} bị bỏ qua vì không đọc được {2} chứa nó").format(
                    levels[i].label, row["name"], levels[i - 1].label.lower()))

    def node(i: int, row: dict) -> dict:
        ref = i < index
        names_out = levels[i].required if ref else chosen_fields(i, fields)
        values = {f: _value(row, f) for f in names_out if f in row}
        kids = sorted(children.get(i + 1, {}).get(row["name"], ()), key=lambda r: _order(i + 1, r)) if i + 1 < len(levels) else []
        return {"ref": ref, "values": values, "children": [node(i + 1, kid) for kid in kids]}

    roots = [node(0, row) for row in sorted(rows[0].values(), key=lambda r: _order(0, r))]
    counts = {levels[i].doctype: len(rows[i]) for i in range(len(levels))}
    return roots, counts, warnings


def _order(i: int, row: dict) -> tuple:
    level = schema.LEVELS[i]
    return (str(row.get(level.code) or ""), str(row.get(level.title) or ""), row["name"])


def run_export(job) -> None:
    """Worker body of an export job."""
    options = jobs.options_of(job)
    doctype = options["level"]
    index = schema.index_of(doctype)
    params = clean_params(doctype, options.get("filters"))
    jobs.set_progress(job.name, phase=_("Đang tìm bản ghi"), processed=0, total=0)
    matched, names = count_matching(doctype, params)
    if not matched:
        return jobs.finish(job, jobs.FAILED, _("Không có bản ghi nào khớp tiêu chí tìm kiếm"))
    if matched > xmlio.MAX_NODES:
        return jobs.finish(job, jobs.FAILED, _("Có hơn {0} bản ghi khớp, hãy thu hẹp tiêu chí rồi xuất lại").format(xmlio.MAX_NODES))
    jobs.check_cancel(job.name)
    jobs.set_progress(job.name, phase=_("Đang đọc dữ liệu"))
    roots, counts, warnings = build_tree(doctype, names, options.get("fields"), cint(options.get("include_children")))
    total = sum(counts.values())
    if total > xmlio.MAX_NODES:
        return jobs.finish(job, jobs.FAILED, _("Kết quả có {0} bản ghi, vượt giới hạn {1}. Hãy thu hẹp tiêu chí.").format(
            total, xmlio.MAX_NODES))
    jobs.check_cancel(job.name)
    jobs.set_progress(job.name, phase=_("Đang ghi tệp XML"), total=total, processed=total)
    attributes = {"version": schema.VERSION, "exported_at": now_datetime().strftime("%Y-%m-%dT%H:%M:%S"),
                  "source": frappe.local.site, "level": doctype}
    handle, path = tempfile.mkstemp(suffix=".xml", prefix="dm-export-")
    os.close(handle)
    try:
        xmlio.write(path, attributes, roots)
        stored = jobs.save_result_file(job, path, f"xuat-{schema.BY_DOCTYPE[doctype].element.lower()}-{job.name}.xml")
    finally:
        os.unlink(path)
    job.reload()
    job.update({"result_file": stored["file_url"], "file_name": os.path.basename(stored["file_url"]),
                "file_size_kb": stored["size_kb"], "checksum": stored["checksum"]})
    job.save(ignore_permissions=True)
    result = {level.doctype: {"exported": counts[level.doctype] if i >= index else 0,
                              "ancestors": counts[level.doctype] if i < index else 0}
              for i, level in enumerate(schema.LEVELS)}
    exported = sum(v["exported"] for v in result.values())
    summary = _("Đã xuất {0} bản ghi ({1}) ra tệp XML").format(
        exported, ", ".join(f"{schema.BY_DOCTYPE[d].label.lower()} {v['exported']}" for d, v in result.items() if v["exported"]))
    jobs.finish(job, jobs.DONE_WITH_ERRORS if warnings else jobs.DONE, summary, result=result,
                rows=[{"severity": "Cảnh báo", "level": doctype, "message": w} for w in warnings],
                processed=total, total=total, created=exported, skipped=len(warnings))


def selected_fields_ok(fields) -> dict:
    """Validate the {doctype: [fields]} choice of a request: unknown levels and fields are refused."""
    fields = frappe.parse_json(fields) if isinstance(fields, str) and fields else (fields or {})
    for doctype, names in fields.items():
        level = schema.BY_DOCTYPE.get(doctype)
        if not level:
            frappe.throw(_("Không hỗ trợ trao đổi XML cho {0}").format(doctype))
        for name in names:
            if name not in level.fields:
                frappe.throw(_("Trường {0} không có trong dữ liệu trao đổi của {1}").format(name, level.label))
    return fields


def validate_request(doctype: str, options: dict) -> dict:
    schema.index_of(doctype)
    return {"level": doctype, "filters": clean_params(doctype, options.get("filters")),
            "fields": selected_fields_ok(options.get("fields")), "include_children": 1 if cint(options.get("include_children")) else 0}

