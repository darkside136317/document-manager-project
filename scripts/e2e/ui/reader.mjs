// Browser end-to-end flow of the reader site (Playwright) against a running stack.
//
//   cd scripts/e2e/ui && npm install      (once; or set PW_CHANNEL=msedge / chrome to use an installed browser)
//   create the accounts: see ../accounts.py (with DM_E2E_PASSWORD set); run `down` afterwards
//   DM_E2E_PASSWORD=... OUT_DIR=out node reader.mjs
//
// A visitor registers, an officer approves the request in the staff app and hands over the one-time
// link, the new reader sets a password, searches (basic and advanced), builds slips, sends one, hears
// the decision through the bell, edits the account, sends feedback and signs out; then the same pages
// are checked on a phone. The archive data the flow needs is created and removed by the script;
// `accounts.py down` also removes the reader account created here.
import { chromium } from "playwright";
import fs from "node:fs";

const PW = process.env.DM_E2E_PASSWORD || (() => { throw new Error("Set DM_E2E_PASSWORD"); })();
const OUT = process.env.OUT_DIR || "out";
fs.mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE_URL || "http://localhost:8888";
const RUN = Date.now() % 1000000;
const TAG = `R${RUN}`;
const EMAIL = `e2e.newreader.${RUN}@example.com`;
const NEW_PW = `Kh!${RUN}-Doc-gia-Moi`;
const created = [];

const browser = await chromium.launch(process.env.PW_CHANNEL ? { channel: process.env.PW_CHANNEL } : {});
const problems = [];
function watch(page, label) {
  page.on("pageerror", (e) => problems.push(`${label} pageerror: ${e.message}`));
  page.on("console", (m) => {
    if ((m.type() === "error" || m.type() === "warning") && !/favicon|status of 4\d\d|Failed to load resource/.test(m.text())) problems.push(`${label} console: ${m.text()}`);
  });
}
const newContext = async (viewport = { width: 1360, height: 900 }, storageState) =>
  browser.newContext({ viewport, locale: "vi-VN", storageState, acceptDownloads: false });

let step = 0;
let page;
async function run(name, fn) {
  try { await fn(); console.log(`PASS ${String(++step).padStart(2, "0")} ${name}`); } catch (e) {
    console.log(`FAIL ${name}: ${e.message.split("\n")[0]}`); process.exitCode = 1;
    try { await page.screenshot({ path: `${OUT}/reader_fail_${++step}.png` }); } catch { /* the page may be gone */ }
  }
}
const expect = (cond, msg) => { if (!cond) throw new Error(msg); };
const visible = (locator, timeout = 8000) => locator.first().waitFor({ state: "visible", timeout });
const noOverflow = async (label) => {
  const extra = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(extra <= 0, `${label}: horizontal overflow of ${extra}px`);
};

async function login(context, email, password) {
  const response = await context.request.post(`${BASE}/api/method/login`, { form: { usr: email, pwd: password } });
  expect(response.ok(), `login of ${email} failed (${response.status()})`);
}
async function csrfOf(context) {
  const html = await (await context.request.get(`${BASE}/dashboard`)).text();
  return html.match(/"csrf_token":\s*"([^"]+)"/)?.[1];
}

