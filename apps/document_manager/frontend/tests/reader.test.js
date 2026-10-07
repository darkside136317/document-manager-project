// The reader site's script (document_manager/public/js/dm-reader.js) is a plain browser script that
// registers Alpine components. Here it runs in jsdom with a stand-in Alpine, so its logic (API calls,
// search state, form rules) is tested without a browser.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// vitest runs from the frontend folder (see package.json "test")
const SOURCE = readFileSync(resolve(process.cwd(), "../document_manager/public/js/dm-reader.js"), "utf8");

let components;
let stores;
let dm;

function load(boot = {}) {
  components = {};
  stores = {};
  window.__DM__ = { csrf: "tok", basket: undefined, unread: 0, ...boot };
  globalThis.Alpine = {
    data: (name, factory) => { components[name] = factory; },
    store: (name, value) => (value === undefined ? stores[name] : (stores[name] = value)),
  };
  new Function(SOURCE)();
  document.dispatchEvent(new Event("alpine:init"));
  dm = window.dm;
  dm.nav.go = vi.fn();
  dm.nav.reload = vi.fn();
}

const reply = (body, status = 200) => ({ status, ok: status >= 200 && status < 300, json: async () => body });
const mockFetch = (...replies) => {
  const fn = vi.fn();
  replies.forEach((r) => fn.mockResolvedValueOnce(r));
  globalThis.fetch = fn;
  return fn;
};

beforeEach(() => {
  window.history.replaceState(null, "", "/portal");
  load();
});
afterEach(() => vi.restoreAllMocks());

describe("helpers", () => {
  it("keeps only the <mark> tags of the search engine", () => {
    expect(dm.safeHighlight('a <mark>b</mark> <img src=x onerror=alert(1)> "q"')).toBe(
      'a <mark>b</mark> &lt;img src=x onerror=alert(1)&gt; &quot;q&quot;',
    );
  });

  it("follows a redirect target only when it stays on the site", () => {
    expect(dm.safeRedirect("/portal/phieu")).toBe("/portal/phieu");
    for (const bad of ["//evil.example", "https://evil.example", "/\\evil.example", "javascript:alert(1)", "", null, undefined]) {
      expect(dm.safeRedirect(bad)).toBe("");
    }
  });

  it("formats dates the Vietnamese way", () => {
    expect(dm.fmtDate("2024-03-09")).toBe("09/03/2024");
    expect(dm.fmtDate("")).toBe("");
  });

  it("reads Frappe's doubly encoded server messages", () => {
    const payload = { _server_messages: JSON.stringify([JSON.stringify({ message: "Lỗi <b>A</b>" })]) };
    expect(dm.errorMessage(payload, 417)).toBe("Lỗi A");
    expect(dm.errorMessage({}, 429)).toMatch(/quá nhanh/);
    const english = { _server_messages: JSON.stringify([JSON.stringify({ message: "You hit the rate limit" })]) };
    expect(dm.errorMessage(english, 429)).toMatch(/quá nhanh/); // the limiter's own text is English
    expect(dm.errorMessage({}, 500)).toMatch(/Máy chủ/);
  });
});

