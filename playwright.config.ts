import { defineConfig, devices } from "@playwright/test";

const externalBaseURL = process.env.BASE_URL;
const baseURL = externalBaseURL ?? "http://localhost:3000";
const clerkPublishableKey =
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ??
  `pk_test_${Buffer.from("playwright.clerk.accounts.dev$").toString("base64")}`;

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
  tsconfig: "./tsconfig.playwright.json",

  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],

  use: {
    // All requests go to the local Next.js dev server
    baseURL,
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

  // Start a dedicated server unless the caller explicitly supplies one.
  webServer: externalBaseURL
    ? undefined
    : {
        command: "npm run dev",
        url: "http://localhost:3000",
        env: {
          NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: clerkPublishableKey,
        },
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
