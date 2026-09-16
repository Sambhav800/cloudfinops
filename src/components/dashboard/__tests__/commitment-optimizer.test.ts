import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/* ═══════════════════════════════════════════════════════════════════════
 * COMMITMENT OPTIMIZER CONTRACT & UI TESTS
 *
 * Verifies:
 *   1. Next.js API proxy route contract & parameter forwarding
 *   2. Backend route registration in routes.py
 *   3. CommitmentOptimizerCard component design system & badges
 *   4. Alerts for underutilized commitments & expiring-soon (<60 days)
 *   5. Slide-over drawer / breakdown modal structure
 *   6. Type safety and schema completeness
 * ═══════════════════════════════════════════════════════════════════════ */

test("Next.js API proxy route proxies GET /api/commitment-recommendations through backend auth", () => {
    const routePath = path.resolve(
        __dirname,
        "../../../app/api/commitment-recommendations/route.ts"
    );
    assert.ok(fs.existsSync(routePath), "Route file should exist");

    const routeSource = fs.readFileSync(routePath, "utf-8");

    // Auth verification
    assert.match(routeSource, /getBackendAuthContext/);
    assert.match(routeSource, /fetchWithBackendAuthFallback/);
    assert.match(routeSource, /hasBackendAuthCandidate/);

    // Target endpoint
    assert.match(routeSource, /\/api\/commitment-recommendations/);

    // Parameter forwarding
    assert.match(routeSource, /searchParams\.get\("coverage_target"\)/);
    assert.match(routeSource, /searchParams\.get\("max_term"\)/);
    assert.match(routeSource, /searchParams\.get\("payment_option"\)/);

    // Error handling
    assert.match(routeSource, /status:\s*401/);
    assert.match(routeSource, /status:\s*503/);
});

test("backend routes.py registers GET /api/commitment-recommendations with ClerkUser and query parameters", () => {
    const backendRoutesPath = path.resolve(
        __dirname,
        "../../../../backend/app/api/routes.py"
    );
    assert.ok(fs.existsSync(backendRoutesPath), "backend routes.py should exist");

    const source = fs.readFileSync(backendRoutesPath, "utf-8");

    // Route decorator
    assert.match(source, /@router\.get\("\/commitment-recommendations"\)/);

    // Clerk user dependency
    assert.match(source, /user:\s*ClerkUser\s*=\s*Depends\(get_current_user\)/);

    // Query parameters
    assert.match(source, /coverage_target:\s*float\s*=\s*Query/);
    assert.match(source, /max_term:\s*Optional\[str\]\s*=\s*Query/);
    assert.match(source, /payment_option:\s*Optional\[str\]\s*=\s*Query/);

    // Core function calls
    assert.match(source, /analyze_usage_baselines/);
    assert.match(source, /generate_commitment_recommendations/);
    assert.match(source, /commitment_engine\.get_commitments/);
});

test("CommitmentOptimizerCard follows design system: bg-slate-900/50, border-white/10, indigo-600, risk badges", () => {
    const cardPath = path.resolve(
        __dirname,
        "../commitments/commitment-optimizer-card.tsx"
    );
    assert.ok(fs.existsSync(cardPath), "CommitmentOptimizerCard component should exist");

    const source = fs.readFileSync(cardPath, "utf-8");

    // Card styling
    assert.match(source, /bg-slate-900\/50/);
    assert.match(source, /border-white\/10/);
    assert.match(source, /backdrop-blur-xl/);

    // Risk badge colors: emerald (low), amber (medium), rose (high)
    assert.match(source, /border-emerald-500\/30 bg-emerald-500\/10 text-emerald-400/);
    assert.match(source, /border-amber-500\/30 bg-amber-500\/10 text-amber-400/);
    assert.match(source, /border-rose-500\/30 bg-rose-500\/10 text-rose-400/);

    // Provider badge mapping: AWS, Azure, GCP
    assert.match(source, /AWS/);
    assert.match(source, /Azure/);
    assert.match(source, /GCP/);

    // Action button styling
    assert.match(source, /bg-indigo-600/);
});

test("CommitmentOptimizerCard renders all required KPI metrics", () => {
    const cardPath = path.resolve(
        __dirname,
        "../commitments/commitment-optimizer-card.tsx"
    );
    const source = fs.readFileSync(cardPath, "utf-8");

    // Total potential savings / yr
    assert.match(source, /Potential Annual Savings/);
    assert.match(source, /total_annual_savings/);

    // Recommendations count
    assert.match(source, /Active Recommendations/);
    assert.match(source, /recommendations\.length/);

    // Overall coverage %
    assert.match(source, /Target Coverage/);
    assert.match(source, /overall_coverage_pct/);

    // Projected spend after commitments
    assert.match(source, /Projected Monthly Spend/);
    assert.match(source, /projected_monthly_after_commitments/);
});

test("CommitmentOptimizerCard includes underutilized alerts and expiring-soon warnings", () => {
    const cardPath = path.resolve(
        __dirname,
        "../commitments/commitment-optimizer-card.tsx"
    );
    const source = fs.readFileSync(cardPath, "utf-8");

    // Underutilized commitments section
    assert.match(source, /underutilized_commitments/);
    assert.match(source, /Underutilized Commitment/);
    assert.match(source, /wasted_monthly/);
    assert.match(source, /utilization_pct/);

    // Expiring soon section
    assert.match(source, /expiring_soon/);
    assert.match(source, /Expiring Soon/);
    assert.match(source, /days_left/);
});

test("CommitmentOptimizerCard includes expandable drawer with spend transformation, break-even, and engine explanation", () => {
    const cardPath = path.resolve(
        __dirname,
        "../commitments/commitment-optimizer-card.tsx"
    );
    const source = fs.readFileSync(cardPath, "utf-8");

    // Drawer id & trigger
    assert.match(source, /id="commitment-optimizer-drawer"/);
    assert.match(source, /id="view-all-commitments-btn"/);
    assert.match(source, /id="close-commitment-drawer-btn"/);

    // Commitment type badges (SP, RI, CUD)
    assert.match(source, /Compute SP/);
    assert.match(source, /EC2 Instance SP/);
    assert.match(source, /Azure RI/);
    assert.match(source, /Resource CUD/);
    assert.match(source, /Flexible CUD/);

    // Spend transformation & break-even
    assert.match(source, /Current Spend/);
    assert.match(source, /Projected Spend/);
    assert.match(source, /break_even_months/);

    // Engine explanation
    assert.match(source, /Engine Explanation/);
    assert.match(source, /rec\.explanation/);
});

test("DashboardSectionsClient embeds CommitmentOptimizerCard on main dashboard", () => {
    const dashboardSectionsPath = path.resolve(
        __dirname,
        "../dashboard-sections-client.tsx"
    );
    const source = fs.readFileSync(dashboardSectionsPath, "utf-8");

    assert.match(
        source,
        /import\s*\{\s*CommitmentOptimizerCard\s*\}\s*from\s*["']@\/components\/dashboard\/commitments\/commitment-optimizer-card["']/
    );
    assert.match(source, /<CommitmentOptimizerCard\s*\/>/);
});
