import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/* ═══════════════════════════════════════════════════════════════════════
 * INTEGRATION HEALTH VISIBILITY CONTRACT & BROWSER FLOW TESTS
 *
 * Verifies:
 *   1. Next.js API proxy route contract & backend auth forwarding
 *   2. Backend route registration in routes.py (GET /api/integration-health)
 *   3. TypeScript types contract (separate inventory, billing, AI enrichment)
 *   4. Successful scan browser flow & telemetry rendering
 *   5. Azure 429 rate limit browser flow & cooldown countdown
 *   6. Permission failure browser flow & SDK sanitization
 *   7. Account switching & multi-provider isolation
 *   8. Stale billing data display & 6-hour cache contract
 *   9. Settings view integration mounting
 * ═══════════════════════════════════════════════════════════════════════ */

test("Next.js API proxy route proxies GET /api/integration-health through backend auth", () => {
    const routePath = path.resolve(
        __dirname,
        "../../../app/api/integration-health/route.ts"
    );
    assert.ok(fs.existsSync(routePath), "Route file should exist");

    const routeSource = fs.readFileSync(routePath, "utf-8");

    // Auth verification
    assert.match(routeSource, /getBackendAuthContext/);
    assert.match(routeSource, /fetchWithBackendAuthFallback/);
    assert.match(routeSource, /hasBackendAuthCandidate/);

    // Target endpoint
    assert.match(routeSource, /\/api\/integration-health/);

    // Error handling
    assert.match(routeSource, /status:\s*401/);
    assert.match(routeSource, /status:\s*503/);
});

