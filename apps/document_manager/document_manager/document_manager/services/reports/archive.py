# -*- coding: utf-8 -*-
"""Reports of module 4 (Thống kê, báo cáo): fonds, catalogues, files, documents, statistics and the inventory."""

import frappe
from frappe import _
from frappe.utils import cint, flt

from document_manager.document_manager.services.reports.base import (
    UNKNOWN,
    Report,
    Where,
    bar_chart,
    check,
    col,
    data,
    date,
    grouped,
    integer,
    link,
    mb,
    page_args,
    period,
    register,
    rows,
    scalar,
    select,
    share,
)

GROUP = "Phông, mục lục, hồ sơ, văn bản"
GROUP_STATS = "Thống kê"
FONDS_STATUS = ["Đang xử lý", "Đã hoàn thành", "Đã đóng"]
FILE_STATUS = ["Nháp", "Đang xử lý", "Đã hoàn thành", "Đã đóng"]
DISPOSAL_STATUS = ["Bình thường", "Cảnh báo tiêu hủy", "Đã tiêu hủy"]
FILE_TYPES = ["PDF", "DOCX", "XLSX", "JPG", "PNG", "TIFF", "Khác"]


# --- Báo cáo phông lưu trữ ------------------------------------------------------------------------------------------

def run_fonds(filters, page, page_size):
    page, page_size = page_args(page, page_size)
    where = Where().equal("fo.archival_agency", filters, "archival_agency").equal("fo.status", filters, "status")
    where.like(["fo.fonds_name", "fo.fonds_code"], filters, "q")
    if "year_from" in filters:
        where.add("(fo.end_year IS NULL OR fo.end_year = 0 OR fo.end_year >= %(year_from)s)", year_from=filters["year_from"])
    if "year_to" in filters:
        where.add("(fo.start_year IS NULL OR fo.start_year = 0 OR fo.start_year <= %(year_to)s)", year_to=filters["year_to"])

    total = scalar(f"SELECT COUNT(*) FROM `tabFonds` fo WHERE {where.sql}", where.params)
    fonds = rows(
        f"""SELECT fo.name, fo.fonds_code, fo.fonds_name, fo.archival_agency, fo.status, fo.start_year, fo.end_year,
                   fo.total_boxes, fo.total_shelf_meters
            FROM `tabFonds` fo WHERE {where.sql} ORDER BY fo.fonds_name, fo.name LIMIT %(limit)s OFFSET %(offset)s""",
        {**where.params, "limit": page_size, "offset": (page - 1) * page_size})
    names = [f.name for f in fonds]
    groups = grouped("Record Group", "fonds", names)
    catalogs = grouped("Catalog", "fonds", names)
    files = grouped("Archival File", "fonds", names, ", COALESCE(SUM(total_pages), 0) AS pages")
    documents = grouped("Archive Document", "fonds", names, ", COALESCE(SUM(file_size_kb), 0) AS kb")

    out = []
    for f in fonds:
        out.append({
            "name": f.name, "fonds_code": f.fonds_code or "", "fonds_name": f.fonds_name,
            "archival_agency": f.archival_agency or "", "status": f.status or "",
            "period": period(f.start_year, f.end_year),
            "record_groups": cint(groups[f.name].n) if f.name in groups else 0,
            "catalogs": cint(catalogs[f.name].n) if f.name in catalogs else 0,
            "files": cint(files[f.name].n) if f.name in files else 0,
            "documents": cint(documents[f.name].n) if f.name in documents else 0,
            "pages": cint(files[f.name].pages) if f.name in files else 0,
            "size_mb": mb(documents[f.name].kb) if f.name in documents else 0.0,
            "total_boxes": cint(f.total_boxes), "total_shelf_meters": flt(f.total_shelf_meters),
        })

    inner = f"SELECT fo.name FROM `tabFonds` fo WHERE {where.sql}"
    summary = {
        "fonds_name": _("Tổng cộng"),
        "record_groups": scalar(f"SELECT COUNT(*) FROM `tabRecord Group` WHERE fonds IN ({inner})", where.params),
        "catalogs": scalar(f"SELECT COUNT(*) FROM `tabCatalog` WHERE fonds IN ({inner})", where.params),
        "files": scalar(f"SELECT COUNT(*) FROM `tabArchival File` WHERE fonds IN ({inner})", where.params),
        "documents": scalar(f"SELECT COUNT(*) FROM `tabArchive Document` WHERE fonds IN ({inner})", where.params),
        "pages": scalar(f"SELECT COALESCE(SUM(total_pages), 0) FROM `tabArchival File` WHERE fonds IN ({inner})", where.params),
        "total_boxes": scalar(f"SELECT COALESCE(SUM(fo.total_boxes), 0) FROM `tabFonds` fo WHERE {where.sql}", where.params),
    }
    return {"rows": out, "total": total, "summary": summary}


