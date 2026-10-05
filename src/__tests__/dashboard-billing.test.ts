import assert from "node:assert/strict";
import test from "node:test";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import type { DashboardBillingSummaryResponse, DashboardMtdSpend, DashboardProviderCost } from "../lib/dashboard/data";

const root = fileURLToPath(new URL("../../", import.meta.url));
const require = createRequire(import.meta.url);

// Exercise the real transforms and TSX in memory without loading server credentials or services.
function loadModule<T>(path: string, overrides: Record<string, unknown> = {}): T {
    const cache = new Map<string, { exports: Record<string, unknown> }>();
    function load(filename: string): Record<string, unknown> {
        const cached = cache.get(filename);
        if (cached) return cached.exports;
        const loaded = { exports: {} as Record<string, unknown> };
        cache.set(filename, loaded);
        const output = ts.transpileModule(readFileSync(filename, "utf8"), {
            compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
            fileName: filename,
        }).outputText;
        const localRequire = (name: string): unknown => {
            if (Object.hasOwn(overrides, name)) return overrides[name];
            if (name.startsWith("@/") || name.startsWith(".")) {
                const base = name.startsWith("@/") ? resolve(root, "src", name.slice(2)) : resolve(dirname(filename), name);
                const target = [base, `${base}.ts`, `${base}.tsx`].find(existsSync);
                if (target) return load(target);
            }
            return require(name);
        };
        new Function("require", "module", "exports", output)(localRequire, loaded, loaded.exports);
        return loaded.exports;
    }
    return load(resolve(root, path)) as T;
}

function billing(overrides: Partial<DashboardMtdSpend> = {}): DashboardMtdSpend {
    return {
        amount: 200,
        currency: "INR",
        status: "fresh",
        completeness: "complete",
        observed_at: "2026-08-30T10:00:00Z",
        period_start: "2026-08-01",
        reason: null,
        retry_at: null,
        ...overrides,
    };
}

function summary(overrides: Partial<DashboardBillingSummaryResponse> = {}): DashboardBillingSummaryResponse {
    return {
        stats: { total_spend: 900, potential_savings: 0, active_resources_count: 1, ai_confidence_score: 50, carbon_footprint_kg: 0, cost_of_inaction_6mo: 0 },
        resources: [{ id: "vm-1", user_id: "user-1", integration_id: "azure-1", provider: "azure", cost: 800 }],
        resource_count: 1,
        integrations: [{ id: "azure-1", provider: "azure", name: "Azure", status: "active", last_scan: null, regions: [] }],
        integration_count: 1,
        waste_distribution: [],
        spend_history: [],
        permission_alert: null,
        provider_mtd_spend: [{ provider: "azure", ...billing() }],
        mtd_spend: billing(),
        ...overrides,
    };
}

function dataFor(response: DashboardBillingSummaryResponse | null) {
    return loadModule<typeof import("../lib/dashboard/data")>("src/lib/dashboard/data.ts", {
        "@/lib/api": { getDashboardSummary: () => Promise.resolve(response) },
    });
}

const { CostScoreSection } = loadModule<typeof import("../components/dashboard/cost-score-section")>("src/components/dashboard/cost-score-section.tsx", {
    "@/components/dashboard/savings-copilot-card": { SavingsCopilotCard: () => null },
});

function provider(value: DashboardMtdSpend): DashboardProviderCost {
    return { provider: "Azure", spend: 76543, resources: 1, savings: 0, current: value.amount, billing: value };
}

function render(props: Partial<React.ComponentProps<typeof CostScoreSection>> = {}): string {
    return renderToStaticMarkup(React.createElement(CostScoreSection, {
        totalSpend: 98765,
        potentialSavings: 0,
        annualSavings: 0,
        aiConfidence: 50,
        totalResources: 1,
        costOfInaction: 0,
        providerCosts: [provider(billing())],
        mtdSpend: billing(),
        ...props,
    }));
}

const dashboardOverrides = {
    "@/components/dashboard/savings-copilot-card": { SavingsCopilotCard: () => null },
    "@/components/dashboard/commitments/commitment-optimizer-card": { CommitmentOptimizerCard: () => null },
    "@/components/dashboard/rescan-button": { RescanButton: () => null },
    "@/components/dashboard/exclude-resource-modal": { ExcludeResourceModal: () => null },
};

const { DashboardSectionsClient } = loadModule<typeof import("../components/dashboard/dashboard-sections-client")>(
    "src/components/dashboard/dashboard-sections-client.tsx", dashboardOverrides,
);

