// Browser end-to-end flow of the administration screens (Playwright): users, staff groups, role matrix, log, monitor, settings.
//
//   accounts: ../accounts.py (e2e.admin, e2e.cataloger, e2e.officer, e2e.preserver, three old log rows) with DM_E2E_PASSWORD set;
//   run `down` afterwards
//   DM_E2E_PASSWORD=... OUT_DIR=out PW_CHANNEL=msedge node admin.mjs
//
// An administrator adds a staff account, hands over its one-time link, changes its roles and locks it; a group grants a role to
// its members; the log is filtered, downloaded and cleaned (only the three old rows ../accounts.py plants); nobody else gets in.
import { chromium } from "playwright";
import fs from "node:fs";

const PW = process.env.DM_E2E_PASSWORD || (() => { throw new Error("Set DM_E2E_PASSWORD"); })();
const OUT = process.env.OUT_DIR || "out";
fs.mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE_URL || "http://localhost:8888";
const API = `${BASE}/api/method/document_manager.document_manager.api`;
const RUN = Date.now() % 1000000;
const TAG = `E2E-A${RUN}`;
const NEW_MAIL = `e2e.newstaff${RUN}@example.com`;
const SPARE_MAIL = `e2e.spare${RUN}@example.com`;
const GROUP = `${TAG} Nhóm`;

const browser = await chromium.launch(process.env.PW_CHANNEL ? { channel: process.env.PW_CHANNEL } : {});
const problems = [];
const watch = (page, label) => {
  page.on("pageerror", (e) => problems.push(`${label} pageerror: ${e.message}`));
  page.on("console", (m) => {
    if ((m.type() === "error" || m.type() === "warning") && !/favicon|status of 4\d\d|Failed to load resource/.test(m.text())) problems.push(`${label} console: ${m.text()}`);
  });
};
const newContext = (viewport = { width: 1440, height: 900 }) => browser.newContext({ viewport, locale: "vi-VN", acceptDownloads: true });

let step = 0;
let page;
async function run(name, fn) {
  try { await fn(); console.log(`PASS ${String(++step).padStart(2, "0")} ${name}`); } catch (e) {
    console.log(`FAIL ${name}: ${e.message.split("\n").slice(0, 3).join(" ")}`); process.exitCode = 1;
    try { await page.screenshot({ path: `${OUT}/admin_fail_${++step}.png` }); } catch { /* the page may be gone */ }
  }
}
const expect = (cond, msg) => { if (!cond) throw new Error(msg); };
const visible = (locator, timeout = 10000) => locator.first().waitFor({ state: "visible", timeout });
const nav = () => page.getByRole("navigation", { name: "Điều hướng chính" });
const row = (text) => page.getByRole("row").filter({ hasText: text });
const dialog = () => page.getByRole("dialog");

async function login(context, email, password = PW) {
  const response = await context.request.post(`${BASE}/api/method/login`, { form: { usr: email, pwd: password } });
  return response;
}
const loginOk = async (context, email) => {
  const response = await login(context, email);
  expect(response.ok(), `login of ${email} failed (${response.status()})`);
};
const overflowOf = (p) => p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
const searchUsers = async (text) => {
  await page.getByLabel("Tìm người dùng").fill(text);
  await page.waitForTimeout(900);
};
const staffAdminEntries = ["Người dùng", "Phân quyền vai trò", "Nhật ký hệ thống", "Giám sát hệ thống", "Thông tin đơn vị", "Cơ cấu tổ chức", "Nhóm cán bộ", "Thiết lập hệ thống"];