register(Report(
    slug="phong", title="Báo cáo phông lưu trữ", group=GROUP, icon="library", paged=True,
    description="Danh sách phông kèm số khối tài liệu, mục lục, hồ sơ, văn bản, số trang và dung lượng.",
    needs=("Fonds",), run=run_fonds,
    filters=[link("archival_agency", "Cơ quan lưu trữ", "Archival Agency"), select("status", "Tình trạng", FONDS_STATUS),
             integer("year_from", "Từ năm"), integer("year_to", "Đến năm"), data("q", "Tên hoặc mã phông")],
    columns=[col("fonds_code", "Mã phông"), col("fonds_name", "Tên phông"), col("archival_agency", "Cơ quan lưu trữ"),
             col("status", "Tình trạng"), col("period", "Thời gian"), col("record_groups", "Khối", "Int"),
             col("catalogs", "Mục lục", "Int"), col("files", "Hồ sơ", "Int"), col("documents", "Văn bản", "Int"),
             col("pages", "Số trang", "Int"), col("size_mb", "Dung lượng (MB)", "Float"), col("total_boxes", "Số hộp", "Int")],
))


# --- Báo cáo mục lục tài liệu ---------------------------------------------------------------------------------------

def run_catalogs(filters, page, page_size):
    page, page_size = page_args(page, page_size)
    where = Where().equal("c.fonds", filters, "fonds").equal("c.record_group", filters, "record_group")
    where.like(["c.catalog_title", "c.catalog_number"], filters, "q")
    total = scalar(f"SELECT COUNT(*) FROM `tabCatalog` c WHERE {where.sql}", where.params)
    catalogs = rows(
        f"""SELECT c.name, c.catalog_number, c.catalog_title, c.record_group, c.fonds, c.start_year, c.end_year,
                   rg.group_title, fo.fonds_name
            FROM `tabCatalog` c
            LEFT JOIN `tabRecord Group` rg ON rg.name = c.record_group
            LEFT JOIN `tabFonds` fo ON fo.name = c.fonds
            WHERE {where.sql}
            ORDER BY fo.fonds_name, rg.group_title, c.catalog_number, c.name LIMIT %(limit)s OFFSET %(offset)s""",
        {**where.params, "limit": page_size, "offset": (page - 1) * page_size})
    names = [c.name for c in catalogs]
    files = grouped("Archival File", "catalog", names, ", COALESCE(SUM(total_pages), 0) AS pages")
    documents = grouped("Archive Document", "catalog", names)
    out = [{
        "name": c.name, "catalog_number": c.catalog_number or "", "catalog_title": c.catalog_title,
        "group_title": c.group_title or c.record_group or "", "fonds_name": c.fonds_name or c.fonds or "",
        "period": period(c.start_year, c.end_year),
        "files": cint(files[c.name].n) if c.name in files else 0,
        "documents": cint(documents[c.name].n) if c.name in documents else 0,
        "pages": cint(files[c.name].pages) if c.name in files else 0,
    } for c in catalogs]

    inner = f"SELECT c.name FROM `tabCatalog` c WHERE {where.sql}"
    summary = {
        "catalog_title": _("Tổng cộng"),
        "files": scalar(f"SELECT COUNT(*) FROM `tabArchival File` WHERE catalog IN ({inner})", where.params),
        "documents": scalar(f"SELECT COUNT(*) FROM `tabArchive Document` WHERE catalog IN ({inner})", where.params),
        "pages": scalar(f"SELECT COALESCE(SUM(total_pages), 0) FROM `tabArchival File` WHERE catalog IN ({inner})", where.params),
    }
    return {"rows": out, "total": total, "summary": summary}


