import assert from "node:assert/strict";
import test from "node:test";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import type { CloudCommitment, CommitmentRecommendationResponse, CommitmentScenario, CommitmentSummary, FinanceCommitmentsResponse } from "../../../lib/api";

const root = fileURLToPath(new URL("../../../../", import.meta.url));
const require = createRequire(import.meta.url);

// Transpile in memory: exercise actual TSX without a browser, build artifacts, or live services.
function loadModule<T>(path: string, states?: unknown[], overrides: Record<string, unknown> = {}): T {
    const cache = new Map<string, { exports: Record<string, unknown> }>();
    let stateIndex = 0;
    function load(filename: string): Record<string, unknown> {
        const cached = cache.get(filename);
        if (cached) return cached.exports;
        const loadedModule = { exports: {} as Record<string, unknown> };
        cache.set(filename, loadedModule);
        const source = readFileSync(filename, "utf8");
        const output = ts.transpileModule(source, {
            compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
            fileName: filename,
        }).outputText;
        const localRequire = (name: string): unknown => {
            if (Object.hasOwn(overrides, name)) return overrides[name];
            if (name === "react" && states) return {
                ...React,
                useEffect: () => undefined,
                useState: (initial: unknown) => [stateIndex < states.length ? states[stateIndex++] : initial, () => undefined],
            };
            if (name.startsWith("@/") || name.startsWith(".")) {
                const base = name.startsWith("@/") ? resolve(root, "src", name.slice(2)) : resolve(dirname(filename), name);
                const target = [base, `${base}.ts`, `${base}.tsx`].find((candidate) => existsSync(candidate));
                if (target) return load(target);
            }
            return require(name);
        };
        new Function("require", "module", "exports", output)(localRequire, loadedModule, loadedModule.exports);
        return loadedModule.exports;
    }
    return load(resolve(root, path)) as T;
}

const presentation = loadModule<typeof import("../../../lib/commitments/presentation")>("src/lib/commitments/presentation.ts");
const client = loadModule<typeof import("../../../lib/commitments/client")>("src/lib/commitments/client.ts");
const exporter = loadModule<typeof import("../../../lib/commitments/export")>("src/lib/commitments/export.ts");

const summary: CommitmentSummary = {
    currency: "USD", monthly_commitment: 730, measured_savings: 70,
    savings_period_start: "2026-09-01", savings_period_end: "2026-09-08",
    utilization_pct: null, coverage_pct: null, active_count: 1, measurement_status: "partial",
};

function commitment(overrides: Partial<CloudCommitment> = {}): CloudCommitment {
    return {
        id: "plan-1", integration_id: "aws-1", provider: "aws", type: "Savings Plan", name: "Compute Savings Plan",
        status: "active", start_date: "2026-01-01T00:00:00Z", end_date: "2099-01-01T00:00:00Z",
        commitment_amount: 730, hourly_commitment: 1, amount_period: "monthly", currency: "USD", region: null,
        utilization_pct: null, savings_amount: 70, savings_period_start: "2026-09-01", savings_period_end: "2026-09-08",
        source: "provider_api", pricing_basis: "live_api", coverage_type: "Compute", ...overrides,
    };
}

function scenario(overrides: Partial<CommitmentScenario> = {}): CommitmentScenario {
    return {
        label: "1-year Compute Savings Plan", commitment_pct: null, monthly_commitment_usd: 730,
        monthly_saving_usd: 100, annual_saving_usd: 1200, effective_discount_pct: null, provider_estimated_savings_pct: 12.5,
        over_commitment_risk_pct: null, risk_level: "Unassessed", term_years: 1, hourly_commitment_usd: 1,
        estimated_utilization_pct: null, integration_id: "aws-1", account_id: "123456789012", recommendation_id: "rec-1",
        source: "aws_cost_explorer", generated_at: "2026-09-15T03:00:00Z", payment_option: "NO_UPFRONT",
        savings_plans_type: "COMPUTE_SP", lookback_days: 60, ...overrides,
    };
}