const admin = await newContext();
await loginOk(admin, "e2e.admin@example.com");
let keepMin = null;
const spare = [];
try {
  page = await admin.newPage();
  watch(page, "admin");

  await run("the administration menu lists the screens of an administrator", async () => {
    await page.goto(`${BASE}/dashboard/quan-tri/nguoi-dung`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Người dùng", level: 1 }));
    for (const label of staffAdminEntries) await visible(nav().getByRole("link", { name: label, exact: true }));
    await page.screenshot({ path: `${OUT}/admin_users.png` });
  });

  await run("users are searched, filtered by role and marked when they are you", async () => {
    await searchUsers("e2e.preserver");
    await visible(row("e2e.preserver@example.com"));
    expect((await row("e2e.cataloger@example.com").count()) === 0, "the search kept an unrelated account");
    await searchUsers("");
    await visible(row("e2e.cataloger@example.com"));
    await page.getByLabel("Lọc theo vai trò").selectOption({ label: "Cán bộ bảo quản" });
    await page.waitForTimeout(900);
    await visible(row("e2e.preserver@example.com"));
    expect((await row("e2e.cataloger@example.com").count()) === 0, "the role filter kept a cataloguer");
    await page.getByLabel("Lọc theo vai trò").selectOption({ label: "Mọi vai trò" });
    await page.getByLabel("Lọc theo tình trạng").selectOption({ label: "Đã khóa" });
    await page.waitForTimeout(900);
    expect((await row("e2e.preserver@example.com").count()) === 0, "an active account is listed as locked");
    await page.getByLabel("Lọc theo tình trạng").selectOption({ label: "Mọi tình trạng" });
    await searchUsers("e2e.admin");
    await visible(row("e2e.admin@example.com").filter({ hasText: "Bạn" }));
  });

  let linkPath = "";
  await run("a new account needs a name and an email, then shows its one-time link once", async () => {
    await page.getByRole("button", { name: "Thêm người dùng" }).click();
    await visible(dialog());
    await dialog().getByRole("button", { name: "Tạo", exact: true }).click();
    await visible(dialog().getByRole("alert"));
    await dialog().locator("input[type=email]").fill(NEW_MAIL);
    await dialog().locator("input[type=text]").first().fill("Nhân viên");
    await dialog().locator("input[type=text]").nth(1).fill(`Mới ${RUN}`);
    await dialog().locator("label", { hasText: "Biên mục viên" }).locator("input").check();
    await dialog().getByRole("button", { name: "Tạo", exact: true }).click();
    const input = page.getByRole("textbox", { name: "Liên kết đặt mật khẩu" });
    await visible(input);
    const url = await input.inputValue();
    expect(/\/dat-mat-khau\?key=/.test(url), `unexpected link ${url}`);
    linkPath = new URL(url).pathname + new URL(url).search;
    await page.screenshot({ path: `${OUT}/admin_link.png` });
    await page.getByRole("button", { name: "Đã chuyển cho người dùng" }).click();
    await searchUsers(NEW_MAIL);
    await visible(row(NEW_MAIL).filter({ hasText: "Biên mục viên" }));
  });

  let staffCtx;
  await run("the new user chooses a password from the link and only gets what the role allows", async () => {
    staffCtx = await newContext();
    const p = await staffCtx.newPage();
    watch(p, "newstaff");
    await p.goto(`${BASE}${linkPath}`, { waitUntil: "networkidle" });
    await visible(p.getByRole("heading", { name: "Đặt mật khẩu" }));
    await p.locator("#pwd").fill(PW);
    await p.locator("#again").fill(PW);
    await p.getByRole("button", { name: "Lưu mật khẩu và đăng nhập" }).click();
    await p.waitForURL(/\/(dashboard|portal)/);
    await p.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
    const sidebar = p.getByRole("navigation", { name: "Điều hướng chính" });
    await visible(sidebar.getByRole("link", { name: "Biên mục hồ sơ, văn bản" }));
    expect((await sidebar.getByRole("link", { name: "Người dùng", exact: true }).count()) === 0, "a cataloguer is offered the users");
    await p.goto(`${BASE}/dashboard/quan-tri/nguoi-dung`, { waitUntil: "networkidle" });
    await visible(p.getByText(/không có quyền/i));
    await p.close();
    const again = await newContext();
    const q = await again.newPage();
    await q.goto(`${BASE}${linkPath}`, { waitUntil: "networkidle" });
    await visible(q.getByText("không hợp lệ hoặc đã được sử dụng"));
    await again.close();
  });

  await run("roles change, the account is locked and unlocked, a new link can be issued", async () => {
    await searchUsers(NEW_MAIL);
    await row(NEW_MAIL).click();
    await visible(dialog());
    await dialog().locator("label", { hasText: "Cán bộ phòng đọc" }).locator("input").check();
    await dialog().getByRole("button", { name: "Lưu", exact: true }).click();
    await visible(page.getByText("Đã lưu thay đổi"));
    await dialog().getByRole("button", { name: "Khóa", exact: true }).click();
    await visible(page.getByText("Đã khóa tài khoản"));
    const refused = await login(await newContext(), NEW_MAIL);
    expect(!refused.ok(), "a locked account could sign in");
    await dialog().getByRole("button", { name: "Mở khóa", exact: true }).click();
    await visible(page.getByText("Đã mở khóa tài khoản"));
    expect((await login(await newContext(), NEW_MAIL)).ok(), "an unlocked account cannot sign in");
    await dialog().getByRole("button", { name: "Cấp liên kết mật khẩu" }).click();
    await visible(page.getByRole("textbox", { name: "Liên kết đặt mật khẩu" }));
    await page.getByRole("button", { name: "Đã chuyển cho người dùng" }).click();
    await dialog().getByRole("button", { name: "Đóng", exact: true }).last().click(); // the footer one: the icon has the same name
    await visible(row(NEW_MAIL).filter({ hasText: "Cán bộ phòng đọc" }));
  });

  await run("an administrator can neither lock, demote nor delete themselves", async () => {
    await searchUsers("e2e.admin");
    await row("e2e.admin@example.com").click();
    await visible(dialog());
    await dialog().getByRole("button", { name: "Khóa", exact: true }).click();
    await visible(dialog().getByText("Không thể tự khóa tài khoản của chính mình"));
    await dialog().locator("label", { hasText: "Quản trị tài liệu" }).locator("input").uncheck();
    await dialog().getByRole("button", { name: "Lưu", exact: true }).click();
    await visible(dialog().getByText("Không thể tự bỏ quyền Quản trị tài liệu"));
    await dialog().getByRole("button", { name: "Xóa", exact: true }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Xóa" }).click();
    await visible(dialog().getByText("Không thể xóa tài khoản của chính mình"));
    await dialog().getByRole("button", { name: "Đóng", exact: true }).last().click(); // the footer one: the icon has the same name
    const me = await (await admin.request.get(`${API}.users.get_user?name=e2e.admin@example.com`)).json();
    expect(me.message.enabled && me.message.roles.includes("Document Admin"), "the administrator lost their account or role");
  });

  await run("an account that was never used can be deleted", async () => {
    await page.getByRole("button", { name: "Thêm người dùng" }).click();
    await visible(dialog());
    await dialog().locator("input[type=email]").fill(SPARE_MAIL);
    await dialog().locator("input[type=text]").first().fill("Dự phòng");
    await dialog().locator("label", { hasText: "Cán bộ bảo quản" }).locator("input").check();
    await dialog().getByRole("button", { name: "Tạo", exact: true }).click();
    await visible(page.getByRole("textbox", { name: "Liên kết đặt mật khẩu" }));
    await page.getByRole("button", { name: "Đã chuyển cho người dùng" }).click();
    spare.push(SPARE_MAIL);
    await searchUsers(SPARE_MAIL);
    await row(SPARE_MAIL).click();
    await dialog().getByRole("button", { name: "Xóa", exact: true }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Xóa" }).click();
    await visible(page.getByText("Đã xóa tài khoản"));
    await page.waitForTimeout(600);
    expect((await row(SPARE_MAIL).count()) === 0, "the deleted account is still listed");
    spare.pop();
  });

  await run("a staff group grants its role to the members and can be removed", async () => {
    await page.goto(`${BASE}/dashboard/quan-tri/nhom-can-bo`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Nhóm cán bộ", level: 1 }));
    await page.getByRole("button", { name: "Thêm nhóm" }).click();
    await visible(dialog());
    await dialog().getByRole("button", { name: "Lưu", exact: true }).click();
    await visible(dialog().getByText("Nhập tên nhóm"));
    await dialog().locator("input[type=text]").first().fill(GROUP);
    await dialog().locator("label", { hasText: "Lãnh đạo" }).locator("input").check();
    await dialog().getByLabel("Tìm cán bộ").fill(NEW_MAIL);
    await dialog().locator("label", { hasText: NEW_MAIL }).locator("input").check();
    await dialog().getByRole("button", { name: "Lưu", exact: true }).click();
    await visible(page.getByText("Đã tạo nhóm"));
    await visible(row(GROUP).filter({ hasText: "1 người" }));
    await page.screenshot({ path: `${OUT}/admin_groups.png` });
    await page.goto(`${BASE}/dashboard/quan-tri/nguoi-dung`, { waitUntil: "networkidle" });
    await searchUsers(NEW_MAIL);
    await visible(row(NEW_MAIL).filter({ hasText: "Lãnh đạo" }).filter({ hasText: GROUP }));
    await page.getByLabel("Lọc theo nhóm").selectOption({ label: GROUP });
    await page.waitForTimeout(900);
    await visible(row(NEW_MAIL));
    await page.getByLabel("Lọc theo nhóm").selectOption({ label: "Mọi nhóm" });
    await page.goto(`${BASE}/dashboard/quan-tri/nhom-can-bo`, { waitUntil: "networkidle" });
    await row(GROUP).click();
    await dialog().getByRole("button", { name: "Xóa", exact: true }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Xóa" }).click();
    await visible(page.getByText("Đã xóa nhóm"));
    await page.waitForTimeout(600);
    expect((await row(GROUP).count()) === 0, "the deleted group is still listed");
  });

  await run("the role matrix shows every role and every group of data", async () => {
    await page.goto(`${BASE}/dashboard/quan-tri/phan-quyen`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Phân quyền vai trò", level: 1 }));
    for (const role of ["Quản trị tài liệu", "Lãnh đạo", "Biên mục viên", "Cán bộ phòng đọc", "Cán bộ bảo quản"]) await visible(page.getByRole("heading", { name: new RegExp(`^${role}`), level: 2 }));
    for (const section of ["Biên mục", "Danh mục", "Độc giả và khai thác", "Bảo quản", "Quản trị"]) await visible(page.getByRole("heading", { name: section, level: 2, exact: true }));
    await page.screenshot({ path: `${OUT}/admin_roles.png` });
  });

  await run("the log is filtered, opened and downloaded as CSV", async () => {
    await page.goto(`${BASE}/dashboard/quan-tri/nhat-ky`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Nhật ký hệ thống", level: 1 }));
    await page.getByLabel("Loại thao tác").selectOption({ label: "Quản lý người dùng" });
    await page.getByPlaceholder(/Từ khóa trong nội dung/).fill(NEW_MAIL);
    await visible(row(NEW_MAIL).filter({ hasText: "Quản lý người dùng" }), 15000);
    await row(NEW_MAIL).first().click();
    await visible(dialog().getByText(/Nhật ký LOG-/).or(dialog().getByRole("heading", { name: /Nhật ký LOG-/ })));
    await dialog().getByRole("button", { name: "Đóng" }).first().click();
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Tải CSV" }).click()]);
    const text = fs.readFileSync(await download.path(), "utf8");
    expect(text.includes("Thời gian") && text.includes(NEW_MAIL), "the CSV lacks the header or the filtered row");
    await page.getByRole("button", { name: "Xóa bộ lọc" }).click();
    await page.screenshot({ path: `${OUT}/admin_logs.png` });
  });

  await run("a clean-up shows what it would delete, refuses recent days and needs the count typed back", async () => {
    await page.getByRole("button", { name: "Dọn dẹp" }).click();
    await visible(dialog());
    const today = new Date().toISOString().slice(0, 10);
    await dialog().locator("input[type=date]").fill(today);
    await dialog().getByRole("button", { name: "Xem trước" }).click();
    await visible(dialog().getByText(/Chỉ được dọn nhật ký cũ hơn 7 ngày/));
    await dialog().locator("input[type=date]").fill("2020-01-16");
    await dialog().getByRole("button", { name: "Xem trước" }).click();
    await visible(dialog().getByText(/Sẽ xóa\s*3\s*dòng/));
    const remove = dialog().getByRole("button", { name: "Xóa", exact: true });
    expect(await remove.isDisabled(), "the clean-up can run without confirmation");
    await dialog().getByLabel(/Gõ lại số dòng/).fill("2");
    expect(await remove.isDisabled(), "the clean-up runs with a wrong count");
    await dialog().getByLabel(/Gõ lại số dòng/).fill("3");
    await remove.click();
    await visible(page.getByText("Đã xóa 3 dòng nhật ký"));
    await page.getByPlaceholder(/Từ khóa trong nội dung/).fill("E2E old log");
    await page.waitForTimeout(900);
    expect((await row("E2E old log").count()) === 0, "the cleaned rows are still listed");
    await page.getByPlaceholder(/Từ khóa trong nội dung/).fill("");
    await page.getByLabel("Loại thao tác").selectOption({ label: "Dọn dẹp nhật ký" });
    await visible(row("Dọn dẹp").first(), 15000);
  });

  await run("the monitor reports services, index, jobs, storage, backups and accounts", async () => {
    await page.goto(`${BASE}/dashboard/quan-tri/giam-sat`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Giám sát hệ thống", level: 1 }));
    for (const region of ["Dịch vụ", "Chỉ mục tìm kiếm", "Công việc nền", "Lưu trữ", "Sao lưu và kiểm tra", "Người dùng và nhật ký"]) await visible(page.getByRole("region", { name: region }), 20000);
    await visible(page.getByText("Meilisearch"));
    await page.screenshot({ path: `${OUT}/admin_monitor.png` });
  });

  await run("unit information, structure and settings are forms; a setting is saved and put back", async () => {
    await page.goto(`${BASE}/dashboard/quan-tri/thong-tin-don-vi`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Thông tin đơn vị", level: 1 }));
    await page.goto(`${BASE}/dashboard/quan-tri/co-cau-to-chuc`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Cơ cấu tổ chức", level: 1 }));
    await page.goto(`${BASE}/dashboard/quan-tri/thiet-lap-he-thong`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Thiết lập hệ thống", level: 1 }));
    const field = page.locator("#f-backup_keep_min");
    await visible(field);
    keepMin = await field.inputValue();
    const changed = String((Number(keepMin) || 3) + 1);
    await field.fill(changed);
    await page.getByRole("button", { name: "Lưu thiết lập" }).click();
    await visible(page.getByText("Đã lưu thiết lập"));
    await page.reload({ waitUntil: "networkidle" });
    expect((await page.locator("#f-backup_keep_min").inputValue()) === changed, "the setting was not kept");
    await page.locator("#f-backup_keep_min").fill(keepMin);
    await page.getByRole("button", { name: "Lưu thiết lập" }).click();
    await visible(page.getByText("Đã lưu thiết lập"));
    keepMin = null;
  });

  for (const [who, email] of [["cataloguer", "e2e.cataloger@example.com"], ["reading room officer", "e2e.officer@example.com"]]) {
    await run(`a ${who} has no user, log or monitor screens`, async () => {
      const ctx = await newContext();
      await loginOk(ctx, email);
      page = await ctx.newPage();
      watch(page, who);
      await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
      for (const label of ["Người dùng", "Phân quyền vai trò", "Nhật ký hệ thống", "Giám sát hệ thống"]) {
        expect((await nav().getByRole("link", { name: label, exact: true }).count()) === 0, `${label} is offered to a ${who}`);
      }
      for (const slug of ["nguoi-dung", "nhat-ky", "giam-sat", "phan-quyen"]) {
        await page.goto(`${BASE}/dashboard/quan-tri/${slug}`, { waitUntil: "networkidle" });
        await visible(page.getByText(/không có quyền/i));
      }
      const api = await ctx.request.get(`${API}.users.list_users`);
      expect(api.status() === 403, `list_users answered ${api.status()} to a ${who}`);
      await ctx.close();
      page = await admin.newPage();
      watch(page, "admin");
    });
  }

  await run("the administration screens fit a phone", async () => {
    const phone = await newContext({ width: 375, height: 812 });
    await loginOk(phone, "e2e.admin@example.com");
    const small = await phone.newPage();
    watch(small, "phone");
    for (const slug of ["nguoi-dung", "nhom-can-bo", "phan-quyen", "nhat-ky", "giam-sat", "thiet-lap-he-thong"]) {
      await small.goto(`${BASE}/dashboard/quan-tri/${slug}`, { waitUntil: "networkidle" });
      await small.waitForTimeout(600);
      const overflow = await overflowOf(small);
      expect(overflow <= 1, `${slug} overflows the phone by ${overflow}px`);
    }
    await small.screenshot({ path: `${OUT}/admin_phone.png` });
    await phone.close();
  });
} finally {
  const headersResponse = await admin.request.get(`${BASE}/dashboard`);
  const csrf = (await headersResponse.text()).match(/"csrf(?:_token)?":\s*"([^"]+)"/)?.[1];
  const headers = { "X-Frappe-CSRF-Token": csrf, "Content-Type": "application/json" };
  const notes = [];
  if (keepMin !== null) { // the setting step stopped half way: put the value back
    const r = await admin.request.put(`${BASE}/api/resource/Document%20Manager%20Settings/Document%20Manager%20Settings`, { headers, data: { backup_keep_min: Number(keepMin) || 3 } });
    if (!r.ok()) notes.push(`setting backup_keep_min not restored (${r.status()})`);
  }
  for (const email of [...spare, NEW_MAIL]) {
    const r = await admin.request.post(`${API}.users.delete_user`, { headers, data: { name: email } });
    if (!r.ok() && ![404, 417].includes(r.status())) notes.push(`${email}: ${r.status()} (accounts.py down removes it)`); // 417: it signed in, so it has records
  }
  if (notes.length) console.log(`NOTE ${notes.join("; ")}`);
  await browser.close();
}

if (problems.length) {
  console.log(`FAIL console problems:\n  ${[...new Set(problems)].join("\n  ")}`);
  process.exitCode = 1;
}
console.log(process.exitCode ? "RESULT: failed" : "RESULT: all steps passed");