register(Report(
    slug="muc-luc", title="Báo cáo mục lục tài liệu", group=GROUP, icon="book-open-text", paged=True,
    description="Danh sách mục lục theo phông và khối tài liệu, kèm số hồ sơ, văn bản và số trang.",
    needs=("Catalog",), run=run_catalogs,
    filters=[link("fonds", "Phông", "Fonds"), link("record_group", "Khối tài liệu", "Record Group", depends="fonds"),
             data("q", "Tên hoặc số mục lục")],
    columns=[col("fonds_name", "Phông"), col("group_title", "Khối tài liệu"), col("catalog_number", "Số mục lục"),
             col("catalog_title", "Tên mục lục"), col("period", "Thời gian"), col("files", "Hồ sơ", "Int"),
             col("documents", "Văn bản", "Int"), col("pages", "Số trang", "Int")],
))


# --- Báo cáo hồ sơ lưu trữ ------------------------------------------------------------------------------------------

def _location(*parts) -> str:
    return " · ".join(p for p in parts if p)


def run_files(filters, page, page_size):
    page, page_size = page_args(page, page_size)
    where = Where()
    for column in ("fonds", "record_group", "catalog", "status", "confidentiality_level", "document_type_category",
                   "document_group", "storage_warehouse", "disposal_status"):
        where.equal(f"af.{column}", filters, column)
    where.between("af.start_date", filters, "date_from", "date_to")
    where.like(["af.file_title", "af.file_number"], filters, "q")
    total = scalar(f"SELECT COUNT(*) FROM `tabArchival File` af WHERE {where.sql}", where.params)
    files = rows(
        f"""SELECT af.name, af.file_number, af.file_title, af.start_date, af.end_date, af.total_documents, af.total_pages,
                   af.confidentiality_level, af.status, af.disposal_status, af.storage_warehouse, af.shelf_number,
                   af.box_number, af.physical_location, c.catalog_title, fo.fonds_name
            FROM `tabArchival File` af
            LEFT JOIN `tabCatalog` c ON c.name = af.catalog
            LEFT JOIN `tabFonds` fo ON fo.name = af.fonds
            WHERE {where.sql}
            ORDER BY fo.fonds_name, c.catalog_title, af.file_number, af.name LIMIT %(limit)s OFFSET %(offset)s""",
        {**where.params, "limit": page_size, "offset": (page - 1) * page_size})
    out = [{
        "name": f.name, "file_number": f.file_number or "", "file_title": f.file_title,
        "catalog_title": f.catalog_title or "", "fonds_name": f.fonds_name or "",
        "start_date": f.start_date, "end_date": f.end_date,
        "total_documents": cint(f.total_documents), "total_pages": cint(f.total_pages),
        "confidentiality_level": f.confidentiality_level or "", "status": f.status or "",
        "disposal_status": f.disposal_status or "",
        "location": _location(f.storage_warehouse, f"Giá {f.shelf_number}" if f.shelf_number else "",
                              f"Hộp {f.box_number}" if f.box_number else "", f.physical_location),
    } for f in files]
    summary = {
        "file_title": _("Tổng cộng"),
        "total_documents": scalar(f"SELECT COALESCE(SUM(af.total_documents), 0) FROM `tabArchival File` af WHERE {where.sql}", where.params),
        "total_pages": scalar(f"SELECT COALESCE(SUM(af.total_pages), 0) FROM `tabArchival File` af WHERE {where.sql}", where.params),
    }
    return {"rows": out, "total": total, "summary": summary}


