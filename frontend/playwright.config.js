import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 15_000 },
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173', ...devices['Desktop Chrome'] },
  webServer: process.env.PLAYWRIGHT_BASE_URL ? undefined : [
    { command: 'npm run dev -- --host 127.0.0.1', url: 'http://127.0.0.1:5173', reuseExistingServer: true },
    { command: 'python -m uvicorn app.main:app --port 8000', cwd: '../backend', url: 'http://127.0.0.1:8000/api/v1/health', reuseExistingServer: true },
  ],
})
