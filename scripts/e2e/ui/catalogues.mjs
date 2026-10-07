// Browser end-to-end flow (Playwright) against a running stack.
//
//   cd scripts/e2e/ui && npm install                      (once; add `npx playwright install chromium`
//                                                          or set PW_CHANNEL=msedge / chrome to use an installed browser)
//   create the accounts: see ../accounts.py, with DM_E2E_PASSWORD set; run `down` afterwards
//   python make_sample_files.py samples                    (only for cataloguing.mjs)
//   DM_E2E_PASSWORD=... OUT_DIR=out SAMPLES_DIR=samples node catalogues.mjs
//
// Screenshots land in OUT_DIR; every step prints PASS/FAIL and the exit code is non-zero on a failure.
import { chromium } from "playwright";
import fs from "node:fs";

const PW = process.env.DM_E2E_PASSWORD || (() => { throw new Error("Set DM_E2E_PASSWORD"); })();
const OUT = process.env.OUT_DIR || "out";
fs.mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE_URL || "http://localhost:8888";
const API = `${BASE}/api/method/document_manager.document_manager.api.crud`;
const TYPE = `UIF Chuc danh ${Date.now() % 100000}`;

const browser = await chromium.launch(process.env.PW_CHANNEL ? { channel: process.env.PW_CHANNEL } : {});
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "vi-VN" });
const page = await context.newPage();
const problems = [];
page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error" && !/favicon/.test(m.text())) problems.push(`console: ${m.text()}`); });
page.on("dialog", (d) => d.accept());

let step = 0;
const ok = (name) => console.log(`PASS ${String(++step).padStart(2, "0")} ${name}`);
const fail = (name, e) => { console.log(`FAIL ${name}: ${e.message.split("\n")[0]}`); process.exitCode = 1; };
async function run(name, fn) {
  try { await fn(); ok(name); } catch (e) { fail(name, e); await page.screenshot({ path: `${OUT}/flow_fail_${step + 1}.png` }); step++; }
}
const expect = (cond, msg) => { if (!cond) throw new Error(msg); };
const save = () => page.getByRole("button", { name: "Lưu" }).click();

await context.request.post(`${BASE}/api/method/login`, { form: { usr: "e2e.admin@example.com", pwd: PW } });
const csrf = (await (await context.request.get(`${BASE}/dashboard`)).text()).match(/"csrf_token":\s*"([^"]+)"/)?.[1];