register(Report(
    slug="ho-so", title="Báo cáo hồ sơ lưu trữ", group=GROUP, icon="folder", paged=True,
    description="Danh sách hồ sơ theo phông, mục lục, tình trạng, mức độ mật, kho và thời gian hình thành.",
    needs=("Archival File",), run=run_files,
    filters=[link("fonds", "Phông", "Fonds"), link("record_group", "Khối tài liệu", "Record Group", depends="fonds"),
             link("catalog", "Mục lục", "Catalog", depends="record_group"), select("status", "Tình trạng", FILE_STATUS),
             link("confidentiality_level", "Mức độ mật", "Confidentiality Level"),
             link("document_type_category", "Loại hình tài liệu", "Document Type Category"),
             link("document_group", "Nhóm tài liệu", "Document Group"),
             link("storage_warehouse", "Kho, giá, hộp", "Storage Warehouse"),
             select("disposal_status", "Tiêu hủy", DISPOSAL_STATUS),
             date("date_from", "Hình thành từ ngày"), date("date_to", "Hình thành đến ngày"),
             data("q", "Số hoặc tiêu đề hồ sơ")],
    columns=[col("fonds_name", "Phông"), col("catalog_title", "Mục lục"), col("file_number", "Số hồ sơ"),
             col("file_title", "Tiêu đề hồ sơ", link="/ho-so/{name}"), col("start_date", "Từ ngày", "Date"),
             col("end_date", "Đến ngày", "Date"), col("total_documents", "Văn bản", "Int"),
             col("total_pages", "Số trang", "Int"), col("confidentiality_level", "Mức độ mật"),
             col("location", "Vị trí lưu trữ"), col("status", "Tình trạng")],
))


# --- Báo cáo văn bản, tài liệu --------------------------------------------------------------------------------------

def run_documents(filters, page, page_size):
    page, page_size = page_args(page, page_size)
    where = Where()
    for column in ("fonds", "record_group", "catalog", "archival_file", "file_type", "confidentiality_level"):
        where.equal(f"ad.{column}", filters, column)
    where.like(["ad.author"], filters, "author")
    where.like(["ad.document_title", "ad.document_number", "ad.author"], filters, "q")
    where.between("ad.document_date", filters, "date_from", "date_to")
    total = scalar(f"SELECT COUNT(*) FROM `tabArchive Document` ad WHERE {where.sql}", where.params)
    documents = rows(
        f"""SELECT ad.name, ad.document_number, ad.document_title, ad.document_date, ad.author, ad.page_count,
                   ad.file_type, ad.file_size_kb, ad.confidentiality_level, af.file_number, af.file_title, fo.fonds_name
            FROM `tabArchive Document` ad
            LEFT JOIN `tabArchival File` af ON af.name = ad.archival_file
            LEFT JOIN `tabFonds` fo ON fo.name = ad.fonds
            WHERE {where.sql}
            ORDER BY fo.fonds_name, af.file_number, ad.document_date, ad.name LIMIT %(limit)s OFFSET %(offset)s""",
        {**where.params, "limit": page_size, "offset": (page - 1) * page_size})
    out = [{
        "name": d.name, "document_number": d.document_number or "", "document_title": d.document_title,
        "file_title": _location(d.file_number, d.file_title) if d.file_number else (d.file_title or ""),
        "fonds_name": d.fonds_name or "", "document_date": d.document_date, "author": d.author or "",
        "page_count": cint(d.page_count), "file_type": d.file_type or "", "size_mb": mb(d.file_size_kb),
        "confidentiality_level": d.confidentiality_level or "",
    } for d in documents]
    summary = {
        "document_title": _("Tổng cộng"),
        "page_count": scalar(f"SELECT COALESCE(SUM(ad.page_count), 0) FROM `tabArchive Document` ad WHERE {where.sql}", where.params),
    }
    return {"rows": out, "total": total, "summary": summary}


