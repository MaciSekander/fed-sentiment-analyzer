import { defineConfig, devices } from "@playwright/test";

// Runs against the real backend + frontend dev servers, not a mock -- the
// whole point is to catch integration/interaction bugs (like a chart
// click handler silently reading a property that doesn't exist) that
// backend-only pytest and a TypeScript compile can't.
export default defineConfig({
  testDir: "./tests-e2e",
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: "http://localhost:5173",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // Relies on `uvicorn` already being on PATH -- run `npx playwright
      // test` from an activated venv locally; in CI, requirements.txt is
      // pip-installed directly (no venv), so it's on PATH there too.
      command: "uvicorn backend.app.main:app --port 8000",
      cwd: "..",
      url: "http://localhost:8000/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
