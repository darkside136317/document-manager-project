// Browser end-to-end flow of the report screens and the inventory of the fonds (Playwright).
//
//   accounts: ../accounts.py (e2e.admin, e2e.officer, e2e.cataloger, e2e.leader) with DM_E2E_PASSWORD set; run `down` afterwards
//   DM_E2E_PASSWORD=... OUT_DIR=out PW_CHANNEL=msedge node reports.mjs
//
// The hub lists the reports the user may run; a report is filtered (with filters that hang on each other), shows
// totals and a chart, downloads as Excel and CSV and prints with the unit's header; the reader reports are for the
// reading room, not for a cataloguer; an inventory is built from the system's figures, counted, completed and
// reported with its differences. The archive data created for the run is removed at the end.
import { chromium } from "playwright";
import fs from "node:fs";

const PW = process.env.DM_E2E_PASSWORD || (() => { throw new Error("Set DM_E2E_PASSWORD"); })();
const OUT = process.env.OUT_DIR || "out";
fs.mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE_URL || "http://localhost:8888";
const RUN = Date.now() % 1000000;
const TAG = `E2E-R${RUN}`;
const created = [];

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
    try { await page.screenshot({ path: `${OUT}/reports_fail_${++step}.png` }); } catch { /* the page may be gone */ }
  }
}
const expect = (cond, msg) => { if (!cond) throw new Error(msg); };
const visible = (locator, timeout = 10000) => locator.first().waitFor({ state: "visible", timeout });
const nav = () => page.getByRole("navigation", { name: "Điều hướng chính" });

async function login(context, email) {
  const response = await context.request.post(`${BASE}/api/method/login`, { form: { usr: email, pwd: PW } });
  expect(response.ok(), `login of ${email} failed (${response.status()})`);
}
const csrfFrom = async (context, path) => (await (await context.request.get(`${BASE}${path}`)).text()).match(/"csrf(?:_token)?":\s*"([^"]+)"/)?.[1];

// ---- data ----------------------------------------------------------------------------------------------
const admin = await newContext();
await login(admin, "e2e.admin@example.com");
const adminHeaders = { "X-Frappe-CSRF-Token": await csrfFrom(admin, "/dashboard"), "Content-Type": "application/json" };
async function make(doctype, values) {
  const response = await admin.request.post(`${BASE}/api/resource/${encodeURIComponent(doctype)}`, { headers: adminHeaders, data: values });
  expect(response.ok(), `create ${doctype}: ${response.status()} ${(await response.text()).slice(0, 200)}`);
  const name = (await response.json()).data.name;
  created.unshift([doctype, name]);
  return name;
}
const CODE = `E2E-C${RUN}`;
const agency = await make("Archival Agency", { agency_name: `${TAG} Cơ quan` });
const fonds = await make("Fonds", { fonds_name: `${TAG} Phông`, fonds_code: CODE, archival_agency: agency, start_year: 1990, end_year: 2005, total_boxes: 5 });
const group = await make("Record Group", { group_title: `${TAG} Khối`, fonds });
const catalog = await make("Catalog", { catalog_title: `${TAG} Mục lục`, record_group: group, fonds });
const base = { fonds, record_group: group, catalog, status: "Đã hoàn thành", confidentiality_level: "Thường" };
const files = [];
for (const [i, [title, start, pages]] of [["A", "1995-03-04", 10], ["B", "1996-05-06", 5], ["C", "2001-07-08", 0]].entries()) {
  files.push(await make("Archival File", { ...base, file_title: `${TAG} Hồ sơ ${title}`, file_number: `0${i + 1}`, start_date: start, total_pages: pages }));
}
for (const [i, file] of files.entries()) {
  await make("Archive Document", { document_title: `${TAG} Văn bản ${i + 1}`, archival_file: file, document_number: `VB-${i + 1}`, author: `${TAG} Bộ Nội vụ`, document_date: `1995-0${i + 1}-02`, page_count: i + 2 });
}