register(Report(
    slug="van-ban", title="Báo cáo văn bản, tài liệu", group=GROUP, icon="file-text", paged=True,
    description="Danh sách văn bản, tài liệu theo phông, hồ sơ, loại tệp, mức độ mật, tác giả và ngày văn bản.",
    needs=("Archive Document",), run=run_documents,
    filters=[link("fonds", "Phông", "Fonds"), link("record_group", "Khối tài liệu", "Record Group", depends="fonds"),
             link("catalog", "Mục lục", "Catalog", depends="record_group"),
             link("archival_file", "Hồ sơ", "Archival File", depends="catalog"),
             select("file_type", "Loại tệp", FILE_TYPES), link("confidentiality_level", "Mức độ mật", "Confidentiality Level"),
             data("author", "Tác giả, cơ quan ban hành"), date("date_from", "Văn bản từ ngày"), date("date_to", "Văn bản đến ngày"),
             data("q", "Số, tiêu đề hoặc tác giả")],
    columns=[col("fonds_name", "Phông"), col("file_title", "Hồ sơ"), col("document_number", "Số văn bản"),
             col("document_title", "Tiêu đề", link="/van-ban/{name}"), col("document_date", "Ngày văn bản", "Date"),
             col("author", "Tác giả"), col("page_count", "Số trang", "Int"), col("file_type", "Loại tệp"),
             col("size_mb", "Dung lượng (MB)", "Float"), col("confidentiality_level", "Mức độ mật")],
))


# --- Thống kê theo phông, năm, mức mật, tình trạng ------------------------------------------------------------------

BY_FONDS = "Phông"
BY_YEAR = "Năm hình thành hồ sơ"
BY_LEVEL = "Mức độ mật"
BY_STATUS = "Tình trạng hồ sơ"
FONDS_DIMENSIONS = {BY_FONDS: "af.fonds", BY_YEAR: "YEAR(af.start_date)", BY_LEVEL: "af.confidentiality_level",
                    BY_STATUS: "af.status"}


def _stat_rows(dimension: str, where: Where, label_of=None, order="files DESC") -> list:
    found = rows(
        f"""SELECT {dimension} AS k, COUNT(*) AS files, COALESCE(SUM(af.total_documents), 0) AS documents,
                   COALESCE(SUM(af.total_pages), 0) AS pages
            FROM `tabArchival File` af WHERE {where.sql} GROUP BY {dimension} ORDER BY {order}""", where.params)
    files_total = sum(cint(r.files) for r in found)
    docs_total = sum(cint(r.documents) for r in found)
    out = []
    for r in found:
        label = label_of(r.k) if label_of else r.k
        out.append({"label": str(label) if label not in (None, "") else UNKNOWN, "files": cint(r.files),
                    "documents": cint(r.documents), "pages": cint(r.pages),
                    "files_pct": share(r.files, files_total), "documents_pct": share(r.documents, docs_total)})
    return out


def _stat_result(label: str, out: list, title: str) -> dict:
    summary = {"label": _("Tổng cộng"), "files": sum(r["files"] for r in out), "documents": sum(r["documents"] for r in out),
               "pages": sum(r["pages"] for r in out)}
    top = out[:15]
    chart = bar_chart(title, [r["label"] for r in top], [r["documents"] for r in top], _("Văn bản"))
    columns = _stat_columns(label)
    return {"rows": out, "total": len(out), "summary": summary, "chart": chart, "columns": columns}


def _stat_columns(label: str) -> list:
    return [col("label", label), col("files", "Hồ sơ", "Int"), col("files_pct", "% hồ sơ", "Percent"),
            col("documents", "Văn bản", "Int"), col("documents_pct", "% văn bản", "Percent"), col("pages", "Số trang", "Int")]


