/**
 * Playwright browser tests for IntegrationHealthPanel
 *
 * Strategy
 * --------
 * Each test navigates to /test-harness/integration-health and intercepts
 * GET /api/integration-health with a fixture payload via page.route().
 * The component renders in real Chromium (headless), so every assertion
 * is against live DOM / network behaviour — not source-code grep.
 *
 * Flows covered
 * 1. Successful scans  — ok badges, resource totals, enriched counts
 * 2. Azure 429 rate-limit — cached costs banner, cooldown countdown
 * 3. Permission failure — safe allowlisted message, no SDK leakage
 * 4. Account switching — multi-integration isolation, empty-state
 * 5. API error / 503   — error panel with Retry button
 */

import { test, expect, type Page, type Route } from "@playwright/test";
import type { IntegrationHealthBatchResponse } from "../integration-health-types";

// ─── Helpers ────────────────────────────────────────────────────────────────

const HARNESS_URL = "/test-harness/integration-health";
const API_GLOB = "**/api/integration-health";

/** Intercept /api/integration-health with a given fixture payload */
async function mockHealthApi(
  page: Page,
  payload: IntegrationHealthBatchResponse
) {
  await page.route(API_GLOB, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload),
    })
  );
}

/** Intercept /api/integration-health with a HTTP error */
async function mockHealthApiError(page: Page, status: number, detail: string) {
  await page.route(API_GLOB, (route: Route) =>
    route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify({ detail }),
    })
  );
}

// ─── Fixtures ───────────────────────────────────────────────────────────────

const NOW = new Date().toISOString();
const HOUR_AGO = new Date(Date.now() - 3_600_000).toISOString();
const DAY_AGO = new Date(Date.now() - 86_400_000).toISOString();
const RETRY_IN_FUTURE = new Date(Date.now() + 900_000).toISOString(); // 15 min ahead

/** Single Azure integration — all green */
const FIXTURE_SUCCESS: IntegrationHealthBatchResponse = {
  fetched_at: NOW,
  integrations: [
    {
      integration_id: "azure-001",
      provider: "azure",
      name: "Prod Azure (tenant-001)",
      inventory: {
        status: "ok",
        last_success_at: HOUR_AGO,
        last_attempt_at: HOUR_AGO,
        data_observed_at: HOUR_AGO,
        resource_count: 142,
        reason_code: null,
        display_message: null,
      },
      billing: {
        status: "ok",
        last_success_at: HOUR_AGO,
        last_attempt_at: HOUR_AGO,
        data_observed_at: HOUR_AGO,
        retry_at: null,
        using_cached_costs: false,
        reason_code: null,
        display_message: null,
      },
      ai_enrichment: {
        queued: 0,
        running: 0,
        enriched: 138,
        failed: 0,
        last_success_at: HOUR_AGO,
      },
    },
  ],
};

/** Azure 429 — billing rate-limited; using cached costs */
const FIXTURE_AZURE_429: IntegrationHealthBatchResponse = {
  fetched_at: NOW,
  integrations: [
    {
      integration_id: "azure-002",
      provider: "azure",
      name: "Staging Azure",
      inventory: {
        status: "ok",
        last_success_at: HOUR_AGO,
        last_attempt_at: HOUR_AGO,
        data_observed_at: HOUR_AGO,
        resource_count: 58,
        reason_code: null,
        display_message: null,
      },
      billing: {
        status: "stale",
        last_success_at: DAY_AGO,
        last_attempt_at: HOUR_AGO,
        data_observed_at: DAY_AGO,
        retry_at: RETRY_IN_FUTURE,
        using_cached_costs: true,
        reason_code: "RATE_LIMITED",
        display_message:
          "Azure billing API is temporarily rate-limited. Showing costs from last successful fetch.",
      },
      ai_enrichment: {
        queued: 2,
        running: 1,
        enriched: 55,
        failed: 0,
        last_success_at: HOUR_AGO,
      },
    },
  ],
};

/** AWS — permission failure on inventory */
const FIXTURE_PERMISSION_FAILURE: IntegrationHealthBatchResponse = {
  fetched_at: NOW,
  integrations: [
    {
      integration_id: "aws-001",
      provider: "aws",
      name: "Dev AWS (us-east-1)",
      inventory: {
        status: "failed",
        last_success_at: DAY_AGO,
        last_attempt_at: HOUR_AGO,
        data_observed_at: DAY_AGO,
        resource_count: 0,
        reason_code: "PERMISSION_DENIED",
        display_message:
          "CloudFinOps lacks required IAM permissions. Please re-attach the CloudFinOps managed policy.",
      },
      billing: {
        status: "stale",
        last_success_at: DAY_AGO,
        last_attempt_at: HOUR_AGO,
        data_observed_at: DAY_AGO,
        retry_at: null,
        using_cached_costs: true,
        reason_code: "PERMISSION_DENIED",
        display_message: "Billing access denied. Check Cost Explorer permissions.",
      },
      ai_enrichment: {
        queued: 0,
        running: 0,
        enriched: 0,
        failed: 3,
        last_success_at: null,
      },
    },
  ],
};

