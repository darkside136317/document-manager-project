# -*- coding: utf-8 -*-
"""Unified search of files and documents: engines, filters, totals, visibility.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_search_service
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager.api import search as api
from document_manager.document_manager.services import search_index, search_service
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _reader, _seed_archive, _user

READER = "ss.reader@example.com"
NOPROFILE = "ss.noprofile@example.com"
OFFICER = "ss.officer@example.com"


class TestSearchService(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.ensure_roles()
        install.ensure_confidentiality_levels()
        install.ensure_default_reader_group()
        _user(READER, ["Reader"], "Website User")
        _user(NOPROFILE, ["Reader"], "Website User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        cls.profile = _reader(READER, "SS Reader")
        cls._seeded = _seed_archive(2)
        cls.file_1, cls.file_2 = _names(cls._seeded, "Archival File")
        cls.doc_1, cls.doc_2 = _names(cls._seeded, "Archive Document")
        # distinctive data to search for
        frappe.db.set_value("Archival File", cls.file_1, {
            "file_title": "SSALPHA Hồ sơ thử", "file_number": "SS-001", "start_date": "2020-01-10"})
        frappe.db.set_value("Archival File", cls.file_2, {
            "file_title": "SSBETA Hồ sơ khác", "file_number": "SS-002", "start_date": "2022-06-01"})
        frappe.db.set_value("Archive Document", cls.doc_1, {
            "document_title": "SSALPHA công văn", "document_number": "CV-77", "author": "Bộ Nội vụ",
            "document_date": "2021-03-05", "file_type": "PDF"})
        frappe.db.set_value("Archive Document", cls.doc_2, {
            "document_title": "SSBETA quyết định", "document_number": "QD-88", "author": "Sở Tài chính",
            "document_date": "2023-09-09", "file_type": "DOCX"})

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for dt, name in cls._seeded:
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        frappe.delete_doc("Reader", cls.profile, force=True, ignore_permissions=True)
        for email in (READER, NOPROFILE, OFFICER):
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user(OFFICER)

    def tearDown(self):
        frappe.set_user("Administrator")

    # ---- archival files
    def test_basic_file_search_matches_title_number_and_counts_correctly(self):
        res = api.search_archival_files(query="SSALPHA")
        self.assertEqual([r.name for r in res["data"]], [self.file_1])
        self.assertEqual(res["total"], 1)  # the old count ignored the OR filter and over-counted
        self.assertEqual(api.search_archival_files(query="SS-002")["total"], 1)
        self.assertEqual(api.search_archival_files(query="no-such-thing-xyz")["total"], 0)

    def test_advanced_file_filters_combine_with_and(self):
        self.assertEqual(api.search_archival_files(file_title="SSALPHA", file_number="SS-001")["total"], 1)
        # the old implementation OR-ed these two and returned the file for either
        self.assertEqual(api.search_archival_files(file_title="SSALPHA", file_number="SS-002")["total"], 0)

    def test_date_filters_are_applied(self):
        names = lambda **kw: {r.name for r in api.search_archival_files(file_title="SS", **kw)["data"]}  # noqa: E731
        self.assertEqual(names(start_date_from="2021-01-01"), {self.file_2})
        self.assertEqual(names(start_date_to="2021-01-01"), {self.file_1})
        self.assertEqual(names(start_date_from="2020-01-01", start_date_to="2023-01-01"), {self.file_1, self.file_2})

    def test_paging_is_bounded(self):
        res = api.search_archival_files(file_title="SS", page_size=1)
        self.assertEqual((len(res["data"]), res["total"], res["page_size"]), (1, 2, 1))
        self.assertEqual(api.search_archival_files(file_title="SS", page_size=100000)["page_size"], 100)
        self.assertEqual(api.search_archival_files(file_title="SS", page=0)["page"], 1)

    # ---- documents: database engine
    def test_document_filters_with_like_use_the_database(self):
        with patch.object(search_index, "search") as meili:
            res = api.search_documents(query="SSALPHA", author="Nội vụ")  # `author` needs a substring match
        meili.assert_not_called()
        self.assertEqual(res["engine"], "database")
        self.assertEqual([r["id"] for r in res["data"]], [self.doc_1])

    def test_document_date_range_and_equality_filters(self):
        res = api.search_documents(document_title="SS", date_from="2022-01-01")
        self.assertEqual([r["id"] for r in res["data"]], [self.doc_2])
        res = api.search_documents(document_title="SS", file_type="PDF")
        self.assertEqual([r["id"] for r in res["data"]], [self.doc_1])
        self.assertEqual(api.search_documents(document_title="SS", date_to="2030-01-01")["total"], 2)

    # ---- documents: Meilisearch engine and fallback
    def _hit(self, doc_id):
        return {"id": doc_id, "document_title": "t", "content_text": "secret " * 500,
                "_formatted": {"document_title": "<mark>t</mark>", "content_text": "…snippet…"}}

    def test_a_free_text_query_goes_to_meilisearch_without_the_extracted_text(self):
        with patch.object(search_index, "search",
                          return_value={"hits": [self._hit(self.doc_1)], "estimatedTotalHits": 1}) as meili:
            res = api.search_documents(query="công văn", fonds="F1", date_from="2021-01-01", date_to="2021-12-31")
        kwargs = meili.call_args.kwargs
        self.assertEqual(kwargs["query"], "công văn")
        self.assertEqual(kwargs["filters"], {"fonds": "F1"})
        self.assertLess(kwargs["date_from"], kwargs["date_to"])
        self.assertEqual(res["engine"], "meilisearch")
        self.assertEqual(res["total"], 1)
        self.assertNotIn("content_text", res["data"][0])
        self.assertEqual(res["data"][0]["_formatted"]["content_text"], "…snippet…")  # the short snippet stays
        self.assertEqual(res["data"][0]["name"], self.doc_1)

    def test_search_falls_back_to_the_database_when_meilisearch_is_down(self):
        with patch.object(search_index, "search", side_effect=ConnectionError("down")):
            res = api.search_documents(query="SSBETA")
        self.assertEqual(res["engine"], "database")
        self.assertEqual([r["id"] for r in res["data"]], [self.doc_2])

    def test_search_fulltext_keeps_working_for_the_current_portal(self):
        self.assertEqual(api.search_fulltext(query=None)["data"], [])
        with patch.object(search_index, "search", side_effect=ConnectionError("down")):
            res = api.search_fulltext(query="SSALPHA")
        self.assertEqual([r["id"] for r in res["data"]], [self.doc_1])

    # ---- visibility
    def test_readers_never_find_draft_files_or_their_documents(self):
        frappe.db.set_value("Archival File", self.file_1, "status", "Nháp")
        frappe.set_user(READER)
        self.assertEqual(api.search_archival_files(query="SSALPHA")["total"], 0)
        self.assertEqual(api.search_documents(document_title="SSALPHA")["total"], 0)
        self.assertEqual(api.search_documents(document_title="SSBETA")["total"], 1)  # the published one is found
        frappe.set_user(OFFICER)
        self.assertEqual(api.search_archival_files(query="SSALPHA")["total"], 1)  # staff still see drafts

    def test_a_reader_cannot_widen_the_scope_with_a_filter(self):
        secret = "SS Secret"
        frappe.get_doc({"doctype": "Confidentiality Level", "level_name": secret, "priority": 9}
                       ).insert(ignore_permissions=True)
        frappe.db.set_value("Archival File", self.file_2, "confidentiality_level", secret)
        frappe.set_user(READER)
        self.assertEqual(api.search_archival_files(query="SSBETA", confidentiality_level=secret)["total"], 0)
        self.assertEqual(api.search_archival_files(query="SSBETA")["total"], 0)
        frappe.set_user(OFFICER)
        self.assertEqual(api.search_archival_files(query="SSBETA", confidentiality_level=secret)["total"], 1)
        frappe.db.set_value("Archival File", self.file_2, "confidentiality_level", "Thường")
        frappe.delete_doc("Confidentiality Level", secret, force=True, ignore_permissions=True)

    def test_search_is_refused_without_an_active_reader_profile(self):
        frappe.set_user(NOPROFILE)
        for call in (lambda: api.search_archival_files(query="x"), lambda: api.search_documents(query="x"),
                     lambda: api.search_fulltext(query="x")):
            with self.assertRaises(frappe.PermissionError):
                call()

    def test_service_helpers_are_importable_without_the_api(self):
        self.assertEqual(search_service.search_files({"query": "SSALPHA"})["total"], 1)
