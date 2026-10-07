// Browser end-to-end flow (Playwright) against a running stack.
//
//   cd scripts/e2e/ui && npm install                      (once; add `npx playwright install chromium`
//                                                          or set PW_CHANNEL=msedge / chrome to use an installed browser)
//   create the accounts: see ../accounts.py, with DM_E2E_PASSWORD set; run `down` afterwards
//   python make_sample_files.py samples                    (only for cataloguing.mjs)
//   DM_E2E_PASSWORD=... OUT_DIR=out SAMPLES_DIR=samples node cataloguing.mjs
//
// Screenshots land in OUT_DIR; every step prints PASS/FAIL and the exit code is non-zero on a failure.
import { chromium } from "playwright";
import fs from "node:fs";

const PW = process.env.DM_E2E_PASSWORD || (() => { throw new Error("Set DM_E2E_PASSWORD"); })();
const OUT = process.env.OUT_DIR || "out";
fs.mkdirSync(OUT, { recursive: true });
const SAMPLES = process.env.SAMPLES_DIR || "samples";
const BASE = process.env.BASE_URL || "http://localhost:8888";
const API = `${BASE}/api/method/document_manager.document_manager.api`;
const TAG = `G4 ${Date.now() % 100000}`;
const created = { docs: [], file: null, catalog: null, group: null };

const browser = await chromium.launch(process.env.PW_CHANNEL ? { channel: process.env.PW_CHANNEL } : {});
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "vi-VN" });
const page = await context.newPage();
const problems = [];
page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error" && !/favicon|417|status of 4\d\d/.test(m.text())) problems.push(`console: ${m.text()}`); });
page.on("dialog", (d) => d.accept(d.type() === "prompt" ? `Bộ lọc ${TAG}` : undefined));

let step = 0;
const ok = (name) => console.log(`PASS ${String(++step).padStart(2, "0")} ${name}`);
async function run(name, fn) {
  try { await fn(); ok(name); } catch (e) {
    console.log(`FAIL ${name}: ${e.message.split("\n")[0]}`); process.exitCode = 1;
    await page.screenshot({ path: `${OUT}/g4_fail_${++step}.png` });
  }
}
const expect = (cond, msg) => { if (!cond) throw new Error(msg); };
const save = () => page.getByRole("button", { name: "Lưu" }).click();

await context.request.post(`${BASE}/api/method/login`, { form: { usr: "e2e.admin@example.com", pwd: PW } });
const csrf = (await (await context.request.get(`${BASE}/dashboard`)).text()).match(/"csrf_token":\s*"([^"]+)"/)?.[1];
const headers = { "X-Frappe-CSRF-Token": csrf, "Content-Type": "application/json" };

