// Browser end-to-end flow of the slip queues and the reader management of the staff app (Playwright).
//
//   accounts: ../accounts.py (e2e.reader, e2e.officer, e2e.leader, e2e.admin) with DM_E2E_PASSWORD set; run `down` afterwards
//   DM_E2E_PASSWORD=... OUT_DIR=out PW_CHANNEL=msedge node slips.mjs
//
// Readers (driven through the API) send slips; the reading room receives, decides item by item, hands over,
// renews and takes the documents back; a slip with a confidential item goes to the leader, who decides on
// their own screen; a copy slip is completed; feedback is answered; a reader is created at the counter and
// given online access; a reader group, a request template and the settings are edited. The archive data
// created for the run is removed at the end (`accounts.py down` removes the reader created at the counter).
import { chromium } from "playwright";
import fs from "node:fs";

const PW = process.env.DM_E2E_PASSWORD || (() => { throw new Error("Set DM_E2E_PASSWORD"); })();
const OUT = process.env.OUT_DIR || "out";
fs.mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE_URL || "http://localhost:8888";
const API = `${BASE}/api/method/document_manager.document_manager.api`;
const RUN = Date.now() % 1000000;
const TAG = `E2E-S${RUN}`;
const created = [];

const browser = await chromium.launch(process.env.PW_CHANNEL ? { channel: process.env.PW_CHANNEL } : {});
const problems = [];
const watch = (page, label) => {
  page.on("pageerror", (e) => problems.push(`${label} pageerror: ${e.message}`));
  page.on("console", (m) => {
    if ((m.type() === "error" || m.type() === "warning") && !/favicon|status of 4\d\d|Failed to load resource/.test(m.text())) problems.push(`${label} console: ${m.text()}`);
  });
};
const newContext = (viewport = { width: 1440, height: 900 }, storageState) => browser.newContext({ viewport, locale: "vi-VN", storageState });

let step = 0;
let page;
async function run(name, fn) {
  try { await fn(); console.log(`PASS ${String(++step).padStart(2, "0")} ${name}`); } catch (e) {
    console.log(`FAIL ${name}: ${e.message.split("\n")[0]}`); process.exitCode = 1;
    try { await page.screenshot({ path: `${OUT}/slips_fail_${++step}.png` }); } catch { /* the page may be gone */ }
  }
}
const expect = (cond, msg) => { if (!cond) throw new Error(msg); };
const visible = (locator, timeout = 10000) => locator.first().waitFor({ state: "visible", timeout });

async function login(context, email) {
  const response = await context.request.post(`${BASE}/api/method/login`, { form: { usr: email, pwd: PW } });
  expect(response.ok(), `login of ${email} failed (${response.status()})`);
}
const csrfFrom = async (context, path) => (await (await context.request.get(`${BASE}${path}`)).text()).match(/"csrf(?:_token)?":\s*"([^"]+)"/)?.[1];
const headersOf = (csrf) => ({ "X-Frappe-CSRF-Token": csrf, "Content-Type": "application/json" });

// ---- contexts and data ------------------------------------------------------------------------------
const admin = await newContext();
await login(admin, "e2e.admin@example.com");
const adminHeaders = headersOf(await csrfFrom(admin, "/dashboard"));
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
const level = await make("Confidentiality Level", { level_name: `${TAG} Mật`, priority: 2, requires_leader_approval: 1 });
const base = { fonds, record_group: group, catalog, status: "Đã hoàn thành" };
const fileA = await make("Archival File", { ...base, file_title: `${TAG} Hồ sơ A`, file_number: `A-${RUN}`, confidentiality_level: "Thường", shelf_number: "G7", box_number: "H21" });
const fileB = await make("Archival File", { ...base, file_title: `${TAG} Hồ sơ B`, file_number: `B-${RUN}`, confidentiality_level: "Thường" });
const fileSecret = await make("Archival File", { ...base, file_title: `${TAG} Hồ sơ mật`, file_number: `M-${RUN}`, confidentiality_level: level });

