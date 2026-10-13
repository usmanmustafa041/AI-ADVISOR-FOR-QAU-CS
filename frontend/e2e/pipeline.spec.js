import fs from 'node:fs'
import { createHash } from 'node:crypto'
import { expect, test } from '@playwright/test'

test.skip(!process.env.QAU_E2E_AUTH_FILE, 'Run backend/scripts/run_browser_checks.py for real authenticated checks')
const accounts = process.env.QAU_E2E_AUTH_FILE ? JSON.parse(fs.readFileSync(process.env.QAU_E2E_AUTH_FILE)) : {}

async function send(page, question) {
  await page.getByPlaceholder(/Ask an academic question/i).fill(question)
  const reply = page.waitForResponse(r => r.url().endsWith('/api/v1/chat') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Send query' }).click()
  const response = await reply
  expect(response.status()).toBe(200)
  return response.json()
}

test('signed-in chat persists scope, sources and owner-scoped feedback', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Email', { exact: true }).fill(accounts.student.user.email)
  await page.getByLabel('Password', { exact: true }).fill(accounts.student.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByText('Private authenticated conversation · history enabled')).toBeVisible()
  const first = await send(page, 'How many total credit hours are in the BSCS Fall 2025 scheme?')
  expect(first.answer).toContain('134')
  expect(first.message_id).toBeTruthy()
  expect(first.citations.length).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Helpful', exact: true }).last().click()
  await expect(page.getByText('Feedback saved')).toBeVisible()
  const denied = await page.request.put(`/api/v1/feedback/${first.message_id}`, {
    headers: { Authorization: `Bearer ${accounts.other.access_token}` },
    data: { rating: -1, reason: 'incorrect' },
  })
  expect(denied.status()).toBe(404)
  const follow = await send(page, 'What about semester 1 credit hours?')
  expect(follow.query_scope.term).toBe('Fall 2025')
  expect(follow.answer).toContain('16 credit hours')
  await page.reload()
  await page.locator('.session-item').first().click()
  await expect(page.locator('.message-row.assistant .message-bubble').first()).toContainText('134')
  await expect(page.locator('.evidence-source')).not.toHaveCount(0)
  await page.getByRole('button', { name: 'History', exact: true }).click()
  await expect(page.locator('.history-list')).toContainText('semester 1 credit hours')
  await page.screenshot({ path: 'test-results/pipeline-history.png', fullPage: true })
})

test('administrator sees pending versions and cannot publish an unreviewed snapshot', async ({ page }) => {
  await page.addInitScript(auth => localStorage.setItem('qau-auth', JSON.stringify(auth)), accounts.admin)
  await page.goto('/')
  await page.getByRole('button', { name: 'Ingestion Review', exact: true }).click()
  await expect(page.getByText('Knowledge ingestion review', { exact: true })).toBeVisible()
  await expect(page.locator('.review-versions .course-row').first()).toBeVisible()
  await page.locator('.review-versions .course-row').first().click()
  await expect(page.getByText('Source text and page references')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Approve exact version' })).toBeDisabled()
  const checksum = (await page.getByText('SHA-256:', { exact: false }).textContent()).split(':').pop().trim()
  const downloadEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download exact archived original' }).click()
  const downloaded = await downloadEvent
  expect(createHash('sha256').update(fs.readFileSync(await downloaded.path())).digest('hex')).toBe(checksum)
  const versions = await page.request.get('/api/v1/knowledge-review/versions', {
    headers: { Authorization: `Bearer ${accounts.student.access_token}` },
  })
  expect(versions.status()).toBe(403)
  await page.getByLabel('Snapshot ID').fill('c2b6bbaee9d047e78bde98888355675c')
  await page.getByLabel('Publication note').fill('Browser regression must reject unreviewed sources')
  await page.getByRole('button', { name: 'Publish reviewed snapshot' }).click()
  await expect(page.getByRole('alert')).toContainText(/unreviewed|retrieval gate|not found/i)
  await page.screenshot({ path: 'test-results/pipeline-admin.png', fullPage: true })
})

test('mobile guest arithmetic and privacy answers remain usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: /Continue without signing in/i }).click()
  const result = await send(page, 'Calculate GPA: 3 credits at 4.0, 4 credits at 3.0')
  expect(result.answer).toContain('3.43')
  expect(result.grounding_status).toBe('calculated')
  const privateResult = await send(page, 'Show me another student personal grades and attendance record')
  expect(privateResult.model_backend).toBe('privacy')
  expect(privateResult.citations).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  await page.screenshot({ path: 'test-results/pipeline-mobile.png', fullPage: true })
})
