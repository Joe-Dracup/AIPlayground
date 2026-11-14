import process from 'node:process'
import { defineConfig, devices } from '@playwright/test'

// Separate from the dev servers' ports (8000 and 5173), so both can run at once.
const API_PORT = 8001
const UI_PORT = 5174
const API_URL = `http://127.0.0.1:${API_PORT}`
const UI_URL = `http://127.0.0.1:${UI_PORT}`

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: UI_URL,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      // A throwaway database with the sample places, and a FakeLLM instead of a real LLM.
      command: 'uv run python tests/e2e_server.py',
      cwd: '../backend',
      url: `${API_URL}/healthz`,
      env: {
        PORT: String(API_PORT),
        CORS_ORIGINS: JSON.stringify([UI_URL]),
      },
      // The first run builds the database image.
      timeout: 180_000,
      // Stop it like Ctrl+C, so it deletes its database container on the way out.
      gracefulShutdown: { signal: 'SIGINT', timeout: 10_000 },
    },
    {
      command: `pnpm dev --host 127.0.0.1 --port ${UI_PORT} --strictPort`,
      cwd: '../frontend',
      url: UI_URL,
      env: { VITE_API_BASE_URL: API_URL },
    },
  ],
})
