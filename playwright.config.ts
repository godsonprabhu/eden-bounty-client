import { defineConfig } from "@playwright/test";

const baseURL = process.env.PW_BASE_URL;
const databaseUrl = process.env.DATABASE_URL;

if (process.env.PW_LOCAL_TEST !== "1") {
  throw new Error("Run browser tests with `npm run test:e2e:local`; direct Playwright runs are disabled.");
}
if (!baseURL) throw new Error("PW_BASE_URL must point to the local E2E frontend.");
const parsedBase = new URL(baseURL);
if (!(["127.0.0.1", "localhost", "::1"].includes(parsedBase.hostname))) {
  throw new Error("Playwright is restricted to a loopback PW_BASE_URL.");
}
if (!databaseUrl) throw new Error("DATABASE_URL must point to the disposable Playwright database.");
const parsedDatabase = new URL(databaseUrl.replace(/^postgresql\+asyncpg:/, "postgresql:"));
if (!(["127.0.0.1", "localhost", "::1"].includes(parsedDatabase.hostname)) || !/^\/eb_playwright_test_[a-z0-9_]+$/i.test(parsedDatabase.pathname)) {
  throw new Error("Playwright requires a loopback database named eb_playwright_test_*.");
}

const backendURL = process.env.PW_BACKEND_URL || "http://127.0.0.1:8100";
if (!(["127.0.0.1", "localhost", "::1"].includes(new URL(backendURL).hostname))) {
  throw new Error("PW_BACKEND_URL must be loopback-only.");
}
const frontendDir = process.env.PW_FRONTEND_DIR;
if (!frontendDir) throw new Error("PW_FRONTEND_DIR must point to the isolated local frontend copy.");
const frontendPort = parsedBase.port || "80";
const backendPort = new URL(backendURL).port || "80";
const isStandalone = process.env.PW_STANDALONE === "1";

export default defineConfig({
  testDir: "./e2e/tests",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "test-results/playwright-html", open: "never" }]],
  outputDir: "test-results/playwright",
  timeout: 45_000,
  expect: { timeout: 8_000 },
  use: {
    baseURL,
    browserName: "chromium",
    channel: "chrome",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    actionTimeout: 10_000,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium", channel: "chrome" } }],
  webServer: [
    {
      command: `backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port ${backendPort}`,
      url: `${backendURL}/health`,
      reuseExistingServer: false,
      timeout: 90_000,
    },
    {
      command: isStandalone
        ? `node server.js`
        : `npm run dev -- --webpack --hostname 127.0.0.1 --port ${frontendPort}`,
      url: baseURL,
      cwd: isStandalone ? `${frontendDir}/.next/standalone` : frontendDir,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        INTERNAL_BACKEND_URL: backendURL,
        NEXT_TELEMETRY_DISABLED: "1",
        PORT: frontendPort,
        HOSTNAME: "127.0.0.1",
      },
    },
  ],
});