function recommendation(overrides: Partial<CommitmentRecommendationResponse> = {}): CommitmentRecommendationResponse {
    return {
        status: "ready", source: "aws_cost_explorer", pricing_basis: "live_api", currency: "USD",
        fetched_at: "2026-09-15T04:00:00Z", generated_at: "2026-09-15T03:00:00Z",
        recommended_scenario: null, scenarios: [scenario()], ...overrides,
    };
}

test("unknown money/percent remain unmeasured; measured zero and native currencies remain distinct", () => {
    assert.equal(presentation.formatCommitmentMoney(null, "USD"), "Not measured");
    assert.equal(presentation.formatCommitmentMoney(730, null), "Not measured");
    assert.equal(presentation.formatCommitmentPercent(null), "Not measured");
    assert.equal(presentation.formatCommitmentPercent(0), "0.0%");
    assert.match(presentation.formatCommitmentMoney(0, "USD"), /USD\s+0\.00/);
    assert.match(presentation.formatCommitmentMoney(70, "EUR"), /EUR\s+70\.00/);
    assert.equal(presentation.formatCommitmentMoney(NaN, "USD"), "Not measured");
});

test("KPI renders backend monthly equivalent and dated seven-day savings without monthly relabeling", () => {
    const { CommitmentsKpiStrip } = loadModule<{ CommitmentsKpiStrip: React.ComponentType<{ summary: CommitmentSummary }> }>("src/components/dashboard/commitments/kpi-strip.tsx");
    const html = renderToStaticMarkup(React.createElement(CommitmentsKpiStrip, { summary }));
    assert.match(html, /USD\s+730\.00/);
    assert.match(html, /USD\s+70\.00/);
    assert.match(html, /Sep 1, 2026 to Sep 8, 2026/);
    assert.match(html, /Not measured/);
    assert.doesNotMatch(html, /Monthly Savings|Monthly savings|Net ROI|Effective Savings Rate|0\.0%/);
});

test("mixed-currency snapshot uses backend null totals and keeps inventory currencies and errors visible", () => {
    const snapshot: FinanceCommitmentsResponse = {
        commitments: [commitment(), commitment({ id: "plan-2", currency: "EUR", commitment_amount: 400 })], count: 2,
        summary: { ...summary, currency: null, monthly_commitment: null, measured_savings: null, active_count: 2 },
        integrations: [{ integration_id: "aws-1", provider: "aws", status: "error", commitment_count: 2, last_success_at: null, last_attempt_at: null, stale: true, error: "Access denied" }],
    };
    const { default: Page } = loadModule<{ default: React.ComponentType }>("src/app/dashboard/commitments/page.tsx", [snapshot, null, false, false, null, "Cost Explorer unavailable"]);
    const html = renderToStaticMarkup(React.createElement(Page));
    assert.match(html, /EUR\s+400\.00/);
    assert.match(html, /USD\s+730\.00/);
    assert.doesNotMatch(html, /1,130\.00/);
    assert.match(html, /Sync failed/);
    assert.match(html, /Stale snapshot/);
    assert.match(html, /Access denied/);
    assert.match(html, /Cost Explorer unavailable/);
    assert.match(html, /Retry/);
    assert.doesNotMatch(html, /NaN|No commitments found/);
});

test("unsupported and pending integrations are not represented as empty successful inventory", () => {
    const snapshot: FinanceCommitmentsResponse = {
        commitments: [], count: 0,
        summary: { ...summary, currency: null, monthly_commitment: null, measured_savings: null, active_count: 0, measurement_status: "unavailable" },
        integrations: [
            { integration_id: "azure-1", provider: "azure", status: "unsupported", commitment_count: 0, last_success_at: null, last_attempt_at: null },
            { integration_id: "gcp-1", provider: "gcp", status: "pending", commitment_count: 0, last_success_at: null, last_attempt_at: null },
        ],
    };
    const { default: Page } = loadModule<{ default: React.ComponentType }>("src/app/dashboard/commitments/page.tsx", [snapshot, null, false, false, null, null]);
    const html = renderToStaticMarkup(React.createElement(Page));
    assert.match(html, /Azure commitment inventory and purchase estimates unsupported/);
    assert.match(html, /GCP inventory only/);
    assert.match(html, /Sync pending/);
    assert.doesNotMatch(html, /No commitments found|All commitments healthy/);
});