def _stat_where(filters) -> Where:
    where = Where().equal("af.fonds", filters, "fonds").equal("af.status", filters, "status")
    return where.between("af.start_date", filters, "date_from", "date_to")


def run_stats_by_fonds(filters, page, page_size):
    dimension = filters.get("group_by", BY_FONDS)
    where = _stat_where(filters)
    names = {}
    label_of = None
    if dimension == BY_FONDS:
        names = dict(frappe.db.sql("SELECT name, fonds_name FROM `tabFonds`"))
        label_of = lambda key: names.get(key) or key  # noqa: E731
    order = "k ASC" if dimension == BY_YEAR else "files DESC"
    out = _stat_rows(FONDS_DIMENSIONS[dimension], where, label_of, order)
    return _stat_result(dimension, out, _("Số văn bản theo {0}").format(dimension.lower()))


register(Report(
    slug="thong-ke-phong", title="Thống kê hồ sơ, tài liệu theo phông", group=GROUP_STATS, icon="chart-bar",
    description="Số hồ sơ, văn bản, số trang theo phông, năm hình thành, mức độ mật hoặc tình trạng hồ sơ.",
    needs=("Archival File",), run=run_stats_by_fonds, landscape=False,
    filters=[select("group_by", "Thống kê theo", list(FONDS_DIMENSIONS), BY_FONDS),
             link("fonds", "Phông", "Fonds"), select("status", "Tình trạng hồ sơ", FILE_STATUS),
             date("date_from", "Hình thành từ ngày"), date("date_to", "Hình thành đến ngày")],
    columns=_stat_columns(BY_FONDS),
))


# --- Thống kê theo loại hình, nhóm tài liệu, kho --------------------------------------------------------------------

BY_TYPE = "Loại hình tài liệu"
BY_GROUP = "Nhóm tài liệu"
BY_WAREHOUSE = "Kho lưu trữ (kho gốc)"
BY_PLACE = "Vị trí lưu trữ (kho, giá, hộp)"
TYPE_DIMENSIONS = {BY_TYPE: "af.document_type_category", BY_GROUP: "af.document_group",
                   BY_WAREHOUSE: "af.storage_warehouse", BY_PLACE: "af.storage_warehouse"}


def _warehouse_roots() -> dict:
    """{warehouse: top-level warehouse above it} from the tree (a cycle or a dangling parent stops at the node)."""
    parent = dict(frappe.db.sql("SELECT name, COALESCE(parent_warehouse, '') FROM `tabStorage Warehouse`"))
    roots = {}
    for name in parent:
        node, seen = name, {name}
        while parent.get(node) and parent[node] in parent and parent[node] not in seen:
            node = parent[node]
            seen.add(node)
        roots[name] = node
    return roots


def run_stats_by_type(filters, page, page_size):
    dimension = filters.get("group_by", BY_TYPE)
    where = _stat_where(filters)
    out = _stat_rows(TYPE_DIMENSIONS[dimension], where)
    if dimension == BY_WAREHOUSE:  # merge the places of one warehouse
        roots, merged = _warehouse_roots(), {}
        for r in out:
            key = roots.get(r["label"], r["label"]) if r["label"] != UNKNOWN else UNKNOWN
            into = merged.setdefault(key, {"label": key, "files": 0, "documents": 0, "pages": 0})
            for metric in ("files", "documents", "pages"):
                into[metric] += r[metric]
        files_total = sum(r["files"] for r in merged.values())
        docs_total = sum(r["documents"] for r in merged.values())
        out = sorted(merged.values(), key=lambda r: -r["files"])
        for r in out:
            r["files_pct"], r["documents_pct"] = share(r["files"], files_total), share(r["documents"], docs_total)
    return _stat_result(dimension, out, _("Số văn bản theo {0}").format(dimension.lower()))


