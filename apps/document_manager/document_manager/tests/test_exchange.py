# -*- coding: utf-8 -*-
"""XML exchange (module 5): the format and its XSD, search and export, safe reading of uploads, analysis, import with a
choice of fields, dry runs, permissions, jobs.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_exchange
"""

import glob
import hashlib
import os
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from lxml import etree

from document_manager.document_manager.api import exchange
from document_manager.document_manager.services.exchange import exporter, importer, jobs, schema, xmlio
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _reader, _seed_archive, _user

TAG = frappe.generate_hash(length=5).lower()
ADMIN = f"ex.admin.{TAG}@example.com"
CATALOGER = f"ex.cataloger.{TAG}@example.com"
OFFICER = f"ex.officer.{TAG}@example.com"
READER = f"ex.reader.{TAG}@example.com"
OTHER_ADMIN = f"ex.admin2.{TAG}@example.com"
USERS = (ADMIN, CATALOGER, OFFICER, READER, OTHER_ADMIN)
FONDS_CODE = f"PX-{TAG}"


def xml_of(*nodes: str, level="Archival File") -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><ArchiveExchange version="1.0" level="{level}">{"".join(nodes)}</ArchiveExchange>'


def doc_node(title, number="", extra="", ref=False):
    mark = ' ref="true"' if ref else ""
    return (f"<ArchiveDocument{mark}><document_title>{title}</document_title><document_number>{number}</document_number>"
            f"{extra}</ArchiveDocument>")


def file_node(title, number="", children="", extra="", ref=False):
    mark = ' ref="true"' if ref else ""
    return f"<ArchivalFile{mark}><file_title>{title}</file_title><file_number>{number}</file_number>{extra}{children}</ArchivalFile>"


def catalog_node(title, number="", children="", ref=False):
    mark = ' ref="true"' if ref else ""
    return f"<Catalog{mark}><catalog_title>{title}</catalog_title><catalog_number>{number}</catalog_number>{children}</Catalog>"


def group_node(title, code="", children="", ref=False):
    mark = ' ref="true"' if ref else ""
    return f"<RecordGroup{mark}><group_title>{title}</group_title><group_code>{code}</group_code>{children}</RecordGroup>"


def fonds_node(name, code="", agency="", children="", ref=False, extra=""):
    mark = ' ref="true"' if ref else ""
    return (f"<Fonds{mark}><fonds_name>{name}</fonds_name><fonds_code>{code}</fonds_code>"
            f"<archival_agency>{agency}</archival_agency>{extra}{children}</Fonds>")


