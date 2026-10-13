import fs from 'node:fs'
import { expect, test } from '@playwright/test'

const accounts = process.env.QAU_E2E_AUTH_FILE ? JSON.parse(fs.readFileSync(process.env.QAU_E2E_AUTH_FILE)) : {}

test('guest can use the advisor without sign-in and history remains disabled', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /Continue without signing in/i }).click()
  await expect(page.getByText(/Guest conversation · not saved/i)).toBeVisible()
  await page.getByPlaceholder(/Ask an academic question/i).fill('Hello')
  await page.getByRole('button', { name: 'Send query' }).click()
  await expect(page.getByText('Hi! How can I help you with QAU today?')).toBeVisible()
  await expect(page.getByRole('button', { name: 'History' })).toHaveCount(0)
  await expect(page.getByText(/Sign in to save and revisit/i)).toBeVisible()
  await page.getByRole('button', { name: 'Fees', exact: true }).click()
  await expect(page.getByText('BS Computer Science fee structure')).toBeVisible()
  await expect(page.getByRole('link', { name: /official QAU fee page/i })).toBeVisible()
  await page.getByRole('button', { name: 'Study Plan', exact: true }).click()
  await expect(page.getByText('BSCS eight-semester study plan')).toBeVisible()
  await expect(page.getByText(/source-backed structured study plan has not been loaded|Semester 8/i).first()).toBeVisible()
  await page.screenshot({ path: 'test-results/study-plan.png', fullPage: true })
})

test('student registers, asks a bilingual-ready academic query, and sees saved history', async ({ page }) => {
  test.skip(!accounts.registration, 'Use the temporary-account browser runner')
  const { email, password } = accounts.registration
  await page.goto('/')
  await expect(page.getByText('Sign in to your advisor')).toBeVisible()
  await page.getByRole('button', { name: /Create an account/i }).click()
  await page.getByLabel('Full name').fill('E2E Student')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: 'Register', exact: true }).click()

  await expect(page.getByText('Private authenticated conversation · history enabled')).toBeVisible()
  await expect(page.getByRole('button', { name: 'اردو' })).toBeVisible()
  await page.getByPlaceholder(/Ask an academic question/i).fill('Calculate GPA: 3 credits at 4.0, 4 credits at 3.0')
  await page.getByRole('button', { name: 'Send query' }).click()
  await expect(page.locator('.message-row.assistant .message-bubble').last()).toContainText('3.43')

  await page.getByRole('button', { name: /Timetable/ }).click()
  await expect(page.getByRole('heading', { name: /timetable/i }).first()).toBeVisible()

  await page.getByRole('button', { name: /History/ }).click()
  await expect(page.getByText('Calculate GPA: 3 credits at 4.0, 4 credits at 3.0')).toBeVisible()
  await page.screenshot({ path: 'test-results/student-history.png', fullPage: true })
})

test('administrator signs in and can open protected management modules', async ({ page }) => {
  test.skip(!accounts.admin, 'Use the temporary-account browser runner')
  await page.goto('/')
  await page.getByLabel('Email').fill(accounts.admin.user.email)
  await page.getByLabel('Password').fill(accounts.admin.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByText(/Admin control centre/i)).toBeVisible()
  await page.getByRole('button', { name: /Query Logs/ }).first().click()
  await expect(page.getByText('Search and export query logs')).toBeVisible()
  await page.getByRole('button', { name: /Reports/ }).first().click()
  await expect(page.getByText('Generate report')).toBeVisible()
})