register(Report(
    slug="thong-ke-loai-hinh-kho", title="Thống kê theo loại hình tài liệu, kho lưu trữ", group=GROUP_STATS,
    icon="warehouse", landscape=False,
    description="Số hồ sơ, văn bản, số trang theo loại hình, nhóm tài liệu, kho lưu trữ hoặc giá, hộp.",
    needs=("Archival File",), run=run_stats_by_type,
    filters=[select("group_by", "Thống kê theo", list(TYPE_DIMENSIONS), BY_TYPE),
             link("fonds", "Phông", "Fonds"), select("status", "Tình trạng hồ sơ", FILE_STATUS),
             date("date_from", "Hình thành từ ngày"), date("date_to", "Hình thành đến ngày")],
    columns=_stat_columns(BY_TYPE),
))


# --- Tổng kiểm kê phông ---------------------------------------------------------------------------------------------

def _inventory_columns() -> list:
    return [col("fonds_name", "Phông"),
            col("recorded_files", "Hồ sơ (sổ sách)", "Int"), col("counted_files", "Hồ sơ (thực tế)", "Int"),
            col("difference_files", "Chênh lệch", "Int", diff=True),
            col("recorded_documents", "Văn bản (sổ sách)", "Int"), col("counted_documents", "Văn bản (thực tế)", "Int"),
            col("difference_documents", "Chênh lệch", "Int", diff=True),
            col("recorded_boxes", "Hộp (sổ sách)", "Int"), col("counted_boxes", "Hộp (thực tế)", "Int"),
            col("difference_boxes", "Chênh lệch", "Int", diff=True), col("state", "Kiểm"), col("note", "Ghi chú")]


def run_inventory(filters, page, page_size):
    name = filters.get("inventory_check") or frappe.db.get_value(
        "Inventory Check", {}, "name", order_by="check_date desc, creation desc")
    if not name:
        return {"rows": [], "total": 0, "summary": None, "info": [(_("Đợt kiểm kê"), _("Chưa có đợt kiểm kê nào"))]}
    doc = frappe.get_doc("Inventory Check", name)
    doc.check_permission("read")
    fonds_names = dict(frappe.db.sql("SELECT name, fonds_name FROM `tabFonds`"))
    out = []
    for item in doc.items:
        out.append({
            "name": item.fonds, "fonds_name": fonds_names.get(item.fonds) or item.fonds,
            **{k: cint(item.get(k)) for k in ("recorded_files", "counted_files", "difference_files", "recorded_documents",
                                              "counted_documents", "difference_documents", "recorded_boxes",
                                              "counted_boxes", "difference_boxes")},
            "state": _("Đã kiểm") if cint(item.counted) else _("Chưa kiểm"), "note": item.note or "",
        })
    summary = {"fonds_name": _("Tổng cộng"), **{
        k: sum(r[k] for r in out) for k in ("recorded_files", "counted_files", "difference_files", "recorded_documents",
                                            "counted_documents", "difference_documents", "recorded_boxes",
                                            "counted_boxes", "difference_boxes")}}
    info = [(_("Đợt kiểm kê"), f"{doc.check_title} ({doc.name})"), (_("Ngày kiểm kê"), str(doc.check_date)),
            (_("Phạm vi"), fonds_names.get(doc.fonds) or doc.fonds or _("Tất cả các phông")), (_("Tình trạng"), doc.status),
            (_("Người kiểm kê"), frappe.db.get_value("User", doc.checked_by, "full_name") or doc.checked_by or "")]
    if doc.notes:
        info.append((_("Nhận xét, kiến nghị"), doc.notes))
    return {"rows": out, "total": len(out), "summary": summary, "info": info}


register(Report(
    slug="tong-kiem-ke", title="Tổng kiểm kê phông", group=GROUP_STATS, icon="clipboard-check",
    description="Số liệu sổ sách và số đếm thực tế của từng phông trong một đợt kiểm kê, kèm chênh lệch.",
    needs=("Inventory Check", "Fonds"), run=run_inventory,
    filters=[link("inventory_check", "Đợt kiểm kê", "Inventory Check")],
    columns=_inventory_columns(),
))
