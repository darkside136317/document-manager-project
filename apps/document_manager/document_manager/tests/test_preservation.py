# -*- coding: utf-8 -*-
"""Preservation (module 7): the file store, backups, retention and the schedule, integrity checks, restoring files,
the controlled database restore, the API and its permissions.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_preservation
"""

import glob
import gzip
import hashlib
import os
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from document_manager.document_manager.api import preservation as api
from document_manager.document_manager.services.preservation import backup, filestore, integrity, restore, runner, sources
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _seed_archive, _user

TAG = frappe.generate_hash(length=5).lower()
ADMIN = f"pv.admin.{TAG}@example.com"
PRESERVER = f"pv.preserver.{TAG}@example.com"
CATALOGER = f"pv.cataloger.{TAG}@example.com"
OFFICER = f"pv.officer.{TAG}@example.com"
READER = f"pv.reader.{TAG}@example.com"
USERS = (ADMIN, PRESERVER, CATALOGER, OFFICER, READER)
_BODIES: dict = {}


def body(n: int, extra: bytes = b"") -> bytes:
    """A real one-page PDF (Frappe checks the PDFs it stores), different for each n/extra and the same every time."""
    key = (n, extra)
    if key not in _BODIES:
        import io

        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(72, 72)
        writer.add_metadata({"/Title": f"document {n} {TAG} {extra.decode()}"})
        stream = io.BytesIO()
        writer.write(stream)
        _BODIES[key] = stream.getvalue()
    return _BODIES[key]


