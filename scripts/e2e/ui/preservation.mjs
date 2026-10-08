// Browser end-to-end flow of the preservation screens (Playwright): backups, integrity checks and restores.
//
//   accounts: ../accounts.py (e2e.admin, e2e.preserver, e2e.cataloger) with DM_E2E_PASSWORD set; run `down` afterwards
//   python make_sample_files.py samples   (once)
//   DM_E2E_PASSWORD=... OUT_DIR=out SAMPLES_DIR=samples PW_CHANNEL=msedge node preservation.mjs
//
// Needs the queue workers. Two documents with real files are backed up (files and database); a file is then lost,
// an integrity check finds it, says a backup can restore it and the restore brings back exactly the same bytes;
// the database backup is verified and downloaded, and its restore is prepared as a checked runbook (nothing is run).
// The archive data and the batches created for the run are removed at the end.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const PW = process.env.DM_E2E_PASSWORD || (() => { throw new Error("Set DM_E2E_PASSWORD"); })();
const OUT = process.env.OUT_DIR || "out";
const SAMPLES = process.env.SAMPLES_DIR || "samples";
fs.mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE_URL || "http://localhost:8888";
const API = `${BASE}/api/method/document_manager.document_manager.api`;
const RUN = Date.now() % 1000000;
const TAG = `E2E-B${RUN}`;
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
    try { await page.screenshot({ path: `${OUT}/preservation_fail_${++step}.png` }); } catch { /* the page may be gone */ }
  }
}
const expect = (cond, msg) => { if (!cond) throw new Error(msg); };
const visible = (locator, timeout = 10000) => locator.first().waitFor({ state: "visible", timeout });
const nav = () => page.getByRole("navigation", { name: "Điều hướng chính" });

async function login(context, email) {
  const response = await context.request.post(`${BASE}/api/method/login`, { form: { usr: email, pwd: PW } });
  expect(response.ok(), `login of ${email} failed (${response.status()})`);
}
const csrfFrom = async (context, path_) => (await (await context.request.get(`${BASE}${path_}`)).text()).match(/"csrf(?:_token)?":\s*"([^"]+)"/)?.[1];

// ---- data: a fonds with two documents that have real files ---------------------------------------------
const admin = await newContext();
await login(admin, "e2e.admin@example.com");
const csrf = await csrfFrom(admin, "/dashboard");
const headers = { "X-Frappe-CSRF-Token": csrf, "Content-Type": "application/json" };
async function make(doctype, values) {
  const response = await admin.request.post(`${BASE}/api/resource/${encodeURIComponent(doctype)}`, { headers, data: values });
  expect(response.ok(), `create ${doctype}: ${response.status()} ${(await response.text()).slice(0, 200)}`);
  const name = (await response.json()).data.name;
  created.unshift([doctype, name]);
  return name;
}
const agency = await make("Archival Agency", { agency_name: `${TAG} Cơ quan` });
const fonds = await make("Fonds", { fonds_name: `${TAG} Phông`, fonds_code: TAG, archival_agency: agency });
const group = await make("Record Group", { group_title: `${TAG} Khối`, fonds });
const catalog = await make("Catalog", { catalog_title: `${TAG} Mục lục`, record_group: group, fonds });
const file = await make("Archival File", { file_title: `${TAG} Hồ sơ`, file_number: "01", catalog, record_group: group, fonds, status: "Đã hoàn thành" });
const documents = [];
const sampleFiles = ["Bao cao nam 2020.pdf", "Quyet dinh 123 ve luu tru.pdf"];
const original = {};
for (const name of sampleFiles) {
  const buffer = fs.readFileSync(path.join(SAMPLES, name));
  const upload = await admin.request.post(`${BASE}/api/method/upload_file`, { headers: { "X-Frappe-CSRF-Token": csrf }, multipart: { file: { name: `${TAG}-${name}`, mimeType: "application/pdf", buffer }, is_private: "1", folder: "Home/Attachments" } });
  expect(upload.ok(), `upload ${name}: ${upload.status()}`);
  const fileUrl = (await upload.json()).message.file_url;
  const added = await admin.request.post(`${API}.archive.add_document_from_file`, { headers, data: { archival_file: file, file_url: fileUrl, title: `${TAG} ${name}` } });
  expect(added.ok(), `add document: ${added.status()} ${(await added.text()).slice(0, 200)}`);
  const docName = (await added.json()).message.name || (await added.json()).message.document;
  documents.push(docName);
  created.unshift(["Archive Document", docName]);
  const attachment = (await (await admin.request.get(`${BASE}/api/resource/Archive%20Document/${docName}`)).json()).data.file_attachment;
  original[docName] = { url: attachment, bytes: (await (await admin.request.get(`${BASE}${attachment}`)).body()) };
}