// ---- archive data (admin, through the REST API) -----------------------------------------------
const admin = await newContext();
await login(admin, "e2e.admin@example.com", PW);
const adminHeaders = { "X-Frappe-CSRF-Token": await csrfOf(admin), "Content-Type": "application/json" };
async function make(doctype, values) {
  const response = await admin.request.post(`${BASE}/api/resource/${encodeURIComponent(doctype)}`, { headers: adminHeaders, data: values });
  expect(response.ok(), `create ${doctype}: ${response.status()} ${(await response.text()).slice(0, 200)}`);
  const name = (await response.json()).data.name;
  created.unshift([doctype, name]);
  return name;
}
const agency = await make("Archival Agency", { agency_name: `${TAG} Cơ quan` });
const fonds = await make("Fonds", { fonds_name: `${TAG} Phông`, archival_agency: agency });
const group = await make("Record Group", { group_title: `${TAG} Khối`, fonds });
const catalog = await make("Catalog", { catalog_title: `${TAG} Mục lục`, record_group: group, fonds });
const file = await make("Archival File", {
  file_title: `${TAG} Hồ sơ hiến chương`, file_number: `HS-${RUN}`, fonds, record_group: group, catalog,
  confidentiality_level: "Thường", status: "Đã hoàn thành", start_date: "1960-01-01", end_date: "1965-12-31",
});
const doc = await make("Archive Document", { document_title: `${TAG} Công văn số 12`, document_number: `CV-${RUN}`, author: "Sở Nội vụ", document_date: "1962-05-20", archival_file: file });
const secretLevel = await make("Confidentiality Level", { level_name: `${TAG} Mật`, priority: 7 });
const secretFile = await make("Archival File", {
  file_title: `${TAG} Hồ sơ mật`, fonds, record_group: group, catalog, confidentiality_level: secretLevel, status: "Đã hoàn thành",
});

let readerContext;
let officerContext;
let officerHeaders;
let linkPath;
let slipUrl;
let copyUrl;

