import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for integration-health browser tests.
 *
 * Tests are kept in src/**\/__tests__/*.browser.spec.ts
 * The Next.js dev server is started automatically before the suite runs.
 */
export default defineConfig({
  // Only look for browser spec files so existing node:test files are untouched
  testMatch: ["**/__tests__/*.browser.spec.ts"],
  testDir: "./src",
  fullyParallel: true,
  // Use dedicated tsconfig so moduleResolution matches Playwright's expectations
  // without touching the Next.js tsconfig.json

  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],

  use: {
    // All requests go to the local Next.js dev server
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    // Run headless by default; set HEADED=1 to watch
    headless: !process.env.HEADED,
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  // Start the Next.js dev server automatically if not running in CI
  webServer: process.env.CI
    ? undefined
    : {
        command: "npm run dev",
        url: "http://localhost:3000",
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