/** Two integrations — Azure (ok) + GCP (never) — for account-switching / isolation */
const FIXTURE_MULTI_PROVIDER: IntegrationHealthBatchResponse = {
  fetched_at: NOW,
  integrations: [
    {
      integration_id: "azure-003",
      provider: "azure",
      name: "Corp Azure",
      inventory: {
        status: "ok",
        last_success_at: HOUR_AGO,
        last_attempt_at: HOUR_AGO,
        data_observed_at: HOUR_AGO,
        resource_count: 201,
        reason_code: null,
        display_message: null,
      },
      billing: {
        status: "ok",
        last_success_at: HOUR_AGO,
        last_attempt_at: HOUR_AGO,
        data_observed_at: HOUR_AGO,
        retry_at: null,
        using_cached_costs: false,
        reason_code: null,
        display_message: null,
      },
      ai_enrichment: {
        queued: 0,
        running: 0,
        enriched: 199,
        failed: 0,
        last_success_at: HOUR_AGO,
      },
    },
    {
      integration_id: "gcp-001",
      provider: "gcp",
      name: "Data GCP project",
      inventory: {
        status: "never",
        last_success_at: null,
        last_attempt_at: null,
        data_observed_at: null,
        resource_count: 0,
        reason_code: null,
        display_message: null,
      },
      billing: {
        status: "never",
        last_success_at: null,
        last_attempt_at: null,
        data_observed_at: null,
        retry_at: null,
        using_cached_costs: false,
        reason_code: null,
        display_message: null,
      },
      ai_enrichment: {
        queued: 0,
        running: 0,
        enriched: 0,
        failed: 0,
        last_success_at: null,
      },
    },
  ],
};

/** Zero integrations — empty state */
const FIXTURE_EMPTY: IntegrationHealthBatchResponse = {
  fetched_at: NOW,
  integrations: [],
};

// ─── Tests ──────────────────────────────────────────────────────────────────