try {
  // ---- a visitor ------------------------------------------------------------------------------
  const guest = await newContext();
  page = await guest.newPage();
  watch(page, "guest");

  await run("the home page introduces the unit and offers sign in and sign up", async () => {
    await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { level: 1 }));
    await visible(page.getByRole("link", { name: "Đăng nhập để tra cứu" }));
    await page.screenshot({ path: `${OUT}/reader_home.png` });
    for (const [name, heading] of [["Lãnh đạo", /lãnh đạo/i], ["Cơ cấu tổ chức", /cơ cấu/i], ["Liên hệ", /liên hệ/i], ["Hướng dẫn", /hướng dẫn/i]]) {
      await page.getByRole("navigation", { name: "Điều hướng chính" }).getByRole("link", { name }).click();
      await visible(page.getByRole("heading", { level: 1, name: heading }));
    }
  });

  await run("the reader area sends a guest to sign in and keeps the way back", async () => {
    await page.goto(`${BASE}/portal`);
    await page.waitForURL(/\/dang-nhap\?redirect-to=(%2F|\/)portal/);
    await visible(page.getByRole("heading", { name: "Đăng nhập" }));
    await page.screenshot({ path: `${OUT}/reader_login.png` });
  });

  await run("a wrong password is refused without saying which part was wrong", async () => {
    await page.locator("#usr").fill("e2e.reader@example.com");
    await page.locator("#pwd").fill("không-đúng-mật-khẩu");
    await page.getByRole("button", { name: "Đăng nhập" }).last().click();
    await visible(page.getByRole("alert").filter({ hasText: "Email hoặc mật khẩu không đúng" }));
  });

  await run("a visitor registers and is told the request is waiting", async () => {
    await page.goto(`${BASE}/dang-ky`, { waitUntil: "networkidle" });
    await page.locator("#full_name").fill(`Nguyễn Văn Mới ${RUN}`);
    await page.locator("#email").fill(EMAIL);
    await page.locator("#phone").fill("0912 345 678");
    await page.locator("#organization").fill("Viện Sử học");
    await page.locator("#purpose").fill("Nghiên cứu văn bản giai đoạn 1960–1965");
    await page.screenshot({ path: `${OUT}/reader_register.png` });
    await page.getByRole("button", { name: "Gửi đăng ký" }).click();
    await visible(page.getByText("Yêu cầu đã được ghi nhận"));
    await page.screenshot({ path: `${OUT}/reader_register_done.png` });
  });

  await run("registering the same email again, or an email that has an account, gives the same answer", async () => {
    for (const email of [EMAIL, "e2e.reader@example.com"]) {
      await page.goto(`${BASE}/dang-ky`, { waitUntil: "networkidle" });
      await page.locator("#full_name").fill("Người Thử Lại");
      await page.locator("#email").fill(email);
      await page.getByRole("button", { name: "Gửi đăng ký" }).click();
      await visible(page.getByText("Yêu cầu đã được ghi nhận"));
    }
    await page.goto(`${BASE}/quen-mat-khau`, { waitUntil: "networkidle" });
    await page.locator("#email").fill(`khong.ton.tai.${RUN}@example.com`);
    await page.getByRole("button", { name: "Gửi yêu cầu" }).click();
    await visible(page.getByText("Yêu cầu đã được ghi nhận"));
  });

  await run("an invalid link to set a password is explained", async () => {
    await page.goto(`${BASE}/dat-mat-khau?key=khong-hop-le`, { waitUntil: "networkidle" });
    await visible(page.getByText("không hợp lệ hoặc đã được sử dụng"));
  });

  // ---- an officer approves in the staff app -----------------------------------------------------
  officerContext = await newContext();
  page = await officerContext.newPage();
  watch(page, "officer");

  await run("the officer signs in on the same page and lands in the staff app", async () => {
    await page.goto(`${BASE}/dang-nhap`, { waitUntil: "networkidle" });
    await page.locator("#usr").fill("e2e.officer@example.com");
    await page.locator("#pwd").fill(PW);
    await page.getByRole("button", { name: "Đăng nhập" }).last().click();
    await page.waitForURL(/\/dashboard/);
    officerHeaders = { "X-Frappe-CSRF-Token": await csrfOf(officerContext), "Content-Type": "application/json" };
  });

  await run("the queue shows the new request with its counter in the sidebar", async () => {
    await page.goto(`${BASE}/dashboard/doc-gia/dang-ky`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Đăng ký độc giả" }));
    await visible(page.getByRole("row").filter({ hasText: EMAIL }));
    await visible(page.getByRole("navigation", { name: "Điều hướng chính" }).getByText(/^\d+$/));
    await page.screenshot({ path: `${OUT}/reader_queue.png` });
  });

  await run("approving creates the account and shows the one-time link once", async () => {
    await page.getByRole("row").filter({ hasText: EMAIL }).click();
    await visible(page.getByRole("dialog").getByText("Nguyễn Văn Mới"));
    await page.getByRole("button", { name: "Duyệt", exact: true }).click();
    const input = page.getByRole("textbox", { name: "Liên kết đặt mật khẩu" });
    await visible(input);
    const url = await input.inputValue();
    expect(/\/dat-mat-khau\?key=/.test(url), `unexpected link ${url}`);
    linkPath = new URL(url).pathname + new URL(url).search;
    await page.screenshot({ path: `${OUT}/reader_link.png` });
    await page.getByRole("button", { name: "Đã chuyển cho người dùng" }).click();
    await visible(page.getByText("Đã tạo tài khoản độc giả"));
  });

  await run("a decided request leaves the waiting list", async () => {
    await page.getByRole("button", { name: "Chờ xử lý" }).click();
    await page.waitForTimeout(600);
    expect(!(await page.getByRole("row").filter({ hasText: EMAIL }).count()), "the approved request is still listed as waiting");
    await page.getByRole("button", { name: "Đã duyệt", exact: true }).click();
    await visible(page.getByRole("row").filter({ hasText: EMAIL }));
  });

  // ---- the new reader ---------------------------------------------------------------------------
  readerContext = await newContext();
  page = await readerContext.newPage();
  watch(page, "reader");

  await run("the reader chooses a password from the link and is signed in", async () => {
    await page.goto(`${BASE}${linkPath}`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Đặt mật khẩu" }));
    await page.locator("#pwd").fill("ngan");
    await page.getByRole("button", { name: "Lưu mật khẩu và đăng nhập" }).click();
    await visible(page.getByRole("alert").filter({ hasText: "ít nhất 8 ký tự" }));
    await page.locator("#pwd").fill(NEW_PW);
    await page.locator("#again").fill(NEW_PW + "x");
    await page.getByRole("button", { name: "Lưu mật khẩu và đăng nhập" }).click();
    await visible(page.getByRole("alert").filter({ hasText: "không khớp" }));
    await page.locator("#again").fill(NEW_PW);
    await page.getByRole("button", { name: "Lưu mật khẩu và đăng nhập" }).click();
    await page.waitForURL(/\/portal/);
    await visible(page.getByRole("heading", { name: "Tra cứu tài liệu" }));
  });

  await run("the link works only once", async () => {
    const other = await newContext();
    const p = await other.newPage();
    await p.goto(`${BASE}${linkPath}`, { waitUntil: "networkidle" });
    await visible(p.getByText("không hợp lệ hoặc đã được sử dụng"));
    await other.close();
  });

  await run("basic search of hồ sơ finds the file and adds it to a usage slip", async () => {
    await page.locator("#q").fill(`${TAG} Hồ sơ hiến chương`);
    await page.getByRole("button", { name: "Tìm kiếm" }).click();
    const result = page.locator(".result").filter({ hasText: `${TAG} Hồ sơ hiến chương` });
    await visible(result);
    await page.screenshot({ path: `${OUT}/reader_results.png` });
    await result.getByRole("button", { name: "Phiếu sử dụng" }).click();
    await visible(page.locator(".toast").filter({ hasText: "Đã thêm" }));
    await expect_badge("clipboard-list", "1");
  });

  async function expect_badge(_icon, text) {
    await page.locator(".site-header .count-badge").first().waitFor({ state: "visible" });
    const shown = (await page.locator(".site-header .count-badge").first().textContent()).trim();
    expect(shown === text, `basket badge shows ${shown}, expected ${text}`);
  }

  await run("adding the same file twice changes nothing", async () => {
    await page.locator(".result").first().getByRole("button", { name: "Phiếu sử dụng" }).click();
    await visible(page.locator(".toast").filter({ hasText: "Đã có trong" }));
    await expect_badge("clipboard-list", "1");
  });

  await run("a file above the reader's clearance is invisible in search and by address", async () => {
    await page.locator("#q").fill(`${TAG} Hồ sơ mật`);
    await page.getByRole("button", { name: "Tìm kiếm" }).click();
    await visible(page.getByText("Không tìm thấy kết quả"));
    const response = await readerContext.request.get(`${BASE}/portal/ho-so/${secretFile}`);
    expect(response.status() === 404, `a secret file answered ${response.status()}`);
  });

  await run("advanced search of văn bản by number and author, then adding to a copy slip", async () => {
    await page.getByRole("tab", { name: /Văn bản/ }).click();
    await page.locator("#q").fill(""); // the keyword box stays when the kind changes and would narrow the search
    await page.getByRole("button", { name: "Tìm nâng cao" }).click();
    await page.locator("#d-num").fill(`CV-${RUN}`);
    await page.locator("#d-author").fill("Nội vụ");
    await page.locator("#d-from").fill("1962-01-01");
    await page.locator("#d-to").fill("1962-12-31");
    await page.screenshot({ path: `${OUT}/reader_advanced.png` });
    await page.getByRole("button", { name: "Tìm kiếm" }).click();
    const result = page.locator(".result").filter({ hasText: `${TAG} Công văn số 12` });
    await visible(result);
    await result.getByRole("button", { name: "Phiếu sao chụp" }).click();
    await visible(page.locator(".toast").filter({ hasText: "phiếu sao chụp" }));
    expect(page.url().includes("k=documents"), "the search is not kept in the address");
  });

  await run("the search can be reopened from the address", async () => {
    const url = page.url();
    await page.goto(url, { waitUntil: "networkidle" });
    await visible(page.locator(".result").filter({ hasText: `${TAG} Công văn số 12` }));
  });

  await run("the file page lists its documents and the document page previews it", async () => {
    await page.goto(`${BASE}/portal/ho-so/${file}`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { level: 1, name: new RegExp(`${TAG} Hồ sơ hiến chương`) }));
    await visible(page.getByRole("link", { name: `${TAG} Công văn số 12` }));
    await page.getByRole("link", { name: `${TAG} Công văn số 12` }).click();
    await visible(page.getByRole("heading", { level: 1, name: new RegExp(`${TAG} Công văn số 12`) }));
    await visible(page.getByRole("heading", { name: "Bản xem trước" }));
    await page.screenshot({ path: `${OUT}/reader_document.png` });
  });

  await run("the draft usage slip is completed and sent for approval", async () => {
    await page.getByRole("button", { name: "Phiếu đang soạn" }).click();
    await page.getByRole("menuitem", { name: /Phiếu yêu cầu sử dụng/ }).click();
    await page.waitForURL(/\/portal\/phieu\/UR-/);
    slipUrl = page.url();
    await visible(page.getByRole("heading", { level: 1, name: /Phiếu yêu cầu sử dụng UR-/ }));
    await page.getByRole("button", { name: "Gửi yêu cầu" }).click();
    await visible(page.getByRole("alert").filter({ hasText: "mục đích" })); // a purpose is required before sending
    await page.locator("#purpose").fill("Nghiên cứu hiến chương giai đoạn 1960–1965");
    await page.screenshot({ path: `${OUT}/reader_slip_draft.png` });
    await page.getByRole("button", { name: "Gửi yêu cầu" }).click();
    await visible(page.getByText("đang chờ cán bộ phòng đọc"));
    expect(!(await page.getByRole("button", { name: "Gửi yêu cầu" }).count()), "a sent slip is still editable");
    await visible(page.getByRole("button", { name: "In phiếu" }));
    await page.screenshot({ path: `${OUT}/reader_slip_sent.png` });
  });

  await run("the copy slip is edited (number of copies) and sent", async () => {
    await page.goto(`${BASE}/portal/sao-chep`, { waitUntil: "networkidle" });
    await page.getByRole("link", { name: /^CR-/ }).first().click();
    copyUrl = page.url();
    await page.getByLabel(/Số bản của/).fill("3");
    await page.locator("#purpose").fill("Sao chụp công văn để lưu hồ sơ");
    await page.getByRole("button", { name: "Lưu nháp" }).click();
    await visible(page.locator(".toast").filter({ hasText: "Đã lưu phiếu" }));
    await page.reload({ waitUntil: "networkidle" });
    expect((await page.getByLabel(/Số bản của/).inputValue()) === "3", "the copy count was not saved");
    await page.getByRole("button", { name: "Gửi yêu cầu" }).click();
    await visible(page.getByText("đang chờ cán bộ phòng đọc"));
  });

  await run("the slip lists show the reader's own slips by state", async () => {
    await page.goto(`${BASE}/portal/phieu`, { waitUntil: "networkidle" });
    await visible(page.getByRole("row").filter({ hasText: "Chờ duyệt" }));
    await page.getByRole("link", { name: "Nháp", exact: true }).click();
    await visible(page.getByText(/Không có phiếu yêu cầu sử dụng ở trạng thái/));
  });

  // ---- the officer decides; the reader hears about it ------------------------------------------
  await run("the officer approves the usage slip and refuses the copy slip", async () => {
    const usage = slipUrl.split("/").pop();
    const copy = copyUrl.split("/").pop();
    const act = async (doctype, name, action, text) => {
      const response = await officerContext.request.post(`${BASE}/api/method/document_manager.document_manager.api.requests.apply_action`, {
        headers: officerHeaders, data: { doctype, name, action, text },
      });
      expect(response.ok(), `${action} ${name}: ${response.status()} ${(await response.text()).slice(0, 200)}`);
    };
    await act("Usage Request", usage, "Duyệt");
    await act("Copy Request", copy, "Từ chối", "Tài liệu đang được số hóa");
  });

  await run("the bell counts both decisions and the notification page links to the slips", async () => {
    await page.goto(`${BASE}/portal`, { waitUntil: "networkidle" });
    await expect_bell("2");
    await page.getByRole("link", { name: "Thông báo" }).click();
    await visible(page.getByText(/đã được duyệt/));
    await visible(page.getByText(/bị từ chối\. Lý do: Tài liệu đang được số hóa/));
    await page.screenshot({ path: `${OUT}/reader_notifications.png` });
    await page.getByRole("link", { name: /đã được duyệt/ }).click();
    await visible(page.getByText("Phiếu đã được duyệt"));
    await page.goto(`${BASE}/portal/thong-bao`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Đánh dấu đã đọc tất cả" }).click();
    await page.waitForTimeout(500);
    await page.goto(`${BASE}/portal`, { waitUntil: "networkidle" });
    expect(!(await page.locator(".site-header a[aria-label='Thông báo'] .count-badge").isVisible()), "the bell still counts after reading");
  });

  async function expect_bell(text) {
    const bell = page.locator(".site-header a[aria-label='Thông báo'] .count-badge");
    await bell.waitFor({ state: "visible" });
    expect((await bell.textContent()).trim() === text, `bell shows ${(await bell.textContent()).trim()}, expected ${text}`);
  }

  await run("the refused slip shows the reason and no way to edit", async () => {
    await page.goto(copyUrl, { waitUntil: "networkidle" });
    await visible(page.getByText("Lý do từ chối:"));
    await visible(page.getByText("Tài liệu đang được số hóa").first());
    expect(!(await page.getByRole("button", { name: "Gửi yêu cầu" }).count()), "a refused slip is editable");
  });

  await run("account: contact details are saved; the password needs the current one", async () => {
    await page.goto(`${BASE}/portal/tai-khoan`, { waitUntil: "networkidle" });
    await page.locator("#phone").fill("0987 654 321");
    await page.locator("#position").fill("Nghiên cứu viên");
    await page.getByRole("button", { name: "Lưu thông tin" }).click();
    await visible(page.getByText("Đã lưu thông tin."));
    await page.reload({ waitUntil: "networkidle" });
    expect((await page.locator("#position").inputValue()) === "Nghiên cứu viên", "the position was not saved");
    await page.locator("#old").fill("sai-mat-khau-hien-tai");
    await page.locator("#next").fill(NEW_PW + "2");
    await page.locator("#again").fill(NEW_PW + "2");
    await page.getByRole("button", { name: "Đổi mật khẩu" }).click();
    await visible(page.getByRole("alert").filter({ hasText: /không đúng/ }));
    await page.locator("#old").fill(NEW_PW);
    await page.getByRole("button", { name: "Đổi mật khẩu" }).click();
    await visible(page.getByText("Đã đổi mật khẩu."));
    await page.screenshot({ path: `${OUT}/reader_account.png` });
  });

  await run("feedback is sent and the officer's answer is shown", async () => {
    await page.goto(`${BASE}/portal/gop-y`, { waitUntil: "networkidle" });
    await page.locator("#subject").fill(`${TAG} Cần bổ sung bản quét`);
    await page.locator("#content").fill("Xin bổ sung bản quét chất lượng cao cho hồ sơ này.");
    await page.getByRole("button", { name: "Gửi góp ý" }).click();
    await visible(page.getByRole("link", { name: `${TAG} Cần bổ sung bản quét` }));
    const name = (await page.getByRole("link", { name: `${TAG} Cần bổ sung bản quét` }).getAttribute("href")).split("/").pop();
    const response = await officerContext.request.post(`${BASE}/api/method/document_manager.document_manager.api.requests.apply_action`, {
      headers: officerHeaders, data: { doctype: "Reader Feedback", name, action: "Phản hồi", text: "Đã bổ sung bản quét." },
    });
    expect(response.ok(), `reply: ${response.status()}`);
    await page.getByRole("link", { name: `${TAG} Cần bổ sung bản quét` }).click();
    await visible(page.getByText("Đã bổ sung bản quét."));
    await page.screenshot({ path: `${OUT}/reader_feedback.png` });
  });

  await run("the theme can be switched and is remembered", async () => {
    await page.getByRole("button", { name: "Chuyển sang giao diện tối" }).click();
    expect((await page.locator("html").getAttribute("data-theme")) === "dark", "dark theme not applied");
    await page.goto(`${BASE}/portal`, { waitUntil: "networkidle" });
    expect((await page.locator("html").getAttribute("data-theme")) === "dark", "theme not remembered");
    await page.screenshot({ path: `${OUT}/reader_dark.png` });
    await page.getByRole("button", { name: "Chuyển sang giao diện sáng" }).click();
  });

  // ---- phone ------------------------------------------------------------------------------------
  await run("the reader pages fit a phone", async () => {
    const phone = await newContext({ width: 390, height: 844 }, await readerContext.storageState());
    page = await phone.newPage();
    watch(page, "phone");
    for (const [label, path] of [["search", "/portal"], ["slip", slipUrl.replace(BASE, "")], ["slips", "/portal/phieu"], ["file", `/portal/ho-so/${file}`],
                                  ["notifications", "/portal/thong-bao"], ["account", "/portal/tai-khoan"], ["home", "/gioi-thieu"], ["feedback", "/portal/gop-y"]]) {
      await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
      await noOverflow(label);
      await page.screenshot({ path: `${OUT}/reader_phone_${label}.png`, fullPage: true });
    }
    await page.goto(`${BASE}/portal`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Mở menu" }).click();
    await visible(page.getByRole("navigation", { name: "Điều hướng trên điện thoại" }).getByRole("link", { name: "Phiếu sử dụng" }));
    await page.screenshot({ path: `${OUT}/reader_phone_menu.png` });
    await phone.close();
  });

  // ---- sign out -----------------------------------------------------------------------------------
  await run("signing out returns to the sign-in page and closes the reader area", async () => {
    page = await readerContext.newPage();
    await page.goto(`${BASE}/portal`, { waitUntil: "networkidle" });
    await page.locator(".site-header").getByRole("button", { name: /Tài khoản: Nguyễn Văn Mới/ }).click();
    await page.getByRole("menuitem", { name: "Đăng xuất" }).click();
    await page.waitForURL(/\/dang-nhap/);
    await page.goto(`${BASE}/portal/phieu`);
    await page.waitForURL(/\/dang-nhap\?redirect-to=/);
  });

  await run("the new password works and the reader returns to the page they asked for", async () => {
    await page.goto(`${BASE}/portal/phieu`, { waitUntil: "networkidle" });
    await page.locator("#usr").fill(EMAIL);
    await page.locator("#pwd").fill(NEW_PW + "2"); // the password changed on the account page
    await page.getByRole("button", { name: "Đăng nhập" }).last().click();
    await page.waitForURL(/\/portal\/phieu/);
    await visible(page.getByRole("heading", { name: "Phiếu yêu cầu sử dụng" }));
  });

  await run("a reader cannot open the staff app or its API", async () => {
    await page.goto(`${BASE}/dashboard`);
    await page.waitForURL(/\/portal/);
    const response = await page.request.get(`${BASE}/api/method/document_manager.document_manager.api.registration.list_registrations`);
    expect(response.status() === 403, `the registration queue answered ${response.status()} to a reader`);
  });
} finally {
  // ---- clean up the archive data created for this run ------------------------------------------
  const cleanup = [];
  // the slips and feedback of the reader this run registered point at the archive data: remove them first
  const readers = (await (await admin.request.get(`${BASE}/api/resource/Reader?filters=${encodeURIComponent(JSON.stringify([["email", "=", EMAIL]]))}`, { headers: adminHeaders })).json()).data || [];
  for (const reader of readers) {
    for (const doctype of ["Usage Request", "Copy Request", "Reader Feedback"]) {
      const filters = encodeURIComponent(JSON.stringify([["reader", "=", reader.name]]));
      const rows = (await (await admin.request.get(`${BASE}/api/resource/${encodeURIComponent(doctype)}?filters=${filters}&fields=["name","docstatus"]`, { headers: adminHeaders })).json()).data || [];
      for (const row of rows) {
        if (row.docstatus === 1) await admin.request.post(`${BASE}/api/method/frappe.client.cancel`, { headers: adminHeaders, data: { doctype, name: row.name } });
        await admin.request.delete(`${BASE}/api/resource/${encodeURIComponent(doctype)}/${row.name}`, { headers: adminHeaders });
      }
    }
  }
  for (const [doctype, name] of created) {
    const response = await admin.request.delete(`${BASE}/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`, { headers: adminHeaders });
    if (!response.ok()) cleanup.push(`${doctype} ${name}: ${response.status()}`);
  }
  if (cleanup.length) console.log(`NOTE could not remove: ${cleanup.join("; ")}`);
  await browser.close();
}

if (problems.length) {
  console.log(`FAIL console problems:\n  ${[...new Set(problems)].join("\n  ")}`);
  process.exitCode = 1;
}
console.log(process.exitCode ? "RESULT: failed" : "RESULT: all steps passed");
