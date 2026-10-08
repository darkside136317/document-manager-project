# -*- coding: utf-8 -*-
"""Live status of the external services (never raises, never leaks credentials)."""

import frappe

CACHE_KEY = "dm_service_health"
CACHE_OK_SECONDS = 20
CACHE_DOWN_SECONDS = 60  # a probe of a service that is down waits for its timeout: do not repeat it on every refresh


def check_services(fresh: bool = False) -> dict:
    """Both probes; the answer is kept for a few seconds so that a monitor screen refreshing itself does not hammer them."""
    if not fresh:
        cached = frappe.cache.get_value(CACHE_KEY)
        if cached:
            return cached
    result = {"mongodb": _check_mongodb(), "meilisearch": _check_meilisearch()}
    frappe.cache.set_value(CACHE_KEY, result, expires_in_sec=CACHE_OK_SECONDS if all(s["ok"] for s in result.values()) else CACHE_DOWN_SECONDS)
    return result


def _check_mongodb() -> dict:
    try:
        from document_manager.document_manager.services.mongodb_storage import _get_database

        db = _get_database()
        db.client.admin.command("ping")
        files = db["documents.files"].estimated_document_count()
        return {"ok": True, "message": "Kết nối thành công", "files": files}
    except Exception as e:
        return {"ok": False, "message": _short(e)}


def _check_meilisearch() -> dict:
    try:
        from document_manager.document_manager.services.search_index import INDEX_NAME, _get_client

        client = _get_client()
        client.health()
        stats = client.index(INDEX_NAME).get_stats()
        documents = getattr(stats, "number_of_documents", None)
        if documents is None and isinstance(stats, dict):
            documents = stats.get("numberOfDocuments", 0)
        return {"ok": True, "message": "Kết nối thành công", "documents": documents or 0}
    except Exception as e:
        return {"ok": False, "message": _short(e)}


def _short(error: Exception) -> str:
    """One-line error text; anything after a connection-string scheme is dropped (credentials)."""
    text = " ".join(str(error).split())
    for scheme in ("mongodb+srv://", "mongodb://"):
        text = text.split(scheme)[0]
    return (text.strip() or type(error).__name__)[:160]
