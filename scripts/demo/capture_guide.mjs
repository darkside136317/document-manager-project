/** Capture local dev screens used by the Vietnamese end-user guide.
 * Prerequisite: seed_user_guide.py up. Admin password comes from docker/.env.dev.
 * Set DM_GUIDE_READER_PASSWORD to include authenticated reader screens.
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const root = path.resolve(import.meta.dirname, '../..')
const require = createRequire(path.join(root, 'scripts/e2e/ui/package.json'))
const { chromium } = require('playwright')
const env = fs.readFileSync(path.join(root, 'docker/.env.dev'), 'utf8')
const adminPassword = env.match(/^ADMIN_PASSWORD=(.*)$/m)?.[1]?.replace(/^['"]|['"]$/g, '')
if (!adminPassword) throw new Error('Thiếu ADMIN_PASSWORD trong docker/.env.dev')
const output = path.join(root, 'docs/assets/huong-dan-su-dung')
fs.mkdirSync(output, { recursive: true })
const base = 'http://localhost:8888'
const selected = new Set(process.argv.slice(2))

async function login(context, usr, pwd) {
  const response = await context.request.post(`${base}/api/method/login`, { form: { usr, pwd } })
  if (!response.ok()) throw new Error(`Đăng nhập ${usr} thất bại: HTTP ${response.status()}`)
}

async function recordName(context, doctype, field, value) {
  const query = new URLSearchParams({ doctype, fieldname: 'name', filters: JSON.stringify({ [field]: value }) })
  const response = await context.request.get(`${base}/api/method/frappe.client.get_value?${query}`)
  if (!response.ok()) throw new Error(`Không lấy được bản ghi ${doctype}: HTTP ${response.status()}`)
  const name = (await response.json()).message?.name
  if (!name) throw new Error(`Thiếu dữ liệu mẫu ${doctype}: ${value}`)
  return name
}

async function capture(page, url, file, prepare) {
  if (selected.size && !selected.has(file)) return
  const response = await page.goto(`${base}${url}`, { waitUntil: 'networkidle' })
  if (!response?.ok()) throw new Error(`${url}: HTTP ${response?.status()}`)
  if (prepare) await prepare(page)
  await page.waitForTimeout(350)
  const title = await page.title()
  if (/404|không tìm thấy|lỗi máy chủ/i.test(title)) throw new Error(`${url}: ${title}`)
  const full = new Set(['tong-quan-can-bo.png', 'tai-tep-ho-so.png', 'tra-cuu-doc-gia.png'])
  const drawers = new Set(['tao-muc-luc.png', 'tao-ho-so.png', 'tai-tep-ho-so.png'])
  if (drawers.has(file)) {
    await page.locator('[role="dialog"] > section').screenshot({ path: path.join(output, file) })
  } else if (full.has(file)) {
    await page.screenshot({ path: path.join(output, file), fullPage: false })
  } else {
    const box = await page.locator('main').boundingBox()
    if (!box) throw new Error(`${url}: không tìm thấy vùng nội dung chính`)
    await page.screenshot({
      path: path.join(output, file),
      clip: { x: box.x, y: box.y, width: box.width, height: Math.min(box.height, 740) },
    })
  }
  console.log(file, title)
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  const staff = await browser.newContext({ viewport: { width: 1200, height: 800 }, deviceScaleFactor: 1 })
  await login(staff, 'Administrator', adminPassword)
  const page = await staff.newPage()
  const file = await recordName(staff, 'Archival File', 'file_title', 'HD MẪU - Tổ chức ngày hội đọc sách 2024')
  const document = await recordName(staff, 'Archive Document', 'document_title', 'HD MẪU - Kế hoạch tổ chức ngày hội đọc sách')
  const usage = await recordName(staff, 'Usage Request', 'purpose', 'HD MẪU - Nghiên cứu văn hóa đọc')
  const copy = await recordName(staff, 'Copy Request', 'purpose', 'HD MẪU - Sao chụp tư liệu ngày hội đọc sách')

  for (const [url, name, prepare] of [
    ['/dashboard', 'tong-quan-can-bo.png'],
    ['/dashboard/danh-muc/co-quan-luu-tru', 'danh-muc-co-quan.png', async p => {
      await p.locator('main input[type="search"]').first().fill('HD MẪU')
      await p.waitForTimeout(600)
    }],
    ['/dashboard/danh-muc/phong-luu-tru', 'danh-muc-phong.png', async p => {
      await p.locator('main input[type="search"]').first().fill('HD MẪU')
      await p.waitForTimeout(600)
    }],
    ['/dashboard/bien-muc', 'bien-muc.png', async p => {
      for (const title of ['HD MẪU - UBND tỉnh Minh Hòa', 'HD MẪU - Văn hóa và giáo dục']) {
        const item = p.locator(`button[title="${title}"]`).locator('xpath=ancestor::li[@role="treeitem"][1]')
        await item.getByRole('button', { name: 'Mở rộng' }).click()
      }
      await p.locator('button[title="HD MẪU - Chương trình văn hóa 2024"]').click()
    }],
    ['/dashboard/bien-muc', 'tao-muc-luc.png', async p => {
      const fonds = p.locator('button[title="HD MẪU - UBND tỉnh Minh Hòa"]').locator('xpath=ancestor::li[@role="treeitem"][1]')
      await fonds.getByRole('button', { name: 'Mở rộng' }).click()
      await p.locator('button[title="HD MẪU - Văn hóa và giáo dục"]').click()
      await p.getByRole('button', { name: 'Thêm mục lục' }).click()
    }],
    ['/dashboard/bien-muc', 'tao-ho-so.png', async p => {
      for (const title of ['HD MẪU - UBND tỉnh Minh Hòa', 'HD MẪU - Văn hóa và giáo dục']) {
        const item = p.locator(`button[title="${title}"]`).locator('xpath=ancestor::li[@role="treeitem"][1]')
        await item.getByRole('button', { name: 'Mở rộng' }).click()
      }
      await p.locator('button[title="HD MẪU - Chương trình văn hóa 2024"]').click()
      await p.getByRole('button', { name: 'Thêm hồ sơ' }).first().click()
    }],
    [`/dashboard/ho-so/${file}`, 'chi-tiet-ho-so.png'],
    [`/dashboard/ho-so/${file}`, 'tai-tep-ho-so.png', async p => p.getByRole('button', { name: 'Tải tệp lên' }).first().click()],
    [`/dashboard/van-ban/${document}`, 'chi-tiet-van-ban.png'],
    ['/dashboard/tim-kiem', 'tim-kiem-can-bo.png', async p => {
      await p.getByPlaceholder(/Từ khóa trong tiêu đề/).fill('HD MẪU')
      await p.getByRole('button', { name: 'Tìm kiếm', exact: true }).click()
      await p.waitForTimeout(900)
    }],
    ['/dashboard/doc-gia/dang-ky', 'duyet-dang-ky.png'],
    ['/dashboard/doc-gia/doc-gia', 'danh-sach-doc-gia.png', async p => {
      await p.locator('main input[type="search"]').first().fill('HD MẪU')
      await p.waitForTimeout(600)
    }],
    ['/dashboard/doc-gia/phieu-su-dung', 'hang-doi-phieu-su-dung.png'],
    [`/dashboard/doc-gia/phieu-su-dung/${usage}`, 'xu-ly-phieu-su-dung.png'],
    ['/dashboard/doc-gia/phieu-sao-chup', 'hang-doi-phieu-sao-chup.png'],
    [`/dashboard/doc-gia/phieu-sao-chup/${copy}`, 'xu-ly-phieu-sao-chup.png'],
    ['/dashboard/bao-cao', 'bao-cao.png'],
    ['/dashboard/kiem-ke', 'kiem-ke.png'],
    ['/dashboard/trao-doi-du-lieu', 'trao-doi-xml.png'],
    ['/dashboard/bao-quan/kiem-tra', 'kiem-tra-toan-ven.png'],
    ['/dashboard/quan-tri/phan-quyen', 'phan-quyen.png'],
    ['/dashboard/quan-tri/giam-sat', 'giam-sat.png'],
  ]) await capture(page, url, name, prepare)

  if (process.env.DM_GUIDE_READER_PASSWORD) {
    const reader = await browser.newContext({ viewport: { width: 1100, height: 780 }, deviceScaleFactor: 1 })
    await login(reader, 'demo.reader@example.com', process.env.DM_GUIDE_READER_PASSWORD)
    const portal = await reader.newPage()
    for (const [url, name, prepare] of [
      ['/portal', 'tra-cuu-doc-gia.png', async p => {
        await p.locator('#q').fill('ngày hội đọc sách')
        await p.getByRole('button', { name: 'Tìm kiếm' }).click()
        await p.waitForTimeout(900)
      }],
      [`/portal/ho-so/${file}`, 'chi-tiet-ho-so-doc-gia.png'],
      [`/portal/van-ban/${document}`, 'chi-tiet-van-ban-doc-gia.png'],
      ['/portal/phieu', 'phieu-su-dung-doc-gia.png'],
      [`/portal/phieu/${usage}`, 'theo-doi-phieu-su-dung.png'],
      ['/portal/sao-chep', 'phieu-sao-chup-doc-gia.png'],
      [`/portal/sao-chep/${copy}`, 'theo-doi-phieu-sao-chup.png'],
      ['/portal/gop-y', 'gop-y-doc-gia.png'],
      ['/portal/thong-bao', 'thong-bao-doc-gia.png'],
      ['/portal/tai-khoan', 'tai-khoan-doc-gia.png'],
    ]) await capture(portal, url, name, prepare)
  }
} finally {
  await browser.close()
}
