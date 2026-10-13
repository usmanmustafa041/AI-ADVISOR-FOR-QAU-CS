import { test, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'

const auth = { user: { role: 'admin', email: 'Synthetic timetable test admin' }, access_token: 'timetable-test-admin' }
const headers = { Authorization: `Bearer ${auth.access_token}` }
const base = '/api/v3/admin/timetables/versions'
const api = 'http://127.0.0.1:8012'

test('real admin upload, source preview, correction, publish B, historical A and rollback', async ({ page, request }) => {
  // Synthetic account exists only in the test API; do not send it to legacy auth.
  await page.route('**/api/v1/admin/report', route => route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }))
  await page.addInitScript(value => localStorage.setItem('qau-auth', JSON.stringify(value)), auth)
  await page.goto('/')
  await page.getByRole('button', { name: 'Timetable Management', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Upload timetable (PDF)' })).toBeVisible()
  const before = await (await request.get(`${api}${base}`, { headers })).json()
  const a = before.find(v => v.is_active && v.metadata.academic_term === 'Spring 2026')
  expect(a).toBeTruthy()
  execFileSync('backend/.venv/bin/python', ['-c', "from chatbot_v3.tests.test_timetable import revised_pdf;from pathlib import Path;Path('.runtime/chatbot-v3/timetable-inspection/revised-test.pdf').write_bytes(revised_pdf())"], { cwd: '..', env: { ...process.env, PYTHONPATH: 'backend' } })
  await page.locator('input[name=pdf]').setInputFiles('../.runtime/chatbot-v3/timetable-inspection/revised-test.pdf')
  await page.getByRole('button', { name: 'Upload and extract', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Spring 2026 · review/ })).toBeVisible()
  await expect(page.getByAltText('Original timetable page 1')).toBeVisible()
  const chosen = await page.getByRole('combobox', { name: 'Uploaded versions', exact: true }).inputValue()
  let detail = await (await request.get(`${api}${base}/${chosen}`, { headers })).json()
  const target = detail.meetings.find(m => m.weekday === 'Monday' && m.courses.some(c => c.code === 'CS-104' && c.section === 'regular'))
  await page.getByRole('textbox', { name: 'Filter room', exact: true }).fill('201')
  await page.locator('tr').filter({ hasText: 'CS-104' }).filter({ hasText: 'Monday' }).getByRole('button', { name: 'Correct / link' }).click()
  await page.locator('.tt-edit input[name=room]').fill('209')
  await page.locator('.tt-edit input[name=reason]').fill('TEST ONLY amendment printed on page three')
  await page.getByRole('button', { name: 'Save correction' }).click()
  await expect(page.locator('.tt-edit')).toHaveCount(0)
  detail = await (await request.get(`${api}${base}/${chosen}`, { headers })).json()
  expect(detail.meetings.find(m => m.id === target.id).room).toBe('209')
  // Exercise authenticated HTTP correction/resolution for the remaining flagged rows.
  for (const m of detail.meetings.filter(m => m.courses.some(c => !c.offering_id))) {
    const response = await request.patch(`${api}${base}/${chosen}/meetings/${m.id}`, { headers, data: { expected_revision: detail.revision, reason: 'TEST ONLY omit ambiguous ownership until human review', changes: { omitted: true } } })
    expect(response.ok()).toBeTruthy(); detail = await response.json()
  }
  for (const issue of detail.issues.filter(i => !i.resolution)) {
    const response = await request.post(`${api}${base}/${chosen}/issues/${issue.id}/resolve`, { headers, data: { expected_revision: detail.revision, reason: 'TEST ONLY lifecycle verification, not human accuracy approval' } })
    expect(response.ok()).toBeTruthy(); detail = await response.json()
  }
  await page.getByRole('combobox', { name: 'Uploaded versions', exact: true }).selectOption('')
  await page.getByRole('combobox', { name: 'Uploaded versions', exact: true }).selectOption(chosen)
  await expect(page.getByRole('heading', { name: /0 unresolved flags/ })).toBeVisible()
  for (const n of [1, 2, 3]) await page.getByRole('checkbox', { name: `I inspected page ${n}` }).check()
  await page.getByRole('checkbox', { name: 'I verified the complete schedule, ownership, legend and diff' }).check()
  await page.getByRole('textbox', { name: 'Publication / rollback reason' }).fill('TEST ONLY publish revised fixture')
  await page.getByRole('button', { name: 'Publish this version', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Published to the V3 preview')
  const query = { academic_term: 'Spring 2026', programme: 'BSCS', semester: 1, section: 'regular', weekday: 'Monday' }
  let live = await (await request.post(`${api}/api/v3/timetables/query`, { data: query })).json()
  expect(live.rows[0].room).toBe('209'); expect(live.version.id).toBe(chosen)
  const historical = await (await request.post(`${api}/api/v3/timetables/query`, { data: { ...query, historical: true, version_id: a.id } })).json()
  expect(historical.rows[0].room).toBe('201')
  await page.screenshot({ path: '../.runtime/chatbot-v3/timetable-inspection/admin-published.png', fullPage: true })
  await page.getByRole('combobox', { name: 'Uploaded versions', exact: true }).selectOption(a.id)
  await expect(page.getByRole('heading', { name: /Spring 2026 · archived/ })).toBeVisible()
  for (const n of [1, 2, 3]) await page.getByRole('checkbox', { name: `I inspected page ${n}` }).check()
  await page.getByRole('checkbox', { name: 'I verified the complete schedule, ownership, legend and diff' }).check()
  await page.getByRole('textbox', { name: 'Publication / rollback reason' }).fill('TEST ONLY restore initial fixture')
  await page.getByRole('button', { name: 'Rollback to this version' }).click()
  await expect(page.getByRole('status')).toContainText('restored')
  live = await (await request.post(`${api}/api/v3/timetables/query`, { data: query })).json()
  expect(live.version.id).toBe(a.id); expect(live.rows[0].room).toBe('201')
  const forbidden = await request.get(`${api}${base}`, { headers: { Authorization: 'Bearer timetable-test-student' } })
  expect(forbidden.status()).toBe(403)
})

test('real student chat renders timetable rows and PDF page citations', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Continue without signing in' }).click()
  const input = page.getByRole('textbox', { name: 'Ask an academic question' })
  await input.fill('Show BSCS semester IV Regular Monday classes in Spring 2026.')
  await page.getByRole('button', { name: 'Send query' }).click()
  await expect(page.getByRole('button', { name: 'Send query' })).toBeVisible({ timeout: 200000 })
  const answer = page.locator('.message-row.assistant').last()
  await expect(answer).toContainText('CS-224')
  await expect(answer).toContainText('CS-222')
  await expect(answer).toContainText('CS-313')
  await expect(answer).toContainText('CS Lab')
  await answer.getByText('What source was used?').click()
  await answer.locator('.evidence-source > summary').first().click()
  const source = await page.request.get(await answer.getByRole('link', { name: 'View captured passage' }).first().getAttribute('href'))
  expect(source.ok()).toBeTruthy(); expect(JSON.stringify(await source.json())).toContain('CS-224')
  await page.screenshot({ path: '../.runtime/chatbot-v3/timetable-inspection/student-chat.png', fullPage: true })
  // Existing portal navigation still renders through the original API integration.
  await page.getByRole('button', { name: 'Courses', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Course name or code' })).toBeVisible()
})