function renderSections(stats: Awaited<ReturnType<typeof import("../lib/dashboard/data").getDashboardPageData>>["stats"], hasConnectedAccounts = true): string {
    return renderToStaticMarkup(React.createElement(DashboardSectionsClient, {
        stats, resources: [], wasteData: [], spendData: [], inventory: undefined, hasConnectedAccounts,
    }));
}

test("dashboard maps authoritative INR MTD without resource substitution or double conversion", async () => {
    const result = await dataFor(summary()).getDashboardPageData();
    assert.equal(result.stats?.providerCosts[0].current, 200);
    assert.equal(result.stats?.mtdSpend.amount, 200);
    assert.notEqual(result.stats?.totalSpend, 200);
});

test("missing billing fields stay unavailable even with large resource costs", async () => {
    const result = await dataFor(summary({ provider_mtd_spend: undefined, mtd_spend: undefined })).getDashboardPageData();
    assert.equal(result.stats?.providerCosts[0].current, null);
    assert.equal(result.stats?.providerCosts[0].billing?.status, "unavailable");
    assert.equal(result.stats?.mtdSpend.amount, null);
});

test("a connected provider with confirmed zero remains visible without resources", async () => {
    const zero = billing({ amount: 0, status: "cached" });
    const result = await dataFor(summary({ resources: [], provider_mtd_spend: [{ provider: "azure", ...zero }], mtd_spend: zero })).getDashboardPageData();
    assert.equal(result.stats?.providerCosts.length, 1);
    assert.equal(result.stats?.providerCosts[0].current, 0);
    assert.equal(result.stats?.mtdSpend.amount, 0);
});

test("summary failure resolves to the existing empty result", async () => {
    const data = loadModule<typeof import("../lib/dashboard/data")>("src/lib/dashboard/data.ts", {
        "@/lib/api": { getDashboardSummary: () => Promise.reject(new Error("Unavailable")) },
    });
    const result = await data.getDashboardPageData();
    assert.equal(result.stats, null);
    assert.deepEqual(result.resources, []);
});

test("unavailable Azure MTD does not fall back to portfolio or resource spend", () => {
    const unavailable = billing({ amount: null, status: "unavailable", completeness: "unavailable", observed_at: null });
    const html = render({ activeProvider: "azure", providerCosts: [provider(unavailable)] });
    assert.match(html, /MTD unavailable/);
    assert.match(html, /Billing unavailable/);
    assert.doesNotMatch(html, /₹200|₹98,765|₹76,543|100% of spend/);
});

test("fresh or cached valid zero renders as zero, not unavailable", () => {
    for (const status of ["fresh", "cached"] as const) {
        const zero = billing({ amount: 0, status });
        const html = render({ activeProvider: "azure", providerCosts: [provider(zero)] });
        assert.match(html, /₹0/);
        assert.match(html, new RegExp(`Billing ${status}`));
        assert.match(html, /No spend this month/);
        assert.doesNotMatch(html, /MTD unavailable/);
    }
});

test("stale preserved billing renders its INR amount, observation and retry", () => {
    const stale = billing({ status: "stale", retry_at: "2026-08-31T15:00:00Z" });
    const html = render({ activeProvider: "azure", providerCosts: [provider(stale)] });
    assert.match(html, /₹200/);
    assert.match(html, /Billing stale/);
    assert.match(html, /Observed .*2026.*UTC/);
    assert.match(html, /Retry after .*2026.*UTC/);
    assert.doesNotMatch(html, /₹19,038/);
});

test("portfolio MTD uses backend billing independently of total_spend stats", () => {
    const html = render({ mtdSpend: billing({ amount: 420 }) });
    assert.match(html, /₹420/);
    assert.doesNotMatch(html, /₹98,765|₹76,543/);
});

test("partial portfolio is unavailable and never shows a complete provider share", () => {
    const html = render({ mtdSpend: billing({ amount: null, status: "unavailable", completeness: "partial" }) });
    assert.match(html, /Partial billing/);
    assert.match(html, /MTD unavailable/);
    assert.doesNotMatch(html, /100% of spend/);
});

test("absent provider and legacy portfolio billing do not fall back to stats", () => {
    const scoped = render({ activeProvider: "aws" });
    assert.match(scoped, /MTD unavailable/);
    assert.doesNotMatch(scoped, /₹200|₹98,765/);
    assert.match(render({ mtdSpend: undefined }), /MTD unavailable/);
});

