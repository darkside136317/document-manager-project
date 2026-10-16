"""ERP-owned AI jobs, document identity checks, and reviewable JSON results."""

import hmac
import json
from urllib.parse import urlparse

import frappe
import requests
from frappe.utils import cint

from document_manager.document_manager.policy import has_capability, is_admin
from document_manager.document_manager.services.digitization_fields import schema_snapshot
from document_manager.document_manager.services.preservation.sources import filename_of, read_document, sha256

MAX_JOB_DOCUMENTS = 100
ENGINE_TIMEOUT = 60
TERMINAL = frozenset({"done", "failed"})


def enabled() -> bool:
    return bool(cint(frappe.db.get_single_value("Document Manager Settings", "digitization_enabled")))


def _require_enabled():
    if not enabled():
        frappe.throw("Chế độ số hóa đang tắt", frappe.PermissionError)


def _engine_settings() -> tuple[str, str]:
    url = (frappe.conf.get("pdfluent_api_url") or "").rstrip("/")
    key = frappe.conf.get("pdfluent_api_key") or ""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or not key:
        frappe.throw("Chưa cấu hình địa chỉ hoặc API key của AI engine")
    return url, key


def _job(job_id: str):
    if not frappe.db.exists("AI Extraction Job", job_id):
        frappe.throw("Không tìm thấy job AI", frappe.DoesNotExistError)
    return frappe.get_doc("AI Extraction Job", job_id)


def _manifest(job) -> dict:
    return json.loads(job.manifest_json or "{}")


def _set_state(job_id: str, status: str, error: str = ""):
    frappe.db.set_value("AI Extraction Job", job_id, {"status": status, "error": error[:500]}, update_modified=False)
    frappe.publish_realtime("dm_ai_job", {"job_id": job_id, "status": status}, after_commit=True)


def start(record_group: str, selection: str = "unprocessed") -> dict:
    """Snapshot document identities and digitization schema, then enqueue the transfer."""
    _require_enabled()
    if not is_admin() or not has_capability("digitization.extract"):
        frappe.throw("Chỉ quản trị viên được gửi job AI", frappe.PermissionError)
    if selection not in ("all", "unprocessed"):
        frappe.throw("Phạm vi bóc tách không hợp lệ")
    group = frappe.get_doc("Record Group", record_group)
    group.check_permission("read")
    fields, schema_hash = schema_snapshot()
    if not fields:
        frappe.throw("Chưa có trường nào trong cây hồ sơ được đánh dấu số hóa")
    _engine_settings()
    selected = []
    offset = 0
    while True:
        rows = frappe.get_list("Archive Document", filters={"record_group": record_group},
                               fields=["name", "archival_file", "catalog", "fonds", "version", "checksum",
                                       "file_attachment", "gridfs_file_id", "ai_extraction_state", "modified"],
                               start=offset, page_length=200, order_by="name asc")
        for row in rows:
            if selection == "unprocessed" and row.ai_extraction_state in ("needs_review", "reviewed"):
                continue
            if row.file_attachment or row.gridfs_file_id:
                selected.append({"document_id": row.name, "archival_file_id": row.archival_file,
                                 "catalog_id": row.catalog, "fonds_id": row.fonds,
                                 "source_version": row.version or 0, "sha256": row.checksum or "",
                                 "source_modified": str(row.modified)})
            if len(selected) > MAX_JOB_DOCUMENTS:
                frappe.throw(f"Một job hiện hỗ trợ tối đa {MAX_JOB_DOCUMENTS} văn bản; hãy chia khối tài liệu thành các lượt")
        if len(rows) < 200:
            break
        offset += len(rows)
    if not selected:
        frappe.throw("Không có văn bản có tệp cần bóc tách")
    job_id = frappe.generate_hash(length=32)
    manifest = {"fonds_id": group.fonds, "record_group_id": group.name, "documents": selected}
    frappe.get_doc({"doctype": "AI Extraction Job", "job_id": job_id, "record_group": group.name,
                    "fonds": group.fonds, "status": "waiting", "selection": selection,
                    "schema_hash": schema_hash, "schema_json": json.dumps(fields, ensure_ascii=False),
                    "manifest_json": json.dumps(manifest, ensure_ascii=False), "event_seq": 0}).insert(ignore_permissions=True)
    for item in selected:
        frappe.db.set_value("Archive Document", item["document_id"],
                            {"ai_extraction_state": "waiting", "ai_last_job_id": job_id}, update_modified=False)
    frappe.enqueue("document_manager.document_manager.services.ai_integration.dispatch",
                   job_id=job_id, queue="long", timeout=4 * 3600, enqueue_after_commit=True)
    return {"job_id": job_id, "status": "waiting", "document_count": len(selected)}


