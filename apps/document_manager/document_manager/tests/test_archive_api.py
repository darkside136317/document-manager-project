# -*- coding: utf-8 -*-
"""Cataloguing API of the staff UI: tree, overviews, documents from uploaded files, printing.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_archive_api
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from document_manager.document_manager.api import archive, crud, meta
from document_manager.document_manager.constants import UPLOAD_EXTENSIONS
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _seed_archive, _user

CATALOGER = "ar.cataloger@example.com"
OFFICER = "ar.officer@example.com"
OTHER = "ar.other@example.com"
READER = "ar.reader@example.com"
USERS = (CATALOGER, OFFICER, OTHER, READER)
def _pdf() -> bytes:
    """A real one-page PDF: Frappe validates PDFs on upload."""
    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


PDF = _pdf()


class TestArchiveApi(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        _user(CATALOGER, ["Cataloger"], "System User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(OTHER, ["Cataloger"], "System User")
        _user(READER, ["Reader"], "Website User")
        cls._seeded = _seed_archive(2)
        cls.fonds = _names(cls._seeded, "Fonds")[0]
        cls.group = _names(cls._seeded, "Record Group")[0]
        cls.catalog = _names(cls._seeded, "Catalog")[0]
        cls.file_a, cls.file_b = _names(cls._seeded, "Archival File")
        cls.doc_a, _doc_b = _names(cls._seeded, "Archive Document")

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for dt, name in cls._seeded:
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for email in USERS:
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user(CATALOGER)
        frappe.db.savepoint("ar_test")
        self.files = []

    def tearDown(self):
        frappe.set_user("Administrator")
        for name in self.files:  # remove the bytes from disk too: a rollback would leave them behind
            if frappe.db.exists("File", name):
                frappe.delete_doc("File", name, force=True, ignore_permissions=True)
        frappe.db.rollback(save_point="ar_test")

    def _upload(self, filename="Báo cáo năm 2020.pdf", content=PDF, user=None):
        previous = frappe.session.user
        if user:
            frappe.set_user(user)
        file = frappe.get_doc({"doctype": "File", "file_name": filename, "content": content, "is_private": 1}
                              ).insert(ignore_permissions=True)
        frappe.set_user(previous)
        self.files.append(file.name)
        return file

    # ---- the tree
    def test_tree_walks_fonds_then_record_groups_then_catalogs(self):
        roots = {n["name"]: n for n in archive.get_tree()}
        self.assertEqual((roots[self.fonds]["child_count"], roots[self.fonds]["file_count"]), (1, 2))
        self.assertEqual(roots[self.fonds]["doctype"], "Fonds")
        groups = archive.get_tree("Fonds", self.fonds)
        self.assertEqual([(g["doctype"], g["name"], g["child_count"], g["file_count"]) for g in groups],
                         [("Record Group", self.group, 1, 2)])
        catalogs = archive.get_tree("Record Group", self.group)
        self.assertEqual([(c["doctype"], c["name"], c["child_count"], c["file_count"]) for c in catalogs],
                         [("Catalog", self.catalog, 0, 2)])
        self.assertEqual(archive.get_tree("Catalog", self.catalog), [])  # catalogs are the leaves
        self.assertEqual(archive.get_tree("Archival File", self.file_a), [])

    def test_tree_titles_and_codes_come_from_the_records(self):
        group = frappe.get_doc("Record Group", self.group)
        node = archive.get_tree("Fonds", self.fonds)[0]
        self.assertEqual(node["title"], group.group_title)

    def test_the_tree_is_for_staff_only(self):
        frappe.set_user(READER)
        for call in (archive.get_tree, lambda: archive.get_file_overview(self.file_a)):
            with self.assertRaises(frappe.PermissionError):
                call()

    # ---- overviews
    def test_file_overview_has_breadcrumb_stats_permissions_and_print_links(self):
        frappe.db.set_value("Archive Document", self.doc_a, {"file_size_kb": 120.5, "search_index_status": "Đã index"})
        info = archive.get_file_overview(self.file_a)
        self.assertEqual([a["doctype"] for a in info["ancestors"]], ["Fonds", "Record Group", "Catalog"])
        self.assertEqual(info["stats"], {"documents": 1, "size_kb": 120.5, "indexed": 1, "failed": 0})
        self.assertEqual(info["permissions"], {"write": True, "delete": True, "add_documents": True})
        self.assertEqual(set(info["print"]), {"standard", "contents"})
        self.assertIn("format=Archival%20File%20Contents", info["print"]["contents"]["view"])
        self.assertIn("download_print_pdf", info["print"]["contents"]["pdf"])
        self.assertEqual(info["upload"]["extensions"], UPLOAD_EXTENSIONS)

    def test_an_officer_may_look_but_not_change(self):
        frappe.set_user(OFFICER)
        info = archive.get_file_overview(self.file_a)
        self.assertEqual(info["permissions"], {"write": False, "delete": False, "add_documents": False})
        self.assertTrue(info["print"])  # printing is allowed

    def test_document_overview_describes_the_stored_file(self):
        file = self._upload()
        created = archive.add_document_from_file(self.file_a, file.file_url)
        info = archive.get_document_overview(created["name"])
        self.assertEqual([a["doctype"] for a in info["ancestors"]], ["Fonds", "Record Group", "Catalog", "Archival File"])
        self.assertEqual((info["file"]["type"], info["file"]["attached"], info["file"]["name"]), ("PDF", True, file.file_name))
        self.assertIn("standard", info["print"])

    # ---- documents from uploaded files
    def test_a_document_is_created_from_an_uploaded_file(self):
        file = self._upload("Báo cáo năm 2020.pdf")
        created = archive.add_document_from_file(self.file_a, file.file_url)
        self.assertEqual((created["title"], created["file_type"]), ("Báo cáo năm 2020", "PDF"))
        doc = frappe.get_doc("Archive Document", created["name"])
        self.assertEqual((doc.archival_file, doc.file_attachment, doc.fonds), (self.file_a, file.file_url, self.fonds))
        bound = frappe.db.get_value("File", file.name, ["attached_to_doctype", "attached_to_name"], as_dict=True)
        self.assertEqual((bound.attached_to_doctype, bound.attached_to_name), ("Archive Document", doc.name))
        self.assertEqual(frappe.db.get_value("Archival File", self.file_a, "total_documents"), 2)

    def test_the_title_can_be_given_and_legacy_office_files_are_not_extracted(self):
        file = self._upload("so-lieu.xls", b"\xd0\xcf\x11\xe0 binary xls")
        created = archive.add_document_from_file(self.file_a, file.file_url, title="Số liệu 1999")
        self.assertEqual((created["title"], created["file_type"]), ("Số liệu 1999", "Khác"))
        word = self._upload("cong-van.docx", b"PK docx")
        self.assertEqual(archive.add_document_from_file(self.file_a, word.file_url)["file_type"], "DOCX")

    def test_only_allowed_file_types_are_accepted_and_the_refused_file_is_removed(self):
        file = self._upload("virus.exe", b"MZ")
        with self.assertRaises(frappe.ValidationError):
            archive.add_document_from_file(self.file_a, file.file_url)
        self.assertFalse(frappe.db.exists("File", file.name))
        self.assertEqual(frappe.db.count("Archive Document", {"archival_file": self.file_a}), 1)

    def test_a_file_over_the_limit_is_refused(self):
        file = self._upload("big.pdf")
        with patch.object(archive, "UPLOAD_MAX_MB", 0):
            with self.assertRaises(frappe.ValidationError):
                archive.add_document_from_file(self.file_a, file.file_url)

    def test_somebody_elses_upload_cannot_be_claimed(self):
        file = self._upload("mine.pdf", user=OTHER)
        with self.assertRaises(frappe.PermissionError):
            archive.add_document_from_file(self.file_a, file.file_url)
        with self.assertRaises(frappe.PermissionError):
            archive.add_document_from_file(self.file_a, "/private/files/does-not-exist.pdf")

    def test_an_upload_can_only_be_used_once(self):
        file = self._upload()
        archive.add_document_from_file(self.file_a, file.file_url)
        with self.assertRaises(frappe.ValidationError):
            archive.add_document_from_file(self.file_b, file.file_url)

    def test_officers_and_readers_cannot_add_documents(self):
        file = self._upload(user=OFFICER)
        frappe.set_user(OFFICER)
        with self.assertRaises(frappe.PermissionError):
            archive.add_document_from_file(self.file_a, file.file_url)
        frappe.set_user(READER)
        with self.assertRaises(frappe.PermissionError):
            archive.add_document_from_file(self.file_a, file.file_url)

    def test_replacing_the_file_of_a_document(self):
        first = self._upload("cu.pdf")
        doc = archive.add_document_from_file(self.file_a, first.file_url)["name"]
        frappe.db.set_value("Archive Document", doc, {"checksum": "abc", "file_size_kb": 5})
        second = self._upload("moi.docx", b"PK new")
        result = archive.attach_file(doc, second.file_url)
        self.assertEqual(result["file_type"], "DOCX")
        self.assertEqual(frappe.db.get_value("Archive Document", doc, "file_attachment"), second.file_url)
        self.assertFalse(frappe.db.exists("File", first.name), "the replaced upload is deleted")
        self.assertEqual(frappe.db.get_value("File", second.name, "attached_to_name"), doc)

    def test_reindex_needs_a_file_and_queues_the_pipeline(self):
        with self.assertRaises(frappe.ValidationError):
            archive.reindex_document(self.doc_a)  # the seeded document has no file
        file = self._upload()
        doc = archive.add_document_from_file(self.file_a, file.file_url)["name"]
        with patch("document_manager.document_manager.services.file_processor.enqueue_extract_and_store") as enqueue:
            self.assertEqual(archive.reindex_document(doc)["status"], "Đang xử lý")
        enqueue.assert_called_once()
        self.assertEqual(frappe.db.get_value("Archive Document", doc, "search_index_status"), "Đang xử lý")

    def test_deleting_a_document_removes_it_from_the_count(self):
        file = self._upload()
        doc = archive.add_document_from_file(self.file_a, file.file_url)["name"]
        self.assertEqual(frappe.db.get_value("Archival File", self.file_a, "total_documents"), 2)
        frappe.set_user("Administrator")
        crud.delete("Archive Document", doc)
        self.assertEqual(frappe.db.get_value("Archival File", self.file_a, "total_documents"), 1)

    # ---- the generic screens for the cataloguing doctypes
    def test_cataloguing_doctypes_are_described_without_their_system_fields(self):
        info = meta.get_doctype_ui("Archive Document")
        names = {f["fieldname"] for f in info["fields"]}
        for hidden in ("content_text", "gridfs_file_id", "checksum", "file_attachment", "search_index_status"):
            self.assertNotIn(hidden, names)
        self.assertTrue({"document_title", "archival_file", "document_date", "author"} <= names)
        self.assertEqual([c["fieldname"] for c in info["columns"]][-2:], ["file_size_kb", "search_index_status"])
        self.assertTrue(all(c["label"] for c in info["columns"]))
        file_info = meta.get_doctype_ui("Archival File")
        self.assertIn("total_documents", {f["fieldname"] for f in file_info["fields"]})
        self.assertTrue(next(f for f in file_info["fields"] if f["fieldname"] == "total_documents")["read_only"])

    def test_author_suggests_the_values_of_the_matching_dictionary(self):
        self.assertEqual(next(f for f in meta.get_doctype_ui("Archive Document")["fields"] if f["fieldname"] == "author")["suggest"], "")
        crud.save("Dictionary Type", {"type_name": "Cơ quan ban hành", "is_hierarchical": 0})
        crud.save("Quick Entry Dictionary", {"dictionary_type": "Cơ quan ban hành", "entry_value": "Bộ Nội vụ"})
        author = next(f for f in meta.get_doctype_ui("Archive Document")["fields"] if f["fieldname"] == "author")
        self.assertEqual(author["suggest"], "Cơ quan ban hành")
        options = crud.link_search("Quick Entry Dictionary", "Nội", {"dictionary_type": "Cơ quan ban hành"})
        self.assertEqual([o["label"] for o in options], ["Bộ Nội vụ"])

    def test_catalogue_records_are_created_edited_and_protected_like_any_other(self):
        group = crud.save("Record Group", {"group_title": "AR Khối mới", "fonds": self.fonds})
        catalog = crud.save("Catalog", {"catalog_title": "AR Mục lục mới", "record_group": group["name"]})
        self.assertEqual(frappe.db.get_value("Catalog", catalog["name"], "fonds"), self.fonds)
        file = crud.save("Archival File", {"file_title": "AR Hồ sơ mới", "catalog": catalog["name"], "status": "Nháp"})
        self.assertEqual(frappe.db.get_value("Archival File", file["name"], "record_group"), group["name"])
        with self.assertRaises(frappe.LinkExistsError):  # a catalog with files cannot go
            frappe.set_user("Administrator")
            crud.delete("Catalog", catalog["name"])

    def test_the_two_new_print_formats_render(self):
        for doctype, name, fmt in (("Archival File", self.file_a, "Archival File Contents"),
                                   ("Archive Document", self.doc_a, "Archive Document Standard"),
                                   ("Archival File", self.file_a, "Archival File Standard")):
            html = frappe.get_print(doctype, name, print_format=fmt)
            self.assertIn(name, html, fmt)
        contents = frappe.get_print("Archival File", self.file_a, print_format="Archival File Contents")
        self.assertIn("RW Test Doc", contents)  # the documents of the file are listed

    def test_upload_limit_seed_is_idempotent_and_keeps_a_larger_value(self):
        frappe.db.set_single_value("System Settings", "max_file_size", 5)
        self.assertTrue(install.set_upload_limit())
        self.assertFalse(install.set_upload_limit())
        frappe.db.set_single_value("System Settings", "max_file_size", 500)
        self.assertFalse(install.set_upload_limit())
        self.assertEqual(frappe.utils.cint(frappe.db.get_single_value("System Settings", "max_file_size")), 500)

    def test_stored_files_are_read_as_exact_bytes_even_when_they_look_like_text(self):
        from document_manager.document_manager.services.file_processor import read_file_bytes as _read_frappe_file

        for filename, content in (("ascii.pdf", PDF), ("plain.docx", b"PK just ascii")):
            file = self._upload(filename, content)
            data = _read_frappe_file(file.file_url)
            self.assertIsInstance(data, bytes, filename)
            self.assertEqual(data, content, filename)
        self.assertIsNone(_read_frappe_file("/private/files/nothing-here.pdf"))

    def test_a_deadlock_on_the_document_number_is_retried(self):
        file = self._upload()
        real_insert = frappe.model.document.Document.insert
        calls = {"n": 0}

        def flaky_insert(doc, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise frappe.QueryDeadlockError("Record has changed since last read in table 'tabSeries'")
            return real_insert(doc, *args, **kwargs)

        # a real retry rolls the transaction back, which would take this test's own data with it
        with patch("time.sleep"), patch.object(frappe.db, "rollback"):
            with patch.object(frappe.model.document.Document, "insert", flaky_insert):
                created = archive.add_document_from_file(self.file_a, file.file_url)
        self.assertGreaterEqual(calls["n"], 2)  # the failed attempt and the retry (the audit log inserts too)
        self.assertEqual(frappe.db.count("Archive Document", {"archival_file": self.file_a}), 2)
        self.assertTrue(created["name"])

    def test_a_persistent_deadlock_is_reported(self):
        file = self._upload()

        def always(doc, *args, **kwargs):
            raise frappe.QueryDeadlockError("deadlock")

        with patch("time.sleep"), patch.object(frappe.db, "rollback"):
            with patch.object(frappe.model.document.Document, "insert", always):
                with self.assertRaises(frappe.QueryDeadlockError):
                    archive.add_document_from_file(self.file_a, file.file_url)

    def test_the_print_formats_download_as_pdf(self):
        for doctype, name, kind in (("Archival File", self.file_a, "contents"), ("Archival File", self.file_a, "standard"),
                                    ("Archive Document", self.doc_a, "standard")):
            archive.download_print_pdf(doctype, name, kind)
            self.assertEqual(frappe.local.response.type, "pdf")
            self.assertTrue(frappe.local.response.filecontent.startswith(b"%PDF"), f"{doctype} {kind}")
            self.assertEqual(frappe.local.response.filename, f"{name}.pdf")
        with self.assertRaises(frappe.DoesNotExistError):
            archive.download_print_pdf("Archival File", self.file_a, "no-such-kind")
        with self.assertRaises(frappe.DoesNotExistError):
            archive.download_print_pdf("User", "Administrator", "standard")  # only the archive formats
        frappe.set_user(READER)
        with self.assertRaises(frappe.PermissionError):
            archive.download_print_pdf("Archival File", self.file_a, "standard")

    def test_the_pdf_page_has_no_external_resources(self):
        page = (
            '<html><head><link rel="stylesheet" href="http://localhost:8888/a.css"><script src="/x.js"></script>'
            "<style>p{color:red}</style></head><body><p>nội dung</p><script>alert(1)</script></body></html>"
        )
        cleaned = archive._self_contained(page)
        self.assertNotIn("<link", cleaned)
        self.assertNotIn("<script", cleaned)
        self.assertIn("<style>p{color:red}</style>", cleaned)
        self.assertIn("nội dung", cleaned)