try {
  await run("the cataloguing tree lists the fonds", async () => {
    await page.goto(`${BASE}/dashboard/bien-muc`, { waitUntil: "networkidle" });
    await page.getByRole("tree").getByRole("button").first().waitFor();
    await page.screenshot({ path: `${OUT}/g4_browser_start.png` });
  });

  await run("add a record group under the first fonds", async () => {
    await page.getByRole("tree").locator("li[role=treeitem] > div button").nth(1).click(); // the fonds title
    await page.getByRole("button", { name: "Thêm khối tài liệu" }).click();
    await page.locator("#f-group_title").fill(`${TAG} Khối`);
    await save();
    await page.getByText("Đã thêm mới").first().waitFor();
    const open = page.getByRole("tree").getByRole("button", { name: "Mở rộng" }).first();
    if (await open.count()) await open.click();
    await page.getByRole("tree").getByRole("button", { name: `${TAG} Khối` }).waitFor();
  });

  await run("add a catalog under the group, then a file under the catalog", async () => {
    await page.getByRole("tree").getByRole("button", { name: `${TAG} Khối` }).click();
    await page.getByRole("button", { name: "Thêm mục lục" }).click();
    await page.locator("#f-catalog_title").fill(`${TAG} Mục lục`);
    await save();
    await page.getByText("Đã thêm mới").first().waitFor();
    await page.getByRole("tree").locator("li[role=treeitem]", { hasText: `${TAG} Khối` }).last().getByRole("button", { name: "Mở rộng" }).click();
    await page.getByRole("tree").getByRole("button", { name: `${TAG} Mục lục` }).click();
    await page.getByRole("button", { name: "Thêm hồ sơ" }).first().click();
    await page.locator("#f-file_title").fill(`${TAG} Hồ sơ quyết định`);
    await page.locator("#f-file_number").fill("HS-01");
    await save();
    await page.waitForURL(/\/dashboard\/ho-so\/AF-/);
    created.file = decodeURIComponent(page.url().split("/ho-so/")[1]);
    await page.getByRole("heading", { name: `${TAG} Hồ sơ quyết định` }).waitFor();
    await page.screenshot({ path: `${OUT}/g4_file_empty.png` });
  });

  await run("the file page shows its breadcrumb and an empty document list", async () => {
    await page.getByRole("navigation", { name: "Vị trí" }).getByText(`${TAG} Mục lục`).waitFor();
    await page.getByText("Hồ sơ chưa có văn bản").waitFor();
  });

  await run("upload two PDFs, an image and a refused text file", async () => {
    await page.getByRole("button", { name: "Tải tệp lên" }).first().click();
    const names = ["Quyet dinh 123 ve luu tru.pdf", "Bao cao nam 2020.pdf", "Anh scan trang 1.png", "ghi chu.txt"];
    await page.locator("input[type=file]").setInputFiles(names.map((n) => `${SAMPLES}/${n}`));
    await page.getByText("không được hỗ trợ").waitFor();
    await page.screenshot({ path: `${OUT}/g4_upload_selected.png` });
    await page.getByRole("button", { name: /Tải lên 3 tệp/ }).click();
    await page.getByText("3/4 hoàn tất").waitFor({ timeout: 60000 });
    await page.screenshot({ path: `${OUT}/g4_upload_done.png` });
    await page.keyboard.press("Escape");
  });

  await run("the uploaded files are documents of the file, counted and listed", async () => {
    await page.getByRole("cell", { name: "Quyet dinh 123 ve luu tru" }).waitFor();
    await page.getByRole("cell", { name: "Bao cao nam 2020" }).waitFor();
    await page.getByRole("cell", { name: "Anh scan trang 1" }).waitFor();
    const list = await (await context.request.get(`${API}.crud.get_list`, { params: { doctype: "Archive Document", filters: JSON.stringify({ archival_file: created.file }) } })).json();
    created.docs = list.message.data.map((d) => d.name);
    expect(created.docs.length === 3, `expected 3 documents, got ${created.docs.length}`);
  });

  await run("background processing finishes: every document becomes searchable", async () => {
    await page.waitForFunction(() => document.body.innerText.match(/3\/3\s*\n?\s*Đã lập chỉ mục/) || document.body.innerText.includes("3/3"), null, { timeout: 90000 });
    await page.screenshot({ path: `${OUT}/g4_file_with_docs.png` });
  });

  await run("a document page previews the PDF and saves its description with dictionary suggestions", async () => {
    await page.getByRole("cell", { name: "Quyet dinh 123 ve luu tru" }).click();
    await page.waitForURL(/\/dashboard\/van-ban\/DOC-/);
    await page.locator("iframe").waitFor();
    const src = await page.locator("iframe").getAttribute("src");
    expect(/preview_file/.test(src), "preview iframe does not use the preview endpoint");
    const frameResponse = await context.request.get(`${BASE}${src}`);
    expect(frameResponse.status() === 200 && (frameResponse.headers()["content-type"] || "").includes("pdf"), `preview endpoint answered ${frameResponse.status()}`);
    await page.locator("#f-document_number").fill("QĐ-123");
    await page.locator("#f-author").fill("Bộ Nội vụ");
    await page.locator("#f-document_date").fill("2020-05-17");
    await save();
    await page.getByText("Đã lưu thay đổi").waitFor();
    await page.screenshot({ path: `${OUT}/g4_document.png` });
  });

  await run("search finds the document by its CONTENT, with a highlight, and by an advanced filter", async () => {
    // saving the description sends the document through processing again: its content reaches the index a few seconds later
    for (let i = 0; i < 24; i++) {
      const found = await (await context.request.get(`${API}.search.search_documents`, { params: { query: "zebra" } })).json();
      if (found.message?.total === 1) break;
      await page.waitForTimeout(2500);
    }
    await page.goto(`${BASE}/dashboard/tim-kiem?tab=van-ban&q=zebra`, { waitUntil: "networkidle" });
    await page.getByText("1 kết quả").waitFor({ timeout: 20000 });
    await page.locator("mark").first().waitFor();
    await page.screenshot({ path: `${OUT}/g4_search_content.png` });
    await page.goto(`${BASE}/dashboard/tim-kiem?tab=van-ban&author=${encodeURIComponent("Nội vụ")}`, { waitUntil: "networkidle" });
    await page.getByText("1 kết quả").waitFor();
    await page.getByRole("link", { name: "Quyet dinh 123 ve luu tru" }).waitFor();
  });

  await run("search of files, saved filter and the URL carries the state", async () => {
    await page.goto(`${BASE}/dashboard/tim-kiem?tab=ho-so`, { waitUntil: "networkidle" });
    await page.getByLabel("Từ khóa").fill(TAG);
    await page.getByRole("button", { name: "Tìm kiếm", exact: true }).click();
    await page.waitForURL(/q=G4/);
    await page.getByRole("cell", { name: `${TAG} Hồ sơ quyết định` }).waitFor();
    await page.getByRole("button", { name: /Nâng cao/ }).click();
    await page.getByRole("button", { name: "Lưu bộ lọc" }).click();
    await page.getByRole("button", { name: `Bộ lọc ${TAG}`, exact: true }).waitFor();
  });

  await run("Ctrl+K finds the file by title and opens it", async () => {
    await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
    await page.keyboard.press("Control+k");
    await page.getByRole("combobox", { name: "Tìm nhanh" }).fill(`${TAG} Hồ sơ`);
    await page.getByRole("option", { name: new RegExp(`${TAG} Hồ sơ quyết định`) }).waitFor();
    await page.screenshot({ path: `${OUT}/g4_palette.png` });
    await page.keyboard.press("ArrowDown");
    await page.getByRole("option", { name: new RegExp(`${TAG} Hồ sơ quyết định`) }).click();
    await page.waitForURL(new RegExp(created.file));
  });

  await run("printing: the file's document list and the document sheet render with the data", async () => {
    const info = await (await context.request.get(`${API}.archive.get_file_overview`, { params: { name: created.file } })).json();
    const html = await (await context.request.get(`${BASE}${info.message.print.contents.view}`)).text();
    expect(html.includes("Quyet dinh 123 ve luu tru") && html.includes("QĐ-123"), "contents print is missing the documents");
    const docInfo = await (await context.request.get(`${API}.archive.get_document_overview`, { params: { name: created.docs[0] } })).json();
    const sheet = await (await context.request.get(`${BASE}${docInfo.message.print.standard.view}`)).text();
    expect(sheet.includes("PHIẾU MÔ TẢ VĂN BẢN"), "document sheet did not render");
    const pdf = await context.request.get(`${BASE}${info.message.print.contents.pdf}`);
    expect(pdf.status() === 200 && (pdf.headers()["content-type"] || "").includes("pdf"), `PDF export answered ${pdf.status()}: ${(await pdf.text()).slice(0, 500)}`);
  });

  await run("replace the file of a document, then delete the document from its page", async () => {
    await page.goto(`${BASE}/dashboard/van-ban/${created.docs[1]}`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Thay tệp" }).first().click();
    await page.locator("input[type=file]").setInputFiles(`${SAMPLES}/Quyet dinh 123 ve luu tru.pdf`);
    await page.getByRole("dialog").getByRole("button", { name: "Thay tệp" }).click();
    await page.getByText("Đã cập nhật tệp của văn bản").waitFor({ timeout: 30000 });
    await page.getByRole("button", { name: "Xóa" }).first().click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Xóa" }).click();
    await page.waitForURL(new RegExp(`/ho-so/${created.file}`));
    await page.getByText("Văn bản trong hồ sơ").waitFor();
  });

  await run("a file that still holds documents cannot be deleted; the message says why", async () => {
    await page.getByRole("button", { name: "Sửa hồ sơ" }).click();
    await page.getByRole("button", { name: "Xóa" }).first().click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Xóa" }).click();
    await page.getByRole("alertdialog").getByRole("alert").waitFor();
    await page.screenshot({ path: `${OUT}/g4_file_delete_blocked.png` });
    await page.getByRole("alertdialog").getByRole("button", { name: "Hủy" }).click();
    await page.keyboard.press("Escape");
  });

  await run("phone layout of the cataloguing browser and the file page fits the screen", async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    for (const path of ["/dashboard/bien-muc", `/dashboard/ho-so/${created.file}`, "/dashboard/tim-kiem"]) {
      await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      if (overflow) {
        const wide = await page.evaluate(() => [...document.querySelectorAll("body *")].filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1).slice(0, 6).map((e) => `${e.tagName}.${String(e.className).slice(0, 60)} right=${Math.round(e.getBoundingClientRect().right)}`));
        console.log("   wide elements:", JSON.stringify(wide));
      }
      expect(!overflow, `${path} scrolls sideways on a phone`);
    }
    await page.goto(`${BASE}/dashboard/ho-so/${created.file}`, { waitUntil: "networkidle" });
    await page.screenshot({ path: `${OUT}/g4_file_mobile.png` });
  });
} finally {
  // remove everything the test created, deepest first
  const del = (doctype, name) => context.request.post(`${API}.crud.delete`, { headers, data: { doctype, name } }).catch(() => null);
  const docs = created.file ? ((await (await context.request.get(`${API}.crud.get_list`, { params: { doctype: "Archive Document", filters: JSON.stringify({ archival_file: created.file }), page_size: "50" } })).json()).message?.data || []) : [];
  for (const d of docs) await del("Archive Document", d.name);
  if (created.file) await del("Archival File", created.file);
  const cats = (await (await context.request.get(`${API}.crud.get_list`, { params: { doctype: "Catalog", search: TAG } })).json()).message?.data || [];
  for (const c of cats) await del("Catalog", c.name);
  const groups = (await (await context.request.get(`${API}.crud.get_list`, { params: { doctype: "Record Group", search: TAG } })).json()).message?.data || [];
  for (const g of groups) await del("Record Group", g.name);
  console.log(`cleanup: ${docs.length} documents, file, ${cats.length} catalog, ${groups.length} group`);
  console.log("problems:", problems.length ? "\n" + [...new Set(problems)].join("\n") : "none");
  await browser.close();
}