describe("call", () => {
  it("sends reads as GET with the filled arguments and the CSRF header", async () => {
    const fetch = mockFetch(reply({ message: { ok: 1 } }));
    expect(await dm.call("x.y", { a: 1, b: "", c: null, d: { z: 1 } })).toEqual({ ok: 1 });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/method/x.y?a=1&d=%7B%22z%22%3A1%7D");
    expect(init.method).toBe("GET");
    expect(init.headers["X-Frappe-CSRF-Token"]).toBe("tok");
  });

  it("sends writes as JSON POST", async () => {
    const fetch = mockFetch(reply({ message: "done" }));
    await dm.call("x.y", { a: 1 }, { post: true });
    const [, init] = fetch.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ a: 1 });
  });

  it("sends an expired session to the sign-in page, remembering where it was", async () => {
    mockFetch(reply({ exc_type: "AuthenticationError" }, 401));
    window.history.replaceState(null, "", "/portal/phieu?status=Nh%C3%A1p");
    await expect(dm.call("x.y")).rejects.toThrow();
    expect(dm.nav.go).toHaveBeenCalledWith("/dang-nhap?redirect-to=" + encodeURIComponent("/portal/phieu?status=Nh%C3%A1p"));
  });

  it("lets a call treat 401 as an answer (wrong password)", async () => {
    mockFetch(reply({ _server_messages: JSON.stringify([JSON.stringify({ message: "Sai mật khẩu" })]) }, 401));
    await expect(dm.call("x.y", {}, { post: true, signInOn401: false })).rejects.toMatchObject({ status: 401, message: "Sai mật khẩu" });
    expect(dm.nav.go).not.toHaveBeenCalled();
  });

  it("explains a network failure", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(dm.call("x.y")).rejects.toThrow(/Không kết nối/);
  });
});

