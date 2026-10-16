"""Admin-controlled field visibility and AI schema for the shared archive records."""

import hashlib
import json
import re

import frappe

from document_manager.document_manager.constants import REGISTRY
from document_manager.document_manager.policy import is_admin

SCHEMA_DOCTYPES = ("Fonds", "Record Group", "Catalog", "Archival File", "Archive Document")
VISIBILITIES = frozenset({"exploitation", "digitization", "both"})
AI_TYPES = frozenset({"text", "number", "date", "choice", "boolean"})
FIELD_TYPES = {"Data": "text", "Small Text": "text", "Text": "text", "Long Text": "text",
               "Int": "number", "Float": "number", "Date": "date", "Check": "boolean", "Select": "choice"}
PROTECTED_FIELDS = frozenset({"fonds", "record_group", "catalog", "archival_file", "file_attachment",
                              "gridfs_file_id", "gridfs_preview_id", "checksum", "content_text",
                              "digitization_enabled", "digitization_fields_json", "ai_extraction_state", "ai_last_job_id"})


def _require_admin():
    if not is_admin():
        frappe.throw("Chỉ quản trị viên được chỉnh sửa cấu hình trường", frappe.PermissionError)


def load_config() -> dict:
    """Read the field overlay; older sites with no configuration keep their existing UI."""
    raw = frappe.db.get_single_value("Document Manager Settings", "digitization_fields_json") or "{}"
    try:
        config = json.loads(raw)
    except (TypeError, ValueError):
        frappe.throw("Cấu hình trường số hóa không hợp lệ")
    return config if isinstance(config, dict) else {}


def _field_key(doctype: str, fieldname: str) -> str:
    return f"{doctype}.{fieldname}"


def fields_for_mode(doctype: str, mode: str, fields: list[dict]) -> list[dict]:
    """Overlay labels/order and show only fields assigned to the requested mode."""
    config = load_config()
    enriched = []
    for index, field in enumerate(fields):
        spec = config.get(_field_key(doctype, field["fieldname"])) or {}
        visibility = spec.get("visibility", "exploitation")
        if mode == "digitization" and visibility not in ("digitization", "both"):
            # Keep ancestry and required links available to create valid archive records.
            if not field.get("reqd") and field["fieldname"] not in PROTECTED_FIELDS:
                continue
        if mode == "exploitation" and visibility == "digitization":
            continue
        enriched.append({**field, "label": spec.get("label") or field["label"],
                         "_position": spec.get("position", index)})
    return [{k: v for k, v in field.items() if k != "_position"}
            for field in sorted(enriched, key=lambda item: item["_position"])]


def schema_snapshot() -> tuple[list[dict], str]:
    """Build the immutable AI field contract from fields marked for digitization."""
    config = load_config()
    fields = []
    for doctype in SCHEMA_DOCTYPES:
        meta = frappe.get_meta(doctype)
        for df in meta.fields:
            spec = config.get(_field_key(doctype, df.fieldname)) or {}
            if spec.get("visibility") not in ("digitization", "both"):
                continue
            ai_type = FIELD_TYPES.get(df.fieldtype)
            if not ai_type or df.fieldname in PROTECTED_FIELDS:
                continue
            fields.append({"field_id": _field_key(doctype, df.fieldname), "target_doctype": doctype,
                           "fieldname": df.fieldname, "label": spec.get("label") or df.label or df.fieldname,
                           "type": ai_type, "required": bool(spec.get("required")),
                           "options": df.options.split("\n") if ai_type == "choice" and df.options else []})
    fields.sort(key=lambda f: (SCHEMA_DOCTYPES.index(f["target_doctype"]),
                               config[f["field_id"]].get("position", 0), f["field_id"]))
    serialized = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return fields, hashlib.sha256(serialized.encode()).hexdigest()


def list_config() -> dict:
    """Describe editable metadata to administrators without exposing hidden storage fields."""
    _require_admin()
    config = load_config()
    result = {}
    for doctype in REGISTRY:
        meta = frappe.get_meta(doctype)
        result[doctype] = [{"fieldname": df.fieldname, "label": df.label or df.fieldname,
                            "fieldtype": df.fieldtype, "required": bool(df.reqd),
                            "visibility": (config.get(_field_key(doctype, df.fieldname)) or {}).get(
                                "visibility", "exploitation"),
                            "position": (config.get(_field_key(doctype, df.fieldname)) or {}).get("position", df.idx)}
                           for df in meta.fields if df.fieldname and not df.hidden and df.fieldtype in FIELD_TYPES
                           and df.fieldname not in PROTECTED_FIELDS]
    return result


