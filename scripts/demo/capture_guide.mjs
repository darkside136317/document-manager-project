/** Capture current local development UI for the end-user guide. */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const root = path.resolve(import.meta.dirname, '../..')
const require = createRequire(path.join(root, 'scripts/e2e/ui/package.json'))
const { chromium } = require('playwright')
const env = fs.readFileSync(path.join(root, 'docker/.env.dev'), 'utf8')
const password = env.match(/^ADMIN_PASSWORD=(.*)$/m)?.[1]?.replace(/^['"]|['"]$/g, '')
if (!password) throw new Error('Thiếu ADMIN_PASSWORD trong docker/.env.dev')
const output = path.join(root, 'docs/assets/huong-dan-su-dung')
fs.mkdirSync(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
  const login = await context.request.post('http://localhost:8888/api/method/login', {
    form: { usr: 'Administrator', pwd: password },
  })
  if (!login.ok()) throw new Error(`Đăng nhập thất bại: HTTP ${login.status()}`)
  const page = await context.newPage()
  for (const [url, name] of [
    ['/dashboard', 'tong-quan-can-bo.png'],
    ['/dashboard/bien-muc', 'bien-muc.png'],
    ['/dashboard/tim-kiem', 'tim-kiem-can-bo.png'],
    ['/dashboard/doc-gia/doc-gia', 'danh-sach-doc-gia.png'],
  ]) {
    await page.goto(`http://localhost:8888${url}`, { waitUntil: 'networkidle' })
    if (url === '/dashboard/bien-muc') {
      for (const title of ['HD MẪU - UBND tỉnh Minh Hòa', 'HD MẪU - Văn hóa và giáo dục']) {
        const item = page.locator(`button[title="${title}"]`).locator('xpath=ancestor::li[@role="treeitem"][1]')
        await item.getByRole('button', { name: 'Mở rộng' }).click()
      }
      await page.locator('button[title="HD MẪU - Chương trình văn hóa 2024"]').click()
      await page.waitForTimeout(500)
    }
    if (url === '/dashboard/tim-kiem') {
      await page.getByPlaceholder(/Từ khóa trong tiêu đề/).fill('HD MẪU')
      await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click()
      await page.waitForTimeout(1200)
    }
    await page.waitForTimeout(700)
    await page.screenshot({ path: path.join(output, name), fullPage: false })
    console.log(name, await page.title())
  }
} finally {
  await browser.close()
}
