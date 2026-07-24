# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document

class DocumentManagerSettings(Document):
    """Cấu hình hệ thống Document Manager."""

    @frappe.whitelist()
    def test_mongodb_connection(self):
        """Test MongoDB Atlas connection."""
        try:
            import pymongo
            uri = self.get_password("mongodb_atlas_uri")
            client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            client.close()
            self.db_set("mongodb_status", "✅ Kết nối thành công")
            return {"status": "success"}
        except Exception as e:
            self.db_set("mongodb_status", f"❌ Lỗi: {str(e)[:100]}")
            return {"status": "error", "message": str(e)}

    @frappe.whitelist()
    def test_meilisearch_connection(self):
        """Test Meilisearch connection."""
        try:
            import meilisearch
            client = meilisearch.Client(
                self.meilisearch_host,
                self.get_password("meilisearch_master_key"),
            )
            health = client.health()
            stats = client.get_all_stats()
            total = sum(
                idx.get("numberOfDocuments", 0)
                for idx in stats.get("indexes", {}).values()
            ) if isinstance(stats.get("indexes"), dict) else 0

            self.db_set("meilisearch_status", "✅ Kết nối thành công")
            self.db_set("total_indexed", total)
            return {"status": "success", "total_indexed": total}
        except Exception as e:
            self.db_set("meilisearch_status", f"❌ Lỗi: {str(e)[:100]}")
            return {"status": "error", "message": str(e)}
