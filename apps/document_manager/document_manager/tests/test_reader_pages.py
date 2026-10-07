# -*- coding: utf-8 -*-
"""The pages of the reader site, rendered the way Frappe renders them (route rules, redirects, page
controllers and Jinja templates together): who gets what, what is escaped, where old links go.

Run: bench --site <site> run-tests --app document_manager --module document_manager.tests.test_reader_pages
"""

from unittest.mock import patch
from urllib.parse import parse_qsl, urlsplit

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.routing import Map, Rule
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from document_manager.document_manager.api import basket as basket_api
from document_manager.document_manager.api import requests as request_api
from document_manager.document_manager.services import public_site, registration
from document_manager.document_manager.setup import install
from document_manager.tests.test_request_workflow import _names, _reader, _seed_archive, _user
from document_manager.www import _reader_ui

TAG = frappe.generate_hash(length=5).lower()
READER = f"rp.reader.{TAG}@example.com"
OTHER = f"rp.other.{TAG}@example.com"
NO_PROFILE = f"rp.noprofile.{TAG}@example.com"
OFFICER = f"rp.officer.{TAG}@example.com"
STAFF_READER = f"rp.staffreader.{TAG}@example.com"
SECRET_LEVEL = f"RP Secret {TAG}"
XSS = "<script>alert(1)</script>"


def render(path: str, user: str = "Guest"):
    """(status, body) of a page; for a redirect, (status, target)."""
    frappe.set_user(user)
    parts = urlsplit(path)
    environ = EnvironBuilder(path=parts.path, query_string=parts.query, base_url="http://localhost").get_environ()
    frappe.local.request = Request(environ)
    frappe.local.form_dict = frappe._dict(parse_qsl(parts.query))
    frappe.local.flags.redirect_location = None
    with patch.object(_reader_ui, "csrf_token", return_value="test-csrf"):
        try:
            _endpoint, renderer = __import__("frappe.website.path_resolver", fromlist=["PathResolver"]).PathResolver(
                parts.path.strip("/")).resolve()
            response = renderer.render()
        except frappe.Redirect as redirect:
            return redirect.http_status_code or 302, frappe.local.flags.redirect_location
        except frappe.DoesNotExistError:
            return 404, ""
    location = response.headers.get("Location")
    if location:
        return response.status_code, location
    return response.status_code, response.get_data(as_text=True)


