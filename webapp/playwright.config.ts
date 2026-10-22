import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the real API and a production build of the web app.
 * Both servers are started here on test ports; the API gets a throwaway
 * database seeded with the fixture accounts below (test values, not secrets).
 */
const API_PORT = 8100;
const WEB_PORT = 3100;

export const E2E_USERS = {
  admin: { email: "e2e.admin@example.test", password: "e2e-admin-password" },
  analyst: { email: "e2e.analyst@example.test", password: "e2e-analyst-password" },
};

const python = process.env.PYTHON ?? "python";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  // argon2 (64 MiB, 3 passes) competes with Chromium and Next for the CPU: one
  // login measured up to 5.4 s on a laptop running this suite (0.2 s when idle).
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} scripts/e2e_api.py --port ${API_PORT}`,
      cwd: "..",
      url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        PYTHONPATH: "src",
        JWT_SECRET: "e2e-only-secret-not-for-production-0123456789",
        DEMO_ADMIN_EMAIL: E2E_USERS.admin.email,
        DEMO_ADMIN_PASSWORD: E2E_USERS.admin.password,
        DEMO_ANALYST_EMAIL: E2E_USERS.analyst.email,
        DEMO_ANALYST_PASSWORD: E2E_USERS.analyst.password,
      },
    },
    {
      command: `npm run build && npx next start --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}/login`,
      reuseExistingServer: false,
      timeout: 300_000,
      env: {
        API_BASE_URL: `http://127.0.0.1:${API_PORT}`,
        NEXT_TELEMETRY_DISABLED: "1",
      },
    },
  ],
});