let preserverCtx; let catalogerCtx; let backupName; let dbBackupName; let checkName; let restoreName;
const batches = { backup: [], integrity: [], restore: [] };
const statusOf = async (kind, name) => (await (await admin.request.get(`${API}.preservation.get_job`, { params: { kind, name } })).json()).message;

try {
  page = await admin.newPage();
  watch(page, "admin");

  await run("the preservation menu and the overview of the backups", async () => {
    await page.goto(`${BASE}/dashboard/bao-quan/sao-luu`, { waitUntil: "networkidle" });
    for (const label of ["Sao lưu", "Kiểm tra toàn vẹn", "Khôi phục"]) await visible(nav().getByRole("link", { name: label, exact: true }));
    await visible(page.getByRole("heading", { name: "Sao lưu", level: 1 }));
    for (const tile of ["Bản sao lưu gần nhất", "Sao lưu theo lịch", "Kho tệp sao lưu", "Dung lượng đĩa còn trống"]) await visible(page.getByText(tile));
    await page.screenshot({ path: `${OUT}/preservation_backups.png` });
  });

  await run("a file backup is started, runs in the background and copies both files", async () => {
    await page.getByRole("button", { name: "Sao lưu mới" }).click();
    await page.getByRole("dialog").locator("select").first().selectOption("Tệp tài liệu");
    await page.getByRole("dialog").locator("input[role=combobox]").first().fill(TAG);
    await page.getByRole("option", { name: new RegExp(`${TAG} Phông`) }).first().click();
    await page.getByRole("button", { name: "Bắt đầu" }).click();
    const drawer = page.getByRole("dialog");
    await visible(drawer.getByRole("heading", { name: /Sao lưu: BK-/ }));
    backupName = (await drawer.getByRole("heading", { name: /Sao lưu: BK-/ }).innerText()).match(/BK-[\w-]+/)[0];
    batches.backup.push(backupName);
    await drawer.getByText("Thành công", { exact: true }).waitFor({ timeout: 120000 });
    await visible(drawer.getByText(/2 \/ 2 tệp/));
    await visible(drawer.getByRole("link", { name: "Tải bảng kê (manifest)" }));
    const manifest = await (await admin.request.get(`${API}.preservation.download_backup`, { params: { name: backupName, which: "manifest" } })).text();
    const lines = manifest.trim().split("\n").map((l) => JSON.parse(l));
    expect(lines.length === 2 && lines.every((l) => /^[0-9a-f]{64}$/.test(l.sha256) && documents.includes(l.document)), `manifest: ${manifest.slice(0, 300)}`);
    await page.screenshot({ path: `${OUT}/preservation_backup_done.png` });
  });

  await run("a database backup is verified, downloads as gzip and its restore is only prepared", async () => {
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Sao lưu mới" }).click();
    await page.getByRole("dialog").locator("select").first().selectOption("Cơ sở dữ liệu");
    await page.getByRole("button", { name: "Bắt đầu" }).click();
    const drawer = page.getByRole("dialog");
    await visible(drawer.getByRole("heading", { name: /Sao lưu: BK-/ }));
    dbBackupName = (await drawer.getByRole("heading", { name: /Sao lưu: BK-/ }).innerText()).match(/BK-[\w-]+/)[0];
    batches.backup.push(dbBackupName);
    await drawer.getByText("Thành công", { exact: true }).waitFor({ timeout: 180000 });
    await drawer.getByRole("button", { name: "Kiểm tra bản sao lưu" }).click();
    await visible(drawer.getByText(/Bản sao lưu hợp lệ/));
    const dump = await admin.request.get(`${API}.preservation.download_backup`, { params: { name: dbBackupName } });
    const bytes = await dump.body();
    expect(dump.ok() && bytes[0] === 0x1f && bytes[1] === 0x8b && bytes.length > 1000, `the dump is not gzip (${dump.status()}, ${bytes.length} bytes)`);
    await drawer.getByRole("button", { name: /Khôi phục từ bản này/ }).click();
    await visible(drawer.getByText(/set-maintenance-mode on/));
    await visible(drawer.getByText(/Tự khôi phục đang tắt/));
    const restoreLink = await drawer.getByRole("button", { name: /^RS-/ }).innerText();
    batches.restore.push(restoreLink);
    await page.screenshot({ path: `${OUT}/preservation_db_restore.png` });
  });

  await run("a lost file is found by an integrity check that says a backup can restore it", async () => {
    const lost = documents[0];
    const record = (await (await admin.request.get(`${BASE}/api/resource/File?filters=${encodeURIComponent(JSON.stringify([["file_url", "=", original[lost].url]]))}`)).json()).data[0];
    const removed = await admin.request.delete(`${BASE}/api/resource/File/${record.name}`, { headers });
    expect(removed.ok(), `could not delete the file record: ${removed.status()}`);
    expect((await admin.request.get(`${BASE}${original[lost].url}`)).status() !== 200, "the file is still served");
    await page.goto(`${BASE}/dashboard/bao-quan/kiem-tra`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Kiểm tra mới" }).click();
    await page.getByRole("dialog").locator("select").first().selectOption("Tệp tài liệu");
    await page.getByRole("dialog").locator("input[role=combobox]").first().fill(TAG);
    await page.getByRole("option", { name: new RegExp(`${TAG} Phông`) }).first().click();
    await page.getByRole("button", { name: "Bắt đầu" }).click();
    const drawer = page.getByRole("dialog");
    await visible(drawer.getByRole("heading", { name: /Kiểm tra toàn vẹn: IC-/ }));
    checkName = (await drawer.getByRole("heading", { name: /IC-/ }).innerText()).match(/IC-[\w-]+/)[0];
    batches.integrity.push(checkName);
    await drawer.getByText("Phát hiện lỗi", { exact: true }).first().waitFor({ timeout: 120000 });
    await visible(drawer.getByText("Mất tệp"));
    await visible(drawer.getByText("Phục hồi được"));
    await visible(drawer.getByRole("button", { name: /Chuyển sang khôi phục \(1 tài liệu/ }));
    await page.screenshot({ path: `${OUT}/preservation_check.png` });
  });

  await run("the restore batch brings back the very same bytes", async () => {
    const drawer = page.getByRole("dialog");
    await drawer.getByRole("button", { name: /Chuyển sang khôi phục/ }).click();
    await page.waitForURL(/bao-quan\/khoi-phuc\?open=RS-/);
    restoreName = new URL(page.url()).searchParams.get("open");
    batches.restore.push(restoreName);
    const restoreDrawer = page.getByRole("dialog");
    await restoreDrawer.getByText("Thành công", { exact: true }).first().waitFor({ timeout: 120000 });
    await visible(restoreDrawer.getByText("Đã khôi phục", { exact: true }));
    const lost = documents[0];
    const attachment = (await (await admin.request.get(`${BASE}/api/resource/Archive%20Document/${lost}`)).json()).data.file_attachment;
    const back = await admin.request.get(`${BASE}${attachment}`);
    expect(back.ok(), `the restored file is not served (${back.status()})`);
    expect(Buffer.compare(await back.body(), original[lost].bytes) === 0, "the restored bytes differ from the original");
    await page.screenshot({ path: `${OUT}/preservation_restore.png` });
    const job = await statusOf("integrity", checkName);
    expect(job.items.some((i) => i.code === "FILE_MISSING" && i.status === "Đã khôi phục"), "the finding was not marked restored");
  });

  await run("a second check is clean and the database and metadata checks run too", async () => {
    await page.goto(`${BASE}/dashboard/bao-quan/kiem-tra`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Kiểm tra mới" }).click();
    await page.getByRole("dialog").locator("input[role=combobox]").first().fill(TAG);
    await page.getByRole("option", { name: new RegExp(`${TAG} Phông`) }).first().click();
    await page.getByRole("button", { name: "Bắt đầu" }).click();
    const drawer = page.getByRole("dialog");
    await visible(drawer.getByRole("heading", { name: /Kiểm tra toàn vẹn: IC-/ }));
    const name = (await drawer.getByRole("heading", { name: /IC-/ }).innerText()).match(/IC-[\w-]+/)[0];
    batches.integrity.push(name);
    await drawer.getByText(/Hoàn thành|Phát hiện lỗi/).first().waitFor({ timeout: 180000 });
    const job = await statusOf("integrity", name);
    expect(job.errors === 0, `errors after the restore: ${JSON.stringify(job.items?.filter((i) => i.severity === "Lỗi"))}`);
    expect(job.total_checked === 2, `checked ${job.total_checked} documents`);
    await visible(drawer.getByText(/Thiếu siêu dữ liệu/));
  });

  await run("the restore page lists the batches and a database restore ends as a runbook", async () => {
    await page.goto(`${BASE}/dashboard/bao-quan/khoi-phuc`, { waitUntil: "networkidle" });
    const table = page.getByRole("table", { name: "Khôi phục" });
    await visible(table.getByRole("row", { name: new RegExp(restoreName) }));
    const dbRow = table.getByRole("row", { name: new RegExp(batches.restore[0]) });
    await dbRow.click();
    const drawer = page.getByRole("dialog");
    await drawer.getByRole("button", { name: "Chạy khôi phục" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Chạy" }).click();
    await drawer.getByText("Cần thao tác thủ công", { exact: true }).first().waitFor({ timeout: 120000 });
    await visible(drawer.getByText(/set-maintenance-mode on/));
    const job = await statusOf("restore", batches.restore[0]);
    expect(job.log.includes("--force restore") && !job.log.includes("--db-root-password s"), "the runbook is wrong or leaks a password");
    await page.screenshot({ path: `${OUT}/preservation_runbook.png` });
  });

  catalogerCtx = await newContext();
  await login(catalogerCtx, "e2e.cataloger@example.com");
  page = await catalogerCtx.newPage();
  watch(page, "cataloger");
  await run("a cataloguer has no preservation menu and cannot open its pages", async () => {
    await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
    expect((await nav().getByRole("link", { name: "Kiểm tra toàn vẹn" }).count()) === 0, "preservation is offered to a cataloguer");
    await page.goto(`${BASE}/dashboard/bao-quan/sao-luu`, { waitUntil: "networkidle" });
    await visible(page.getByText(/không có quyền/i));
  });

  preserverCtx = await newContext();
  await login(preserverCtx, "e2e.preserver@example.com");
  page = await preserverCtx.newPage();
  watch(page, "preserver");
  await run("a preservation officer has the preservation menu and no administration of users", async () => {
    await page.goto(`${BASE}/dashboard/bao-quan/sao-luu`, { waitUntil: "networkidle" });
    await visible(page.getByRole("heading", { name: "Sao lưu", level: 1 }));
    expect((await nav().getByRole("link", { name: "Người dùng", exact: true }).count()) === 0, "a preserver is offered the users");
    await page.goto(`${BASE}/dashboard/bao-quan/kiem-tra`, { waitUntil: "networkidle" });
    await visible(page.getByRole("row", { name: new RegExp(checkName) }));
  });

  page = await admin.newPage();
  watch(page, "admin");
  await run("old backups can be deleted from the screen", async () => {
    await page.goto(`${BASE}/dashboard/bao-quan/sao-luu`, { waitUntil: "networkidle" });
    const table = page.getByRole("table", { name: "Sao lưu" });
    await table.getByRole("row", { name: new RegExp(dbBackupName) }).click();
    const drawer = page.getByRole("dialog");
    await drawer.getByRole("button", { name: "Xóa" }).first().click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Xóa" }).click();
    await page.waitForTimeout(1500);
    expect((await table.getByRole("row", { name: new RegExp(dbBackupName) }).count()) === 0, "the backup is still listed");
    batches.backup = batches.backup.filter((b) => b !== dbBackupName);
  });

  await run("the preservation screens fit a phone", async () => {
    const phone = await newContext({ width: 375, height: 812 });
    await login(phone, "e2e.admin@example.com");
    const small = await phone.newPage();
    for (const route of ["sao-luu", "kiem-tra", "khoi-phuc"]) {
      await small.goto(`${BASE}/dashboard/bao-quan/${route}`, { waitUntil: "networkidle" });
      await small.waitForTimeout(500);
      const overflow = await small.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow <= 1, `${route} overflows the phone by ${overflow}px`);
    }
    await small.screenshot({ path: `${OUT}/preservation_phone.png` });
    await phone.close();
  });
} finally {
  const problemsRemoving = [];
  for (const [kind, names] of Object.entries(batches)) {
    for (const name of names) {
      const response = await admin.request.post(`${API}.preservation.delete_job`, { headers, data: { kind, name } });
      if (!response.ok() && response.status() !== 404 && response.status() !== 417) problemsRemoving.push(`${kind} ${name}: ${response.status()}`);
    }
  }
  let pending = created.slice();
  for (let pass = 0; pass < 3 && pending.length; pass++) {
    const left = [];
    for (const [doctype, name] of pending) {
      const response = await admin.request.delete(`${BASE}/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`, { headers });
      if (!response.ok() && response.status() !== 404) left.push([doctype, name, response.status()]);
    }
    pending = left.map(([doctype, name]) => [doctype, name]);
    if (pass === 2) problemsRemoving.push(...left.map(([doctype, name, status]) => `${doctype} ${name}: ${status}`));
  }
  if (problemsRemoving.length) console.log(`NOTE could not remove: ${problemsRemoving.join("; ")}`);
  await browser.close();
}

if (problems.length) {
  console.log(`FAIL console problems:\n  ${[...new Set(problems)].join("\n  ")}`);
  process.exitCode = 1;
}
console.log(process.exitCode ? "RESULT: failed" : "RESULT: all steps passed");