class TestPreservation(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        for email, roles, kind in ((ADMIN, ["Document Admin"], "System User"), (PRESERVER, ["Preservation Officer"], "System User"),
                                   (CATALOGER, ["Cataloger"], "System User"), (OFFICER, ["Reading Room Officer"], "System User"),
                                   (READER, ["Reader"], "Website User")):
            _user(email, roles, kind)
        cls._seeded = _seed_archive(3)
        cls.fonds = _names(cls._seeded, "Fonds")[0]
        cls.files = _names(cls._seeded, "Archival File")
        cls.documents = _names(cls._seeded, "Archive Document")
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for dt, name in cls._seeded:
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for email in USERS:
            frappe.db.delete("Notification Log", {"for_user": email})
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        # a worker commits, and when a run fails it rolls back to what it last committed: simulated with savepoints
        original = frappe.db.rollback
        self.commits, self.last_commit = 0, "pv_test"

        def commit():
            self.commits += 1
            self.last_commit = f"pv_commit_{self.commits}"
            frappe.db.savepoint(self.last_commit)

        def rollback(**kw):
            return original(**(kw if kw.get("save_point") else {"save_point": self.last_commit}))

        for target, replacement in (("commit", commit), ("rollback", rollback)):
            patcher = patch.object(frappe.db, target, side_effect=replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.original_rollback = original
        enqueue = patch.object(frappe, "enqueue", MagicMock())
        self.enqueue = enqueue.start()
        self.addCleanup(enqueue.stop)
        # the file store and the dumps live in a folder of their own
        self.folder = tempfile.mkdtemp(prefix="dm-backups-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        store = os.path.join(self.folder, "store")
        for target, value in (("document_manager.document_manager.services.preservation.backups_dir", self.folder),
                              ("document_manager.document_manager.services.preservation.backup.backups_dir", self.folder),
                              ("document_manager.document_manager.api.preservation.backups_dir", self.folder),
                              ("document_manager.document_manager.services.preservation.filestore.store_dir", store),
                              ("document_manager.document_manager.api.preservation.store_dir", store)):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        frappe.cache.delete_keys("dm_preserve:*")  # job names repeat from test to test (the counter is rolled back)
        self.addCleanup(frappe.cache.delete_keys, "dm_preserve:*")
        self.touched: list[str] = []
        self.paths: dict[str, str] = {}
        frappe.set_user(ADMIN)
        frappe.db.savepoint("pv_test")
        sources.forget_probe()
        patcher = patch.object(sources, "mongo_available", return_value=(False, "không kết nối"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        frappe.set_user("Administrator")
        self.original_rollback(save_point="pv_test")
        for stem in self.touched:
            for path in glob.glob(frappe.get_site_path("private", "files", f"*{stem}*")):
                os.unlink(path)

    # ---- helpers
    def attach(self, index: int, content: bytes | None = None, ext="pdf") -> str:
        """Give document `index` a real private file; returns its url."""
        name = self.documents[index]
        content = body(index) if content is None else content
        record = frappe.get_doc({"doctype": "File", "file_name": f"{TAG}-{index}.{ext}", "is_private": 1, "content": content,
                                 "attached_to_doctype": "Archive Document", "attached_to_name": name}).insert(ignore_permissions=True)
        frappe.db.set_value("Archive Document", name, {"file_attachment": record.file_url, "file_type": ext.upper(),
                                                       "checksum": hashlib.sha256(content).hexdigest()})
        self.touched.append(os.path.basename(record.file_url))
        self.paths[name] = record.get_full_path()
        return record.file_url

    def attach_all(self):
        for i in range(3):
            self.attach(i)

    def run_backup(self, backup_type="Tệp tài liệu", **kw):
        batch = backup.create_batch(backup_type, fonds=kw.pop("fonds", self.fonds), **kw)
        backup.run(batch.name)
        return frappe.get_doc("Backup Batch", batch.name)

    def run_check(self, check_type="Tệp tài liệu"):
        check = integrity.create(check_type, self.fonds)
        integrity.run(check.name)
        return frappe.get_doc("Integrity Check", check.name)

    def findings(self, check, code=None):
        filters = {"check": check.name, **({"code": code} if code else {})}
        return frappe.get_all("Integrity Check Item", filters=filters, fields=["document", "code", "severity", "message", "restorable", "status"])

    # ---- the file store
    def test_the_store_keeps_one_blob_per_content_and_notices_a_damaged_one(self):
        digest, added = filestore.put(b"abc")
        self.assertEqual((digest, added), (hashlib.sha256(b"abc").hexdigest(), True))
        self.assertEqual(filestore.put(b"abc"), (digest, False))
        self.assertEqual(filestore.get(digest), b"abc")
        self.assertTrue(filestore.has(digest))
        with open(filestore.blob_path(digest), "wb") as handle:
            handle.write(b"damaged")
        self.assertIsNone(filestore.get(digest))  # it no longer matches its name
        self.assertIsNone(filestore.get("0" * 64))
        self.assertEqual(filestore.usage()["blobs"], 1)

    def test_manifests_list_a_batch_and_garbage_collection_keeps_what_is_referenced(self):
        kept, _a = filestore.put(b"kept")
        lost, _b = filestore.put(b"lost")
        filestore.append_manifest("BK-1", [{"document": "D1", "sha256": kept}])
        filestore.append_manifest("BK-1", [{"document": "D2", "sha256": kept}])
        self.assertEqual([e["document"] for e in filestore.read_manifest("BK-1")], ["D1", "D2"])
        self.assertEqual(list(filestore.read_manifest("BK-none")), [])
        self.assertEqual(filestore.collect_garbage(["BK-1"], min_age=3600), (0, 0))  # too young to be sure
        removed, freed = filestore.collect_garbage(["BK-1"], min_age=0)
        self.assertEqual((removed, freed), (1, len(b"lost")))
        self.assertTrue(filestore.has(kept) and not filestore.has(lost))

    # ---- backing up
    def test_a_file_backup_copies_every_file_and_lists_it(self):
        self.attach_all()
        batch = self.run_backup()
        self.assertEqual((batch.status, batch.files_total, batch.files_done, batch.files_failed), ("Thành công", 3, 3, 0))
        entries = list(filestore.read_manifest(batch.name))
        self.assertEqual({e["document"] for e in entries}, set(self.documents))
        for entry in entries:
            self.assertEqual(filestore.get(entry["sha256"]), body(self.documents.index(entry["document"])))
            self.assertEqual((entry["source"], entry["fonds"]), ("disk", self.fonds))
        self.assertEqual(batch.expires_on, frappe.utils.getdate(add_days(nowdate(), runner.settings().backup_retention_days)))
        self.assertTrue(frappe.db.exists("Notification Log", {"for_user": ADMIN, "document_name": batch.name}))

    def test_a_second_backup_copies_only_what_the_store_lacks(self):
        self.attach_all()
        self.run_backup()
        blobs = filestore.usage()["blobs"]
        self.attach(1, body(1, b" changed"))
        second = self.run_backup()
        self.assertEqual(second.files_done, 3)
        self.assertEqual(filestore.usage()["blobs"], blobs + 1)  # only the changed file is new

    def test_a_missing_or_damaged_source_is_reported_and_never_replaces_a_good_copy(self):
        self.attach_all()
        os.unlink(self.paths[self.documents[0]])  # gone
        with open(self.paths[self.documents[1]], "wb") as handle:
            handle.write(body(1, b" corrupted"))  # no longer what was uploaded
        batch = self.run_backup()
        self.assertEqual((batch.status, batch.files_done, batch.files_failed), ("Một phần", 1, 2))
        items = frappe.get_all("Backup Batch Item", filters={"batch": batch.name}, fields=["document", "message", "severity"])
        self.assertEqual({i.document for i in items}, {self.documents[0], self.documents[1]})
        self.assertTrue(all(i.severity == "Lỗi" for i in items))
        self.assertFalse(any(sha for sha in [hashlib.sha256(body(1, b" corrupted")).hexdigest()] if filestore.has(sha)))

    def test_a_stopped_backup_continues_from_its_cursor_without_repeating_documents(self):
        self.attach_all()
        batch = backup.create_batch("Tệp tài liệu", fonds=self.fonds)
        runner.request_cancel("Backup Batch", batch.name)
        with patch.object(runner, "PAGE", 1):
            backup.run(batch.name)
        stopped = frappe.get_doc("Backup Batch", batch.name)
        self.assertEqual((stopped.status, stopped.files_done), ("Đã hủy", 1))
        self.assertEqual(stopped.cursor, self.documents[0])
        with patch.object(runner, "PAGE", 1):
            backup.run(batch.name)
        done = frappe.get_doc("Backup Batch", batch.name)
        self.assertEqual((done.status, done.files_done), ("Thành công", 3))
        entries = [e["document"] for e in filestore.read_manifest(batch.name)]
        self.assertEqual(sorted(entries), sorted(self.documents))  # no document twice

    def test_the_database_dump_is_recorded_with_its_size_and_hash(self):
        dump = os.path.join(self.folder, "20261008_000000-site-database.sql.gz")
        with gzip.open(dump, "wb") as handle:
            handle.write(b"-- MariaDB dump\nCREATE TABLE t (id int);\n")
        with patch("frappe.utils.backups.new_backup", return_value=SimpleNamespace(backup_path_db=dump)):
            batch = self.run_backup("Cơ sở dữ liệu")
        self.assertEqual(batch.status, "Thành công")
        self.assertEqual(batch.backup_path, dump)
        with open(dump, "rb") as handle:
            self.assertEqual(batch.db_checksum, hashlib.sha256(handle.read()).hexdigest())

    def test_a_failed_dump_is_an_error_and_a_combined_backup_is_then_partial(self):
        self.attach_all()
        with patch("frappe.utils.backups.new_backup", side_effect=RuntimeError("mysqldump không chạy được")):
            only_db = self.run_backup("Cơ sở dữ liệu")
            both = self.run_backup("Cả hai")
        self.assertEqual(only_db.status, "Lỗi")
        self.assertIn("mysqldump", only_db.error_log)
        self.assertEqual((both.status, both.files_done), ("Một phần", 3))

    def test_deleting_a_backup_removes_its_dump_manifest_and_unshared_blobs(self):
        self.attach_all()
        first = self.run_backup()
        dump = os.path.join(self.folder, "x-database.sql.gz")
        with open(dump, "wb") as handle:
            handle.write(b"dump")
        frappe.db.set_value("Backup Batch", first.name, "backup_path", dump)
        self.attach(0, body(0, b" v2"))
        second = self.run_backup()
        with patch.object(filestore, "GC_MIN_AGE", 0):
            result = backup.delete_batch(first.name)
        self.assertTrue(result["database_file_removed"])
        self.assertGreaterEqual(result["blobs_removed"], 1)  # the first version of document 0 is in no other batch
        self.assertFalse(os.path.exists(dump))
        self.assertFalse(os.path.exists(filestore.manifest_path(first.name)))
        self.assertTrue(os.path.exists(filestore.manifest_path(second.name)))
        self.assertFalse(frappe.db.exists("Backup Batch", first.name))
        self.assertEqual(frappe.db.count("Backup Batch Item", {"batch": first.name}), 0)

    def test_a_running_backup_cannot_be_deleted(self):
        batch = backup.create_batch("Tệp tài liệu", fonds=self.fonds)
        with self.assertRaises(frappe.ValidationError):
            backup.delete_batch(batch.name)

    def test_retention_deletes_old_batches_but_keeps_the_newest_good_ones(self):
        self.attach_all()
        frappe.db.delete("Backup Batch")  # only these batches count here (rolled back with the test)
        names = []
        for age in (40, 35, 5, 3):
            batch = self.run_backup()
            frappe.db.set_value("Backup Batch", batch.name, "creation", frappe.utils.add_days(frappe.utils.now(), -age))
            names.append(batch.name)
        with patch.object(runner, "settings", return_value=frappe._dict(backup_retention_days=30, backup_keep_min=3, auto_backup_enabled=0,
                                                                         backup_frequency="Hàng tuần", backup_include_files=1)):
            removed = backup.apply_retention()
        self.assertEqual(removed, [names[0]])  # the 35 day old one is protected as one of the newest three
        self.assertEqual(sorted(frappe.get_all("Backup Batch", filters={"name": ["in", names]}, pluck="name")), sorted(names[1:]))

    def test_the_schedule_knows_when_a_backup_is_due(self):
        today = "2026-10-08"
        self.assertTrue(backup.is_due(None, "Hàng tuần", today))
        self.assertFalse(backup.is_due("2026-10-08 02:00:00", "Hàng ngày", today))
        self.assertTrue(backup.is_due("2026-10-07 02:00:00", "Hàng ngày", today))
        self.assertTrue(backup.is_due("2026-10-06 02:00:00", "Hàng ngày", today))
        self.assertFalse(backup.is_due("2026-10-02 02:00:00", "Hàng tuần", today))
        self.assertTrue(backup.is_due("2026-10-01 02:00:00", "Hàng tuần", today))
        self.assertFalse(backup.is_due("2026-09-20 02:00:00", "Hàng tháng", "2026-10-19"))
        self.assertTrue(backup.is_due("2026-09-08 02:00:00", "Hàng tháng", today))

    def test_the_daily_job_starts_a_scheduled_backup_only_when_enabled_due_and_idle(self):
        def config(**kw):
            return frappe._dict(auto_backup_enabled=1, backup_frequency="Hàng ngày", backup_retention_days=30, backup_keep_min=3,
                                backup_include_files=1, **kw)

        with patch.object(runner, "settings", return_value=config()), patch.object(backup, "apply_retention", return_value=[]):
            name = backup.run_scheduled()
            self.assertTrue(name)
            batch = frappe.get_doc("Backup Batch", name)
            self.assertEqual((batch.backup_type, batch.trigger, batch.initiated_by), ("Cả hai", "Theo lịch", None))
            self.assertIsNone(backup.run_scheduled())  # one is already waiting
        with patch.object(runner, "settings", return_value=frappe._dict(**{**config(), "auto_backup_enabled": 0})), \
                patch.object(backup, "apply_retention", return_value=[]):
            frappe.db.set_value("Backup Batch", name, "status", "Thành công")
            self.assertIsNone(backup.run_scheduled())

    # ---- integrity: the database
    def test_database_checks_find_structure_problems_and_the_counters_can_be_fixed(self):
        frappe.db.set_value("Fonds", self.fonds, "total_files", 99)
        frappe.db.set_value("Archival File", self.files[0], {"file_number": "01", "end_date": "1990-01-01", "start_date": "1995-01-01"})
        frappe.db.set_value("Archival File", self.files[1], "file_number", "01")
        frappe.db.set_value("Archive Document", self.documents[2], "record_group", "RG-KHONG-CO")  # a column that disagrees with the file
        check = self.run_check("Cơ sở dữ liệu")
        codes = {f.code for f in self.findings(check)}
        self.assertTrue({"COUNTER_FONDS", "DATE_FILE", "DUPLICATE_FILE_NUMBER", "HIERARCHY_DOCUMENT"} <= codes, codes)
        counter = self.findings(check, "COUNTER_FONDS")[0]
        self.assertIn(self.fonds, counter.message)
        self.assertEqual((counter.severity, counter.restorable), ("Cảnh báo", 0))
        self.assertEqual(self.findings(check, "HIERARCHY_DOCUMENT")[0].severity, "Lỗi")
        self.assertEqual(check.status, "Phát hiện lỗi")  # a hierarchy error
        self.assertGreaterEqual(check.warnings_found, 3)
        result = api.fix_counters()
        self.assertGreaterEqual(result["fonds"], 1)
        self.assertEqual(frappe.db.get_value("Fonds", self.fonds, "total_files"), 3)
        again = self.run_check("Cơ sở dữ liệu")
        self.assertNotIn("COUNTER_FONDS", {f.code for f in self.findings(again)})

    def test_a_clean_scope_is_complete_and_a_scope_only_looks_at_its_fonds(self):
        frappe.db.set_value("Fonds", self.fonds, "total_files", 3)
        for i, file in enumerate(self.files):
            frappe.db.set_value("Archival File", file, {"total_documents": 1, "file_number": f"0{i + 1}"})
        check = self.run_check("Cơ sở dữ liệu")
        errors = [f for f in self.findings(check) if f.severity == "Lỗi"]
        self.assertEqual(errors, [])
        self.assertEqual(check.status, "Hoàn thành")
        self.assertIn("0 lỗi", check.summary)

    def test_metadata_checks_report_what_an_electronic_archive_should_describe(self):
        frappe.db.set_value("Archive Document", self.documents[0], {"document_number": "1/QĐ", "document_date": "1995-01-01", "author": "Bộ"})
        check = self.run_check("Siêu dữ liệu")
        by_code = {f.code: f for f in self.findings(check)}
        self.assertIn("META_DOCUMENT_NUMBER", by_code)
        self.assertIn(": 2", by_code["META_DOCUMENT_NUMBER"].message)  # the other two have no number
        self.assertIn("META_DOCUMENT_FILE", by_code)
        self.assertIn("META_FONDS_CODE", by_code)
        self.assertTrue(all(f.severity == "Cảnh báo" for f in by_code.values()))
        self.assertEqual(check.status, "Hoàn thành")  # warnings do not make a check fail

    # ---- integrity: the files
    def test_file_checks_find_missing_changed_empty_and_wrongly_typed_files(self):
        self.attach_all()
        os.unlink(self.paths[self.documents[0]])
        with open(self.paths[self.documents[1]], "wb") as handle:
            handle.write(body(1, b" tampered"))
        png = b"\x89PNG\r\n\x1a\nnot a pdf"
        with open(self.paths[self.documents[2]], "wb") as handle:  # a PNG where a PDF is declared
            handle.write(png)
        frappe.db.set_value("Archive Document", self.documents[2], "checksum", hashlib.sha256(png).hexdigest())
        check = self.run_check()
        by_doc = {}
        for f in self.findings(check):
            by_doc.setdefault(f.document, set()).add(f.code)
        self.assertEqual(by_doc[self.documents[0]], {"FILE_MISSING"})
        self.assertEqual(by_doc[self.documents[1]], {"CHECKSUM"})
        self.assertEqual(by_doc[self.documents[2]], {"TYPE_MISMATCH"})
        self.assertEqual((check.status, check.errors_found, check.warnings_found, check.total_checked), ("Phát hiện lỗi", 2, 2, 3))  # + MongoDB is down here
        self.assertTrue(all(not f.restorable for f in self.findings(check)))  # there is no backup yet

    def test_a_finding_says_whether_a_backup_could_restore_it(self):
        self.attach_all()
        self.run_backup()
        os.unlink(self.paths[self.documents[0]])
        check = self.run_check()
        missing = self.findings(check, "FILE_MISSING")[0]
        self.assertEqual((missing.document, missing.restorable), (self.documents[0], 1))

    def test_an_empty_file_and_documents_without_files_are_told_apart(self):
        self.attach(0)
        open(self.paths[self.documents[0]], "wb").close()  # truncated to nothing
        check = self.run_check()
        codes = {f.code for f in self.findings(check)}
        self.assertIn("FILE_EMPTY", codes)
        self.assertEqual(check.total_checked, 1)  # only the document with a file is a file to check

    def test_without_mongodb_the_check_says_so_and_with_it_gridfs_is_checked(self):
        self.attach_all()
        down = self.run_check()
        self.assertTrue(any(f.code == "MONGO_DOWN" for f in self.findings(down)))
        frappe.db.set_value("Archive Document", self.documents[0], "gridfs_file_id", "abc123")
        with patch.object(sources, "mongo_available", return_value=(True, "")), patch.object(sources, "gridfs_exists", return_value=False):
            up = self.run_check()
            links = self.run_check("Liên kết file-metadata")
        self.assertEqual([f.document for f in self.findings(up, "GRIDFS_MISSING")], [self.documents[0]])
        self.assertFalse(any(f.code == "MONGO_DOWN" for f in self.findings(up)))
        self.assertEqual({f.document for f in self.findings(links, "GRIDFS_NOT_STORED")}, {self.documents[1], self.documents[2]})

    def test_a_check_continues_after_it_was_stopped(self):
        self.attach_all()
        with open(self.paths[self.documents[2]], "wb") as handle:
            handle.write(b"changed")
        check = integrity.create("Tệp tài liệu", self.fonds)
        runner.request_cancel("Integrity Check", check.name)
        with patch.object(runner, "PAGE", 1):
            integrity.run(check.name)
        stopped = frappe.get_doc("Integrity Check", check.name)
        self.assertEqual((stopped.status, stopped.total_checked), ("Đã hủy", 1))
        with patch.object(runner, "PAGE", 1):
            integrity.run(check.name)
        done = frappe.get_doc("Integrity Check", check.name)
        self.assertEqual((done.status, done.total_checked, done.errors_found), ("Phát hiện lỗi", 3, 1))

    # ---- restoring files
    def test_a_check_leads_to_a_restore_batch_that_brings_the_files_back(self):
        self.attach_all()
        backed_up = self.run_backup()
        os.unlink(self.paths[self.documents[0]])
        with open(self.paths[self.documents[1]], "wb") as handle:
            handle.write(b"ruined")
        check = self.run_check()
        self.assertEqual(check.errors_found, 2)
        batch = restore.create_from_check(check.name)
        self.assertEqual((batch.total, batch.source_check, batch.restore_type), (2, check.name, "Tệp tài liệu"))
        restore.run(batch.name)
        done = frappe.get_doc("Restore Batch", batch.name)
        self.assertEqual((done.status, done.records_restored, done.failed), ("Thành công", 2, 0))
        for index in (0, 1):
            with open(self.paths[self.documents[index]], "rb") as handle:
                self.assertEqual(handle.read(), body(index))
        items = frappe.get_all("Restore Batch Item", filters={"restore": batch.name}, fields=["document", "status", "source_backup", "message"])
        self.assertTrue(all(i.status == "Đã khôi phục" and i.source_backup == backed_up.name for i in items))
        self.assertTrue(all(f.status == "Đã khôi phục" for f in self.findings(check) if f.document), self.findings(check))
        self.assertEqual(self.run_check().errors_found, 0)  # and the next check is clean

    def test_a_restore_recreates_the_file_record_when_it_is_gone(self):
        self.attach_all()
        self.run_backup()
        record = frappe.get_doc("File", {"file_url": frappe.db.get_value("Archive Document", self.documents[0], "file_attachment")})
        record.delete()
        frappe.db.set_value("Archive Document", self.documents[0], "file_attachment", "")
        batch = restore.create_files_restore([self.documents[0]])
        restore.run(batch.name)
        url = frappe.db.get_value("Archive Document", self.documents[0], "file_attachment")
        self.assertTrue(url, frappe.get_all("Restore Batch Item", filters={"restore": batch.name}, pluck="message"))
        self.touched.append(os.path.basename(url))
        self.assertEqual(sources.read_disk(url), body(0))
        self.assertEqual(frappe.get_doc("Restore Batch", batch.name).status, "Thành công")

    def test_documents_a_backup_cannot_restore_are_reported_one_by_one(self):
        self.attach_all()
        first = self.run_backup()
        entries = list(filestore.read_manifest(first.name))
        os.unlink(filestore.blob_path(next(e["sha256"] for e in entries if e["document"] == self.documents[1])))  # a blob lost
        batch = restore.create_files_restore(self.documents[1:3])
        restore.run(batch.name)
        done = frappe.get_doc("Restore Batch", batch.name)
        self.assertEqual((done.status, done.records_restored, done.failed), ("Một phần", 1, 1))
        messages = {i.document: i.message for i in frappe.get_all("Restore Batch Item", filters={"restore": batch.name}, fields=["document", "message"])}
        self.assertIn("thiếu hoặc hỏng", messages[self.documents[1]])

    def test_a_document_that_is_in_no_backup_is_an_error_and_nothing_else_is_touched(self):
        batch = restore.create_files_restore([self.documents[0]])
        restore.run(batch.name)
        done = frappe.get_doc("Restore Batch", batch.name)
        self.assertEqual((done.status, done.failed), ("Lỗi", 1))
        self.assertIn("Không có bản sao lưu", frappe.get_all("Restore Batch Item", filters={"restore": batch.name}, pluck="message")[0])

    def test_a_restore_can_name_its_backup_and_refuses_one_without_files(self):
        self.attach_all()
        files = self.run_backup()
        batch = restore.create_files_restore([self.documents[0]], files.name)
        self.assertEqual(batch.source_backup, files.name)
        dump_only = backup.create_batch("Cơ sở dữ liệu")
        frappe.db.set_value("Backup Batch", dump_only.name, "status", "Thành công")
        with self.assertRaises(frappe.ValidationError):
            restore.create_files_restore([self.documents[0]], dump_only.name)
        with self.assertRaises(frappe.ValidationError):
            restore.create_files_restore([])
        with self.assertRaises(frappe.ValidationError):
            restore.create_files_restore(["DOC-KHONG-CO"])
        with self.assertRaises(frappe.ValidationError):
            restore.create_from_check(self.run_check().name)  # nothing restorable

    # ---- restoring the database
    def make_dump(self, content=b"-- MariaDB dump\nCREATE TABLE t (id int);\n"):
        path = os.path.join(self.folder, f"{TAG}-database.sql.gz")
        with gzip.open(path, "wb") as handle:
            handle.write(content)
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        batch = backup.create_batch("Cơ sở dữ liệu")
        frappe.db.set_value("Backup Batch", batch.name, {"status": "Thành công", "backup_path": path, "db_checksum": digest})
        return batch.name, path

    def test_a_dump_is_verified_before_anything_is_said_about_restoring_it(self):
        name, path = self.make_dump()
        self.assertEqual(restore.verify_db_backup(name)["ok"], True)
        frappe.db.set_value("Backup Batch", name, "db_checksum", "0" * 64)
        self.assertIn("SHA-256", restore.verify_db_backup(name)["problems"][0])
        frappe.db.set_value("Backup Batch", name, "db_checksum", "")
        with open(path, "wb") as handle:
            handle.write(b"this is not gzip")
        self.assertFalse(restore.verify_db_backup(name)["ok"])
        os.unlink(path)
        self.assertIn("Không còn tệp", restore.verify_db_backup(name)["problems"][0])
        other, other_path = self.make_dump(b"just some text, not a dump")
        self.assertFalse(restore.verify_db_backup(other)["ok"])

    def test_by_default_a_database_restore_is_a_checked_runbook_not_an_action(self):
        name, path = self.make_dump()
        batch = restore.create_db_restore(name)
        with patch.object(restore.subprocess, "run") as runs:
            restore.run(batch.name, confirm_site=frappe.local.site)
        runs.assert_not_called()
        done = frappe.get_doc("Restore Batch", batch.name)
        self.assertEqual(done.status, "Cần thao tác thủ công")
        self.assertIn("set-maintenance-mode on", done.error_log)
        self.assertIn(f'restore "{path}"', done.error_log)
        self.assertNotIn("--db-root-password", done.error_log.replace("--db-root-password <mật khẩu root MariaDB>", ""))

    def test_a_site_that_allows_it_restores_itself_only_with_the_site_name_typed(self):
        name, path = self.make_dump()
        calls = []

        def fake_run(command, **kw):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")

        conf = {"dm_allow_db_restore": 1, "dm_db_root_password": "s3cret"}
        with patch.object(frappe, "conf", frappe._dict({**frappe.conf, **conf})), patch.object(restore.subprocess, "run", side_effect=fake_run):
            wrong = restore.create_db_restore(name)
            restore.run(wrong.name, confirm_site="khac.example.com")
            self.assertEqual(frappe.get_doc("Restore Batch", wrong.name).status, "Cần thao tác thủ công")
            self.assertEqual(calls, [])
            right = restore.create_db_restore(name)
            restore.run(right.name, confirm_site=frappe.local.site)
        self.assertEqual(frappe.get_doc("Restore Batch", right.name).status, "Thành công")
        verbs = [" ".join(c[3:5]) if c[3] != "--force" else "restore" for c in calls]
        self.assertEqual(verbs, ["set-maintenance-mode on", "restore", "migrate", "set-maintenance-mode off"])
        self.assertIn(path, calls[1])

    def test_a_failing_restore_command_ends_in_error_and_maintenance_mode_is_switched_off(self):
        name, _path = self.make_dump()
        calls = []

        def fake_run(command, **kw):
            calls.append(command)
            return SimpleNamespace(returncode=1 if "restore" in command else 0, stdout="", stderr="lỗi")

        with patch.object(frappe, "conf", frappe._dict({**frappe.conf, "dm_allow_db_restore": 1, "dm_db_root_password": "x"})), \
                patch.object(restore.subprocess, "run", side_effect=fake_run):
            batch = restore.create_db_restore(name)
            restore.run(batch.name, confirm_site=frappe.local.site)
        self.assertEqual(frappe.get_doc("Restore Batch", batch.name).status, "Lỗi")
        self.assertEqual(calls[-1][3:5], ["set-maintenance-mode", "off"])

    def test_a_damaged_dump_ends_the_restore_in_error_without_a_runbook(self):
        name, path = self.make_dump()
        with open(path, "wb") as handle:
            handle.write(b"broken")
        batch = restore.create_db_restore(name)
        restore.run(batch.name)
        done = frappe.get_doc("Restore Batch", batch.name)
        self.assertEqual(done.status, "Lỗi")
        self.assertIn("không dùng được", done.error_log)

    # ---- the API and who may use it
    def test_only_preservation_roles_use_the_api(self):
        calls = (lambda: api.overview(), lambda: api.list_jobs("backup"), lambda: api.start_backup(), lambda: api.start_check(),
                 lambda: api.fix_counters(), lambda: api.get_job("backup", "BK-1"), lambda: api.run_retention(),
                 lambda: api.download_backup("BK-1"), lambda: api.cancel("backup", "BK-1"), lambda: api.delete_job("backup", "BK-1"))
        for user in (CATALOGER, OFFICER, READER, "Guest"):
            frappe.set_user(user)
            for call in calls:
                with self.assertRaises(frappe.PermissionError, msg=user):
                    call()
        frappe.set_user(PRESERVER)
        self.assertIn("settings", api.overview())
        frappe.set_user(ADMIN)
        self.assertIn("store", api.overview())

    def test_the_api_starts_jobs_lists_them_and_refuses_a_second_at_once(self):
        job = api.start_backup("Tệp tài liệu", self.fonds, "thử")
        self.assertEqual((job["kind"], job["status"], job["busy"], job["can_cancel"], job["can_delete"]), ("backup", "Đang chờ", True, True, False))
        self.enqueue.assert_called()
        with self.assertRaises(frappe.ValidationError):
            api.start_backup()
        with self.assertRaises(frappe.ValidationError):
            api.start_backup("Không có loại này")
        listing = api.list_jobs("backup")
        self.assertIn(job["name"], [j["name"] for j in listing["data"]])
        check = api.start_check("Cơ sở dữ liệu", self.fonds)
        self.assertEqual(check["check_type"], "Cơ sở dữ liệu")
        with self.assertRaises(frappe.ValidationError):
            api.start_check()
        with self.assertRaises(frappe.ValidationError):
            api.list_jobs("khong-co")

    def test_a_job_is_cancelled_resumed_and_deleted_only_when_its_state_allows(self):
        self.attach_all()
        job = api.start_backup("Tệp tài liệu", self.fonds)
        stopped = api.cancel("backup", job["name"])
        self.assertEqual(stopped["status"], "Đã hủy")
        self.assertTrue(stopped["can_resume"])
        with self.assertRaises(frappe.ValidationError):
            api.cancel("backup", job["name"])  # nothing running
        resumed = api.resume("backup", job["name"])
        self.assertEqual(resumed["status"], "Đang chờ")
        with self.assertRaises(frappe.ValidationError):
            api.resume("backup", job["name"])  # it is waiting now, not stopped
        with self.assertRaises(frappe.ValidationError):
            api.delete_job("backup", job["name"])  # still busy
        api.cancel("backup", job["name"])
        self.assertEqual(api.delete_job("backup", job["name"])["name"], job["name"])
        self.assertFalse(frappe.db.exists("Backup Batch", job["name"]))

    def test_the_detail_of_a_check_lists_its_findings_and_they_can_be_set_aside(self):
        self.attach_all()
        self.run_backup()
        os.unlink(self.paths[self.documents[0]])
        check = self.run_check()
        detail = api.get_job("integrity", check.name)
        self.assertEqual((detail["errors"], detail["restorable"]), (1, 1))
        self.assertEqual(detail["items_total"], len(detail["items"]))
        page = api.list_findings(check.name, severity="Lỗi")
        self.assertEqual(page["total"], 1)
        finding = page["data"][0]
        self.assertEqual(api.set_finding_status(finding["name"], "Đã bỏ qua")["status"], "Đã bỏ qua")
        self.assertEqual(api.get_job("integrity", check.name)["restorable"], 0)  # no longer waiting to be restored
        with self.assertRaises(frappe.ValidationError):
            api.set_finding_status(finding["name"], "Tùy tiện")

    def test_a_restore_is_started_from_documents_or_from_a_check_and_a_database_restore_is_prepared_not_run(self):
        self.attach_all()
        self.run_backup()
        job = api.start_restore(documents=[self.documents[0]])
        self.assertEqual((job["kind"], job["total"], job["status"]), ("restore", 1, "Đang chờ"))
        name, _path = self.make_dump()
        prepared = api.prepare_db_restore(name)
        self.assertTrue(prepared["verification"]["ok"])
        self.assertEqual((prepared["batch"]["restore_type"], prepared["batch"]["status"], prepared["batch"]["busy"]), ("Cơ sở dữ liệu", "Chưa chạy", False))
        self.assertIn("set-maintenance-mode on", prepared["runbook"])
        self.assertFalse(prepared["can_run"])
        with self.assertRaises(frappe.ValidationError):
            api.resume("restore", prepared["batch"]["name"])  # a database restore is run on purpose, not resumed

    def test_a_download_is_logged_stays_inside_the_backup_folder_and_has_a_size_limit(self):
        name, path = self.make_dump()
        before = frappe.db.count("Business Activity Log", {"reference_name": name, "activity_type": "Tải xuống"})
        api.download_backup(name)
        response = frappe.local.response
        self.assertEqual((response["type"], response["filename"]), ("download", f"{name}-database.sql.gz"))
        self.assertEqual(frappe.db.count("Business Activity Log", {"reference_name": name, "activity_type": "Tải xuống"}), before + 1)
        elsewhere = os.path.join(tempfile.gettempdir(), f"{TAG}-outside.gz")
        with open(elsewhere, "wb") as handle:
            handle.write(b"x")
        self.addCleanup(os.unlink, elsewhere)
        frappe.db.set_value("Backup Batch", name, "backup_path", elsewhere)
        with self.assertRaises(frappe.DoesNotExistError):
            api.download_backup(name)  # a path outside the backups folder is never served
        frappe.db.set_value("Backup Batch", name, "backup_path", path)
        with patch.object(api, "MAX_DOWNLOAD_MB", 0):
            with self.assertRaises(frappe.ValidationError):
                api.download_backup(name)
        self.attach_all()
        batch = self.run_backup()
        api.download_backup(batch.name, "manifest")
        self.assertEqual(frappe.local.response["filename"], f"{batch.name}-manifest.jsonl")
        self.assertEqual(len(frappe.local.response["filecontent"].decode().splitlines()), 3)

    # ---- the settings
    def test_the_security_settings_reach_frappes_system_settings_and_are_validated(self):
        settings = frappe.get_doc("Document Manager Settings")
        settings.update({"enforce_password_policy": 1, "minimum_password_score": "3", "login_max_attempts": 7, "login_lock_seconds": 120})
        settings.save()
        system = frappe.get_doc("System Settings")
        cint = frappe.utils.cint
        self.assertEqual(cint(system.enable_password_policy), 1)
        self.assertEqual((str(system.minimum_password_score), cint(system.allow_consecutive_login_attempts), cint(system.allow_login_after_fail)),
                         ("3", 7, 120))
        settings.login_max_attempts = 1
        with self.assertRaises(frappe.ValidationError):
            settings.save()
        settings.reload()
        settings.backup_retention_days = 0
        with self.assertRaises(frappe.ValidationError):
            settings.save()

    def test_the_old_open_entry_points_are_gone(self):
        for module in ("document_manager.document_manager.services.backup_service",):
            with self.assertRaises(ImportError):
                __import__(module)
        for doctype in ("backup_batch", "integrity_check", "restore_batch"):
            mod = __import__(f"document_manager.document_manager.doctype.{doctype}.{doctype}", fromlist=["x"])
            self.assertFalse([n for n in dir(mod) if n.startswith("trigger_")])