def dispatch(job_id: str):
    """Upload each source with the ERP API key and submit a correlated AI job."""
    job = _job(job_id)
    if job.status in TERMINAL:
        return
    try:
        base, key = _engine_settings()
        headers = {"Authorization": f"Bearer {key}"}
        manifest = _manifest(job)
        for item in manifest["documents"]:
            if item.get("ai_doc_id"):
                continue
            row = frappe.db.get_value("Archive Document", item["document_id"],
                                      ["name", "file_attachment", "gridfs_file_id", "file_type", "version", "checksum"], as_dict=True)
            if not row or (row.version or 0) != item["source_version"]:
                raise RuntimeError(f"Văn bản {item['document_id']} đã thay đổi trước khi gửi AI")
            content, _source = read_document(row)
            if not content:
                raise RuntimeError(f"Không đọc được tệp của văn bản {item['document_id']}")
            digest = sha256(content)
            if item["sha256"] and item["sha256"] != digest:
                raise RuntimeError(f"Checksum của văn bản {item['document_id']} đã thay đổi")
            item["sha256"] = digest
            filename = filename_of(row)
            if "." not in filename and row.file_type:
                filename += f".{row.file_type.lower()}"
            if not filename.lower().endswith((".pdf", ".jpg", ".jpeg", ".png", ".webp")):
                raise RuntimeError(f"PDFluent chưa nhận định dạng tệp của văn bản {item['document_id']}: {filename}")
            response = requests.post(f"{base}/documents", headers=headers,
                                     files={"file": (filename, content)}, data={"classify": "false"}, timeout=ENGINE_TIMEOUT)
            response.raise_for_status()
            item["ai_doc_id"] = str(response.json()["doc_id"])
            frappe.db.set_value("AI Extraction Job", job_id, "manifest_json",
                                json.dumps(manifest, ensure_ascii=False), update_modified=False)
            frappe.db.commit()
        payload = {"job_id": job_id, "fonds_id": manifest["fonds_id"],
                   "record_group_id": manifest["record_group_id"], "schema_hash": job.schema_hash,
                   "schema": json.loads(job.schema_json), "documents": manifest["documents"]}
        response = requests.post(f"{base}/erp/jobs", headers=headers, json=payload, timeout=ENGINE_TIMEOUT)
        response.raise_for_status()
        frappe.db.commit()
    except Exception as exc:
        _set_state(job_id, "failed", str(exc))
        for item in _manifest(_job(job_id)).get("documents", []):
            if frappe.db.get_value("Archive Document", item["document_id"], "ai_last_job_id") == job_id:
                frappe.db.set_value("Archive Document", item["document_id"], "ai_extraction_state", "failed",
                                    update_modified=False)
        frappe.db.commit()
        raise


def receive_callback(payload: dict, callback_key: str) -> dict:
    """Authenticate and apply only ordered events for documents in this job."""
    secret = frappe.conf.get("ai_callback_api_key") or ""
    if not secret or not hmac.compare_digest(callback_key or "", secret):
        frappe.throw("API key callback không hợp lệ", frappe.AuthenticationError)
    return _apply_event(payload)