test("legacy known billing never claims a fresh observation", () => {
    const html = render({ activeProvider: "azure", providerCosts: [provider(billing({ status: "known", observed_at: null }))] });
    assert.match(html, /Freshness unknown/);
    assert.doesNotMatch(html, /Billing fresh|Observed /);
});

test("actual cost-score callsite passes portfolio MTD and retains zero-resource provider lens", async () => {
    const zero = billing({ amount: 0, status: "cached", as_of: "2026-08-31T12:00:00Z" });
    const result = await dataFor(summary({ resources: [], provider_mtd_spend: [{ provider: "azure", ...zero }], mtd_spend: zero })).getDashboardPageData();
    const html = renderSections(result.stats);
    assert.match(html, /AZURE<\/button>/);
    assert.match(html, /No spend this month/);
    assert.match(html, /Billing cached/);
    assert.match(html, /As of .*2026.*UTC/);
    assert.doesNotMatch(html, /MTD unavailable/);
});

test("failed summary shows an error instead of perpetual loading or a disconnected account", () => {
    const html = renderSections(null, false);
    assert.match(html, /role="alert"/);
    assert.match(html, /Dashboard data unavailable/);
    assert.doesNotMatch(html, /Connect an account to start|animate-pulse/);
});

test("initial dashboard and refresh render the same summary path with changed billing state", async () => {
    const unavailable = billing({ amount: null, status: "unavailable", completeness: "unavailable" });
    const responses = [summary(), summary({ provider_mtd_spend: [{ provider: "azure", ...unavailable }], mtd_spend: unavailable })];
    let calls = 0;
    const { default: Page } = loadModule<typeof import("../app/dashboard/page")>("src/app/dashboard/page.tsx", {
        ...dashboardOverrides,
        "@/lib/api": { getDashboardSummary: () => Promise.resolve(responses[calls++]) },
        "@/lib/sync-user": { syncUser: () => Promise.resolve() },
    });
    const initial = renderToStaticMarkup(await Page());
    const refreshed = renderToStaticMarkup(await Page());
    assert.equal(calls, 2);
    assert.match(initial, /₹200/);
    assert.match(refreshed, /MTD unavailable/);
    assert.doesNotMatch(refreshed, /₹200/);
    const scanProviderSource = readFileSync(resolve(root, "src/components/dashboard/scan-provider.tsx"), "utf8");
    assert.match(scanProviderSource, /router\.refresh\(\)/);
    const apiSource = readFileSync(resolve(root, "src/lib/api.ts"), "utf8");
    assert.match(apiSource, /getBackendJson<DashboardSummaryResponse>\("\/api\/dashboard\/summary"\)/);
});

test("real backend fake-DB summary survives the frontend transform and rendered dashboard", async () => {
    const payload = execFileSync(resolve(root, "backend/venv/bin/python"), ["-c", `
import json, runpy, sys
sys.path.insert(0, "backend")
f = runpy.run_path("backend/tests/test_dashboard_billing_summary.py")
f["summary_routes"].datetime = f["FrozenDateTime"]
f["cache"].redis_client = None
row = f["spend"](240)
row["metadata"] = {"billing": f["billing"](observed_at="2026-08-30T10:00:00Z")}
db = f["SummaryDB"]([f["integration"](metadata={"billing": f["billing"]("unavailable", observed_at=None)})], [row])
sys.stdout.write(json.dumps(f["summary"](db)))
`], {
        cwd: root, encoding: "utf8", timeout: 30000,
        env: {
            PATH: process.env.PATH,
            NODE_ENV: "test",
            DEBUG: "false",
            CLERK_SECRET_KEY: "test-only",
            MONGODB_URI: "mongodb://127.0.0.1:1/test-only",
            ENCRYPTION_KEY: "test-only",
        },
    });
    const response = JSON.parse(payload) as DashboardBillingSummaryResponse;
    assert.equal(response.mtd_spend?.status, "stale");
    assert.equal(response.mtd_spend?.observed_at, "2026-08-30T10:00:00+00:00");
    const result = await dataFor(response).getDashboardPageData();
    const html = renderSections(result.stats);
    assert.match(html, /₹240/);
    assert.match(html, /Billing stale/);
    assert.match(html, /Observed .*2026.*UTC/);
    assert.match(html, /As of .*2026.*UTC/);
    const trend = html.slice(html.indexOf("Daily Spend Trend"));
    assert.doesNotMatch(trend, />Live</);
});
