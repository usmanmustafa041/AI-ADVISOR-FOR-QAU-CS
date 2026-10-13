import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './rebuild-e2e',
  outputDir: process.env.V3_E2E_OUTPUT_DIR || '../.runtime/chatbot-v3/playwright',
  timeout: 480000,
  workers: 1,
  expect: { timeout: 20000 },
  use: { baseURL: 'http://127.0.0.1:5180', ...devices['Desktop Chrome'] },
  reporter: [['line'], ['json', { outputFile: process.env.V3_E2E_RESULTS_FILE || '../.runtime/chatbot-v3/evaluation/browser-results.json' }]],
})