def _apply_event(payload: dict) -> dict:
    """Apply a verified callback or a status fetched by ERP's own engine credential."""
    job_id = str(payload.get("job_id") or "")
    frappe.db.sql("SELECT name FROM `tabAI Extraction Job` WHERE name=%s FOR UPDATE", job_id)
    job = _job(job_id)
    seq = int(payload.get("event_seq") or 0)
    if seq <= (job.event_seq or 0):
        return {"job_id": job_id, "status": job.status, "replayed": True}
    status = payload.get("status")
    if status not in ("waiting", "processing", "done", "failed"):
        frappe.throw("Trạng thái AI không hợp lệ")
    if job.status in TERMINAL:
        frappe.throw("Job đã kết thúc; không nhận sự kiện mới")
    manifest = _manifest(job)
    expected = {item["document_id"] for item in manifest["documents"]}
    results = payload.get("documents") or []
    ids = [item.get("document_id") for item in results]
    if len(ids) != len(set(ids)) or any(doc_id not in expected for doc_id in ids):
        frappe.throw("Kết quả AI có mã văn bản sai hoặc trùng")
    if status == "done" and set(ids) != expected:
        frappe.throw("Kết quả AI chưa đủ văn bản trong job")
    schema = {field["field_id"] for field in json.loads(job.schema_json)}
    if payload.get("schema_hash") != job.schema_hash:
        frappe.throw("Schema của kết quả AI không khớp job")
    for result in results:
        if any(field_id not in schema for field_id in (result.get("fields") or {})):
            frappe.throw("Kết quả AI chứa trường ngoài schema của job")
        if result.get("status") not in ("done", "failed"):
            frappe.throw("Trạng thái văn bản AI không hợp lệ")
        for answer in (result.get("fields") or {}).values():
            if not isinstance(answer, dict) or any(key != "value" for key in answer):
                frappe.throw("Kết quả AI chứa cấu trúc trường không hợp lệ")
            value = answer.get("value")
            if value is not None and (not isinstance(value, (str, bool, int, float)) or len(str(value)) > 10000):
                frappe.throw("Giá trị trường AI không hợp lệ")
    frappe.db.set_value("AI Extraction Job", job_id,
                        {"status": status, "event_seq": seq,
                         "result_json": json.dumps(results, ensure_ascii=False) if status == "done" else job.result_json,
                         "error": str(payload.get("error") or "")[:500]}, update_modified=False)
    result_by_id = {item["document_id"]: item for item in results}
    for document_id in expected:
        if frappe.db.get_value("Archive Document", document_id, "ai_last_job_id") == job_id:
            item_result = result_by_id.get(document_id, {})
            extracted = any(answer.get("value") is not None for answer in
                            (item_result.get("fields") or {}).values())
            document_state = (("needs_review" if extracted else "") if item_result.get("status") == "done"
                              else "failed") if status == "done" else status
            frappe.db.set_value("Archive Document", document_id, "ai_extraction_state",
                                document_state, update_modified=False)
    frappe.publish_realtime("dm_ai_job", {"job_id": job_id, "status": status}, after_commit=True)
    if status in TERMINAL:
        _notify_reviewers(job, status)
    return {"job_id": job_id, "status": status}


def _notify_reviewers(job, status: str):
    from document_manager.document_manager.policy import users_with_capability

    users = set(users_with_capability("digitization.review"))
    users.update(frappe.get_all("Has Role", filters={"role": ["in", ["Document Admin", "System Manager"]],
                                                  "parenttype": "User"}, pluck="parent", distinct=True))
    users.add("Administrator")
    for user in users:
        if frappe.db.get_value("User", user, "enabled"):
            frappe.get_doc({"doctype": "Notification Log", "type": "Alert", "for_user": user,
                            "subject": f"AI bóc tách khối {job.record_group}: " +
                                       ("đã hoàn thành, chờ duyệt" if status == "done" else "xử lý lỗi"),
                            "link": f"/dashboard/so-hoa/jobs/{job.name}"}).insert(ignore_permissions=True)


def status(job_id: str) -> dict:
    _require_enabled()
    if not (is_admin() or has_capability("digitization.review") or has_capability("digitization.edit")):
        frappe.throw("Bạn không có quyền xem job số hóa", frappe.PermissionError)
    job = _job(job_id)
    frappe.get_doc("Record Group", job.record_group).check_permission("read")
    manifest = _manifest(job)
    ids = [item["document_id"] for item in manifest.get("documents", [])]
    states = {row.name: row.ai_extraction_state for row in frappe.get_all(
        "Archive Document", filters={"name": ["in", ids]}, fields=["name", "ai_extraction_state"], limit_page_length=MAX_JOB_DOCUMENTS)} if ids else {}
    return {"job_id": job_id, "status": job.status, "error": job.error,
            "record_group": job.record_group, "schema": json.loads(job.schema_json or "[]"),
            "manifest": manifest, "documents": json.loads(job.result_json or "[]"), "document_states": states}