class TestReaderPages(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        install.seed_all()
        _user(READER, ["Reader"], "Website User")
        _user(OTHER, ["Reader"], "Website User")
        _user(NO_PROFILE, ["Reader"], "Website User")
        _user(OFFICER, ["Reading Room Officer"], "System User")
        _user(STAFF_READER, ["Reader", "Reading Room Officer"], "System User")
        cls.profile = _reader(READER, "RP Reader")
        cls.other_profile = _reader(OTHER, "RP Other")
        cls.staff_profile = _reader(STAFF_READER, "RP Staff Reader")
        if not frappe.db.exists("Confidentiality Level", SECRET_LEVEL):
            frappe.get_doc({"doctype": "Confidentiality Level", "level_name": SECRET_LEVEL, "priority": 5}).insert(ignore_permissions=True)
        cls._seeded = _seed_archive()
        cls.file_ok, cls.file_secret = _names(cls._seeded, "Archival File")
        secret = frappe.get_doc("Archival File", cls.file_secret)
        secret.confidentiality_level = SECRET_LEVEL
        secret.save(ignore_permissions=True)
        cls.doc_ok = frappe.get_all("Archive Document", filters={"archival_file": cls.file_ok}, pluck="name")[0]
        cls.doc_secret = frappe.get_all("Archive Document", filters={"archival_file": cls.file_secret}, pluck="name")[0]
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        for dt in ("Usage Request", "Copy Request", "Reader Feedback"):
            for name in frappe.get_all(dt, filters={"reader": ["in", [cls.profile, cls.other_profile, cls.staff_profile]]}, pluck="name"):
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.flags.ignore_permissions = True
                    doc.cancel()
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for dt, name in cls._seeded:
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for profile in (cls.profile, cls.other_profile, cls.staff_profile):
            frappe.delete_doc("Reader", profile, force=True, ignore_permissions=True)
        frappe.delete_doc("Confidentiality Level", SECRET_LEVEL, force=True, ignore_permissions=True)
        for email in (READER, OTHER, NO_PROFILE, OFFICER, STAFF_READER):
            frappe.db.delete("Notification Log", {"for_user": email})
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)
        frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        commit = patch.object(frappe.db, "commit")
        commit.start()
        self.addCleanup(commit.stop)
        frappe.set_user("Administrator")
        frappe.db.savepoint("rp_test")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="rp_test")

    # ---- helpers
    def _sent_slip(self, kind="usage", purpose="Nghiên cứu"):
        frappe.set_user(READER)
        added = basket_api.add_to_basket("file", self.file_ok, kind)
        request_api.save_request("Usage Request" if kind == "usage" else "Copy Request",
                                 frappe.as_json({"purpose": purpose}), name=added["request"], submit=1)
        frappe.set_user("Administrator")
        return added["request"]

    def _draft(self, kind="usage"):
        frappe.set_user(READER)
        name = basket_api.add_to_basket("file", self.file_ok, kind)["request"]
        frappe.set_user("Administrator")
        return name

    def _org(self, **values):
        info = frappe._dict({"org_name": "Trung tâm RP", "leaders": [], "hide_leaders": 0, "hide_structure": 0, **values})
        real = frappe.get_cached_doc
        return patch.object(public_site.frappe, "get_cached_doc",
                            side_effect=lambda doctype, *a, **k: info if doctype == "Organization Info" else real(doctype, *a, **k))

    # ---- routing
    def test_every_website_route_rule_compiles(self):
        # a rule werkzeug cannot parse (a bad converter) would turn every page of the site into a 500
        Map([Rule(rule["from_route"], endpoint=rule["to_route"]) for rule in frappe.get_hooks("website_route_rules")])

    def test_asset_version_changes_with_the_assets(self):
        self.assertTrue(_reader_ui.asset_version().isdigit())

    # ---- public pages
    def test_public_pages_open_for_guests(self):
        with self._org(org_name="Trung tâm RP"):
            for path, marker in (("gioi-thieu", "Giới thiệu đơn vị"), ("lanh-dao", "Ban lãnh đạo"), ("co-cau", "Cơ cấu tổ chức"),
                                 ("lien-he", "Liên hệ"), ("huong-dan", "Hướng dẫn khai thác tài liệu"), ("", "Giới thiệu đơn vị")):
                status, body = render(f"/{path}")
                self.assertEqual(status, 200, path)
                self.assertIn(marker, body, path)
                self.assertIn("Trung tâm RP", body, path)
                self.assertIn('href="/dang-nhap"', body, path)
                self.assertNotIn("frappe.ready", body, path)  # the page is its own document, not Frappe's website template

    def test_active_section_is_marked_in_the_navigation(self):
        with self._org():
            _status, body = render("/lien-he")
        self.assertIn('href="/lien-he" aria-current="page"', body)
        self.assertNotIn('href="/gioi-thieu" aria-current="page"', body)

    def test_pages_the_unit_switched_off_are_not_found(self):
        with self._org(hide_leaders=1, hide_structure=1):
            self.assertEqual(render("/lanh-dao")[0], 404)
            self.assertEqual(render("/co-cau")[0], 404)
            self.assertEqual(render("/gioi-thieu")[0], 200)
            self.assertNotIn('href="/lanh-dao"', render("/gioi-thieu")[1])

    def test_hidden_leaders_and_empty_profile(self):
        leaders = [frappe._dict(idx=1, full_name="Người Hiện", position="Giám đốc", display_order=1, is_visible=1, photo="", bio=""),
                   frappe._dict(idx=2, full_name="Người Ẩn", position="X", display_order=2, is_visible=0, photo="", bio="")]
        with self._org(leaders=leaders):
            body = render("/lanh-dao")[1]
        self.assertIn("Người Hiện", body)
        self.assertNotIn("Người Ẩn", body)
        with self._org():
            self.assertIn("Chưa có thông tin lãnh đạo", render("/lanh-dao")[1])

    def test_text_entered_by_staff_is_escaped_everywhere(self):
        leaders = [frappe._dict(idx=1, full_name=XSS, position=XSS, display_order=1, is_visible=1, photo="", bio=XSS)]
        unit = frappe.get_doc({"doctype": "Organization Unit", "unit_name": f"Phòng X {TAG}", "description": XSS,
                               "head_name": XSS, "is_visible": 1}).insert(ignore_permissions=True)
        with self._org(org_name=XSS, address=XSS, tagline=XSS, leaders=leaders, introduction=f"<p>Chào</p>{XSS}",
                       reading_room_hours=XSS, reader_guide=XSS, leadership_info=XSS, org_structure=XSS):
            for path in ("/gioi-thieu", "/lanh-dao", "/co-cau", "/lien-he", "/huong-dan", "/dang-nhap"):
                body = render(path)[1]
                self.assertNotIn("<script>alert(1)", body, path)
                self.assertIn("&lt;script&gt;" if path != "/dang-nhap" else "Đăng nhập", body, path)
        self.assertIsNotNone(unit.name)

    def test_rich_text_of_the_profile_is_sanitised_not_escaped(self):
        with self._org(introduction="<p>Xin <strong>chào</strong></p><script>alert(1)</script>"):
            body = render("/gioi-thieu")[1]
        self.assertIn("<strong>chào</strong>", body)
        self.assertNotIn("<script>alert(1)", body)

    # ---- sign in / sign up
    def test_sign_in_page_returns_only_to_this_site(self):
        status, body = render("/dang-nhap?redirect-to=/portal/phieu/UR-1")
        self.assertEqual(status, 200)
        self.assertIn("&#34;/portal/phieu/UR-1&#34;", body)
        for bad in ("https://evil.example", "//evil.example", "/\\evil.example"):
            self.assertIn("redirect: &#34;&#34;", render("/dang-nhap?redirect-to=" + bad)[1], bad)

    def test_people_who_are_already_in_skip_the_sign_in_page(self):
        self.assertEqual(render("/dang-nhap", READER), (302, "/portal"))
        self.assertEqual(render("/dang-nhap", OFFICER), (302, "/dashboard"))
        self.assertEqual(render("/dang-ky", READER)[0], 302)
        self.assertEqual(render("/quen-mat-khau", READER)[0], 302)

    def test_sign_up_page_follows_the_site_setting(self):
        with patch.object(registration, "registration_settings", return_value=frappe._dict(allow_self_registration=1, require_approval=1)):
            body = render("/dang-ky")[1]
        self.assertIn("registerForm(", body)
        self.assertIn("Cán bộ sẽ xem xét yêu cầu", body)
        with patch("document_manager.www.dang_ky.registration_settings",
                   return_value=frappe._dict(allow_self_registration=0, require_approval=1)):
            body = render("/dang-ky")[1]
        self.assertNotIn("registerForm(", body)
        self.assertIn("chưa mở đăng ký trực tuyến", body)
        with patch("document_manager.www.dang_ky.registration_settings",
                   return_value=frappe._dict(allow_self_registration=1, require_approval=0)):
            self.assertIn("Tài khoản được tạo ngay", render("/dang-ky")[1])

    def test_set_password_page_knows_good_bad_and_expired_links(self):
        self.assertIn("không hợp lệ hoặc đã được sử dụng", render("/dat-mat-khau?key=bogus")[1])
        self.assertIn("không hợp lệ hoặc đã được sử dụng", render("/dat-mat-khau")[1])
        path = registration.issue_password_link(READER)
        status, body = render(path)
        self.assertEqual(status, 200)
        self.assertIn("setPasswordForm", body)
        self.assertIn(READER, body)
        self.assertIn("noindex", body)  # a link page is never indexed
        frappe.db.set_value("User", READER, "last_reset_password_key_generated_on", frappe.utils.add_days(frappe.utils.now_datetime(), -30))
        real = frappe.get_system_settings
        with patch("frappe.get_system_settings",
                   side_effect=lambda key=None, *a, **k: 3600 if key == "reset_password_link_expiry_duration" else real(key, *a, **k)):
            self.assertIn("đã hết hạn", render(path)[1])

    def test_set_password_link_refuses_staff(self):
        with self.assertRaises(frappe.PermissionError):
            registration.issue_password_link(OFFICER)

    # ---- the reader area is for signed-in people
    def test_guests_are_sent_to_sign_in_and_come_back(self):
        for path in ("/portal", "/portal/phieu", "/portal/sao-chep", "/portal/gop-y", "/portal/tai-khoan", "/portal/thong-bao",
                     f"/portal/ho-so/{self.file_ok}", f"/portal/van-ban/{self.doc_ok}"):
            status, location = render(path)
            self.assertEqual(status, 302, path)  # session-based: never a cacheable 301
            self.assertTrue(location.startswith("/dang-nhap?redirect-to="), f"{path} -> {location}")
        self.assertEqual(render("/portal/phieu?status=Nh%C3%A1p")[1], "/dang-nhap?redirect-to=/portal/phieu%3Fstatus%3DNh%25C3%25A1p")

    def test_user_without_reader_or_staff_role_is_refused(self):
        _user(f"rp.nobody.{TAG}@example.com", [], "Website User")
        with self.assertRaises(frappe.PermissionError):
            render("/portal", f"rp.nobody.{TAG}@example.com")

    def test_search_page_for_reader(self):
        status, body = render("/portal", READER)
        self.assertEqual(status, 200)
        self.assertIn("searchPage(", body)
        self.assertIn("Tìm nâng cao", body)
        self.assertIn('"usage": true', body.replace("&#34;", '"'))
        self.assertIn("Thường", body)  # the level the reader may filter by
        self.assertNotIn(SECRET_LEVEL, body)  # a level above the reader's clearance is not offered
        self.assertIn('"csrf": "test-csrf"', body)
        self.assertIn("noindex", body)

    def test_search_page_tells_staff_and_users_without_a_profile(self):
        self.assertIn("với tư cách cán bộ", render("/portal", OFFICER)[1])
        self.assertIn("chưa có hồ sơ độc giả đang hoạt động", render("/portal", NO_PROFILE)[1])

    def test_search_page_for_a_group_that_may_not_search(self):
        frappe.get_doc({"doctype": "Reader Group", "group_name": f"RP No search {TAG}", "is_active": 1, "can_search": 0,
                        "max_confidentiality_priority": 1}).insert(ignore_permissions=True)
        frappe.db.set_value("Reader", self.other_profile, "reader_group", f"RP No search {TAG}")
        self.assertIn("không được phép tìm kiếm", render("/portal", OTHER)[1])

    # ---- hồ sơ and văn bản
    def test_file_page_shows_the_file_and_its_documents(self):
        status, body = render(f"/portal/ho-so/{self.file_ok}", READER)
        self.assertEqual(status, 200)
        self.assertIn("RW Test File 0", body)
        self.assertIn(f"/portal/van-ban/{self.doc_ok}", body)
        self.assertIn("Thêm vào phiếu sử dụng", body)
        self.assertIn("Thêm vào phiếu sao chụp", body)

    def test_file_and_document_pages_hide_what_the_reader_may_not_see(self):
        answers = {render(f"/portal/ho-so/{name}", READER) for name in (self.file_secret, "AF-99999")}
        self.assertEqual(answers, {(404, "")})  # missing and forbidden look the same
        answers = {render(f"/portal/van-ban/{name}", READER) for name in (self.doc_secret, "DOC-999999")}
        self.assertEqual(answers, {(404, "")})
        self.assertEqual(render(f"/portal/ho-so/{self.file_secret}", OFFICER)[0], 200)  # staff see everything

    def test_document_page_follows_the_preview_flag(self):
        status, body = render(f"/portal/van-ban/{self.doc_ok}", READER)
        self.assertEqual(status, 200)
        self.assertIn("RW Test Doc 0", body)
        self.assertIn("Bản xem trước", body)
        frappe.get_doc({"doctype": "Reader Group", "group_name": f"RP No preview {TAG}", "is_active": 1, "can_preview": 0,
                        "max_confidentiality_priority": 1}).insert(ignore_permissions=True)
        frappe.db.set_value("Reader", self.other_profile, "reader_group", f"RP No preview {TAG}")
        status, body = render(f"/portal/van-ban/{self.doc_ok}", OTHER)
        self.assertEqual(status, 200)
        self.assertIn("không được phép xem trước", body)

    def test_old_document_viewer_address_still_works(self):
        self.assertEqual(render("/portal_document?name=DOC-000001"), (301, "/portal/van-ban?name=DOC-000001"))
        self.assertEqual(render("/organization_info"), (301, "/app/organization-info"))
        self.assertEqual(render(f"/portal/van-ban?name={self.doc_ok}", READER)[0], 200)  # the query form of the same page

    # ---- slips
    def test_slip_list_is_the_readers_own(self):
        mine = self._sent_slip()
        status, body = render("/portal/phieu", READER)
        self.assertEqual(status, 200)
        self.assertIn(f"/portal/phieu/{mine}", body)
        self.assertNotIn(mine, render("/portal/phieu", OTHER)[1])
        self.assertIn("Chờ duyệt", body)
        self.assertNotIn(mine, render("/portal/phieu?status=Nh%C3%A1p", READER)[1])  # filtered by status

    def test_draft_slip_is_editable(self):
        name = self._draft()
        status, body = render(f"/portal/phieu/{name}", READER)
        self.assertEqual(status, 200)
        self.assertIn("slipEditor(", body)
        self.assertIn("Gửi yêu cầu", body)
        self.assertIn("Hủy bản nháp", body)
        self.assertIn("RW Test File 0", body)

    def test_sent_slip_is_read_only_with_progress_and_print(self):
        name = self._sent_slip(purpose='5 < 6 & "x"')
        status, body = render(f"/portal/phieu/{name}", READER)
        self.assertEqual(status, 200)
        self.assertNotIn("Gửi yêu cầu", body)
        self.assertIn('aria-current="step"', body)
        self.assertIn("In phiếu", body)
        self.assertIn("đang chờ cán bộ phòng đọc", body)
        self.assertIn("5 &lt; 6 &amp; &#34;x&#34;", body)  # the purpose the reader typed is escaped
        self.assertIn("Hủy phiếu", body)  # a reader may withdraw a slip that is still waiting

    def test_decided_slips_show_the_outcome(self):
        name = self._sent_slip()
        frappe.set_user(OFFICER)
        request_api.apply_action("Usage Request", name, "Từ chối", text="Tài liệu đang số hóa")
        body = render(f"/portal/phieu/{name}", READER)[1]
        self.assertIn("Lý do từ chối", body)
        self.assertIn("Tài liệu đang số hóa", body)
        self.assertNotIn("Hủy phiếu", body)
        approved = self._sent_slip()
        frappe.set_user(OFFICER)
        request_api.apply_action("Usage Request", approved, "Duyệt")
        self.assertIn("Phiếu đã được duyệt", render(f"/portal/phieu/{approved}", READER)[1])

    def test_nobody_opens_another_readers_slip_and_missing_ones_look_the_same(self):
        name = self._sent_slip()
        for target in (name, "UR-1999-99999"):
            self.assertEqual(render(f"/portal/phieu/{target}", OTHER), (404, ""), target)
        self.assertEqual(render(f"/portal/phieu/{name}", OFFICER)[0], 200)  # officers see slips

    def test_copy_slip_page_has_copy_counts(self):
        name = self._draft("copy")
        status, body = render(f"/portal/sao-chep/{name}", READER)
        self.assertEqual(status, 200)
        self.assertIn("Số bản", body)
        self.assertIn("Phiếu sao chụp", body)
        self.assertEqual(render("/portal/sao-chep", READER)[0], 200)

    def test_slip_pages_for_staff_without_a_profile_explain_themselves(self):
        self.assertIn("chưa có hồ sơ độc giả", render("/portal/phieu", OFFICER)[1])

    # ---- feedback, account, notifications
    def test_feedback_pages(self):
        frappe.set_user(READER)
        name = request_api.submit_feedback("Cần thêm bản quét", XSS)["name"]
        frappe.set_user(OFFICER)
        request_api.apply_action("Reader Feedback", name, "Phản hồi", text="Đã bổ sung")
        status, body = render("/portal/gop-y", READER)
        self.assertEqual(status, 200)
        self.assertIn("Cần thêm bản quét", body)
        self.assertIn("feedbackForm()", body)
        status, body = render(f"/portal/gop-y/{name}", READER)
        self.assertEqual(status, 200)
        self.assertIn("Đã bổ sung", body)
        self.assertNotIn("<script>alert(1)", body)
        self.assertEqual(render(f"/portal/gop-y/{name}", OTHER), (404, ""))

    def test_account_page(self):
        status, body = render("/portal/tai-khoan", READER)
        self.assertEqual(status, 200)
        self.assertIn("RP Reader", body)
        self.assertIn("accountPage(", body)
        self.assertIn("Quyền khai thác của bạn", body)
        self.assertEqual(render("/portal/tai-khoan", OFFICER), (404, ""))  # staff manage their account in the staff app
        self.assertEqual(render("/portal/tai-khoan", STAFF_READER)[0], 200)

    def test_notifications_page_and_bell(self):
        name = self._sent_slip()
        frappe.set_user(OFFICER)
        request_api.apply_action("Usage Request", name, "Duyệt")
        status, body = render("/portal/thong-bao", READER)
        self.assertEqual(status, 200)
        self.assertIn(f"/portal/phieu/{name}", body)
        self.assertIn("đã được duyệt", body)
        self.assertIn('"unread": 1', body)  # the bell of the layout starts from the real count
        self.assertNotIn(name, render("/portal/thong-bao", OTHER)[1])

    def test_header_shows_the_basket_and_the_staff_link(self):
        self._draft()
        body = render("/portal", READER)[1]
        self.assertIn('"count": 1', body)  # basket badge data
        self.assertNotIn('href="/dashboard"', body)
        self.assertIn('href="/dashboard"', render("/portal", STAFF_READER)[1])

    # ---- old reader addresses
    def test_readers_are_sent_from_the_old_pages_to_the_new_ones(self):
        for old, new in (("/usage_requests", "/portal/phieu"), ("/copy_requests", "/portal/sao-chep"),
                         ("/reader_feedbacks", "/portal/gop-y"), ("/usage_requests/form?name=UR-1", "/portal/phieu/UR-1"),
                         ("/copy_requests/form?name=CR-1", "/portal/sao-chep/CR-1"), ("/reader_feedbacks/form?name=FB-1", "/portal/gop-y/FB-1")):
            status, location = render(old, READER)
            self.assertEqual(status, 302, old)
            self.assertEqual(location, new, old)
        status, location = render("/usage_requests", "Guest")
        self.assertTrue(location.startswith("/dang-nhap"), location)

    def test_staff_are_sent_to_the_staff_app_from_the_old_pages(self):
        for old, new in (("/usage_requests", "/dashboard/doc-gia/phieu-su-dung"), ("/copy_requests", "/dashboard/doc-gia/phieu-sao-chup"),
                         ("/reader_feedbacks", "/dashboard/doc-gia/gop-y"), ("/usage_requests/form?name=UR-1", "/dashboard/doc-gia/phieu-su-dung/UR-1"),
                         ("/readers", "/dashboard/doc-gia/doc-gia"), ("/readers/form?name=RDR-1", "/dashboard/doc-gia/doc-gia"),
                         ("/reader_settings", "/dashboard/doc-gia/thiet-lap-doc-gia")):
            status, location = render(old, OFFICER)
            self.assertEqual((status, location), (302, new), old)

    def test_the_staff_only_old_pages_send_readers_to_the_portal(self):
        for old in ("/readers", "/reader_settings"):
            self.assertEqual(render(old, READER), (302, "/portal"), old)
            self.assertTrue(render(old, "Guest")[1].startswith("/dang-nhap"), old)
