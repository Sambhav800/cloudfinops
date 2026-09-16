import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import type { CommitmentRecommendationResponse, CommitmentScenario } from "../../../lib/api";

const root = fileURLToPath(new URL("../../../../", import.meta.url));
const require = createRequire(import.meta.url);
const cardPath = "src/components/dashboard/commitments/commitment-optimizer-card.tsx";
type CardModule = typeof import("../commitments/commitment-optimizer-card");

// Exercise the real components and client without relying on source-string assertions.
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
                const target = [base, `${base}.ts`, `${base}.tsx`].find((candidate) => existsSync(candidate));
                if (target) return load(target);
            }
            return require(name);
        };
        new Function("require", "module", "exports", output)(localRequire, loaded, loaded.exports);
        return loaded.exports;
    }
    return load(resolve(root, path)) as T;
}

const client = loadModule<typeof import("../../../lib/commitments/client")>("src/lib/commitments/client.ts");

function scenario(overrides: Partial<CommitmentScenario> = {}): CommitmentScenario {
    return {
        label: "1-year Compute Savings Plan", commitment_pct: null, monthly_commitment_usd: 730,
        monthly_saving_usd: 100, annual_saving_usd: 1200, effective_discount_pct: null,
        provider_estimated_savings_pct: null, over_commitment_risk_pct: null, risk_level: "Unassessed",
        term_years: 1, hourly_commitment_usd: 1, estimated_utilization_pct: null,
        integration_id: "aws-1", account_id: "123456789012", recommendation_id: "rec-1",
        source: "aws_cost_explorer", generated_at: "2026-09-16T03:00:00Z",
        payment_option: "NO_UPFRONT", savings_plans_type: "COMPUTE_SP", lookback_days: 60, ...overrides,
    };
}

function recommendation(overrides: Partial<CommitmentRecommendationResponse> = {}): CommitmentRecommendationResponse {
    return {
        status: "ready", source: "aws_cost_explorer", pricing_basis: "live_api", currency: "USD",
        fetched_at: "2026-09-16T04:00:00Z", generated_at: "2026-09-16T03:00:00Z",
        scenarios: [scenario()], recommended_scenario: null,
        important_notes: ["Term options for the same account are alternatives and must not be added together."],
        ...overrides,
    };
}

function render(data: CommitmentRecommendationResponse): string {
    const { CommitmentOptimizerCard } = loadModule<CardModule>(cardPath);
    return renderToStaticMarkup(React.createElement(CommitmentOptimizerCard, { initialData: data }));
}

function lifecycle() {
    const states: unknown[] = [];
    let cursor = 0;
    let effect: (() => void | (() => void)) | undefined;
    const react = {
        ...React,
        useState: (initial: unknown) => {
            const index = cursor++;
            if (states.length <= index) states.push(initial);
            return [states[index], (value: unknown) => {
                states[index] = typeof value === "function" ? (value as (prior: unknown) => unknown)(states[index]) : value;
            }];
        },
        useEffect: (callback: () => void | (() => void)) => { effect = callback; },
    };
    const { CommitmentOptimizerCard } = loadModule<CardModule>(cardPath, { react });
    return {
        render: () => {
            cursor = 0;
            return renderToStaticMarkup(React.createElement(CommitmentOptimizerCard, {}));
        },
        start: () => {
            assert.ok(effect);
            return effect();
        },
    };
}

test("ready card renders provider alternatives, nullable measurements and evidence without fabricated totals", () => {
    const html = render(recommendation({ scenarios: [
        scenario(),
        scenario({ term_years: 3, label: "3-year Compute Savings Plan", monthly_saving_usd: 250, recommendation_id: "rec-3" }),
    ] }));
    assert.match(html, /AWS Cost Explorer/);
    assert.match(html, /1-year Compute Savings Plan/);
    assert.match(html, /3-year Compute Savings Plan/);
    assert.match(html, /USD\s+100\.00/);
    assert.match(html, /USD\s+250\.00/);
    assert.match(html, /Not measured/);
    assert.match(html, /Sep 16, 2026/);
    assert.match(html, /Provider API/);
    assert.match(html, /must not be added together/);
    assert.match(html, /href="\/dashboard\/optimizer"/);
    assert.doesNotMatch(html, /USD\s+350\.00|Low Risk|Break.?even|Target Coverage|Projected Monthly Spend|NaN|0\.0%/i);
});