test.describe("IntegrationHealthPanel browser flows", () => {
  // ── 1. Successful scan ────────────────────────────────────────────────────
  test("successful scan: shows ok badges, resource count, and enriched pill", async ({
    page,
  }) => {
    await mockHealthApi(page, FIXTURE_SUCCESS);
    await page.goto(HARNESS_URL);

    // Panel heading visible
    await expect(
      page.getByRole("heading", { name: "Integration Health" })
    ).toBeVisible();

    // Integration card visible with AZURE badge
    const card = page.locator('[id="health-card-azure-001"]');
    await expect(card).toBeVisible();
    await expect(card).toContainText("AZURE");

    // Overall status should be "ok"
    await expect(card).toContainText("ok");

    // Expand the accordion
    await card.click();

    // Inventory Scan sub-panel
    await expect(page.getByText("Inventory Scan")).toBeVisible();
    await expect(page.getByText("142")).toBeVisible(); // resource_count

    // Billing Refresh sub-panel — no cached costs badge
    await expect(page.getByText("Billing Refresh")).toBeVisible();
    await expect(page.getByText("cached costs")).not.toBeVisible();

    // AI Enrichment sub-panel — shows "138 enriched"
    await expect(page.getByText("AI Enrichment")).toBeVisible();
    await expect(page.getByText(/138 enriched/)).toBeVisible();
  });

  // ── 2. Azure 429 rate-limit ───────────────────────────────────────────────
  test("Azure 429: shows cached costs banner and retry cooldown countdown", async ({
    page,
  }) => {
    await mockHealthApi(page, FIXTURE_AZURE_429);
    await page.goto(HARNESS_URL);

    const card = page.locator('[id="health-card-azure-002"]');
    await expect(card).toBeVisible();

    // Expand
    await card.click();

    // "cached costs" amber pill must appear in the Billing sub-panel
    await expect(page.getByText("cached costs")).toBeVisible();

    // Billing status shows stale
    // (there can be multiple "stale" texts — just check at least one is present)
    await expect(page.locator("text=stale").first()).toBeVisible();

    // Retry cooldown text: "retry in Xm" or "retry in Xh"
    await expect(page.getByText(/retry in \d+[mh]/)).toBeVisible();

    // Rate-limited error message must be present
    await expect(
      page.getByText(/Azure billing API is temporarily rate-limited/)
    ).toBeVisible();

    // reason_code badge
    await expect(page.getByText("RATE_LIMITED")).toBeVisible();

    // AI enrichment shows queued and running pills
    await expect(page.getByText(/queued/)).toBeVisible();
    await expect(page.getByText(/running/)).toBeVisible();
  });

  // ── 3. Permission failure — no SDK leakage ───────────────────────────────
  test("permission failure: shows safe allowlisted message without SDK details", async ({
    page,
  }) => {
    await mockHealthApi(page, FIXTURE_PERMISSION_FAILURE);
    await page.goto(HARNESS_URL);

    const card = page.locator('[id="health-card-aws-001"]');
    await expect(card).toBeVisible();
    await expect(card).toContainText("AWS");

    // Overall status is "failed"
    await expect(card).toContainText("failed");

    // Expand
    await card.click();

    // Safe display_message shown
    await expect(
      page.getByText(
        /CloudFinOps lacks required IAM permissions/
      )
    ).toBeVisible();

    // Reason code badge visible
    await expect(page.getByText("PERMISSION_DENIED").first()).toBeVisible();

    // Billing display_message shown
    await expect(
      page.getByText(/Billing access denied/)
    ).toBeVisible();

    // No raw SDK error strings leaked — check absence of typical SDK patterns
    await expect(page.getByText(/botocore|ClientError|AccessDenied:/)).not.toBeVisible();
    await expect(page.getByText(/Traceback/)).not.toBeVisible();

    // AI enrichment: "3 failed" pill visible
    await expect(page.getByText(/3 failed/)).toBeVisible();
  });

  // ── 4. Multi-provider / account switching ────────────────────────────────
  test("multi-provider: renders isolated cards per account with correct badges", async ({
    page,
  }) => {
    await mockHealthApi(page, FIXTURE_MULTI_PROVIDER);
    await page.goto(HARNESS_URL);

    // Both cards visible
    const azureCard = page.locator('[id="health-card-azure-003"]');
    const gcpCard = page.locator('[id="health-card-gcp-001"]');

    await expect(azureCard).toBeVisible();
    await expect(gcpCard).toBeVisible();

    // Provider pill colours are distinct (verify text content)
    await expect(azureCard).toContainText("AZURE");
    await expect(gcpCard).toContainText("GCP");

    // Azure is "ok"; GCP is "never" (has never been scanned)
    await expect(azureCard).toContainText("ok");
    await expect(gcpCard).toContainText("never");

    // Expanding Azure shows resource count; GCP shows "—" for resources
    await azureCard.click();
    await expect(page.getByText("201")).toBeVisible();

    // Close Azure, expand GCP
    await azureCard.click();
    await gcpCard.click();

    // GCP never-scanned shows dashes for all timestamps
    const dashes = page.getByText("—");
    // At least one dash for an unset timestamp
    await expect(dashes.first()).toBeVisible();
  });

  // ── 5. Empty state ────────────────────────────────────────────────────────
  test("empty state: shows no-integrations message when list is empty", async ({
    page,
  }) => {
    await mockHealthApi(page, FIXTURE_EMPTY);
    await page.goto(HARNESS_URL);

    await expect(
      page.getByText("No connected integrations to show health for.")
    ).toBeVisible();

    // Panel heading is NOT rendered in empty state
    await expect(
      page.getByRole("heading", { name: "Integration Health" })
    ).not.toBeVisible();
  });

  // ── 6. API error / 503 ───────────────────────────────────────────────────
  test("API error: shows error alert with Retry button on 503", async ({
    page,
  }) => {
    await mockHealthApiError(page, 503, "Service temporarily unavailable");
    await page.goto(HARNESS_URL);

    // Error alert must be visible
    const alert = page.getByRole("alert");
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("Could not load integration health");
    await expect(alert).toContainText("Service temporarily unavailable");

    // Retry button present
    const retryBtn = alert.getByRole("button", { name: "Retry" });
    await expect(retryBtn).toBeVisible();

    // Clicking Retry should make another API call — re-mock with success
    await page.unroute(API_GLOB);
    await mockHealthApi(page, FIXTURE_SUCCESS);
    await retryBtn.click();

    // Panel recovers and shows health content
    await expect(
      page.getByRole("heading", { name: "Integration Health" })
    ).toBeVisible();
  });

  // ── 7. Manual refresh button ─────────────────────────────────────────────
  test("refresh button triggers new API call and updates panel", async ({
    page,
    context,
  }) => {
    let callCount = 0;

    await page.route(API_GLOB, (route: Route) => {
      callCount++;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(FIXTURE_SUCCESS),
      });
    });

    await page.goto(HARNESS_URL);
    await expect(page.locator('[id="health-card-azure-001"]')).toBeVisible();

    const beforeCount = callCount;

    // Click the refresh button
    await page
      .locator('[id="refresh-integration-health-btn"]')
      .click();

    // Wait for a new network request to the health endpoint
    await page.waitForResponse(API_GLOB);

    expect(callCount).toBeGreaterThan(beforeCount);
  });

  // ── 8. Auth token forwarded in Authorization header ──────────────────────
  test("getToken result is sent as Bearer token in Authorization header", async ({
    page,
  }) => {
    let capturedAuth: string | null = null;

    await page.route(API_GLOB, (route: Route) => {
      capturedAuth = route.request().headers()["authorization"] ?? null;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(FIXTURE_SUCCESS),
      });
    });

    await page.goto(HARNESS_URL);
    await expect(page.locator('[id="health-card-azure-001"]')).toBeVisible();

    // Harness passes "test-token"; component should forward it
    expect(capturedAuth).toBe("Bearer test-token");
  });
});