def latest(record_group: str) -> dict:
    _require_enabled()
    if not (is_admin() or has_capability("digitization.review") or has_capability("digitization.edit")):
        frappe.throw("Bạn không có quyền xem job số hóa", frappe.PermissionError)
    frappe.get_doc("Record Group", record_group).check_permission("read")
    names = frappe.get_all("AI Extraction Job", filters={"record_group": record_group},
                           order_by="creation desc", pluck="name", limit=1)
    return status(names[0]) if names else {}


def refresh(job_id: str) -> dict:
    """Reconcile from PDFluent when the callback was lost; includes the result JSON."""
    current = status(job_id)
    if current["status"] in TERMINAL:
        return current
    base, key = _engine_settings()
    response = requests.get(f"{base}/erp/jobs/{job_id}", headers={"Authorization": f"Bearer {key}"},
                            timeout=ENGINE_TIMEOUT)
    response.raise_for_status()
    _apply_event(response.json())
    return status(job_id)


def review(job_id: str, document_id: str, approved_fields: list[str]) -> dict:
    """Apply selected, verified AI fields to the exact unchanged ERP document."""
    _require_enabled()
    if not (is_admin() or has_capability("digitization.review")):
        frappe.throw("Bạn không có quyền duyệt kết quả AI", frappe.PermissionError)
    job = _job(job_id)
    if job.status != "done":
        frappe.throw("Job AI chưa hoàn thành")
    manifest = _manifest(job)
    source = next((item for item in manifest["documents"] if item["document_id"] == document_id), None)
    result = next((item for item in json.loads(job.result_json or "[]") if item["document_id"] == document_id), None)
    if not source or not result or result.get("status") != "done":
        frappe.throw("Không có kết quả cho văn bản này")
    doc = frappe.get_doc("Archive Document", document_id)
    doc.check_permission("read")
    if (doc.version or 0) != source["source_version"] or (doc.checksum or "") != source["sha256"]:
        frappe.throw("Tệp văn bản đã thay đổi; cần chạy AI lại")
    if str(doc.modified) != source.get("source_modified"):
        frappe.throw("Văn bản đã được chỉnh sửa sau khi gửi AI; hãy kiểm tra và chạy lại")
    if (doc.archival_file != source["archival_file_id"] or doc.catalog != source["catalog_id"]
            or doc.fonds != source["fonds_id"] or doc.record_group != manifest["record_group_id"]):
        frappe.throw("Văn bản đã được chuyển vị trí; cần chạy AI lại")
    schema = {field["field_id"]: field for field in json.loads(job.schema_json)}
    if not isinstance(approved_fields, list) or not approved_fields or any(field_id not in schema for field_id in approved_fields):
        frappe.throw("Trường duyệt không hợp lệ")
    if not any((result.get("fields") or {}).get(field_id, {}).get("value") is not None
               for field_id in approved_fields):
        frappe.throw("Chưa chọn trường có dữ liệu để duyệt")
    targets = {"Archive Document": document_id, "Archival File": source["archival_file_id"],
               "Catalog": source["catalog_id"], "Record Group": manifest["record_group_id"],
               "Fonds": source["fonds_id"]}
    changed = {}
    for field_id in approved_fields:
        if field_id not in (result.get("fields") or {}):
            frappe.throw("Kết quả không có trường được duyệt")
        value = (result.get("fields") or {}).get(field_id, {}).get("value")
        if value is not None:
            field = schema[field_id]
            target = field["target_doctype"]
            changed.setdefault(target, frappe.get_doc(target, targets[target]))
            changed[target].check_permission("read")
            if field["type"] == "date":
                from datetime import datetime
                try:
                    value = datetime.strptime(str(value), "%d/%m/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    frappe.throw(f"Ngày của trường {field['label']} không hợp lệ")
            if field["type"] == "choice" and value not in field["options"]:
                frappe.throw(f"Giá trị của trường {field['label']} ngoài danh sách")
            if field["type"] == "boolean":
                if str(value).lower() not in ("true", "false", "1", "0"):
                    frappe.throw(f"Giá trị của trường {field['label']} không phải đúng/sai")
                value = 1 if str(value).lower() in ("true", "1") else 0
            changed[target].set(field["fieldname"], value)
    for target_doc in changed.values():
        target_doc.save(ignore_permissions=True)
    frappe.db.set_value("Archive Document", document_id, "ai_extraction_state", "reviewed", update_modified=False)
    return {"document_id": document_id, "status": "reviewed"}
