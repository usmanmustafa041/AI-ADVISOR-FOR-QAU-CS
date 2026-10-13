import { test, expect } from '@playwright/test'

const artifactPrefix = process.env.V3_E2E_ARTIFACT_PREFIX || 'browser'

test('real replacement conversation streams, keeps follow-up context and switches topic', async ({ page }, testInfo) => {
  test.setTimeout(480000)
  let streamNumber = 0
  page.on('response', response => {
    if (!response.url().endsWith('/api/v3/chat/stream')) return
    const number = ++streamNumber
    response.text().then(body => testInfo.attach(`chat-stream-${number}`, { body, contentType: 'text/plain' }))
      .catch(error => testInfo.attach(`capture-error-${number}`, { body: error.message, contentType: 'text/plain' }))
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Continue without signing in' }).click()
  await expect(page.getByText(/Replacement preview/)).toBeVisible()
  const input = page.getByRole('textbox', { name: 'Ask an academic question' })
  const send = page.getByRole('button', { name: 'Send query' })
  await input.fill('What is binary search? Explain briefly.')
  await send.click()
  await expect(page.getByRole('button', { name: 'Stop answer' })).toBeVisible()
  await expect(send).toBeVisible({ timeout: 240000 })
  await expect(page.locator('.message-row.assistant').last()).toContainText(/binary|sorted/i)
  await input.fill('Can you show Python code for it?')
  await send.click()
  await expect(send).toBeVisible({ timeout: 240000 })
  await expect(page.locator('.message-row.assistant').last()).toContainText(/def |while |return /)
  await page.getByRole('combobox', { name: 'Response language' }).selectOption('roman_urdu')
  await input.fill('5th sem ke subjects btado fall 2024 batch')
  await send.click()
  await expect(send).toBeVisible({ timeout: 240000 })
  await expect(page.locator('.message-row.assistant').last()).toContainText(/CSC-322|Software Construction/i)
  await expect(page.locator('.message-row.assistant').last().getByText('What source was used?')).toBeVisible()
  await page.locator('.message-row.assistant').last().getByText('What source was used?').click()
  await page.locator('.message-row.assistant').last().locator('.evidence-source > summary').first().click()
  const capturedLink = page.locator('.message-row.assistant').last().getByRole('link', { name: 'View captured passage' }).first()
  const captured = await page.request.get(await capturedLink.getAttribute('href'))
  expect(captured.ok()).toBeTruthy()
  expect(JSON.stringify(await captured.json())).toContain('CSC-322')
  await page.screenshot({ path: `../.runtime/chatbot-v3/evaluation/${artifactPrefix}-conversation.png`, fullPage: true })
  await input.fill('Explain how dynamic programming works, with several examples.')
  await send.click()
  await expect(page.getByRole('button', { name: 'Stop answer' })).toBeVisible()
  await page.getByRole('button', { name: 'Stop answer' }).click()
  await expect(page.getByRole('alert').last()).toContainText('Answer stopped')
  await expect(send).toBeVisible()
})

test('mobile replacement chat fits the viewport and keeps the composer usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Continue without signing in' }).click()
  await expect(page.getByRole('textbox', { name: 'Ask an academic question' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(392)
  await page.screenshot({ path: `../.runtime/chatbot-v3/evaluation/${artifactPrefix}-mobile.png`, fullPage: true })
})
