# -*- coding: utf-8 -*-
"""What keeps the app usable on a table of a million rows: capped counts, a ceiling on scans, cached probes, indexes.

The figures themselves come from `scripts/perf/volume_check.py` on a scratch site; these tests pin the behaviour.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_volume_guards
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from document_manager.document_manager.api import admin, crud, logs
from document_manager.document_manager.services import health, mongodb_storage, queries, search_service
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _seed_archive

TAG = "VG"


class TestVolumeGuards(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.ensure_roles()
        install.ensure_confidentiality_levels()
        cls._seeded = _seed_archive(5)
        for index, name in enumerate(_names(cls._seeded, "Archive Document")):
            frappe.db.set_value("Archive Document", name, {"document_title": f"{TAG}ZEBRA tài liệu {index}", "author": f"{TAG} Sở"})

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for doctype, name in cls._seeded:
            frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        super().tearDownClass()

    def setUp(self):
        frappe.set_user("Administrator")
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.db.savepoint("vg_test")
        self.addCleanup(frappe.db.rollback, save_point="vg_test")

    # ---- counts that stop
    def test_a_count_stops_at_its_ceiling(self):
        filters = [["Archive Document", "document_title", "like", f"%{TAG}ZEBRA%"]]
        self.assertEqual(queries.capped_count("Archive Document", filters), (5, False))
        self.assertEqual(queries.capped_count("Archive Document", filters, cap=3), (3, True))
        self.assertEqual(queries.capped_count("Archive Document", filters, cap=5), (5, False))

    def test_a_text_search_reports_when_its_total_was_cut_short(self):
        with patch("document_manager.document_manager.api.crud.capped_count",
                   side_effect=lambda *a, **k: queries.capped_count(*a, cap=3, **k)):
            found = crud.get_list("Archive Document", search=f"{TAG}ZEBRA", page_size=2)  # a full page: there may be more behind it
        self.assertEqual((found["total"], found["total_capped"]), (3, True))
        self.assertEqual(len(found["data"]), 2)  # the page itself is not cut: only the figure

    def test_a_plain_list_still_counts_exactly(self):
        found = crud.get_list("Archive Document", filters={"author": f"{TAG} Sở"})
        self.assertEqual(found["total"], 5)
        self.assertNotIn("total_capped", found)

    def test_the_database_search_says_when_it_counted_to_a_ceiling(self):
        scanned = search_service.search_documents({"author": f"{TAG} Sở"})
        self.assertIn("total_capped", scanned)
        exact = search_service.search_documents({"file_type": "PDF"})
        self.assertNotIn("total_capped", exact)

    def test_the_search_boxes_of_big_tables_look_at_titles_and_numbers_not_at_link_columns(self):
        from document_manager.document_manager.services.ui import describe

        self.assertEqual(describe("Archive Document")["search_fields"], ["document_title", "document_number", "author"])
        self.assertEqual(describe("Archival File")["search_fields"], ["file_title", "file_number"])

    # ---- a ceiling on how long a scan may run
    def test_a_scan_that_takes_too_long_is_stopped_with_a_message_and_the_limit_is_put_back(self):
        before = frappe.db.sql("select @@max_statement_time")[0][0]
        with self.assertRaises(frappe.ValidationError) as caught:
            with queries.bounded_scan(1):
                frappe.db.sql("select sleep(4)")
        self.assertIn("quá nhiều thời gian", str(caught.exception))
        self.assertEqual(frappe.db.sql("select @@max_statement_time")[0][0], before)
        with queries.bounded_scan(5):  # a fast statement is not touched
            self.assertEqual(frappe.db.sql("select 1")[0][0], 1)

    def test_other_errors_pass_through_the_ceiling_untouched(self):
        with self.assertRaises(ZeroDivisionError):
            with queries.bounded_scan(5):
                raise ZeroDivisionError

    # ---- the log
    def test_a_log_text_search_without_dates_looks_at_the_recent_month(self):
        found = logs.list_logs(search="zzz-nothing-matches")
        self.assertEqual(found["searched_from"], str(add_days(nowdate(), -logs.SEARCH_WINDOW_DAYS)))
        self.assertIn("total_capped", found)
        dated = logs.list_logs(search="zzz-nothing-matches", date_from="2020-01-01")
        self.assertIsNone(dated["searched_from"])
        plain = logs.list_logs()
        self.assertNotIn("searched_from", plain)

    # ---- the monitor and the probes
    def test_service_probes_are_kept_for_a_few_seconds(self):
        frappe.cache.delete_value(health.CACHE_KEY)
        with patch.object(health, "_check_mongodb", return_value={"ok": False, "message": "x"}) as mongo, \
                patch.object(health, "_check_meilisearch", return_value={"ok": True, "message": "ok", "documents": 1}) as meili:
            first = health.check_services()
            second = health.check_services()
            self.assertEqual(first, second)
            self.assertEqual((mongo.call_count, meili.call_count), (1, 1))
            health.check_services(fresh=True)
            self.assertEqual(mongo.call_count, 2)
        frappe.cache.delete_value(health.CACHE_KEY)

    def test_a_mongodb_that_just_failed_is_not_waited_for_again(self):
        uri = "mongodb://127.0.0.1:1/never"
        saved = dict(mongodb_storage._mongo_clients)
        mongodb_storage._mongo_clients.clear()
        frappe.cache.set_value(mongodb_storage.DOWN_KEY, "không kết nối", expires_in_sec=30)
        try:
            with patch.dict(frappe.local.conf, {"mongodb_atlas_uri": uri}):
                with self.assertRaises(frappe.ValidationError) as caught:
                    mongodb_storage._get_mongo_client()
            self.assertIn("tạm thời", str(caught.exception))
        finally:
            frappe.cache.delete_value(mongodb_storage.DOWN_KEY)
            mongodb_storage._mongo_clients.update(saved)

    def test_the_size_of_the_uploaded_files_is_measured_in_the_background(self):
        frappe.cache.delete_value(admin.FILES_SIZE_KEY)
        with patch.object(frappe, "enqueue") as enqueue:
            self.assertIsNone(admin.private_files_bytes())
            self.assertEqual(enqueue.call_count, 1)
            self.assertEqual(enqueue.call_args.kwargs["job_id"], "dm_measure_private_files")
        total = admin.measure_private_files()
        with patch.object(frappe, "enqueue") as enqueue:
            self.assertEqual(admin.private_files_bytes(), total)
            enqueue.assert_not_called()
        frappe.cache.delete_value(admin.FILES_SIZE_KEY)

    # ---- indexes
    def test_the_duplicate_number_checks_have_their_composite_indexes(self):
        def indexes(table):
            rows = frappe.db.sql(f"show index from `tab{table}`", as_dict=True)
            found = {}
            for row in rows:
                found.setdefault(row["Key_name"], []).append(row["Column_name"])
            return found

        self.assertEqual(indexes("Archive Document").get("archival_file_document_number"), ["archival_file", "document_number"])
        self.assertEqual(indexes("Archival File").get("catalog_file_number"), ["catalog", "file_number"])

    def test_a_short_page_is_its_own_total_and_costs_no_second_scan(self):
        rows = [object()] * 7
        self.assertEqual(queries.total_of_short_page(rows, 1, 20), 7)
        self.assertEqual(queries.total_of_short_page(rows, 3, 20), 47)
        self.assertEqual(queries.total_of_short_page([], 1, 20), 0)
        self.assertIsNone(queries.total_of_short_page([], 3, 20))  # past the end: not known from the page
        self.assertIsNone(queries.total_of_short_page([object()] * 20, 1, 20))  # a full page may have more behind it
        with patch("document_manager.document_manager.api.crud.capped_count") as count:
            found = crud.get_list("Archive Document", search=f"{TAG}ZEBRA")
            count.assert_not_called()
        self.assertEqual((found["total"], found["total_capped"]), (5, False))