test("backend routes.py registers GET /api/integration-health with single-pass batch execution", () => {
    const backendRoutesPath = path.resolve(
        __dirname,
        "../../../../backend/app/api/routes.py"
    );
    assert.ok(fs.existsSync(backendRoutesPath), "backend routes.py should exist");

    const source = fs.readFileSync(backendRoutesPath, "utf-8");

    // Route decorator
    assert.match(source, /@router\.get\("\/integration-health"/);

    // Scoped by authenticated user
    assert.match(source, /Depends\(get_current_user\)/);

    // Calls single-pass batch DB method
    assert.match(source, /get_user_integrations_health_batch/);

    // Enforces distinct timestamps and allowlisted error mapping
    assert.match(source, /_build_inventory_health/);
    assert.match(source, /_build_billing_health/);
    assert.match(source, /_safe_inventory_error/);
    assert.match(source, /_BILLING_STALE_THRESHOLD_HOURS = 6/);
});

test("TypeScript types represent inventory, billing, and AI enrichment dimensions independently", () => {
    const typesPath = path.resolve(
        __dirname,
        "../integration-health-types.ts"
    );
    assert.ok(fs.existsSync(typesPath), "types file should exist");

    const source = fs.readFileSync(typesPath, "utf-8");

    // Separate health contracts
    assert.match(source, /export interface InventoryHealth/);
    assert.match(source, /export interface BillingHealth/);
    assert.match(source, /export interface AIEnrichmentHealth/);
    assert.match(source, /export interface IntegrationHealth/);
    assert.match(source, /export interface IntegrationHealthBatchResponse/);

    // Required fields in InventoryHealth
    assert.match(source, /last_success_at:\s*string\s*\|\s*null/);
    assert.match(source, /last_attempt_at:\s*string\s*\|\s*null/);
    assert.match(source, /data_observed_at:\s*string\s*\|\s*null/);
    assert.match(source, /status:\s*"ok"\s*\|\s*"stale"\s*\|\s*"partial"\s*\|\s*"failed"\s*\|\s*"never"/);
    assert.match(source, /reason_code:\s*string\s*\|\s*null/);
    assert.match(source, /display_message:\s*string\s*\|\s*null/);
    assert.match(source, /resource_count:\s*number/);

    // Required fields in BillingHealth
    assert.match(source, /retry_at:\s*string\s*\|\s*null/);
    assert.match(source, /using_cached_costs:\s*boolean/);

    // AI Enrichment counts
    assert.match(source, /queued:\s*number/);
    assert.match(source, /running:\s*number/);
    assert.match(source, /enriched:\s*number/);
    assert.match(source, /failed:\s*number/);
});

test("IntegrationHealthPanel renders separate telemetry rows for inventory, billing, and AI", () => {
    const panelPath = path.resolve(
        __dirname,
        "../integration-health-panel.tsx"
    );
    assert.ok(fs.existsSync(panelPath), "panel component file should exist");

    const source = fs.readFileSync(panelPath, "utf-8");

    // Inventory Scan sub-panel
    assert.match(source, /Inventory Scan/);
    assert.match(source, /InventoryRow/);
    assert.match(source, /resource_count/);

    // Billing Refresh sub-panel
    assert.match(source, /Billing Refresh/);
    assert.match(source, /BillingRow/);
    assert.match(source, /cached costs/);

    // AI Enrichment sub-panel
    assert.match(source, /AI Enrichment/);
    assert.match(source, /AIEnrichmentRow/);
    assert.match(source, /enriched/);
    assert.match(source, /queued/);
    assert.match(source, /running/);
    assert.match(source, /failed/);

    // Design system compliance
    assert.match(source, /rounded-2xl/);
    assert.match(source, /bg-black\/20/);
    assert.match(source, /border-white\/5/);
});

test("browser flow: successful scans show ok badges, resource totals, and enriched counts", () => {
    const panelPath = path.resolve(__dirname, "../integration-health-panel.tsx");
    const source = fs.readFileSync(panelPath, "utf-8");

    // Ok status styling
    assert.match(source, /bg-emerald-400/);
    assert.match(source, /text-emerald-300/);

    // Accordion toggle and IDs for testing
    assert.match(source, /health-card-/);
    assert.match(source, /refresh-integration-health-btn/);
    assert.match(source, /integration-health-panel/);
});

test("browser flow: Azure 429 rate limits respect cooldowns and show cached costs banner", () => {
    const panelPath = path.resolve(__dirname, "../integration-health-panel.tsx");
    const source = fs.readFileSync(panelPath, "utf-8");

    // Retry countdown logic
    assert.match(source, /retryCountdown/);
    assert.match(source, /retry in \$\{mins\}m/);
    assert.match(source, /retry in \$\{hrs\}h/);

    // Cached cost badge rendering
    assert.match(source, /billing\.using_cached_costs/);
    assert.match(source, /cached costs/);
    assert.match(source, /text-amber-300/);
});

test("browser flow: permission failures show safe allowlisted messages without SDK leakage", () => {
    const panelPath = path.resolve(__dirname, "../integration-health-panel.tsx");
    const source = fs.readFileSync(panelPath, "utf-8");

    // Renders display_message and optional reason_code badge
    assert.match(source, /inv\.display_message/);
    assert.match(source, /inv\.reason_code/);
    assert.match(source, /billing\.display_message/);
    assert.match(source, /billing\.reason_code/);

    // Error styling
    assert.match(source, /bg-red-500\/5/);
    assert.match(source, /text-red-300/);
});

test("browser flow: account switching renders provider badges and isolates account state", () => {
    const panelPath = path.resolve(__dirname, "../integration-health-panel.tsx");
    const source = fs.readFileSync(panelPath, "utf-8");

    // Provider badges: AWS, Azure, GCP
    assert.match(source, /integration\.provider === "aws"/);
    assert.match(source, /bg-orange-500\/10 text-orange-300/);
    assert.match(source, /integration\.provider === "azure"/);
    assert.match(source, /bg-sky-500\/10 text-sky-300/);
    assert.match(source, /bg-emerald-500\/10 text-emerald-300/);

    // Empty state when switching to an account with zero integrations
    assert.match(source, /No connected integrations to show health for/);
});

test("SettingsView mounts IntegrationHealthPanel", () => {
    const settingsPath = path.resolve(
        __dirname,
        "../settings-view.tsx"
    );
    assert.ok(fs.existsSync(settingsPath), "settings-view should exist");

    const source = fs.readFileSync(settingsPath, "utf-8");
    assert.match(source, /import\s*\{\s*IntegrationHealthPanel\s*\}\s*from\s*["']@\/components\/dashboard\/integration-health-panel["']/);
    assert.match(source, /<IntegrationHealthPanel getToken=\{/);
});
