// Browser end-to-end flow of the XML exchange screen (Playwright).
//
//   accounts: ../accounts.py (e2e.admin, e2e.officer) with DM_E2E_PASSWORD set; run `down` afterwards
//   DM_E2E_PASSWORD=... OUT_DIR=out PW_CHANNEL=msedge node exchange.mjs
//
// Needs the queue workers: the export and the import run in the background. The flow searches the archive, previews
// the count, chooses the fields and exports; uploads that file as a copy of the data, rehearses the import (nothing
// is written), imports it, and imports it again (everything already exists); refuses hostile and malformed files;
// reads the history. The archive data created for the run is removed at the end.
import { chromium } from "playwright";
import fs from "node:fs";

const PW = process.env.DM_E2E_PASSWORD || (() => { throw new Error("Set DM_E2E_PASSWORD"); })();
const OUT = process.env.OUT_DIR || "out";
fs.mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE_URL || "http://localhost:8888";
const RUN = Date.now() % 1000000;
const TAG = `E2E-X${RUN}`;
const COPY = `E2E-Y${RUN}`;
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
    try { await page.screenshot({ path: `${OUT}/exchange_fail_${++step}.png` }); } catch { /* the page may be gone */ }
  }
}
const expect = (cond, msg) => { if (!cond) throw new Error(msg); };
const visible = (locator, timeout = 10000) => locator.first().waitFor({ state: "visible", timeout });

async function login(context, email) {
  const response = await context.request.post(`${BASE}/api/method/login`, { form: { usr: email, pwd: PW } });
  expect(response.ok(), `login of ${email} failed (${response.status()})`);
}
const csrfFrom = async (context, path) => (await (await context.request.get(`${BASE}${path}`)).text()).match(/"csrf(?:_token)?":\s*"([^"]+)"/)?.[1];

// ---- data ---------------------------------------------------------------------------------------------
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
const find = async (doctype, filters, fields = ["name"]) =>
  (await (await admin.request.get(`${BASE}/api/resource/${encodeURIComponent(doctype)}?fields=${encodeURIComponent(JSON.stringify(fields))}&filters=${encodeURIComponent(JSON.stringify(filters))}&limit_page_length=50`)).json()).data || [];

const agency = await make("Archival Agency", { agency_name: `${TAG} Cơ quan` });
const fonds = await make("Fonds", { fonds_name: `${TAG} Phông`, fonds_code: TAG, archival_agency: agency, start_year: 1990, end_year: 2005 });
const group = await make("Record Group", { group_title: `${TAG} Khối`, group_code: "K1", fonds });
const catalog = await make("Catalog", { catalog_title: `${TAG} Mục lục`, catalog_number: "M1", record_group: group, fonds });
const base = { fonds, record_group: group, catalog, status: "Đã hoàn thành", confidentiality_level: "Thường" };
const files = [];
for (const [i, title] of ["A", "B", "C"].entries()) files.push(await make("Archival File", { ...base, file_title: `${TAG} Hồ sơ ${title}`, file_number: `0${i + 1}`, total_pages: i + 3 }));
for (const [i, file] of files.entries()) {
  await make("Archive Document", { document_title: `${TAG} Văn bản ${i + 1}`, archival_file: file, document_number: `VB-${i + 1}`, author: `${TAG} Tác giả`, document_date: `1995-0${i + 1}-02` });
}

const nav = () => page.getByRole("navigation", { name: "Điều hướng chính" });
let exported = "";
let officerCtx;