test("every non-ready status remains explicit; missing evidence never implies fully covered", () => {
    const statuses: CommitmentRecommendationResponse["status"][] = [
        "not_synced", "stale", "unavailable", "no_recommendations", "unsupported", "insufficient_history", "no_spend_data",
    ];
    for (const status of statuses) {
        const html = render(recommendation({
            status, scenarios: [], pricing_basis: null, fetched_at: null, generated_at: null,
            message: `Evidence state: ${status}`,
        }));
        assert.ok(html.includes(`Evidence state: ${status}`));
        assert.match(html, /No alternatives available/);
        assert.match(html, /Not measured/);
        assert.doesNotMatch(html, /No new commitments required|fully covered|USD\s+0\.00|NaN|0\.0%/);
    }
});

test("stale or failed snapshots never expose retained purchase alternatives", () => {
    const html = render(recommendation({ status: "stale", message: "Provider estimate expired." }));
    assert.match(html, /Stale provider data|Provider estimate expired/);
    assert.doesNotMatch(html, /USD\s+100\.00|1-year Compute Savings Plan/);
});

test("measured zero is rendered distinctly from missing estimates", () => {
    const html = render(recommendation({ scenarios: [scenario({ monthly_saving_usd: 0, annual_saving_usd: 0, provider_estimated_savings_pct: 0 })] }));
    assert.match(html, /USD\s+0\.00/);
    assert.match(html, /0\.0%/);
    assert.match(html, /Risk: Not measured/);
});

test("loading uses skeletons without provisional financial values", () => {
    const { CommitmentOptimizerCard } = loadModule<CardModule>(cardPath);
    const html = renderToStaticMarkup(React.createElement(CommitmentOptimizerCard, {}));
    assert.match(html, /Loading provider recommendations/);
    assert.match(html, /aria-busy="true"/);
    assert.match(html, /disabled/);
    assert.doesNotMatch(html, /USD|0%|fully covered/);
});

test("dashboard card reads the canonical same-origin endpoint and preserves ready data", async (t) => {
    const payload = recommendation();
    t.mock.method(globalThis, "fetch", (url: string, init: RequestInit) => {
        assert.equal(url, "/api/finance/commitment-recommendation");
        assert.equal(init.cache, "no-store");
        assert.ok(init.signal);
        return Promise.resolve(Response.json(payload));
    });
    const harness = lifecycle();
    harness.render();
    const cleanup = harness.start();
    await new Promise((resolve) => setImmediate(resolve));
    assert.match(harness.render(), /USD\s+100\.00/);
    assert.equal(typeof cleanup, "function");
    if (cleanup) cleanup();
});

test("legacy nullable optimizer payload is rejected as an error, not rendered as a healthy portfolio", async (t) => {
    t.mock.method(globalThis, "fetch", () => Promise.resolve(Response.json({
        status: "withheld", recommendations: [], overall_coverage_pct: null,
        projected_monthly_after_commitments: null, current_monthly_on_demand: null,
        total_monthly_savings: 0, total_annual_savings: 0,
        withheld_reasons: ["validated_hourly_residual_evidence_required", "verified_live_quotes_required"],
    })));
    const harness = lifecycle();
    harness.render();
    const cleanup = harness.start();
    await new Promise((resolve) => setImmediate(resolve));
    const html = harness.render();
    assert.match(html, /invalid response/);
    assert.match(html, /Retry recommendations/);
    assert.doesNotMatch(html, /aria-busy="true"|fully covered|USD\s+0\.00|NaN/);
    if (cleanup) cleanup();
});