describe("searchPage", () => {
  const make = (config) => {
    const page = components.searchPage(config);
    page.init();
    return page;
  };

  it("restores its state from the address", () => {
    window.history.replaceState(null, "", "/portal?k=documents&q=hiến%20pháp&author=Quốc%20hội&page=2&sort=title");
    const fetch = mockFetch(reply({ message: { data: [], total: 0 } }));
    const page = make({ fonds: { "FONDS-1": "Phông A" } });
    expect(page.kind).toBe("documents");
    expect(page.q).toBe("hiến pháp");
    expect(page.f.documents.author).toBe("Quốc hội");
    expect(page.page).toBe(2);
    expect(page.sort).toBe("title");
    expect(page.adv).toBe(true); // an advanced condition is in the address: show the panel
    expect(page.fondsLabel({ fonds: "FONDS-1" })).toBe("Phông A");
    expect(page.fondsLabel({ fonds: "FONDS-9" })).toBe("FONDS-9");
    expect(fetch).toHaveBeenCalledTimes(1); // criteria in the address: the search runs on load
    expect(fetch.mock.calls[0][0]).toContain("search_documents?");
  });

  it("sends only what the reader filled in", () => {
    const page = make();
    page.q = "  bản đồ ";
    page.f.files.file_number = " 12 ";
    page.f.files.file_title = "";
    expect(page.params()).toEqual({ page: 1, page_size: 20, sort_by: "modified", query: "bản đồ", file_number: "12" });
  });

  it("asks for a criterion instead of searching with none", async () => {
    const fetch = mockFetch();
    const page = make();
    await page.submit();
    expect(fetch).not.toHaveBeenCalled();
    expect(page.error).toMatch(/từ khóa/);
  });

  it("searches files, keeps the result and puts the search in the address", async () => {
    const fetch = mockFetch(reply({ message: { data: [{ name: "AF-1", file_title: "Hồ sơ 1" }], total: 45, engine: "database" } }));
    const page = make();
    page.q = "hồ sơ";
    await page.submit();
    expect(fetch.mock.calls[0][0]).toContain("search_archival_files?");
    expect(page.rows).toHaveLength(1);
    expect(page.total).toBe(45);
    expect(page.totalPages).toBe(3);
    expect([page.from, page.to]).toEqual([1, 20]);
    expect(page.searched).toBe(true);
    expect(window.location.search).toContain("q=h%E1%BB%93+s%C6%A1");
    expect(page.href(page.rows[0])).toBe("/portal/ho-so/AF-1");
    expect(page.title(page.rows[0])).toBe("Hồ sơ 1");
  });

  it("searches documents, with highlights and the content snippet", async () => {
    mockFetch(reply({ message: { data: [{ id: "DOC-1", name: "DOC-1", document_title: "Hiến pháp", _formatted: { document_title: "<mark>Hiến</mark> pháp", content_text: "…<mark>hiến</mark> <script>x</script>" } }], total: 1, engine: "meilisearch" } }));
    const page = make();
    page.setKind("documents");
    page.q = "hiến";
    await page.submit();
    expect(page.engine).toBe("meilisearch");
    expect(page.href(page.rows[0])).toBe("/portal/van-ban/DOC-1");
    expect(page.titleHtml(page.rows[0])).toBe("<mark>Hiến</mark> pháp");
    expect(page.snippet(page.rows[0])).toBe("…<mark>hiến</mark> &lt;script&gt;x&lt;/script&gt;");
  });

  it("shows the server's refusal and clears the old results", async () => {
    mockFetch(reply({ _server_messages: JSON.stringify([JSON.stringify({ message: "Nhóm của bạn không được tìm kiếm" })]) }, 403));
    const page = make();
    page.rows = [{ name: "old" }];
    page.q = "x";
    await page.submit();
    expect(page.error).toBe("Nhóm của bạn không được tìm kiếm");
    expect(page.rows).toEqual([]);
    expect(page.loading).toBe(false);
  });

  it("goes to another page within bounds", async () => {
    const fetch = mockFetch(...Array(3).fill(reply({ message: { data: [], total: 45 } })));
    const page = make();
    page.q = "x";
    await page.submit();
    page.go(99);
    await Promise.resolve();
    expect(page.page).toBe(3);
    page.go(0);
    expect(page.page).toBe(1);
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("starts over when the reader switches between files and documents", () => {
    const page = make();
    page.rows = [{ name: "x" }];
    page.total = 1;
    page.searched = true;
    page.setKind("documents");
    expect([page.kind, page.rows, page.total, page.searched, page.page]).toEqual(["documents", [], 0, false, 1]);
  });
});

describe("basket store", () => {
  it("takes its counters from the page", () => {
    load({ basket: { usage: { count: 2, name: "UR-1", route: "/portal/phieu" }, copy: { count: 0, name: null, route: "/portal/sao-chep" } } });
    expect(stores.basket.total).toBe(2);
  });

  it("adds an item, updates the badge and tells the reader", async () => {
    const fetch = mockFetch(reply({ message: { added: true, request: "UR-9", count: 3, message: "Đã thêm vào phiếu", route: "/portal/phieu/UR-9" } }));
    await stores.basket.add("file", "AF-1", "usage");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ kind: "file", name: "AF-1", target: "usage" });
    expect(stores.basket.usage).toMatchObject({ count: 3, name: "UR-9" });
    expect(stores.toast.items[0]).toMatchObject({ message: "Đã thêm vào phiếu", link: "/portal/phieu/UR-9", error: false });
    expect(stores.basket.busy).toBe(false);
  });

  it("reports a refusal without touching the counters", async () => {
    mockFetch(reply({ _server_messages: JSON.stringify([JSON.stringify({ message: "Không có quyền khai thác" })]) }, 403));
    await stores.basket.add("document", "DOC-1", "copy");
    expect(stores.basket.copy.count).toBe(0);
    expect(stores.toast.items[0]).toMatchObject({ message: "Không có quyền khai thác", error: true });
  });
});