// the e2e reader may read the confidential level (a personal override)
const readerName = (await (await admin.request.get(`${BASE}/api/resource/Reader?filters=${encodeURIComponent(JSON.stringify([["email", "=", "e2e.reader@example.com"]]))}`)).json()).data[0].name;
await admin.request.put(`${BASE}/api/resource/Reader/${readerName}`, { headers: adminHeaders, data: { max_confidentiality_priority: 2 } });
// no limit gets in the way of the flow
const settingsBefore = (await (await admin.request.get(`${BASE}/api/resource/Reader%20Settings/Reader%20Settings`)).json()).data;
await admin.request.put(`${BASE}/api/resource/Reader%20Settings/Reader%20Settings`, { headers: adminHeaders, data: { max_requests_per_day: 0, max_copy_requests_per_day: 0, max_open_requests: 0, max_items_per_request: 0, block_when_overdue: 0 } });

const readerCtx = await newContext();
await login(readerCtx, "e2e.reader@example.com");
const readerHeaders = headersOf(await csrfFrom(readerCtx, "/portal"));
async function readerSends(doctype, items, purpose = `${TAG} nghiên cứu`) {
  const response = await readerCtx.request.post(`${API}.requests.save_request`, { headers: readerHeaders, data: { doctype, payload: JSON.stringify({ purpose, items }), submit: 1 } });
  expect(response.ok(), `send ${doctype}: ${response.status()} ${(await response.text()).slice(0, 200)}`);
  return (await response.json()).message.name;
}
const usageNormal = await readerSends("Usage Request", [{ archival_file: fileA }, { archival_file: fileB }]);
const usageSecret = await readerSends("Usage Request", [{ archival_file: fileSecret }]);
const copySlip = await readerSends("Copy Request", [{ archival_file: fileA, copy_count: 2 }]);
const feedback = (await (await readerCtx.request.post(`${API}.requests.submit_feedback`, { headers: readerHeaders, data: { subject: `${TAG} Cần bổ sung bản quét`, content: "Xin bổ sung bản quét hồ sơ A" } })).json()).message.name;

let officerCtx; let leaderCtx; let adminPage; let counterEmail;