try {
  page = await admin.newPage();
  watch(page, "admin");

  await run("the sidebar and the three tabs of the exchange screen", async () => {
    await page.goto(`${BASE}/dashboard/trao-doi-du-lieu`, { waitUntil: "networkidle" });
    await visible(nav().getByRole("link", { name: "Xuất, nhập XML" }));
    await visible(page.getByRole("heading", { name: "Xuất, nhập dữ liệu XML", level: 1 }));
    for (const tab of ["Xuất XML", "Nhập XML", "Lịch sử"]) await visible(page.getByRole("tab", { name: tab }));
    await visible(page.getByRole("tab", { name: "Xuất XML", selected: true }));
    await visible(page.getByRole("link", { name: "Lược đồ XSD" }));
  });

  await run("an export is searched, counted and its fields chosen", async () => {
    await page.getByRole("radio", { name: "Hồ sơ" }).click();
    await page.locator("#f-query").fill(TAG);
    await page.getByLabel("Kèm cả dữ liệu cấp dưới").check();
    await page.getByRole("button", { name: "Xem trước số lượng" }).click();
    const table = page.getByRole("table", { name: "Số bản ghi sẽ xuất" });
    await visible(table);
    const rows = await table.innerText();
    expect(/Hồ sơ\s+3/.test(rows) && /Văn bản\s+3/.test(rows), `counts are not 3 files and 3 documents: ${rows}`);
    expect(/Phông\s+0\s+1/.test(rows.replace(/\t/g, " ")) || /Phông[\s\S]*1/.test(rows), "the ancestors are not counted");
    await visible(page.getByRole("group", { name: /Văn bản/ }));
    const author = page.getByRole("group", { name: /Văn bản/ }).getByLabel("Tác giả");
    await author.uncheck();
    expect(!(await author.isChecked()), "the author could not be switched off");
    const key = page.getByRole("group", { name: /Hồ sơ/ }).getByLabel("Tiêu đề hồ sơ").first();
    expect(await key.isDisabled(), "a key field can be switched off");
    await page.screenshot({ path: `${OUT}/exchange_export.png` });
  });

  await run("the background export finishes and the XML downloads", async () => {
    await page.getByRole("button", { name: "Xuất XML", exact: true }).click();
    const card = page.locator("section[aria-label^='Xuất XML XJ-']");
    await visible(card);
    await card.getByText(/Đã xuất \d+ bản ghi/).waitFor({ timeout: 120000 });
    await visible(card.getByText("Hoàn thành", { exact: true }));
    expect((await card.innerText()).includes("hồ sơ 3") || /hồ sơ\s*3/.test(await card.innerText()), `summary: ${await card.innerText()}`);
    const [download] = await Promise.all([page.waitForEvent("download"), card.getByRole("link", { name: "Tải tệp XML" }).click()]);
    exported = fs.readFileSync(await download.path(), "utf8");
    expect(exported.startsWith("<?xml") && exported.includes("<ArchiveExchange"), "not an exchange file");
    expect(exported.includes(`<fonds_code>${TAG}</fonds_code>`) && exported.includes('<Fonds ref="true">'), "the fonds is not a reference");
    expect(exported.includes("<ArchivalFile>") && exported.includes(`${TAG} Văn bản 3`), "the files and documents are missing");
    expect(!exported.includes("<author>"), "the author was exported although switched off");
    expect(!/gridfs|content_text|<owner>|<name>/.test(exported), "a system field was exported");
    fs.writeFileSync(`${OUT}/exchange_export.xml`, exported);
    await page.screenshot({ path: `${OUT}/exchange_export_done.png` });
  });

  await run("the file is uploaded and shows what it contains", async () => {
    await page.getByRole("tab", { name: "Nhập XML" }).click();
    const copy = exported.replaceAll(TAG, COPY); // the same tree under other names, so the import has something to add
    await page.getByLabel("Chọn tệp XML").setInputFiles({ name: "e2e-import.xml", mimeType: "application/xml", buffer: Buffer.from(copy, "utf8") });
    await visible(page.getByRole("heading", { name: "2. Nội dung tệp" }), 30000);
    const table = page.getByRole("table", { name: "Số bản ghi trong tệp" });
    const text = await table.innerText();
    expect(/Hồ sơ\s+3/.test(text) && /Văn bản\s+3/.test(text), `the counts are wrong: ${text}`);
    await visible(page.getByRole("heading", { name: "4. Chọn các trường đưa vào cơ sở dữ liệu" }));
    expect((await page.getByRole("group", { name: /Văn bản/ }).getByLabel("Tác giả").count()) === 0, "a field the file lacks is offered");
    await page.screenshot({ path: `${OUT}/exchange_import.png` });
  });

  await run("a dry run reports what would happen and writes nothing", async () => {
    await page.getByLabel("Tạo danh mục còn thiếu").check(); // the copy names a new agency the site does not have yet
    await page.getByRole("button", { name: "Chạy thử" }).click();
    const card = page.locator("section[aria-label^='Nhập XML XJ-']");
    await card.getByText(/Chạy thử \(không ghi dữ liệu\): sẽ thêm \d+/).waitFor({ timeout: 120000 });
    expect(/sẽ thêm 9,/.test(await card.innerText()), `the rehearsal says: ${(await card.innerText()).replace(/\s+/g, " ").slice(0, 400)}`);
    await visible(card.getByText("Chạy thử", { exact: true }));
    expect((await find("Fonds", [["fonds_code", "=", COPY]])).length === 0, "the dry run wrote a fonds");
    expect((await find("Archival Agency", [["agency_name", "=", `${COPY} Cơ quan`]])).length === 0, "the dry run created the agency");
    await visible(page.getByText("Đã chạy thử xong"));
  });

  await run("the import adds the records and a second import finds them all there", async () => {
    await page.getByRole("button", { name: "Nhập dữ liệu", exact: true }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Nhập dữ liệu" }).click();
    const card = page.locator("section[aria-label^='Nhập XML XJ-']");
    await card.getByText(/Đã thêm 9/).waitFor({ timeout: 120000 });
    const fondsCopy = await find("Fonds", [["fonds_code", "=", COPY]], ["name", "fonds_name", "archival_agency", "start_year"]); // a reference carries its keys only: no years
    expect(fondsCopy.length === 1, "the fonds was not imported");
    expect(fondsCopy[0].fonds_name === `${COPY} Phông` && fondsCopy[0].start_year === 0 && fondsCopy[0].archival_agency === `${COPY} Cơ quan`, `fonds: ${JSON.stringify(fondsCopy[0])}`);
    created.unshift(["Fonds", fondsCopy[0].name]);
    const importedFiles = await find("Archival File", [["fonds", "=", fondsCopy[0].name]], ["name", "file_number", "total_pages"]);
    expect(importedFiles.length === 3 && importedFiles.map((f) => f.file_number).sort().join() === "01,02,03", `files: ${JSON.stringify(importedFiles)}`);
    const documents = await find("Archive Document", [["fonds", "=", fondsCopy[0].name]], ["name", "document_number", "author"]);
    expect(documents.length === 3 && documents.every((d) => !d.author), `documents: ${JSON.stringify(documents)}`); // the author was left out of the file
    for (const d of documents) created.unshift(["Archive Document", d.name]);
    for (const f of importedFiles) created.unshift(["Archival File", f.name]);
    for (const [doctype, filters] of [["Catalog", [["fonds", "=", fondsCopy[0].name]]], ["Record Group", [["fonds", "=", fondsCopy[0].name]]]]) {
      for (const row of await find(doctype, filters)) created.unshift([doctype, row.name]);
    }
    await page.screenshot({ path: `${OUT}/exchange_import_done.png` });
    // again, with the same file: nothing new
    await page.getByRole("button", { name: "Nhập dữ liệu", exact: true }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Nhập dữ liệu" }).click();
    await card.getByText(/Đã thêm 0, cập nhật 0, không đổi 0, đã có 6/).waitFor({ timeout: 120000 });
    expect((await find("Archival File", [["fonds", "=", fondsCopy[0].name]])).length === 3, "a second import duplicated the files");
  });

  await run("hostile and malformed files are refused with a reason", async () => {
    const send = (name, text) => page.getByLabel("Chọn tệp XML").setInputFiles({ name, mimeType: "application/xml", buffer: Buffer.from(text, "utf8") });
    await send("entity.xml", '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "b">]><ArchiveExchange version="1.0">&a;</ArchiveExchange>');
    await visible(page.getByRole("alert").getByText(/DOCTYPE, ENTITY/));
    await send("wrong.xml", '<?xml version="1.0"?><ArchiveExchange version="1.0"><Fonds><fonds_name>x</fonds_name><start_year>không phải số</start_year></Fonds></ArchiveExchange>');
    await visible(page.getByRole("heading", { name: "Tệp không đúng định dạng của hệ thống" }));
    await visible(page.getByText(/Dòng \d+:/));
    await send("note.txt", "không phải xml");
    await visible(page.getByRole("alert").getByText("Chỉ nhận tệp có đuôi .xml"));
    expect((await page.getByRole("heading", { name: "2. Nội dung tệp" }).count()) === 0, "a refused file is still shown as analysed");
  });

  await run("the history lists the runs and a run can be read and deleted", async () => {
    await page.getByRole("tab", { name: "Lịch sử" }).click();
    const table = page.getByRole("table", { name: "Lịch sử xuất, nhập XML" });
    await visible(table);
    expect((await table.locator("tbody tr").count()) >= 2, "the history is empty");
    await visible(table.getByText("Xuất").first());
    await visible(table.getByText("Nhập").first());
    const exportRow = table.locator("tbody tr").filter({ hasText: /Xuất/ }).first();
    await exportRow.click();
    const drawer = page.getByRole("dialog");
    await visible(drawer.getByRole("link", { name: "Tải tệp XML" }));
    const before = await table.locator("tbody tr").count();
    await drawer.getByRole("button", { name: "Xóa lượt này" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Xóa" }).click();
    for (let i = 0; i < 30 && (await table.locator("tbody tr").count()) >= before; i++) await page.waitForTimeout(500);
    expect((await table.locator("tbody tr").count()) < before, "the deleted run is still listed");
    await page.screenshot({ path: `${OUT}/exchange_history.png` });
  });

  officerCtx = await newContext();
  await login(officerCtx, "e2e.officer@example.com");
  page = await officerCtx.newPage();
  watch(page, "officer");
  await run("the reading room has no exchange screen", async () => {
    await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
    expect((await nav().getByRole("link", { name: "Xuất, nhập XML" }).count()) === 0, "the officer is offered the exchange");
    await page.goto(`${BASE}/dashboard/trao-doi-du-lieu`, { waitUntil: "networkidle" });
    await visible(page.getByText("Không mở được chức năng trao đổi dữ liệu"));
  });

  await run("the exchange screen fits a phone", async () => {
    const phone = await newContext({ width: 375, height: 812 });
    await login(phone, "e2e.admin@example.com");
    const small = await phone.newPage();
    for (const tab of ["xuat", "nhap", "lich-su"]) {
      await small.goto(`${BASE}/dashboard/trao-doi-du-lieu?tab=${tab}`, { waitUntil: "networkidle" });
      await small.waitForTimeout(500);
      const overflow = await small.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow <= 1, `the ${tab} tab overflows the phone by ${overflow}px`);
    }
    await small.screenshot({ path: `${OUT}/exchange_phone.png` });
    await phone.close();
  });
} finally {
  const problemsRemoving = [];
  for (const row of await find("Data Exchange Job", [["owner", "=", "e2e.admin@example.com"]])) {
    await admin.request.delete(`${BASE}/api/resource/Data%20Exchange%20Job/${row.name}`, { headers: adminHeaders });
  }
  const copiedAgency = await find("Archival Agency", [["agency_name", "=", `${COPY} Cơ quan`]]);
  const seen = new Set();
  // children first; whatever a link still holds is tried again after the others have gone
  let pending = created.filter(([doctype, name]) => !seen.has(`${doctype}/${name}`) && seen.add(`${doctype}/${name}`));
  for (let pass = 0; pass < 3 && pending.length; pass++) {
    const left = [];
    for (const [doctype, name] of pending) {
      const response = await admin.request.delete(`${BASE}/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`, { headers: adminHeaders });
      if (!response.ok() && response.status() !== 404) left.push([doctype, name, response.status()]);
    }
    pending = left.map(([doctype, name]) => [doctype, name]);
    if (pass === 2) problemsRemoving.push(...left.map(([doctype, name, status]) => `${doctype} ${name}: ${status}`));
  }
  for (const row of copiedAgency) await admin.request.delete(`${BASE}/api/resource/Archival%20Agency/${encodeURIComponent(row.name)}`, { headers: adminHeaders });
  if (problemsRemoving.length) console.log(`NOTE could not remove: ${problemsRemoving.join("; ")}`);
  await browser.close();
}

if (problems.length) {
  console.log(`FAIL console problems:\n  ${[...new Set(problems)].join("\n  ")}`);
  process.exitCode = 1;
}
console.log(process.exitCode ? "RESULT: failed" : "RESULT: all steps passed");