describe("loginForm", () => {
  it("needs both fields", async () => {
    const fetch = mockFetch();
    const form = components.loginForm({});
    await form.submit();
    expect(fetch).not.toHaveBeenCalled();
    expect(form.error).toMatch(/email và mật khẩu/);
  });

  it("goes back to where the visitor came from, or to the home page of their role", async () => {
    mockFetch(reply({ home_page: "/portal" }), reply({ home_page: "dashboard" }), reply({ home_page: "//evil.example" }));
    for (const [redirect, expected] of [["/portal/phieu/UR-1", "/portal/phieu/UR-1"], ["", "/dashboard"], ["", "/portal"]]) {
      const form = components.loginForm({ redirect });
      form.usr = "a@b.vn";
      form.pwd = "pw";
      await form.submit();
      expect(dm.nav.go).toHaveBeenLastCalledWith(expected);
    }
  });

  it("does not say whether the email or the password was wrong", async () => {
    mockFetch(reply({ message: "Invalid login credentials" }, 401));
    const form = components.loginForm({});
    form.usr = "a@b.vn";
    form.pwd = "bad";
    await form.submit();
    expect(form.error).toMatch(/Email hoặc mật khẩu không đúng/);
    expect(form.busy).toBe(false);
    expect(dm.nav.go).not.toHaveBeenCalled();
  });

  it("does not follow a foreign redirect after signing in", async () => {
    mockFetch(reply({ home_page: "/portal" }));
    const form = components.loginForm({ redirect: "https://evil.example" });
    form.usr = "a@b.vn";
    form.pwd = "pw";
    await form.submit();
    expect(dm.nav.go).toHaveBeenCalledWith("/portal");
  });
});

describe("guest forms", () => {
  it("registers with the honeypot field and shows the outcome", async () => {
    const fetch = mockFetch(reply({ message: { status: "pending", message: "Đã ghi nhận" } }));
    const form = components.registerForm();
    form.v.full_name = "An";
    form.v.email = "an@x.vn";
    await form.submit();
    const body = JSON.parse(fetch.mock.calls[0][1].body);
    expect(body).toMatchObject({ full_name: "An", email: "an@x.vn", website: "" });
    expect(form.done).toBe(true);
    expect(form.result.message).toBe("Đã ghi nhận");
  });

  it("asks for name and email first", async () => {
    const fetch = mockFetch();
    const form = components.registerForm();
    await form.submit();
    expect(fetch).not.toHaveBeenCalled();
    expect(form.error).toMatch(/họ tên và email/);
  });

  it("keeps the form open when the server refuses", async () => {
    mockFetch(reply({ _server_messages: JSON.stringify([JSON.stringify({ message: "Địa chỉ email không hợp lệ" })]) }, 417));
    const form = components.registerForm();
    form.v.full_name = "An";
    form.v.email = "x";
    await form.submit();
    expect([form.done, form.error]).toEqual([false, "Địa chỉ email không hợp lệ"]);
  });

  it("sets the password from the link and signs the reader in", async () => {
    const fetch = mockFetch(reply({ message: "/portal" }));
    const form = components.setPasswordForm({ key: "K1" });
    form.pwd = "Mật-khẩu-Mạnh-1";
    form.again = "Mật-khẩu-Mạnh-1";
    await form.submit();
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ new_password: "Mật-khẩu-Mạnh-1", key: "K1" });
    expect(dm.nav.go).toHaveBeenCalledWith("/portal");
  });

  it("checks the two passwords before asking the server", async () => {
    const fetch = mockFetch();
    const form = components.setPasswordForm({ key: "K1" });
    form.pwd = "short";
    await form.submit();
    expect(form.error).toMatch(/ít nhất 8/);
    form.pwd = "longenough1";
    form.again = "different1";
    await form.submit();
    expect(form.error).toMatch(/không khớp/);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("explains an expired link", async () => {
    mockFetch(reply({}, 410));
    const form = components.setPasswordForm({ key: "old" });
    form.pwd = form.again = "longenough1";
    await form.submit();
    expect(form.error).toMatch(/hết hạn/);
    expect(form.busy).toBe(false);
  });
});