test("timeouts clear loading and render an actionable retry error", async (t) => {
    t.mock.method(globalThis, "fetch", () => Promise.reject(new DOMException("Timed out", "TimeoutError")));
    const harness = lifecycle();
    harness.render();
    const cleanup = harness.start();
    await new Promise((resolve) => setImmediate(resolve));
    const html = harness.render();
    assert.match(html, /timed out.*retry/i);
    assert.match(html, /role="alert"/);
    assert.match(html, /Retry recommendations/);
    assert.doesNotMatch(html, /aria-busy="true"/);
    if (cleanup) cleanup();
});

test("effect cleanup aborts the request and prevents a late response from overwriting state", async (t) => {
    let complete: ((response: Response) => void) | undefined;
    let signal: AbortSignal | null | undefined;
    t.mock.method(globalThis, "fetch", (_url: string, init: RequestInit) => {
        signal = init.signal;
        return new Promise<Response>((resolve) => { complete = resolve; });
    });
    const harness = lifecycle();
    harness.render();
    const cleanup = harness.start();
    assert.ok(signal);
    assert.equal(signal.aborted, false);
    assert.equal(typeof cleanup, "function");
    if (cleanup) cleanup();
    assert.equal(signal.aborted, true);
    assert.ok(complete);
    complete(Response.json(recommendation()));
    await new Promise((resolve) => setImmediate(resolve));
    assert.doesNotMatch(harness.render(), /USD\s+100\.00|Provider alternatives available/);
});

test("client accepts the canonical empty result and measured zero", async (t) => {
    const empty = recommendation({ status: "not_synced", scenarios: [], pricing_basis: null, fetched_at: null, generated_at: null });
    const mock = t.mock.method(globalThis, "fetch", () => Promise.resolve(Response.json(empty)));
    assert.deepEqual(await client.loadCommitmentRecommendations(new AbortController().signal), empty);
    const zero = recommendation({ scenarios: [scenario({ monthly_saving_usd: 0, annual_saving_usd: 0 })] });
    mock.mock.mockImplementation(() => Promise.resolve(Response.json(zero)));
    assert.deepEqual(await client.loadCommitmentRecommendations(new AbortController().signal), zero);
});

test("client rejects malformed or contradictory provider evidence before rendering", async (t) => {
    const malformed: unknown[] = [
        null, {}, recommendation({ scenarios: [] }), recommendation({ status: "stale" }),
        { ...recommendation(), scenarios: [null] },
        { ...recommendation(), scenarios: [{ ...scenario(), risk_level: "low" }] },
        { ...recommendation(), scenarios: [{ ...scenario(), monthly_saving_usd: null }] },
        { ...recommendation(), scenarios: [{ ...scenario(), monthly_saving_usd: -1 }] },
        { ...recommendation(), scenarios: [{ ...scenario(), account_id: "" }] },
        { ...recommendation(), scenarios: [{ ...scenario(), provider_estimated_savings_pct: 101 }] },
        { ...recommendation(), scenarios: [{ ...scenario(), generated_at: "invalid" }] },
        { ...recommendation(), scenarios: [{ ...scenario(), generated_at: "2026-09-16T03:00:00" }] },
        { ...recommendation(), important_notes: [null] },
        { ...recommendation(), message: {} },
        recommendation({ pricing_basis: null }), recommendation({ fetched_at: null }),
    ];
    const mock = t.mock.method(globalThis, "fetch", () => Promise.resolve(Response.json(null)));
    for (const payload of malformed) {
        mock.mock.mockImplementation(() => Promise.resolve(Response.json(payload)));
        await assert.rejects(client.loadCommitmentRecommendations(new AbortController().signal), /invalid response/);
    }
});

test("dashboard retains the card and obsolete duplicate portfolio types are removed", () => {
    const dashboard = readFileSync(resolve(root, "src/components/dashboard/dashboard-sections-client.tsx"), "utf8");
    assert.match(dashboard, /<CommitmentOptimizerCard\s*\/>/);
    assert.equal(existsSync(resolve(root, "src/components/dashboard/commitments/types.ts")), false);
});