test("optimizer shows provider alternatives despite null recommended_scenario, without fabricated discounts or ranking", () => {
    const data = recommendation({ scenarios: [scenario(), scenario({ term_years: 3, label: "3-year Compute Savings Plan", recommendation_id: "rec-3" })] });
    const { default: Page } = loadModule<{ default: React.ComponentType }>("src/app/dashboard/optimizer/page.tsx", [data, false, null, "", null]);
    const html = renderToStaticMarkup(React.createElement(Page));
    assert.match(html, /1-year Compute Savings Plan/);
    assert.match(html, /3-year Compute Savings Plan/);
    assert.match(html, /Estimated savings %/);
    assert.match(html, /12\.5%/);
    assert.match(html, /Export PDF/);
    assert.match(html, /All accounts/);
    assert.match(html, /Not measured/);
    assert.doesNotMatch(html, /AI-powered|Optimal|Our Recommendation|Effective discount|Avg Monthly Spend/);
});

test("optimizer account selection only shows that account's alternatives", () => {
    const data = recommendation({ scenarios: [scenario(), scenario({ account_id: "999999999999", label: "Other account option" })] });
    const { default: Page } = loadModule<{ default: React.ComponentType }>("src/app/dashboard/optimizer/page.tsx", [data, false, null, "123456789012", null]);
    const html = renderToStaticMarkup(React.createElement(Page));
    assert.match(html, /1-year Compute Savings Plan/);
    assert.doesNotMatch(html, /Other account option/);
});

test("every non-ready recommendation status renders explicitly, without zero estimates", () => {
    for (const status of Object.keys(presentation.RECOMMENDATION_STATUS_LABELS) as CommitmentRecommendationResponse["status"][]) {
        if (status === "ready") continue;
        const data = recommendation({ status, scenarios: [], pricing_basis: null, fetched_at: null, generated_at: null });
        const { default: Page } = loadModule<{ default: React.ComponentType }>("src/app/dashboard/optimizer/page.tsx", [data, false, null, "", null]);
        const html = renderToStaticMarkup(React.createElement(Page));
        assert.ok(html.includes(presentation.RECOMMENDATION_STATUS_LABELS[status]));
        assert.match(html, /No provider alternatives available/);
        assert.doesNotMatch(html, /USD\s+0\.00|0\.0%/);
    }
});

test("loading shows skeletons instead of provisional zero coverage or healthy claims", () => {
    const { default: Page } = loadModule<{ default: React.ComponentType }>("src/app/dashboard/commitments/page.tsx", [null, null, true, true, null, null]);
    const html = renderToStaticMarkup(React.createElement(Page));
    assert.match(html, /Loading commitment snapshot/);
    assert.match(html, /Loading provider recommendations/);
    assert.doesNotMatch(html, /0%|healthy|No scenario data/);
});

test("export preserves provider fields, null measurements, periods, and escapes account content", () => {
    const option = scenario({ account_id: "<script>alert(1)</script>" });
    const html = exporter.buildCommitmentExport(recommendation({ important_notes: ["Do not add alternatives together."] }), [option]);
    assert.match(html, /Estimated savings %/);
    assert.match(html, /12\.5%/);
    assert.match(html, /USD\s+730\.00/);
    assert.match(html, /USD\s+1,200\.00/);
    assert.match(html, /Not measured/);
    assert.match(html, /&lt;script&gt;/);
    assert.match(html, /Do not add alternatives together/);
    assert.match(html, /size: landscape/);
    assert.doesNotMatch(html, /<script>|AI-powered|Effective discount|Our Recommendation/);
});

test("client reads same-origin snapshots and preserves legitimate empty results", async (t) => {
    const payload = { commitments: [], count: 0, integrations: [], summary: { ...summary, active_count: 0 } };
    t.mock.method(globalThis, "fetch", (url: string, init: RequestInit) => {
        assert.equal(url, "/api/finance/commitments");
        assert.equal(init.cache, "no-store");
        assert.ok(init.signal);
        return Promise.resolve(Response.json(payload));
    });
    assert.deepEqual(await client.loadCommitmentSnapshot(new AbortController().signal), payload);
});

