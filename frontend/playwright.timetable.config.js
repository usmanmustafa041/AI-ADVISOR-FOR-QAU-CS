import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './timetable-e2e',
  outputDir: process.env.TT_E2E_OUTPUT || '../.runtime/chatbot-v3/timetable-inspection/playwright',
  workers: 1,
  timeout: 240000,
  expect: { timeout: 30000 },
  use: { baseURL: 'http://127.0.0.1:5182', actionTimeout: 30000, screenshot: 'only-on-failure', ...devices['Desktop Chrome'] },
  reporter: [['line'], ['json', { outputFile: process.env.TT_E2E_RESULTS || '../.runtime/chatbot-v3/timetable-inspection/browser-results.json' }]],
})