describe("slipEditor", () => {
  const config = (extra = {}) => ({
    doctype: "Usage Request", name: "UR-1", purpose: "", notes: "", listUrl: "/portal/phieu", target: "usage",
    items: [
      { row: "r1", archival_file: "AF-1", archive_document: "", copy_count: 1, notes: "", title: "Hồ sơ 1", href: "/portal/ho-so/AF-1" },
      { row: "r2", archival_file: "AF-1", archive_document: "DOC-1", copy_count: 2, notes: "", title: "Văn bản 1", href: "/portal/van-ban/DOC-1" },
    ],
    ...extra,
  });

  it("sends the slip without the display-only fields", () => {
    const editor = components.slipEditor(config({ purpose: "Nghiên cứu" }));
    expect(JSON.parse(editor.payload())).toEqual({
      purpose: "Nghiên cứu", notes: "",
      items: [
        { archival_file: "AF-1", archive_document: "", notes: "", copy_count: 1 },
        { archival_file: "AF-1", archive_document: "DOC-1", notes: "", copy_count: 2 },
      ],
    });
  });

  it("will not send a slip without a purpose", async () => {
    const fetch = mockFetch();
    const editor = components.slipEditor(config());
    await editor.send();
    expect(fetch).not.toHaveBeenCalled();
    expect(editor.error).toMatch(/mục đích/);
  });

  it("saves, then sends for approval and reloads the page", async () => {
    const fetch = mockFetch(reply({ message: { name: "UR-1", state: "Chờ duyệt" } }));
    const editor = components.slipEditor(config({ purpose: "Nghiên cứu" }));
    await editor.send();
    const body = JSON.parse(fetch.mock.calls[0][1].body);
    expect(body).toMatchObject({ doctype: "Usage Request", name: "UR-1", submit: 1 });
    expect(dm.nav.reload).toHaveBeenCalled();
  });

  it("removes a row, and leaves the page when the draft is gone", async () => {
    mockFetch(reply({ message: { request: "UR-1", count: 1 } }), reply({ message: { request: null, count: 0 } }));
    const editor = components.slipEditor(config());
    await editor.removeItem(editor.items[0]);
    expect(editor.items.map((i) => i.row)).toEqual(["r2"]);
    expect(stores.basket.usage.count).toBe(1);
    await editor.removeItem(editor.items[0]);
    expect(dm.nav.go).toHaveBeenCalledWith("/portal/phieu");
    expect(stores.basket.usage.name).toBeNull();
  });

  it("asks before discarding the draft", async () => {
    const fetch = mockFetch(reply({ message: { request: null } }));
    vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const editor = components.slipEditor(config());
    await editor.discard();
    expect(fetch).not.toHaveBeenCalled();
    await editor.discard();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(dm.nav.go).toHaveBeenCalledWith("/portal/phieu");
  });
});

describe("account page", () => {
  it("checks the new password before changing it", async () => {
    const fetch = mockFetch();
    const page = components.accountPage({ profile: { phone: "1" } });
    page.next = "abc";
    await page.changePassword();
    expect(page.passError).toMatch(/ít nhất 8/);
    page.next = "longenough1";
    page.again = "other";
    await page.changePassword();
    expect(page.passError).toMatch(/không khớp/);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("says when the current password is wrong", async () => {
    mockFetch(reply({ _server_messages: JSON.stringify([JSON.stringify({ message: "Mật khẩu hiện tại không đúng" })]) }, 417));
    const page = components.accountPage({ profile: {} });
    page.old = "x";
    page.next = page.again = "longenough1";
    await page.changePassword();
    expect(page.passError).toBe("Mật khẩu hiện tại không đúng");
    expect(dm.nav.go).not.toHaveBeenCalled();
  });

  it("clears the password fields after a change", async () => {
    mockFetch(reply({ message: { message: "ok" } }));
    const page = components.accountPage({ profile: {} });
    page.old = "x";
    page.next = page.again = "longenough1";
    await page.changePassword();
    expect([page.passOk, page.old, page.next, page.again]).toEqual([true, "", "", ""]);
  });
});

describe("notifications page", () => {
  it("marks everything read and updates the bell", async () => {
    mockFetch(reply({ message: 0 }));
    const page = components.notificationsPage({ unread: 3 });
    await page.markAll();
    expect(page.unread).toBe(0);
    expect(stores.notes.unread).toBe(0);
  });
});