def save_field_config(doctype: str, fieldname: str, values: dict) -> dict:
    """Save one field's mode, label, order and AI flag; only admins may call this."""
    _require_admin()
    if doctype not in REGISTRY:
        frappe.throw("Loại dữ liệu không hợp lệ")
    df = frappe.get_meta(doctype).get_field(fieldname)
    if not df or df.fieldtype not in FIELD_TYPES or fieldname in PROTECTED_FIELDS:
        frappe.throw("Trường dữ liệu không thể cấu hình")
    visibility = values.get("visibility", "exploitation")
    if visibility not in VISIBILITIES:
        frappe.throw("Chế độ hiển thị không hợp lệ")
    if df.reqd and visibility != "both":
        frappe.throw("Trường bắt buộc phải hiển thị ở cả hai chế độ")
    label = (values.get("label") or df.label or fieldname).strip()
    if not label or len(label) > 140:
        frappe.throw("Tên trường không hợp lệ")
    position = int(values.get("position", df.idx))
    if position < 0 or position > 10000:
        frappe.throw("Thứ tự trường không hợp lệ")
    config = load_config()
    key = _field_key(doctype, fieldname)
    config[key] = {"label": label, "visibility": visibility, "position": position,
                   "required": bool(values.get("required"))}
    frappe.db.set_single_value("Document Manager Settings", "digitization_fields_json",
                               json.dumps(config, ensure_ascii=False))
    return {"field_id": key, **config[key]}


def add_custom_field(doctype: str, fieldname: str, label: str, fieldtype: str = "Data") -> dict:
    """Create a new physical field through Frappe's Custom Field migration path."""
    _require_admin()
    if doctype not in REGISTRY or fieldtype not in FIELD_TYPES:
        frappe.throw("Loại dữ liệu hoặc kiểu trường không hợp lệ")
    if not re.fullmatch(r"custom_[a-z][a-z0-9_]{1,60}", fieldname or ""):
        frappe.throw("Mã trường mới phải bắt đầu bằng custom_ và chỉ gồm chữ thường, số, dấu gạch dưới")
    if frappe.get_meta(doctype).has_field(fieldname):
        frappe.throw("Mã trường đã tồn tại")
    label = (label or "").strip()
    if not label or len(label) > 140:
        frappe.throw("Tên trường không hợp lệ")
    doc = frappe.get_doc({"doctype": "Custom Field", "dt": doctype, "fieldname": fieldname,
                          "fieldtype": fieldtype, "label": label})
    doc.insert(ignore_permissions=True)
    frappe.clear_cache(doctype=doctype)
    return {"doctype": doctype, "fieldname": fieldname, "label": label, "fieldtype": fieldtype}


def remove_custom_field(doctype: str, fieldname: str) -> dict:
    """Remove only empty administrator-created fields; retain populated archive data."""
    _require_admin()
    if doctype not in REGISTRY or not fieldname.startswith("custom_"):
        frappe.throw("Chỉ xóa được trường tùy chỉnh")
    name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": fieldname}, "name")
    if not name:
        frappe.throw("Không tìm thấy trường tùy chỉnh")
    # Both identifiers are validated above against registered metadata.
    if frappe.db.sql(f"SELECT name FROM `tab{doctype}` WHERE `{fieldname}` IS NOT NULL "
                     f"AND CAST(`{fieldname}` AS CHAR) <> '' LIMIT 1"):
        frappe.throw("Trường đã có dữ liệu; hãy chuyển về chế độ ẩn thay vì xóa")
    frappe.delete_doc("Custom Field", name, ignore_permissions=True)
    config = load_config()
    config.pop(_field_key(doctype, fieldname), None)
    frappe.db.set_single_value("Document Manager Settings", "digitization_fields_json",
                               json.dumps(config, ensure_ascii=False))
    frappe.clear_cache(doctype=doctype)
    return {"doctype": doctype, "fieldname": fieldname, "deleted": True}