let officerCtx; let catalogerCtx; let inventoryName;
try {
  page = await admin.newPage();
  watch(page, "admin");

  await run("the hub lists the reports by group and the sidebar has its entry", async () => {
    await page.goto(`${BASE}/dashboard/bao-cao`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Thống kê, báo cáo", level: 1 }));
    for (const group of ["Phông, mục lục, hồ sơ, văn bản", "Thống kê", "Độc giả và khai thác"]) await visible(page.getByRole("heading", { name: group }));
    expect((await page.locator("main a[href*='/dashboard/bao-cao/']").count()) >= 11, "fewer than 11 reports offered");
    await visible(nav().getByRole("link", { name: "Báo cáo, thống kê" }));
    await visible(nav().getByRole("link", { name: "Tổng kiểm kê phông" }));
    await page.screenshot({ path: `${OUT}/reports_hub.png` });
  });

  await run("the fonds report counts every level of the new fonds", async () => {
    await page.getByRole("link", { name: /Báo cáo phông lưu trữ/ }).click();
    await visible(page.getByRole("heading", { name: "Báo cáo phông lưu trữ", level: 1 }));
    await page.locator("#f-q").fill(CODE);
    await page.getByRole("button", { name: "Xem báo cáo" }).click();
    const row = page.getByRole("row", { name: new RegExp(CODE) });
    await visible(row);
    const text = await row.innerText();
    expect(text.includes(`${TAG} Phông`) && text.includes(agency) && text.includes("1990 – 2005"), `row: ${text}`);
    expect(/\b3\b[\s\S]*\b3\b/.test(text), `files and documents not counted: ${text}`);
    await visible(page.getByRole("row", { name: /Tổng cộng/ }));
    expect(page.url().includes("q="), "the filter is not in the address");
    await page.screenshot({ path: `${OUT}/reports_fonds.png` });
  });

  await run("filters that hang on each other search inside the one above", async () => {
    await page.goto(`${BASE}/dashboard/bao-cao/ho-so`, { waitUntil: "networkidle" });
    await page.locator("#f-fonds").fill(TAG);
    await page.getByRole("option", { name: new RegExp(`${TAG} Phông`) }).first().click();
    await page.locator("#f-record_group").click();
    await visible(page.getByRole("option", { name: new RegExp(`${TAG} Khối`) }));
    expect((await page.getByRole("listbox").getByRole("option").count()) === 1, "the group search is not narrowed to the fonds");
    await page.getByRole("option", { name: new RegExp(`${TAG} Khối`) }).click();
    await page.getByRole("button", { name: "Xem báo cáo" }).click();
    await visible(page.getByRole("row", { name: new RegExp(`${TAG} Hồ sơ A`) }));
    expect((await page.locator("tbody tr").count()) === 3, "expected the three files of the fonds");
    await visible(page.getByRole("row", { name: /Tổng cộng/ }).getByText("15"));
    await page.getByRole("link", { name: `${TAG} Hồ sơ A` }).click();
    await page.waitForURL(/\/dashboard\/ho-so\/AF-/);
  });

  await run("a statistic has its chart and can be regrouped", async () => {
    await page.goto(`${BASE}/dashboard/bao-cao/thong-ke-phong?fonds=${encodeURIComponent(fonds)}`, { waitUntil: "networkidle" });
    await visible(page.locator("figure").getByText(`${TAG} Phông`));
    await visible(page.getByRole("row", { name: new RegExp(`${TAG} Phông`) }));
    await page.locator("#f-group_by").selectOption("Năm hình thành hồ sơ");
    await page.getByRole("button", { name: "Xem báo cáo" }).click();
    for (const year of ["1995", "1996", "2001"]) await visible(page.getByRole("row", { name: new RegExp(year) }));
    await page.screenshot({ path: `${OUT}/reports_stats.png` });
  });

  await run("the result downloads as Excel and CSV", async () => {
    await page.goto(`${BASE}/dashboard/bao-cao/van-ban?fonds=${encodeURIComponent(fonds)}`, { waitUntil: "networkidle" });
    await visible(page.getByRole("row", { name: new RegExp(`${TAG} Văn bản 1`) }));
    const [excel] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Excel" }).click()]);
    expect(/^bao-cao-van-ban-.*\.xlsx$/.test(excel.suggestedFilename()), `file name ${excel.suggestedFilename()}`);
    const bytes = fs.readFileSync(await excel.path());
    expect(bytes.subarray(0, 2).toString() === "PK" && bytes.includes(Buffer.from("xl/")), "not an xlsx file");
    const [csv] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "CSV" }).click()]);
    const text = fs.readFileSync(await csv.path(), "utf8");
    expect(text.startsWith("﻿") && text.includes(`${TAG} Văn bản 2`) && text.includes("VB-3"), `csv: ${text.slice(0, 200)}`);
    expect(text.includes("02/02/1995") || text.includes("02/01/1995"), "dates are not in day/month/year");
  });

  await run("the printable page has the unit's header, the filters and the signatures", async () => {
    const [printed] = await Promise.all([page.waitForEvent("popup"), page.getByRole("link", { name: "In", exact: true }).click()]);
    await printed.waitForLoadState("domcontentloaded");
    const text = await printed.locator("body").innerText();
    expect(/BÁO CÁO VĂN BẢN, TÀI LIỆU/i.test(text), "no title");
    expect(text.includes(`${TAG} Văn bản 1`) && text.includes("Người lập biểu") && text.includes("Thủ trưởng đơn vị"), "missing rows or signatures");
    expect(text.includes("Phông:") && text.includes(`${TAG} Phông`), "the filters are not printed");
    await printed.screenshot({ path: `${OUT}/reports_print.png`, fullPage: true });
    await printed.close();
    const pdf = await admin.request.get(`${BASE}/api/method/document_manager.document_manager.api.reports.print_report?slug=phong&format=pdf`);
    expect(pdf.ok() && (await pdf.body()).subarray(0, 4).toString() === "%PDF", "no pdf");
  });

  officerCtx = await newContext();
  await login(officerCtx, "e2e.officer@example.com");
  page = await officerCtx.newPage();
  watch(page, "officer");
  await run("the reading room has the reader reports and sees the readers", async () => {
    await page.goto(`${BASE}/dashboard/bao-cao`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Độc giả và khai thác" }));
    await page.getByRole("link", { name: /Báo cáo độc giả/ }).click();
    await visible(page.getByRole("row", { name: /E2E Reader/ }));
    await page.goto(`${BASE}/dashboard/bao-cao/phieu-qua-han`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Phiếu đang sử dụng và quá hạn", level: 1 }));
    await page.getByLabel("Cả phiếu chưa đến hạn trả").check();
    await page.getByRole("button", { name: "Xem báo cáo" }).click();
    await page.waitForTimeout(800);
    expect((await nav().getByRole("link", { name: "Tổng kiểm kê phông" }).count()) === 0, "the officer is offered the inventory");
  });

  catalogerCtx = await newContext();
  await login(catalogerCtx, "e2e.cataloger@example.com");
  page = await catalogerCtx.newPage();
  watch(page, "cataloger");
  await run("a cataloguer has the archive reports but not the reader ones", async () => {
    await page.goto(`${BASE}/dashboard/bao-cao`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Phông, mục lục, hồ sơ, văn bản" }));
    expect((await page.getByRole("heading", { name: "Độc giả và khai thác" }).count()) === 0, "reader reports offered");
    expect((await page.getByRole("link", { name: /Báo cáo độc giả/ }).count()) === 0, "the reader report is listed");
    await page.goto(`${BASE}/dashboard/bao-cao/doc-gia`, { waitUntil: "networkidle" });
    await visible(page.getByText("Không mở được báo cáo"));
  });

  page = await admin.newPage();
  watch(page, "admin");
  await run("an inventory is made from the figures of the system", async () => {
    await page.goto(`${BASE}/dashboard/kiem-ke`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Thêm mới" }).first().click();
    await page.locator("#f-check_title").fill(`${TAG} Kiểm kê`);
    await page.locator("#f-fonds").fill(TAG);
    await page.getByRole("option", { name: new RegExp(`${TAG} Phông`) }).first().click();
    await page.getByRole("button", { name: "Lưu" }).click();
    await page.getByText("Đã thêm mới").first().waitFor();
    await page.getByRole("row", { name: new RegExp(`${TAG} Kiểm kê`) }).click();
    await visible(page.getByRole("button", { name: "Lập danh sách phông" }));
    await page.getByRole("button", { name: "Lập danh sách phông" }).click();
    await visible(page.getByRole("button", { name: "Hoàn thành kiểm kê" }));
    const lineFonds = page.locator("[role=dialog] table input[role=combobox]").first();
    await visible(lineFonds);
    expect((await lineFonds.inputValue()) === `${TAG} Phông`, "the fonds line is not the fonds of the check");
    expect((await page.getByLabel("Hồ sơ (sổ sách)").first().inputValue()) === "3", "the recorded files are not 3");
    expect((await page.getByLabel("Văn bản (sổ sách)").first().inputValue()) === "3", "the recorded documents are not 3");
    expect((await page.getByLabel("Hộp (sổ sách)").first().inputValue()) === "5", "the recorded boxes are not 5");
    await page.screenshot({ path: `${OUT}/reports_inventory.png` });
  });

  await run("the physical count gives the difference and the check is completed and locked", async () => {
    await page.getByRole("button", { name: "Hoàn thành kiểm kê" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Hoàn thành" }).click();
    await visible(page.getByText(/Còn \d+ phông chưa được đánh dấu đã kiểm/));
    await page.getByLabel("Hồ sơ (thực tế)").first().fill("2"); // files counted: one less than the books
    await page.getByLabel("Đã kiểm").first().check();
    await page.getByRole("button", { name: "Lưu", exact: true }).click();
    await page.getByText("Đã lưu thay đổi").first().waitFor();
    await page.getByRole("row", { name: new RegExp(`${TAG} Kiểm kê`) }).click(); // saving closes the form: open it again
    await visible(page.getByRole("button", { name: "Hoàn thành kiểm kê" }));
    expect((await page.getByLabel("Hồ sơ (thực tế)").first().inputValue()) === "2", "the count was not saved");
    await page.getByRole("button", { name: "Hoàn thành kiểm kê" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Hoàn thành" }).click();
    await visible(page.getByText("Đợt kiểm kê đã hoàn thành"));
    expect((await page.getByRole("button", { name: "Lập danh sách phông" }).count()) === 0, "a completed check can still be rebuilt");
    expect(await page.getByLabel("Hồ sơ (thực tế)").first().isDisabled(), "the figures are not locked");
  });

  await run("the inventory report shows the difference and prints as a record", async () => {
    await page.getByRole("link", { name: "Xem báo cáo" }).click();
    await visible(page.getByRole("heading", { name: "Tổng kiểm kê phông", level: 1 }));
    await visible(page.getByText(`${TAG} Kiểm kê`));
    const row = page.getByRole("row", { name: new RegExp(`${TAG} Phông`) });
    await visible(row);
    expect((await row.innerText()).includes("-1"), `no difference of -1: ${await row.innerText()}`);
    await page.screenshot({ path: `${OUT}/reports_inventory_report.png` });
    inventoryName = new URL(page.url()).searchParams.get("inventory_check");
    expect(Boolean(inventoryName), "the check is not in the address");
  });

  await run("the report screens fit a phone", async () => {
    const phone = await newContext({ width: 375, height: 812 });
    await login(phone, "e2e.admin@example.com");
    const small = await phone.newPage();
    for (const path of ["/dashboard/bao-cao", `/dashboard/bao-cao/ho-so?fonds=${encodeURIComponent(fonds)}`]) {
      await small.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
      await small.waitForTimeout(500);
      const overflow = await small.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow <= 1, `${path} overflows the phone by ${overflow}px`);
    }
    await small.screenshot({ path: `${OUT}/reports_phone.png` });
    await phone.close();
  });
} finally {
  const problemsRemoving = [];
  if (inventoryName) await admin.request.delete(`${BASE}/api/resource/Inventory%20Check/${inventoryName}`, { headers: adminHeaders });
  for (const check of (await (await admin.request.get(`${BASE}/api/resource/Inventory%20Check?filters=${encodeURIComponent(JSON.stringify([["check_title", "like", `${TAG}%`]]))}`)).json()).data || []) {
    await admin.request.delete(`${BASE}/api/resource/Inventory%20Check/${check.name}`, { headers: adminHeaders });
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