test("client preserves service errors instead of returning empty commitments", async (t) => {
    t.mock.method(globalThis, "fetch", () => Promise.resolve(Response.json({ detail: "Sync database unavailable" }, { status: 503 })));
    await assert.rejects(client.loadCommitmentSnapshot(new AbortController().signal), /Sync database unavailable/);
});

test("client rejects malformed success and old synthetic recommendations", async (t) => {
    const mock = t.mock.method(globalThis, "fetch", () => Promise.resolve(Response.json({})));
    await assert.rejects(client.loadCommitmentSnapshot(new AbortController().signal), /missing its summary/);
    mock.mock.mockImplementation(() => Promise.resolve(Response.json({ status: "ready", scenarios: [] })));
    await assert.rejects(client.loadCommitmentRecommendations(new AbortController().signal), /invalid response/);
});

test("client timeout becomes a retryable error", async (t) => {
    t.mock.method(globalThis, "fetch", () => Promise.reject(new DOMException("Timed out", "TimeoutError")));
    await assert.rejects(client.loadCommitmentRecommendations(new AbortController().signal), /timed out.*retry/i);
});

test("proxy preserves authentication checks, error status/body, and integration scope", async () => {
    let target = "";
    const auth = {
        getBackendAuthContext: () => Promise.resolve({ token: "test-token", userId: "test-user" }),
        hasBackendAuthCandidate: () => true,
        fetchWithBackendAuthFallback: (_fetch: unknown, url: string) => {
            target = url;
            return Promise.resolve(Response.json({ detail: "Owned integration not found" }, { status: 404 }));
        },
    };
    const { GET } = loadModule<{ GET: (request: { nextUrl: URL }) => Promise<Response> }>("src/app/api/finance/commitment-recommendation/route.ts", undefined, {
        "../../_shared/backend-auth": auth, "@/lib/config": { BACKEND_URL: "http://backend.invalid" },
    });
    const response = await GET({ nextUrl: new URL("http://localhost/api/finance/commitment-recommendation?integration_id=owned-id") });
    assert.equal(response.status, 404);
    assert.deepEqual(await response.json(), { detail: "Owned integration not found" });
    assert.equal(new URL(target).searchParams.get("integration_id"), "owned-id");
});

test("commitments proxy never fetches without auth and rejects invalid JSON from a successful upstream", async () => {
    let called = false;
    const auth = {
        getBackendAuthContext: (): Promise<{ token: string; userId: string } | null> => Promise.resolve(null),
        hasBackendAuthCandidate: () => true,
        fetchWithBackendAuthFallback: () => { called = true; return Promise.resolve(new Response("not json")); },
    };
    const { GET } = loadModule<{ GET: () => Promise<Response> }>("src/app/api/finance/commitments/route.ts", undefined, {
        "../../_shared/backend-auth": auth, "@/lib/config": { BACKEND_URL: "http://backend.invalid" },
    });
    assert.equal((await GET()).status, 401);
    assert.equal(called, false);
    auth.getBackendAuthContext = () => Promise.resolve({ token: "test-token", userId: "test-user" });
    assert.equal((await GET()).status, 502);
});

test("finance surfaces retain independent bounded reads and never calculate financial totals", () => {
    const page = readFileSync(resolve(root, "src/app/dashboard/commitments/page.tsx"), "utf8");
    const optimizer = readFileSync(resolve(root, "src/app/dashboard/optimizer/page.tsx"), "utf8");
    assert.match(page, /summary=\{snapshot.summary\}/);
    assert.match(page, /void loadInventory\(\)/);
    assert.match(page, /void loadRecommendations\(\)/);
    assert.match(page, /AbortSignal.timeout/);
    assert.match(optimizer, /AbortSignal.timeout/);
    assert.match(optimizer, /buildCommitmentExport\(data, visibleScenarios\)/);
    assert.match(optimizer, /printWindow.print\(\)/);
    assert.doesNotMatch(page + optimizer, /\.reduce\(|toDisplayInrAmount|computeRiskLevel|recommended_scenario|sessionStorage/);
});
