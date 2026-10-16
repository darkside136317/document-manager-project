"""Contract of the MinIO adapter without requiring an external server."""

import io
import os
import unittest
from unittest.mock import Mock, patch

from document_manager.document_manager.services import object_storage


class TestObjectStorage(unittest.TestCase):
    def test_private_object_round_trip_and_legacy_id_guard(self):
        client = Mock()
        client.head_object.return_value = {
            "Metadata": {"filename": "h%E1%BB%93%20s%C6%A1.pdf"},
            "ContentLength": 4, "ContentType": "application/pdf",
        }
        client.get_object.return_value = {"Body": io.BytesIO(b"data")}
        values = {
            "MINIO_ENDPOINT": "http://minio:9000", "MINIO_BUCKET": "documents",
            "MINIO_APP_ACCESS_KEY": "test-access", "MINIO_APP_SECRET_KEY": "test-secret",
        }
        with patch.dict(os.environ, values), patch.object(object_storage, "_client", return_value=client):
            store = object_storage.ObjectStorage()
            object_id = store.upload_file(b"data", "hồ sơ.pdf", "application/pdf")
            self.assertTrue(object_id.startswith("minio:"))
            self.assertEqual(store.get_file_info(object_id)["filename"], "hồ sơ.pdf")
            self.assertEqual(store.download_file(object_id), b"data")
            store.delete_file(object_id)
            self.assertEqual(client.put_object.call_args.kwargs["Bucket"], "documents")
            self.assertEqual(client.put_object.call_args.kwargs["Metadata"]["sha256"],
                             "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7")
            self.assertLess(len(object_id), 140)  # Frappe Data field limit
            with self.assertRaises(ValueError):
                store.download_file("legacy-gridfs-id")