try {
  await run("create a multi-level dictionary type", async () => {
    await page.goto(`${BASE}/dashboard/danh-muc/loai-tu-dien`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: /Thêm mới/ }).first().click();
    await page.locator("#f-type_name").fill(TYPE);
    await page.locator("#f-is_hierarchical").check();
    await save();
    await page.getByText("Đã thêm mới").waitFor();
    await page.getByRole("cell", { name: TYPE }).waitFor();
  });

  await run("required field is reported before any request", async () => {
    await page.getByRole("button", { name: /Thêm mới/ }).first().click();
    await save();
    await page.getByText("Vui lòng nhập tên loại từ điển").waitFor();
    await page.keyboard.press("Escape");
  });

  await run("search narrows the list", async () => {
    await page.getByLabel("Tìm kiếm").fill("khong-co-gi-khop-xyz");
    await page.getByText("Không tìm thấy kết quả").waitFor();
    await page.getByLabel("Tìm kiếm").fill(TYPE);
    await page.getByRole("cell", { name: TYPE }).waitFor();
  });

  await run("pick the dictionary in the tree page and add a root value", async () => {
    await page.goto(`${BASE}/dashboard/danh-muc/tu-dien`, { waitUntil: "networkidle" });
    const combo = page.getByRole("combobox").first();
    await combo.click();
    await combo.fill(TYPE);
    await page.getByRole("option", { name: new RegExp(TYPE) }).click();
    await page.getByRole("button", { name: "Thêm giá trị" }).click();
    await page.locator("#f-entry_value").fill("Lãnh đạo");
    await save();
    await page.getByRole("button", { name: "Lãnh đạo" }).waitFor();
  });

  await run("add a child value under the root", async () => {
    const row = page.locator("li[role=treeitem]").filter({ hasText: "Lãnh đạo" }).first();
    await row.hover();
    await row.getByRole("button", { name: "Thêm mục con" }).click();
    await page.locator("#f-entry_value").fill("Giám đốc");
    await save();
    await page.getByText("Đã thêm mới").first().waitFor();
    await page.locator("li[role=treeitem]").filter({ hasText: "Lãnh đạo" }).first().getByRole("button", { name: "Mở rộng" }).click();
    await page.getByRole("button", { name: "Giám đốc", exact: true }).waitFor();
  });

  await run("duplicate sibling is rejected with a readable message", async () => {
    await page.getByRole("button", { name: "Thêm giá trị" }).click();
    await page.locator("#f-entry_value").fill("Lãnh đạo");
    await save();
    await page.getByText(/đã có trong cùng cấp/).waitFor();
    await page.keyboard.press("Escape");
  });

  await run("edit a value and delete a leaf", async () => {
    await page.getByRole("button", { name: "Giám đốc", exact: true }).click();
    await page.locator("#f-entry_value").fill("Giám đốc điều hành");
    await save();
    await page.getByRole("button", { name: "Giám đốc điều hành" }).waitFor();
    await page.getByRole("button", { name: "Giám đốc điều hành" }).click();
    await page.getByRole("button", { name: "Xóa" }).first().click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Xóa" }).click();
    await page.getByText("Đã xóa").first().waitFor();
  });

  await run("a parent that still has children cannot be deleted (server message shown)", async () => {
    const row = page.locator("li[role=treeitem]").filter({ hasText: "Lãnh đạo" }).first();
    await row.hover();
    await row.getByRole("button", { name: "Thêm mục con" }).click();
    await page.locator("#f-entry_value").fill("Phó giám đốc");
    await save();
    await page.getByText("Đã thêm mới").first().waitFor();
    await page.getByRole("button", { name: "Lãnh đạo", exact: true }).click();
    await page.getByRole("button", { name: "Xóa" }).first().click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Xóa" }).click();
    await page.getByRole("alertdialog").getByRole("alert").waitFor();
    await page.screenshot({ path: `${OUT}/flow_delete_blocked.png` });
    await page.getByRole("alertdialog").getByRole("button", { name: "Hủy" }).click();
    await page.keyboard.press("Escape");
  });

  await run("theme toggle switches to the dark palette", async () => {
    await page.getByRole("button", { name: /giao diện tối/ }).click();
    expect((await page.locator("html").getAttribute("data-theme")) === "dark", "data-theme not dark");
    await page.screenshot({ path: `${OUT}/flow_dark.png` });
    await page.getByRole("button", { name: /giao diện sáng/ }).click();
  });

  await run("mobile layout: menu opens as a drawer and content fits", async () => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(!overflow, "page scrolls horizontally on a phone");
    await page.getByRole("button", { name: "Mở menu" }).click();
    await page.getByRole("navigation", { name: "Điều hướng chính" }).getByRole("link", { name: "Từ điển nhập nhanh" }).waitFor();
    await page.screenshot({ path: `${OUT}/flow_mobile_menu.png` });
  });
} finally {
  const headers = { "X-Frappe-CSRF-Token": csrf, "Content-Type": "application/json" };
  const listed = await (await context.request.get(`${API}.get_list`, {
    params: { doctype: "Quick Entry Dictionary", filters: JSON.stringify({ dictionary_type: TYPE }), page_size: "200" },
  })).json();
  const rows = listed.message?.data || [];
  for (const row of [...rows.filter((r) => r.parent_entry), ...rows.filter((r) => !r.parent_entry)]) {
    await context.request.post(`${API}.delete`, { headers, data: { doctype: "Quick Entry Dictionary", name: row.name } });
  }
  await context.request.post(`${API}.delete`, { headers, data: { doctype: "Dictionary Type", name: TYPE } });
  console.log("cleanup done:", rows.length, "values + 1 type");
  console.log("problems:", problems.length ? "\n" + [...new Set(problems)].join("\n") : "none");
  await browser.close();
}