try {
  officerCtx = await newContext();
  await login(officerCtx, "e2e.officer@example.com");
  page = await officerCtx.newPage();
  watch(page, "officer");

  await run("the sidebar counts what waits for the reading room", async () => {
    await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
    const link = page.getByRole("navigation", { name: "Điều hướng chính" }).getByRole("link", { name: /Phiếu yêu cầu sử dụng/ });
    await visible(link);
    expect(/\d+/.test(await link.textContent()), "no counter next to the usage slips");
    await visible(page.getByRole("navigation", { name: "Điều hướng chính" }).getByRole("link", { name: /Góp ý của độc giả/ }));
  });

  await run("the queue opens on the reception tab and lists the new slips", async () => {
    await page.getByRole("navigation", { name: "Điều hướng chính" }).getByRole("link", { name: /Phiếu yêu cầu sử dụng/ }).click();
    await visible(page.getByRole("tab", { name: /Chờ tiếp nhận/, selected: true }));
    await visible(page.getByRole("row", { name: new RegExp(usageNormal) }));
    await visible(page.getByRole("row", { name: new RegExp(usageSecret) }).getByText("Cần lãnh đạo"));
    await page.screenshot({ path: `${OUT}/slips_queue.png` });
  });

  await run("search narrows the queue", async () => {
    await page.getByRole("searchbox", { name: "Tìm phiếu" }).fill(usageSecret);
    await page.waitForTimeout(700);
    expect((await page.getByRole("row", { name: new RegExp(usageNormal) }).count()) === 0, "search kept another slip");
    await visible(page.getByRole("row", { name: new RegExp(usageSecret) }));
    await page.getByRole("searchbox", { name: "Tìm phiếu" }).fill("");
    await page.waitForTimeout(700);
  });

  await run("a slip opens with the reader, the items and where to fetch them", async () => {
    await page.getByRole("row", { name: new RegExp(usageNormal) }).click();
    await visible(page.getByRole("heading", { level: 1, name: new RegExp(usageNormal) }));
    await visible(page.getByText(`${TAG} Hồ sơ A`).first());
    await visible(page.getByText(/Giá G7/));
    await visible(page.getByRole("link", { name: /In phiếu lấy tài liệu/ }));
    await page.screenshot({ path: `${OUT}/slips_detail.png` });
  });

  await run("an item is turned down with a reason, the rest approved with the slip", async () => {
    await page.getByRole("group", { name: new RegExp(`Quyết định cho ${TAG} Hồ sơ B`) }).getByRole("button", { name: "Từ chối" }).click();
    await page.getByRole("button", { name: "Duyệt", exact: true }).first().waitFor();
    await page.getByRole("button", { name: "Lưu quyết định" }).click();
    await visible(page.getByText("Hãy nhập lý do cho các dòng bị từ chối."));
    await page.getByLabel(new RegExp(`Lý do từ chối ${TAG} Hồ sơ B`)).fill("Đang tu bổ, chưa phục vụ");
    await page.getByRole("button", { name: "Lưu quyết định" }).click();
    await visible(page.getByText("Đã lưu quyết định duyệt"));
    await page.getByRole("region", { name: "Thao tác" }).getByRole("button", { name: "Duyệt", exact: true }).click();
    await visible(page.getByText("Duyệt: đã thực hiện"));
    await visible(page.locator("h1").getByText("Đã duyệt", { exact: true }));
    await visible(page.getByText("Đang tu bổ, chưa phục vụ"));
  });

  await run("handing over sets the due date and the items 'Đã giao'", async () => {
    await page.getByRole("button", { name: "Giao tài liệu" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Giao tài liệu" }).click();
    await visible(page.locator("h1").getByText("Đang sử dụng", { exact: true }));
    await visible(page.getByText("Hạn trả").first());
    await visible(page.getByText("Đã giao", { exact: true }).first());
    await page.screenshot({ path: `${OUT}/slips_in_use.png` });
  });

  await run("renewing extends the due date and counts the renewal", async () => {
    await page.getByRole("button", { name: "Gia hạn" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Gia hạn" }).click();
    await visible(page.getByText(/Đã gia hạn đến/));
    await visible(page.getByText(/gia hạn 1\//));
  });

  await run("the in-use slip is in its tab; the reader sees the hand-over on the reader site", async () => {
    await page.goto(`${BASE}/dashboard/doc-gia/phieu-su-dung?view=dang_su_dung`, { waitUntil: "networkidle" });
    await visible(page.getByRole("row", { name: new RegExp(usageNormal) }));
    const rp = await readerCtx.newPage();
    await rp.goto(`${BASE}/portal/phieu/${usageNormal}`, { waitUntil: "networkidle" });
    await visible(rp.getByText("Tài liệu đã được giao"));
    await visible(rp.getByText("Đã giao", { exact: true }).first());
    await rp.close();
  });

  await run("taking the documents back records the condition of each one", async () => {
    await page.getByRole("row", { name: new RegExp(usageNormal) }).click();
    await page.getByRole("button", { name: "Nhận trả" }).click();
    await page.getByLabel(new RegExp(`Tình trạng của ${TAG} Hồ sơ A`)).selectOption("Thiếu trang");
    await page.getByRole("button", { name: "Xác nhận đã nhận trả" }).click();
    await visible(page.getByText("Đã nhận trả tài liệu"));
    await visible(page.locator("h1").getByText("Đã trả", { exact: true }));
    await visible(page.getByText("Khi trả: Thiếu trang"));
  });

  // ---- a confidential slip goes to the leader ------------------------------------------------------
  await run("a slip with a confidential item cannot be approved by the reading room alone", async () => {
    await page.goto(`${BASE}/dashboard/doc-gia/phieu-su-dung/${usageSecret}`, { waitUntil: "networkidle" });
    await visible(page.getByRole("button", { name: "Chuyển lãnh đạo" }));
    expect((await page.getByRole("region", { name: "Thao tác" }).getByRole("button", { name: "Duyệt", exact: true }).count()) === 0, "the reading room can approve a leader's slip");
    await page.getByRole("button", { name: "Chuyển lãnh đạo" }).click();
    await visible(page.locator("h1").getByText("Chờ lãnh đạo duyệt", { exact: true }));
  });

  leaderCtx = await newContext();
  await login(leaderCtx, "e2e.leader@example.com");
  page = await leaderCtx.newPage();
  watch(page, "leader");

  await run("the leader's queue opens on what waits for a leader and the leader decides", async () => {
    await page.goto(`${BASE}/dashboard/doc-gia/phieu-su-dung`, { waitUntil: "networkidle" });
    await visible(page.getByRole("tab", { name: /Chờ lãnh đạo duyệt/, selected: true }));
    await page.getByRole("row", { name: new RegExp(usageSecret) }).click();
    await visible(page.getByRole("heading", { level: 1, name: new RegExp(usageSecret) }));
    await visible(page.getByRole("button", { name: "Trả lại phòng đọc" }));
    await page.screenshot({ path: `${OUT}/slips_leader.png` });
    await page.getByRole("region", { name: "Thao tác" }).getByRole("button", { name: "Duyệt", exact: true }).click();
    await visible(page.getByText("Duyệt: đã thực hiện"));
    await visible(page.locator("h1").getByText("Đã duyệt", { exact: true }));
  });

  await run("the leader has no reader management or settings in the sidebar", async () => {
    const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
    expect((await nav.getByRole("link", { name: "Đăng ký độc giả" }).count()) === 0, "the leader sees the registrations");
    await visible(nav.getByRole("link", { name: "Danh sách độc giả" }));
    const response = await leaderCtx.request.post(`${API}.slips.renew`, { headers: headersOf(await csrfFrom(leaderCtx, "/dashboard")), data: { name: usageNormal } });
    expect(response.status() === 403, `a leader renewed a slip (${response.status()})`);
  });

  page = await officerCtx.newPage();
  watch(page, "officer");

  await run("the reading room sees the leader's decision and hands the confidential slip over", async () => {
    await page.goto(`${BASE}/dashboard/doc-gia/phieu-su-dung/${usageSecret}`, { waitUntil: "networkidle" });
    await visible(page.getByText(/Lãnh đạo/).first());
    await page.getByRole("button", { name: "Giao tài liệu" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Giao tài liệu" }).click();
    await visible(page.locator("h1").getByText("Đang sử dụng", { exact: true }));
    await visible(page.getByText("Lịch sử xử lý"));
    await visible(page.getByText("Chờ lãnh đạo duyệt → Đã duyệt"));
  });

  await run("a copy slip is approved and completed", async () => {
    await page.goto(`${BASE}/dashboard/doc-gia/phieu-sao-chup`, { waitUntil: "networkidle" });
    await page.getByRole("row", { name: new RegExp(copySlip) }).click();
    await visible(page.getByText("Số bản").first());
    await page.getByRole("region", { name: "Thao tác" }).getByRole("button", { name: "Duyệt", exact: true }).click();
    await visible(page.locator("h1").getByText("Đã duyệt", { exact: true }));
    await page.getByRole("button", { name: "Hoàn thành" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Hoàn thành" }).click();
    await visible(page.locator("h1").getByText("Đã hoàn thành", { exact: true }));
  });

  await run("the reading room files a slip for a walk-in reader and sends it", async () => {
    await page.goto(`${BASE}/dashboard/doc-gia/phieu-su-dung`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Lập phiếu cho độc giả" }).click();
    await page.locator("#ns-reader").fill("E2E");
    await page.getByRole("option").first().click();
    await page.locator("#ns-purpose").fill(`${TAG} lập tại quầy`);
    await page.locator("#ns-file").fill(TAG);
    await page.getByRole("option", { name: new RegExp(`${TAG} Hồ sơ B`) }).click();
    await page.getByRole("button", { name: "Gửi duyệt" }).click();
    await page.waitForURL(/\/phieu-su-dung\/UR-/);
    await visible(page.locator("h1").getByText("Chờ duyệt", { exact: true }));
  });

  // ---- feedback ---------------------------------------------------------------------------------
  await run("feedback is read, marked seen and answered; the reader sees the answer", async () => {
    await page.goto(`${BASE}/dashboard/doc-gia/gop-y`, { waitUntil: "networkidle" });
    await page.getByRole("row", { name: new RegExp(`${TAG} Cần bổ sung`) }).click();
    await visible(page.getByText("Xin bổ sung bản quét hồ sơ A"));
    await page.getByLabel("Phản hồi cho độc giả").fill("Đã bổ sung bản quét chất lượng cao.");
    await page.getByRole("button", { name: "Gửi phản hồi" }).click();
    await visible(page.getByText("Phản hồi đã gửi"));
    const rp = await readerCtx.newPage();
    await rp.goto(`${BASE}/portal/gop-y/${feedback}`, { waitUntil: "networkidle" });
    await visible(rp.getByText("Đã bổ sung bản quét chất lượng cao."));
    await rp.close();
  });

  // ---- readers, groups, templates, settings (Document Admin) ----------------------------------
  adminPage = await admin.newPage();
  page = adminPage;
  watch(page, "admin");

  await run("a reader is created at the counter and given online access", async () => {
    counterEmail = `e2e.counter.${RUN}@example.com`;
    await page.goto(`${BASE}/dashboard/doc-gia/doc-gia`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { level: 1, name: "Danh sách độc giả" }));
    await page.getByRole("button", { name: "Thêm mới" }).click();
    await page.locator("#f-full_name").fill(`${TAG} Độc giả tại quầy`);
    await page.locator("#f-email").fill(counterEmail);
    await page.locator("#f-organization").fill("Viện Sử học");
    await page.getByRole("button", { name: "Lưu" }).click();
    await visible(page.getByText("Đã thêm mới").first());
    await page.getByRole("searchbox", { name: "Tìm kiếm" }).fill(TAG);
    await page.getByRole("row", { name: new RegExp(`${TAG} Độc giả tại quầy`) }).click();
    await visible(page.getByText("Độc giả chưa có tài khoản đăng nhập"));
    await page.getByRole("button", { name: "Tạo tài khoản và cấp liên kết" }).click();
    const link = page.getByRole("textbox", { name: "Liên kết đặt mật khẩu" });
    await visible(link);
    expect(/\/dat-mat-khau\?key=/.test(await link.inputValue()), "no one-time link");
    await page.screenshot({ path: `${OUT}/slips_reader_access.png` });
    await page.getByRole("button", { name: "Đã chuyển cho người dùng" }).click();
    await visible(page.getByText(/Tài khoản đăng nhập:/));
    await page.getByText("In thẻ độc giả").scrollIntoViewIfNeeded();
    await visible(page.getByRole("link", { name: /In thẻ độc giả/ }));
  });

  await run("a reader group takes its fonds from a grid", async () => {
    await page.goto(`${BASE}/dashboard/doc-gia/nhom-doc-gia`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Thêm mới" }).click();
    await page.locator("#f-group_name").fill(`${TAG} Nhóm`);
    await page.locator("#f-fonds_scope").selectOption("Chỉ các phông được chọn");
    await page.getByRole("button", { name: "Thêm dòng" }).click();
    await page.locator("table input[role=combobox]").last().fill(TAG);
    await page.getByRole("option", { name: new RegExp(`${TAG} Phông`) }).click();
    await page.screenshot({ path: `${OUT}/slips_group_grid.png` });
    await page.getByRole("button", { name: "Lưu" }).click();
    await visible(page.getByText("Đã thêm mới").first());
    created.unshift(["Reader Group", `${TAG} Nhóm`]);
  });

  await run("a request template adds a purpose that the reader's slip form offers", async () => {
    await page.goto(`${BASE}/dashboard/doc-gia/mau-phieu`, { waitUntil: "networkidle" });
    await page.getByRole("row", { name: /Mẫu mặc định — Phiếu yêu cầu sử dụng/ }).click();
    await page.getByRole("button", { name: "Thêm dòng" }).click(); // only the purposes grid applies to a usage slip template
    await page.getByLabel("Mục đích").last().fill(`${TAG} Mục đích riêng`);
    await page.getByRole("button", { name: "Lưu" }).click();
    await visible(page.getByText("Đã lưu thay đổi"));
    // the reader opens a draft slip and sees it
    const added = await readerCtx.request.post(`${API}.basket.add_to_basket`, { headers: readerHeaders, data: { kind: "file", name: fileA, target: "usage" } });
    expect(added.ok(), "add to basket failed");
    const draft = (await added.json()).message.request;
    const rp = await readerCtx.newPage();
    await rp.goto(`${BASE}/portal/phieu/${draft}`, { waitUntil: "networkidle" });
    await visible(rp.getByRole("button", { name: `${TAG} Mục đích riêng` }));
    await rp.screenshot({ path: `${OUT}/slips_reader_purposes.png` });
    await rp.close();
    await readerCtx.request.post(`${API}.basket.discard_draft`, { headers: readerHeaders, data: { doctype: "Usage Request", name: draft } });
  });

  await run("the reader settings are one form and a change is saved", async () => {
    await page.goto(`${BASE}/dashboard/doc-gia/thiet-lap-doc-gia`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { level: 1, name: "Thiết lập độc giả" }));
    const days = page.locator("#f-renewal_days");
    await days.fill("9");
    await page.getByRole("button", { name: "Lưu thiết lập" }).click();
    await visible(page.getByText("Đã lưu thiết lập"));
    await page.reload({ waitUntil: "networkidle" });
    expect((await page.locator("#f-renewal_days").inputValue()) === "9", "the setting was not kept");
    await page.screenshot({ path: `${OUT}/slips_settings.png` });
  });

  // ---- phone ----------------------------------------------------------------------------------------
  await run("the queue and the slip fit a phone", async () => {
    const phone = await newContext({ width: 390, height: 844 }, await officerCtx.storageState());
    page = await phone.newPage();
    watch(page, "phone");
    for (const [label, path] of [["queue", "/dashboard/doc-gia/phieu-su-dung"], ["slip", `/dashboard/doc-gia/phieu-su-dung/${usageSecret}`],
                                  ["readers", "/dashboard/doc-gia/doc-gia"], ["feedback", "/dashboard/doc-gia/gop-y"]]) {
      await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
      const extra = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(extra <= 0, `${label}: horizontal overflow of ${extra}px`);
      await page.screenshot({ path: `${OUT}/slips_phone_${label}.png` });
    }
    await phone.close();
  });
} finally {
  // ---- clean up -----------------------------------------------------------------------------------------
  const problemsRemoving = [];
  for (const doctype of ["Usage Request", "Copy Request", "Reader Feedback"]) {
    const rows = (await (await admin.request.get(`${BASE}/api/resource/${encodeURIComponent(doctype)}?fields=${encodeURIComponent('["name","docstatus","purpose","subject"]')}&limit_page_length=500`, { headers: adminHeaders })).json()).data || [];
    for (const row of rows.filter((r) => `${r.purpose || ""}${r.subject || ""}`.includes(TAG))) {
      if (row.docstatus === 1) await admin.request.post(`${BASE}/api/method/frappe.client.cancel`, { headers: adminHeaders, data: { doctype, name: row.name } });
      await admin.request.delete(`${BASE}/api/resource/${encodeURIComponent(doctype)}/${row.name}`, { headers: adminHeaders });
    }
  }
  const counter = counterEmail ? (await (await admin.request.get(`${BASE}/api/resource/Reader?filters=${encodeURIComponent(JSON.stringify([["email", "=", counterEmail]]))}`)).json()).data || [] : [];
  for (const row of counter) await admin.request.delete(`${BASE}/api/resource/Reader/${row.name}`, { headers: adminHeaders });
  await admin.request.put(`${BASE}/api/resource/Reader%20Settings/Reader%20Settings`, { headers: adminHeaders, data: {
    max_requests_per_day: settingsBefore.max_requests_per_day, max_copy_requests_per_day: settingsBefore.max_copy_requests_per_day,
    max_open_requests: settingsBefore.max_open_requests, max_items_per_request: settingsBefore.max_items_per_request,
    block_when_overdue: settingsBefore.block_when_overdue, renewal_days: settingsBefore.renewal_days } });
  // the purpose added to the default usage template
  const templates = (await (await admin.request.get(`${BASE}/api/resource/Request%20Template?filters=${encodeURIComponent(JSON.stringify([["kind", "=", "Phiếu yêu cầu sử dụng"]]))}`)).json()).data || [];
  for (const t of templates) {
    const doc = (await (await admin.request.get(`${BASE}/api/resource/Request%20Template/${encodeURIComponent(t.name)}`)).json()).data;
    const purposes = (doc.purposes || []).filter((p) => !String(p.purpose).includes(TAG));
    if (purposes.length !== (doc.purposes || []).length) await admin.request.put(`${BASE}/api/resource/Request%20Template/${encodeURIComponent(t.name)}`, { headers: adminHeaders, data: { purposes } });
  }
  for (const [doctype, name] of created) {
    const response = await admin.request.delete(`${BASE}/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`, { headers: adminHeaders });
    if (!response.ok()) problemsRemoving.push(`${doctype} ${name}: ${response.status()}`);
  }
  if (problemsRemoving.length) console.log(`NOTE could not remove: ${problemsRemoving.join("; ")}`);
  await browser.close();
}

if (problems.length) {
  console.log(`FAIL console problems:\n  ${[...new Set(problems)].join("\n  ")}`);
  process.exitCode = 1;
}
console.log(process.exitCode ? "RESULT: failed" : "RESULT: all steps passed");