class TestExchange(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        for email, roles in ((ADMIN, ["Document Admin"]), (OTHER_ADMIN, ["Document Admin"]), (CATALOGER, ["Cataloger"]),
                             (OFFICER, ["Reading Room Officer"]), (READER, ["Reader"])):
            _user(email, roles, "Website User" if email == READER else "System User")
        cls.profile = _reader(READER, "EX Người đọc")
        cls._seeded = _seed_archive(2)
        cls.agency = _names(cls._seeded, "Archival Agency")[0]
        cls.fonds = _names(cls._seeded, "Fonds")[0]
        cls.group = _names(cls._seeded, "Record Group")[0]
        cls.catalog = _names(cls._seeded, "Catalog")[0]
        cls.files = _names(cls._seeded, "Archival File")
        cls.documents = _names(cls._seeded, "Archive Document")
        frappe.db.set_value("Fonds", cls.fonds, {"fonds_code": FONDS_CODE, "start_year": 1990, "end_year": 2005, "total_boxes": 4,
                                                 "description": "<p>Phông thử nghiệm</p>"})
        frappe.db.set_value("Record Group", cls.group, {"group_code": "K1", "start_year": 1991})
        frappe.db.set_value("Catalog", cls.catalog, {"catalog_number": "MLC-1"})
        frappe.db.set_value("Archival File", cls.files[0], {"file_number": "01", "total_pages": 12, "start_date": "1995-03-04",
                                                            "shelf_number": "G2", "status": "Đã hoàn thành"})
        frappe.db.set_value("Archival File", cls.files[1], {"file_number": "02", "total_pages": 3})
        frappe.db.set_value("Archive Document", cls.documents[0], {"document_number": "VB-1", "author": "Bộ Nội vụ",
                                                                   "document_date": "1995-03-05", "page_count": 7})
        frappe.db.set_value("Archive Document", cls.documents[1], {"document_number": "VB-2", "author": "UBND tỉnh"})
        frappe.db.commit()
        cls.created_files: list[str] = []

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for dt, name in cls._seeded:
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        frappe.delete_doc("Reader", cls.profile, force=True, ignore_permissions=True)
        for email in USERS:
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        # A worker commits and, when a run fails, rolls back to what it last committed. Inside one test transaction
        # that is simulated with savepoints: a "commit" sets one, a plain "rollback" goes back to the latest.
        original = frappe.db.rollback
        self.commits = 0
        self.last_commit = "ex_test"

        def commit():
            self.commits += 1
            self.last_commit = f"ex_commit_{self.commits}"
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
        self.touched: list[str] = []
        frappe.set_user(ADMIN)
        frappe.db.savepoint("ex_test")

    def tearDown(self):
        frappe.set_user("Administrator")
        self.original_rollback(save_point="ex_test")
        for stem in self.touched:  # a rolled-back File row leaves its file on the disk
            for path in glob.glob(frappe.get_site_path("private", "files", f"*{stem}*")):
                os.unlink(path)

    # ---- helpers
    def _export(self, level="Fonds", filters=None, fields=None, children=0, user=ADMIN) -> tuple[dict, bytes]:
        frappe.set_user(user)
        job = exchange.start_export(level, filters, fields, children)
        self.touched.append(job["name"])
        jobs.run(job["name"])
        done = exchange.get_job(job["name"])
        if not done["has_result"]:
            return done, b""
        exchange.download(job["name"])
        return done, frappe.local.response["filecontent"]

    def _upload(self, xml, name="import.xml", private=1, user=ADMIN) -> str:
        frappe.set_user(user)
        content = xml if isinstance(xml, bytes) else xml.encode("utf-8")
        doc = frappe.get_doc({"doctype": "File", "file_name": f"{TAG}-{name}", "is_private": private, "content": content}).insert()
        self.touched.append(os.path.basename(doc.file_url))
        return doc.file_url

    def _analyse(self, xml, **kw) -> dict:
        return exchange.analyze_import(self._upload(xml, **kw))

    def _import(self, xml, mode=None, fields=None, dry_run=0, create_masters=0) -> dict:
        analysed = self._analyse(xml)
        self.assertTrue(analysed["valid"], analysed["errors"])
        name = analysed["job"]["name"]
        exchange.start_import(name, mode, fields, dry_run, create_masters)
        jobs.run(name)
        return exchange.get_job(name)

    def _wipe_tree(self):
        for dt, name in self._seeded:
            if dt not in ("Archival Agency", "Confidentiality Level"):
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)

    def _fonds(self, code=FONDS_CODE):
        return frappe.db.get_value("Fonds", {"fonds_code": code}, "name")

    # ---- who may use it
    def test_only_administrators_exchange(self):
        for user in (READER, CATALOGER, OFFICER, "Guest"):
            frappe.set_user(user)
            for call in (lambda: exchange.capabilities(), lambda: exchange.preview_export("Fonds"),
                         lambda: exchange.start_export("Fonds"), lambda: exchange.analyze_import("/private/files/x.xml"),
                         lambda: exchange.start_import("XJ-0"), lambda: exchange.get_job("XJ-0"), lambda: exchange.list_jobs(),
                         lambda: exchange.download("XJ-0"), lambda: exchange.download_schema(),
                         lambda: exchange.cancel_job("XJ-0"), lambda: exchange.delete_job("XJ-0")):
                with self.assertRaises(frappe.PermissionError, msg=user):
                    call()
        frappe.set_user(ADMIN)
        self.assertEqual(len(exchange.capabilities()["levels"]), 5)

    # ---- the format
    def test_every_exchanged_field_is_a_real_writable_field_of_its_doctype(self):
        for level in schema.LEVELS:
            meta = frappe.get_meta(level.doctype)
            for name in level.fields:
                df = meta.get_field(name)
                self.assertIsNotNone(df, f"{level.doctype}.{name}")
                self.assertFalse(df.read_only, f"{level.doctype}.{name} is read-only")
                self.assertNotIn(name, ("content_text", "gridfs_file_id", "owner", "docstatus"))
            self.assertTrue(set(level.required) <= set(level.fields))
            self.assertTrue(set(schema.identity_fields(level)) <= set(level.fields))
            if level.parent_field:
                self.assertEqual(meta.get_field(level.parent_field).fieldtype, "Link")

    def test_the_xsd_compiles_and_accepts_a_well_formed_file(self):
        xsd = etree.fromstring(schema.build_xsd())
        etree.XMLSchema(xsd)
        text = schema.build_xsd().decode("utf-8")
        for level in schema.LEVELS:
            for name in level.fields:
                self.assertIn(f'name="{name}"', text)
        sample = xmlio.parse(xml_of(fonds_node("A", "A1", self.agency, group_node("G", "G1", catalog_node("C", "C1")))).encode())
        self.assertEqual(xmlio.validate(sample), [])

    def test_the_xsd_refuses_what_is_not_the_format(self):
        bad = {
            "a number that is not one": xml_of(fonds_node("A", "A1", self.agency, extra="<start_year>abc</start_year>")),
            "a date that is not one": xml_of(fonds_node("A", "A1", self.agency, group_node("G", "G1", catalog_node("C", "1", file_node("F", "1", extra="<start_date>05/03/1995</start_date>"))))),
            "a status outside the list": xml_of(fonds_node("A", "A1", self.agency, extra="<status>Tùy tiện</status>")),
            "an element the format does not have": xml_of(fonds_node("A", "A1", self.agency, extra="<owner>Administrator</owner>")),
            "a field the level does not have": xml_of(fonds_node("A", "A1", self.agency, extra="<docstatus>1</docstatus>")),
            "a title longer than a Data field": xml_of(fonds_node("x" * 200, "A1", self.agency)),
            "no version": '<ArchiveExchange><Fonds><fonds_name>x</fonds_name></Fonds></ArchiveExchange>',
        }
        for reason, xml in bad.items():
            result = self._analyse(xml)
            self.assertFalse(result["valid"], reason)
            self.assertIsNone(result["job"], reason)
            self.assertTrue(result["errors"][0].startswith("Dòng"), f"{reason}: {result['errors']}")

    # ---- reading uploads safely
    def test_hostile_files_are_refused_before_anything_is_read(self):
        entity = '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa">]><ArchiveExchange version="1.0">&a;</ArchiveExchange>'
        external = '<?xml version="1.0"?><!DOCTYPE d SYSTEM "file:///etc/passwd"><ArchiveExchange version="1.0"/>'
        utf16 = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE d [<!ENTITY a "b">]><ArchiveExchange version="1.0"/>'.encode("utf-16")
        for label, content in (("entity", entity), ("external dtd", external), ("utf-16 smuggling", utf16),
                               ("latin-1", '<?xml version="1.0" encoding="ISO-8859-1"?><ArchiveExchange version="1.0"/>'),
                               ("not xml", "đây không phải là XML"), ("empty", " "),
                               ("another root", '<?xml version="1.0"?><Other version="1.0"/>')):
            with self.assertRaises(frappe.ValidationError, msg=label):
                self._analyse(content)

    def test_only_your_own_private_xml_files_are_read(self):
        xml = xml_of(fonds_node("A", "A1", self.agency))
        with self.assertRaises(frappe.PermissionError):
            self._analyse(xml, private=0)  # a public file
        theirs = self._upload(xml, user=OTHER_ADMIN)
        frappe.set_user(ADMIN)
        with self.assertRaises(frappe.PermissionError):
            exchange.analyze_import(theirs)  # another administrator's
        with self.assertRaises(frappe.ValidationError):
            exchange.analyze_import(self._upload(xml, name="import.txt"))
        with self.assertRaises(frappe.DoesNotExistError):
            exchange.analyze_import("/private/files/khong-co.xml")

    def test_a_file_over_the_size_limit_is_refused(self):
        with patch.object(xmlio, "MAX_BYTES", 100):
            with self.assertRaises(frappe.ValidationError):
                self._analyse(xml_of(fonds_node("A", "A1", self.agency)))

    def test_analysis_reports_counts_fields_and_duplicates(self):
        xml = xml_of(fonds_node("A", "A1", self.agency, group_node("G", "G1", catalog_node("C", "C1", file_node(
            "F1", "1", doc_node("D1", "1") + doc_node("D2", "1", "<author>X</author>")) + file_node("F2", "1", ref=True)))))
        result = self._analyse(xml)
        self.assertTrue(result["valid"])
        job = result["job"]
        self.assertEqual(job["status"], "Đã tải lên")
        analysis = job["analysis"]
        self.assertEqual(analysis["total"], 7)
        self.assertEqual(analysis["counts"]["Archive Document"], {"nodes": 2, "ref": 0})
        self.assertEqual(analysis["counts"]["Archival File"], {"nodes": 2, "ref": 1})
        self.assertEqual(analysis["fields"]["Archive Document"]["author"], 1)
        self.assertEqual(job["checksum"], hashlib.sha256(xml.encode()).hexdigest())
        again = self._analyse(xml_of(fonds_node("A", "A1", self.agency, group_node("G", "G1", catalog_node("C", "C1", file_node("F", "1") + file_node("F", "1"))))))
        self.assertTrue(any("nhiều lần" in w for w in again["job"]["analysis"]["warnings"]))

    # ---- export
    def test_export_writes_the_tree_with_its_fields_and_nothing_else(self):
        done, content = self._export("Fonds", {"query": FONDS_CODE}, children=1)
        self.assertEqual(done["status"], "Hoàn thành", done["summary"])
        root = xmlio.parse(content)
        self.assertEqual(xmlio.validate(root), [])
        self.assertEqual((root.get("version"), root.get("level")), ("1.0", "Fonds"))
        fonds = root.find("Fonds")
        self.assertIsNone(fonds.get("ref"))
        self.assertEqual(fonds.findtext("fonds_code"), FONDS_CODE)
        self.assertEqual(fonds.findtext("archival_agency"), self.agency)
        self.assertEqual(fonds.findtext("start_year"), "1990")
        self.assertEqual(fonds.findtext("description"), "<p>Phông thử nghiệm</p>")
        files = fonds.findall("RecordGroup/Catalog/ArchivalFile")
        self.assertEqual([f.findtext("file_number") for f in files], ["01", "02"])
        self.assertEqual(files[0].findtext("total_pages"), "12")
        self.assertEqual(files[0].findtext("start_date"), "1995-03-04")
        document = files[0].find("ArchiveDocument")
        self.assertEqual((document.findtext("document_number"), document.findtext("author"), document.findtext("document_date")),
                         ("VB-1", "Bộ Nội vụ", "1995-03-05"))
        text = content.decode("utf-8")
        for forbidden in ("content_text", "gridfs", "<owner>", "<name>", "checksum", "file_attachment"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(done["result"]["Archive Document"]["exported"], 2)
        self.assertEqual(done["file_name"].endswith(".xml"), True)

    def test_a_lower_level_export_carries_its_ancestors_as_key_only_references(self):
        done, content = self._export("Archival File", {"query": "File 0", "fonds": self.fonds})
        root = xmlio.parse(content)
        fonds = root.find("Fonds")
        self.assertEqual(fonds.get("ref"), "true")
        self.assertEqual({c.tag for c in fonds}, {"fonds_name", "fonds_code", "archival_agency", "RecordGroup"})  # keys only
        group = fonds.find("RecordGroup")
        self.assertEqual(group.get("ref"), "true")
        catalog = group.find("Catalog")
        self.assertEqual(catalog.get("ref"), "true")
        file = catalog.find("ArchivalFile")
        self.assertIsNone(file.get("ref"))
        self.assertEqual(file.findtext("file_number"), "01")
        self.assertIsNone(file.find("ArchiveDocument"))  # children only when asked
        self.assertEqual(done["result"]["Fonds"], {"exported": 0, "ancestors": 1})

    def test_export_fields_are_chosen_per_level_and_the_key_fields_always_travel(self):
        fields = {"Fonds": ["start_year"], "Archive Document": ["author"]}
        done, content = self._export("Fonds", {"query": FONDS_CODE}, fields, children=1)
        root = xmlio.parse(content)
        fonds = root.find("Fonds")
        self.assertEqual({c.tag for c in fonds} - {"RecordGroup"}, {"fonds_name", "fonds_code", "start_year"})
        document = fonds.find("RecordGroup/Catalog/ArchivalFile/ArchiveDocument")
        self.assertEqual({c.tag for c in document}, {"document_title", "document_number", "author"})
        with self.assertRaises(frappe.ValidationError):
            exchange.start_export("Fonds", None, {"Fonds": ["owner"]})
        with self.assertRaises(frappe.ValidationError):
            exchange.start_export("Fonds", None, {"User": ["name"]})

    def test_the_search_that_selects_the_export_is_the_one_of_the_screens(self):
        done, content = self._export("Archive Document", {"author": "Nội vụ", "fonds": self.fonds})
        root = xmlio.parse(content)
        documents = root.findall(".//ArchiveDocument")
        self.assertEqual([d.findtext("document_number") for d in documents], ["VB-1"])
        done, content = self._export("Archive Document", {"date_from": "1995-01-01", "fonds": self.fonds})
        self.assertEqual([d.findtext("document_number") for d in xmlio.parse(content).findall(".//ArchiveDocument")], ["VB-1"])
        with self.assertRaises(frappe.ValidationError):  # nothing matches: said so up front, no empty file
            exchange.start_export("Archival File", {"start_date_from": "1996-01-01", "fonds": self.fonds})

    def test_unknown_filters_are_dropped_and_an_empty_search_is_refused(self):
        self.assertNotIn("owner", exporter.clean_params("Fonds", {"query": "x", "owner": "Administrator"}))
        with self.assertRaises(frappe.ValidationError):
            exchange.start_export("Fonds", {"query": "không có phông nào như vậy"})
        plan = exchange.preview_export("Archival File", {"fonds": self.fonds}, 1)
        self.assertEqual((plan["counts"]["Archival File"], plan["counts"]["Archive Document"], plan["ancestors"]["Fonds"]), (2, 2, 1))

    def test_an_export_beyond_the_limit_is_refused(self):
        with patch.object(xmlio, "MAX_NODES", 3):
            self.assertTrue(exchange.preview_export("Fonds", {"query": FONDS_CODE}, 1)["too_many"])
            with self.assertRaises(frappe.ValidationError):
                exchange.start_export("Fonds", {"query": FONDS_CODE}, None, 1)

    def test_export_reads_with_the_permissions_of_the_user(self):
        frappe.set_user("Administrator")
        frappe.db.set_value("Archival File", self.files[1], "status", "Nháp")
        plan = exchange.preview_export("Archival File", {"fonds": self.fonds})
        self.assertEqual(plan["counts"]["Archival File"], 2)  # staff see drafts

    def test_the_export_file_is_a_private_attachment_of_its_job_and_goes_with_it(self):
        done, _content = self._export("Fonds", {"query": FONDS_CODE})
        url = frappe.db.get_value("Data Exchange Job", done["name"], "result_file")
        self.assertTrue(url.startswith("/private/files/"))
        self.assertTrue(frappe.db.exists("File", {"file_url": url, "attached_to_name": done["name"]}))
        exchange.delete_job(done["name"])
        self.assertFalse(frappe.db.exists("Data Exchange Job", done["name"]))
        self.assertFalse(frappe.db.exists("File", {"file_url": url}))

    # ---- import
    def test_what_was_exported_comes_back_the_same(self):
        _done, content = self._export("Fonds", {"query": FONDS_CODE}, children=1)
        before = {dt: frappe.db.count(dt) for dt in ("Fonds", "Record Group", "Catalog", "Archival File", "Archive Document")}
        self._wipe_tree()
        self.assertIsNone(self._fonds())
        job = self._import(content)
        self.assertEqual(job["status"], "Hoàn thành", job["summary"])
        self.assertEqual({dt: job["result"]["levels"][dt]["created"] for dt in before},
                         {"Fonds": 1, "Record Group": 1, "Catalog": 1, "Archival File": 2, "Archive Document": 2})
        self.assertEqual({dt: frappe.db.count(dt) for dt in before}, before)
        fonds = frappe.get_doc("Fonds", self._fonds())
        self.assertEqual((fonds.fonds_name, fonds.archival_agency, fonds.start_year, fonds.total_boxes),
                         (frappe.db.get_value("Fonds", fonds.name, "fonds_name"), self.agency, 1990, 4))
        self.assertEqual(fonds.description, "<p>Phông thử nghiệm</p>")
        file = frappe.get_doc("Archival File", {"file_number": "01", "fonds": fonds.name})
        self.assertEqual((file.total_pages, str(file.start_date), file.shelf_number, file.status), (12, "1995-03-04", "G2", "Đã hoàn thành"))
        document = frappe.get_doc("Archive Document", {"document_number": "VB-1", "archival_file": file.name})
        self.assertEqual((document.author, str(document.document_date), document.page_count), ("Bộ Nội vụ", "1995-03-05", 7))
        self.assertEqual((document.fonds, document.catalog), (fonds.name, file.catalog))  # the inherited links are filled

    def test_importing_the_same_file_again_adds_nothing(self):
        _done, content = self._export("Fonds", {"query": FONDS_CODE}, children=1)
        total = {dt: frappe.db.count(dt) for dt in ("Fonds", "Archival File", "Archive Document")}
        job = self._import(content)  # everything is already there
        self.assertEqual(job["created"], 0)
        self.assertEqual(job["result"]["levels"]["Archive Document"]["exists"], 2)
        self.assertEqual({dt: frappe.db.count(dt) for dt in total}, total)
        again = self._import(content, mode=importer.MODE_UPSERT)
        self.assertEqual((again["created"], again["updated"], again["failed"]), (0, 0, 0))
        self.assertEqual(again["result"]["levels"]["Archival File"]["unchanged"], 2)

    def test_update_mode_changes_only_the_chosen_fields_of_matching_records(self):
        changed = xml_of(fonds_node("Tên phông mới", FONDS_CODE, self.agency, group_node("Khối", "K1", catalog_node(
            "Mục lục", "MLC-1", file_node("Hồ sơ mới", "01", extra="<total_pages>99</total_pages><shelf_number>Z9</shelf_number>")))))
        job = self._import(changed, mode=importer.MODE_UPSERT, fields={"Fonds": ["fonds_name"], "Archival File": ["total_pages"]})
        self.assertEqual(job["status"], "Hoàn thành", job["summary"])
        self.assertEqual(frappe.db.get_value("Fonds", self.fonds, "fonds_name"), "Tên phông mới")
        file = frappe.db.get_value("Archival File", self.files[0], ["file_title", "total_pages", "shelf_number"], as_dict=True)
        self.assertEqual((file.total_pages, file.shelf_number), (99, "G2"))  # the shelf was not chosen
        self.assertEqual(file.file_title, "RW Test File 0")  # nor was its title
        self.assertEqual(job["result"]["levels"]["Fonds"]["updated"], 1)
        self.assertEqual(job["result"]["levels"]["Archival File"]["updated"], 1)

    def test_created_records_get_only_the_chosen_fields_and_always_their_required_ones(self):
        self._wipe_tree()
        xml = xml_of(fonds_node("Phông mới", "NEW-1", self.agency, group_node("Khối", "G1", catalog_node("Mục lục", "M1", file_node(
            "Hồ sơ", "H1", doc_node("Văn bản", "V1", "<author>Tác giả</author><description>Mô tả</description>"))))))
        job = self._import(xml, fields={"Fonds": [], "Archive Document": ["author"]})
        self.assertEqual(job["status"], "Hoàn thành", job["summary"])
        document = frappe.get_doc("Archive Document", {"document_number": "V1"})
        self.assertEqual((document.author, document.description or ""), ("Tác giả", ""))  # the description was not chosen
        self.assertEqual(frappe.db.get_value("Fonds", {"fonds_code": "NEW-1"}, "archival_agency"), self.agency)

    def test_a_dry_run_does_everything_but_write(self):
        self._wipe_tree()
        xml = xml_of(fonds_node("Phông thử", "DRY-1", self.agency, group_node("Khối", "G1", catalog_node("Mục lục", "M1", file_node(
            "Hồ sơ", "H1", doc_node("Văn bản", "V1"))))), fonds_node("Phông lỗi", "DRY-2", "Cơ quan không tồn tại"))
        counts = {dt: frappe.db.count(dt) for dt in ("Fonds", "Record Group", "Catalog", "Archival File", "Archive Document")}
        job = self._import(xml, dry_run=1)
        self.assertEqual(job["status"], "Hoàn thành có lỗi")
        self.assertEqual((job["dry_run"], job["created"], job["failed"]), (1, 5, 1))
        self.assertIn("Chạy thử", job["summary"])
        self.assertEqual({dt: frappe.db.count(dt) for dt in counts}, counts)
        self.assertFalse(frappe.flags.in_import)
        self.assertFalse(frappe.db.after_commit._observers if hasattr(frappe.db.after_commit, "_observers") else False)
        real = self._import(xml)
        self.assertEqual((real["dry_run"], real["created"], real["failed"]), (0, 5, 1))
        self.assertEqual(frappe.db.count("Archive Document"), counts["Archive Document"] + 1)

    def test_a_failing_record_is_logged_and_its_subtree_skipped_while_the_rest_goes_on(self):
        self._wipe_tree()
        xml = xml_of(
            fonds_node("Phông hỏng", "BAD-1", "Cơ quan không có", group_node("Khối", "G1", catalog_node("Mục lục", "M1"))),
            fonds_node("Phông tốt", "GOOD-1", self.agency, group_node("Khối", "G1", catalog_node("Mục lục", "M1", file_node(
                "Hồ sơ hỏng", "H1", "", "<confidentiality_level>Mức không có</confidentiality_level>", ) + file_node("Hồ sơ tốt", "H2")))))
        job = self._import(xml)
        self.assertEqual(job["status"], "Hoàn thành có lỗi")
        self.assertIsNone(self._fonds("BAD-1"))
        self.assertIsNotNone(self._fonds("GOOD-1"))
        self.assertEqual(frappe.db.count("Archival File", {"file_number": "H2"}), 1)
        self.assertEqual(frappe.db.count("Archival File", {"file_number": "H1"}), 0)
        levels = job["result"]["levels"]
        self.assertEqual((levels["Fonds"]["created"], levels["Fonds"]["failed"], levels["Archival File"]["failed"]), (1, 1, 1))
        messages = [r["message"] for r in job["rows"]]
        self.assertTrue(any("bỏ qua 2 bản ghi con" in m for m in messages), messages)
        self.assertTrue(all(r["severity"] == "Lỗi" and r["path"] for r in job["rows"]), job["rows"])
        self.assertTrue(any("BAD-1" in r["path"] for r in job["rows"]), job["rows"])

    def test_ancestors_of_a_lower_level_file_are_created_when_missing(self):
        _done, content = self._export("Archival File", {"fonds": self.fonds, "query": "File 0"}, children=1)
        self._wipe_tree()
        job = self._import(content)
        self.assertEqual(job["status"], "Hoàn thành", job["summary"])
        levels = job["result"]["levels"]
        self.assertEqual((levels["Fonds"]["refs"], levels["Fonds"]["created"]), (1, 1))  # a reference that had to be made counts as both
        fonds = self._fonds()
        self.assertIsNotNone(fonds)  # created from the key fields of its reference
        self.assertEqual(frappe.db.get_value("Fonds", fonds, "archival_agency"), self.agency)
        self.assertEqual(frappe.db.get_value("Fonds", fonds, "start_year"), 0)  # a reference carries no more than its keys
        self.assertEqual(frappe.db.count("Archival File", {"fonds": fonds}), 1)

    def test_a_missing_catalogue_value_is_an_error_unless_the_import_may_create_it(self):
        self._wipe_tree()
        xml = xml_of(fonds_node("Phông A", "MA-1", f"Cơ quan mới {TAG}", group_node("Khối", "G1", catalog_node("Mục lục", "M1", file_node(
            "Hồ sơ", "H1", "", f"<document_type_category>Loại mới {TAG}</document_type_category>")))))
        refused = self._import(xml)
        self.assertEqual(refused["status"], "Hoàn thành có lỗi")
        self.assertIsNone(self._fonds("MA-1"))
        allowed = self._import(xml, create_masters=1)
        self.assertEqual(allowed["status"], "Hoàn thành", allowed["summary"])
        self.assertEqual(allowed["result"]["masters"], 2)
        self.assertTrue(frappe.db.exists("Archival Agency", f"Cơ quan mới {TAG}"))
        self.assertTrue(frappe.db.exists("Document Type Category", f"Loại mới {TAG}"))
        invented = xml_of(fonds_node("Phông B", "MB-1", self.agency, group_node("Khối", "G1", catalog_node("Mục lục", "M1", file_node(
            "Hồ sơ", "H1", "", "<confidentiality_level>Tối mật tự tạo</confidentiality_level>")))))
        job = self._import(invented, create_masters=1)
        self.assertEqual(job["status"], "Hoàn thành có lỗi")  # a security level is never made up
        self.assertFalse(frappe.db.exists("Confidentiality Level", "Tối mật tự tạo"))

    def test_two_records_with_the_same_key_are_not_guessed_between(self):
        frappe.get_doc({"doctype": "Catalog", "catalog_title": "Mục lục khác", "catalog_number": "MLC-1", "record_group": self.group}).insert()
        xml = xml_of(fonds_node("A", FONDS_CODE, self.agency, group_node("Khối", "K1", catalog_node("Mục lục", "MLC-1", file_node("Hồ sơ", "77")))))
        job = self._import(xml)
        self.assertEqual(job["status"], "Hoàn thành có lỗi")
        self.assertIn("trùng khóa", job["rows"][0]["message"])
        self.assertEqual(frappe.db.count("Archival File", {"file_number": "77"}), 0)

    def test_import_matches_a_record_without_a_code_by_its_title(self):
        title = frappe.db.get_value("Fonds", self.fonds, "fonds_name")
        frappe.db.set_value("Fonds", self.fonds, "fonds_code", "")
        xml = xml_of(fonds_node(title, "NEW-CODE", self.agency))
        job = self._import(xml, mode=importer.MODE_UPSERT)
        self.assertEqual(job["status"], "Hoàn thành", job["summary"])
        self.assertEqual(job["result"]["levels"]["Fonds"]["updated"], 1)
        self.assertEqual(frappe.db.get_value("Fonds", self.fonds, "fonds_code"), "NEW-CODE")

    def test_html_in_imported_text_is_cleaned(self):
        self._wipe_tree()
        xml = xml_of(fonds_node("Phông XSS", "XSS-1", self.agency, extra="<description>&lt;p&gt;an toàn&lt;/p&gt;&lt;script&gt;alert(1)&lt;/script&gt;</description>"))
        self._import(xml)
        description = frappe.db.get_value("Fonds", {"fonds_code": "XSS-1"}, "description")
        self.assertIn("an toàn", description)
        self.assertNotIn("<script", description)

    def test_the_import_runs_with_the_permissions_of_whoever_started_it(self):
        self._wipe_tree()
        xml = xml_of(fonds_node("Phông cấm", "NOPE-1", self.agency))
        analysed = self._analyse(xml)
        job = frappe.get_doc("Data Exchange Job", analysed["job"]["name"])
        job.db_set({"options_json": '{"mode": "Chỉ thêm mới", "dry_run": 0}', "status": jobs.RUNNING})
        frappe.set_user(OFFICER)  # may read the archive, not write it
        importer.run_import(jobs.get(job.name))
        self.assertIsNone(self._fonds("NOPE-1"))
        done = frappe.get_doc("Data Exchange Job", job.name)
        self.assertEqual((done.status, done.failed), ("Hoàn thành có lỗi", 1))
        self.assertTrue(any(w in done.rows[0].message.lower() for w in ("quyền", "permission")), done.rows[0].message)
        self.assertNotIn("traceback", done.rows[0].message.lower())

    def test_an_unknown_element_cannot_set_a_system_field_even_if_the_schema_is_bypassed(self):
        self._wipe_tree()
        xml = xml_of(fonds_node("Phông owner", "OWN-1", self.agency, extra="<owner>Administrator</owner><docstatus>1</docstatus>"))
        root = xmlio.parse(xml.encode())
        values = xmlio.values_of(root.find("Fonds"), schema.LEVELS[0])
        self.assertNotIn("owner", values)
        self.assertNotIn("docstatus", values)

    # ---- jobs
    def test_jobs_report_progress_and_history(self):
        done, _c = self._export("Fonds", {"query": FONDS_CODE})
        self.assertEqual((done["status"], done["direction"], done["owner"]), ("Hoàn thành", "Xuất", ADMIN))
        self.assertTrue(done["finished_on"] and done["started_on"])
        listing = exchange.list_jobs("Xuất")
        self.assertIn(done["name"], [j["name"] for j in listing["data"]])
        self.assertEqual(exchange.list_jobs("Nhập")["total"], frappe.db.count("Data Exchange Job", {"direction": "Nhập"}))
        self.assertTrue(frappe.db.exists("Notification Log", {"for_user": ADMIN, "document_name": done["name"]}))
        self.assertTrue(frappe.db.exists("Business Activity Log", {"reference_name": done["name"], "activity_type": "Xuất XML"}))

    def test_the_progress_of_a_running_job_comes_from_the_run(self):
        job = exchange.start_export("Fonds", {"query": FONDS_CODE})
        doc = jobs.get(job["name"])
        doc.db_set("status", jobs.RUNNING)
        jobs.set_progress(doc.name, processed=40, total=80, created=5, phase="Đang nhập")
        shown = exchange.get_job(doc.name)
        self.assertEqual((shown["processed"], shown["total"], shown["percent"], shown["created"], shown["phase"]), (40, 80, 50, 5, "Đang nhập"))
        jobs.clear_progress(doc.name)

    def test_a_queued_job_can_be_cancelled_and_a_running_one_is_asked_to_stop(self):
        job = exchange.start_export("Fonds", {"query": FONDS_CODE})
        self.assertEqual(exchange.cancel_job(job["name"])["status"], "Đã hủy")
        jobs.run(job["name"])  # the worker finds it cancelled and does nothing
        self.assertEqual(exchange.get_job(job["name"])["status"], "Đã hủy")
        running = jobs.get(exchange.start_export("Fonds", {"query": FONDS_CODE})["name"])
        running.db_set("status", jobs.RUNNING)
        exchange.cancel_job(running.name)
        with self.assertRaises(jobs.Cancelled):
            jobs.check_cancel(running.name)
        jobs.clear_progress(running.name)
        with self.assertRaises(frappe.ValidationError):
            exchange.cancel_job(job["name"])  # no longer running

    def test_a_cancelled_import_leaves_nothing_behind(self):
        self._wipe_tree()
        xml = xml_of(*[fonds_node(f"Phông {i}", f"CX-{i}", self.agency) for i in range(3)])
        analysed = self._analyse(xml)
        name = analysed["job"]["name"]
        exchange.start_import(name)
        jobs.request_cancel(name)
        with patch.object(importer, "PROGRESS_EVERY", 1):
            jobs.run(name)
        self.assertEqual(exchange.get_job(name)["status"], "Đã hủy")
        self.assertEqual(frappe.db.count("Fonds", {"fonds_code": ["like", "CX-%"]}), 0)

    def test_import_start_is_checked(self):
        analysed = self._analyse(xml_of(fonds_node("Phông", "ST-1", self.agency)))
        name = analysed["job"]["name"]
        with self.assertRaises(frappe.ValidationError):
            exchange.start_import(name, mode="Ghi đè tất cả")
        with self.assertRaises(frappe.ValidationError):
            exchange.start_import(name, fields={"Fonds": ["owner"]})
        export = exchange.start_export("Fonds", {"query": FONDS_CODE})
        with self.assertRaises(frappe.ValidationError):
            exchange.start_import(export["name"])  # an export is not an upload
        exchange.start_import(name)
        with self.assertRaises(frappe.ValidationError):
            exchange.start_import(name)  # already queued
        other = self._analyse(xml_of(fonds_node("Phông", "ST-2", self.agency)))["job"]["name"]
        jobs.get(name).db_set("status", jobs.RUNNING)
        with self.assertRaises(frappe.ValidationError):
            exchange.start_import(other)  # one real import at a time
        self.assertEqual(exchange.start_import(other, dry_run=1)["dry_run"], 1)  # but a dry run is harmless

    def test_downloads(self):
        done, content = self._export("Fonds", {"query": FONDS_CODE})
        self.assertEqual(frappe.local.response["type"], "download")
        self.assertEqual(frappe.local.response["filename"], f"{done['name']}.xml")
        self.assertTrue(content.startswith(b"<?xml"))
        upload = self._analyse(xml_of(fonds_node("A", "A1", self.agency)))["job"]
        with self.assertRaises(frappe.DoesNotExistError):
            exchange.download(upload["name"])
        exchange.download_schema()
        self.assertEqual(frappe.local.response["filename"], "archive-exchange.xsd")
        etree.XMLSchema(etree.fromstring(frappe.local.response["filecontent"]))

    def test_the_log_of_a_run_is_capped(self):
        self._wipe_tree()
        xml = xml_of(*[fonds_node(f"Phông {i}", f"LG-{i}", "Cơ quan không có") for i in range(6)])
        with patch.object(jobs, "MAX_LOG_ROWS", 3):
            job = self._import(xml)
        self.assertEqual((job["failed"], job["rows_total"]), (6, 3))

    def test_the_old_open_endpoints_are_gone(self):
        with self.assertRaises(ImportError):
            __import__("document_manager.document_manager.services.xml_handler")
