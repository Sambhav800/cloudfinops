import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const root = fileURLToPath(new URL("../../", import.meta.url));
const require = createRequire(import.meta.url);

interface ApiFixture {
    id: string;
    name: string;
    api_type: string;
    stage_name: string;
    endpoint_type: string;
    invocations_7d: number | null;
    error_rate_4xx: number | null;
    error_rate_5xx: number | null;
    latency_p99_ms: number | null;
    cache_enabled: boolean;
    cache_hit_rate: number | null;
    monthly_cost: number;
    status: string;
    provider: string;
    region: string;
    is_ghost: boolean;
}

function api(overrides: Partial<ApiFixture> = {}): ApiFixture {
    return {
        id: "unknown-api", name: "Unknown API", api_type: "REST", stage_name: "prod",
        endpoint_type: "REGIONAL", invocations_7d: null, error_rate_4xx: null,
        error_rate_5xx: null, latency_p99_ms: null, cache_enabled: false,
        cache_hit_rate: null, monthly_cost: 0, status: "Active", provider: "aws",
        region: "us-east-1", is_ghost: false, ...overrides,
    };
}

interface CapturedChart {
    kind: string;
    data: Record<string, unknown>[];
}

function renderPage(resources: ApiFixture[], options: {
    sortField?: "invocations_7d" | "error_rate_5xx";
    sortDir?: "asc" | "desc";
    searchQuery?: string;
} = {}) {
    const report = {
        api_resources: resources,
        ghost_apis: resources.filter(r => r.is_ghost).map(r => ({
            resource_id: r.id, name: r.name, api_type: r.api_type, stage_name: r.stage_name,
            provider: r.provider, monthly_cost: 0, annual_cost: 0, invocations_7d: r.invocations_7d,
            ghost_reason: "No measured traffic", fix_command: "",
        })),
        cache_waste: [], shadow_apis: [], cost_per_request_ranking: [],
        total_api_count: resources.length, total_api_spend: 0, total_api_waste: 0,
        ghost_api_count: resources.filter(r => r.is_ghost).length,
        cache_waste_monthly: 0, providers_detected: ["aws"], ai_narrative: "",
    };
    const states: unknown[] = [report, false, null, options.searchQuery ?? "", options.sortField ?? "invocations_7d", options.sortDir ?? "desc"];
    let stateIndex = 0;
    const charts: CapturedChart[] = [];
    const chartComponents = Object.fromEntries([
        "AreaChart", "Area", "BarChart", "Bar", "XAxis", "YAxis", "CartesianGrid",
        "Tooltip", "ResponsiveContainer", "Cell", "PieChart", "Pie",
    ].map(kind => [kind, ({ children, data }: { children?: React.ReactNode; data?: CapturedChart["data"] }) => {
        if (data) charts.push({ kind, data });
        return React.createElement(React.Fragment, null, children);
    }]));
    const cache = new Map<string, { exports: Record<string, unknown> }>();

    // Render the real page and chart preparation in memory; only external UI/services are stubbed.
    function load(filename: string): Record<string, unknown> {
        const cached = cache.get(filename);
        if (cached) return cached.exports;
        const loaded = { exports: {} as Record<string, unknown> };
        cache.set(filename, loaded);
        const output = ts.transpileModule(readFileSync(filename, "utf8"), {
            fileName: filename,
            compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
        }).outputText;
        const localRequire = (name: string): unknown => {
            if (name === "react") return {
                ...React,
                useEffect: () => undefined,
                useState: (initial: unknown) => [stateIndex < states.length ? states[stateIndex++] : initial, () => undefined],
            };
            if (name === "next/navigation") return { useSearchParams: () => new URLSearchParams() };
            if (name === "@clerk/nextjs") return { useAuth: () => ({ userId: "test-user" }) };
            if (name === "recharts") return chartComponents;
            if (name.startsWith("@/") || name.startsWith(".")) {
                const base = name.startsWith("@/") ? resolve(root, "src", name.slice(2)) : resolve(dirname(filename), name);
                const target = [base, `${base}.ts`, `${base}.tsx`].find(candidate => existsSync(candidate));
                if (target) return load(target);
            }
            return require(name);
        };
        new Function("require", "module", "exports", output)(localRequire, loaded, loaded.exports);
        return loaded.exports;
    }

    const { default: Page } = load(resolve(root, "src/app/dashboard/apis/page.tsx")) as { default: React.ComponentType };
    const html = renderToStaticMarkup(React.createElement(Page));
    const inventory = html.slice(html.indexOf("API Inventory"));
    const rows = [...inventory.matchAll(/<tbody>([\s\S]*?)<\/tbody>/g)]
        .flatMap(match => [...match[1].matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/g)].map(row => row[1]));
    return { html, rows, charts };
}

test("unknown metrics render as unmeasured without a traffic chart or active/idle/ghost classification", () => {
    const { html, rows, charts } = renderPage([api()]);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].match(/Not measured/g)?.length, 3);
    assert.match(rows[0], />\s*Unknown\s*</);
    assert.doesNotMatch(rows[0], />\s*(Active|Idle|Ghost)\s*<|0\.0%|0ms/);
    assert.equal(charts.some(chart => chart.kind === "BarChart"), false);
    assert.deepEqual(charts.find(chart => chart.kind === "Pie")?.data.map(({ name, value }) => ({ name, value })), [{ name: "Unknown", value: 1 }]);
    assert.doesNotMatch(html, /NaN|Infinity|Cost Per 1K Requests/);
});

test("mixed measurements keep missing error counts null and chart only finite measured traffic", () => {
    const { rows, charts } = renderPage([
        api(),
        api({ id: "known", name: "Measured API", invocations_7d: 1000, error_rate_4xx: 0, error_rate_5xx: 6, latency_p99_ms: 120 }),
        api({ id: "partial", name: "Partial API", invocations_7d: 200 }),
    ]);
    assert.match(rows[0], /Measured API/);
    assert.match(rows[0], />1,000<|>1000</);
    assert.match(rows[0], /6\.0%/);
    assert.match(rows[0], /120ms/);
    assert.match(rows[1], /Partial API/);
    assert.equal(rows[1].match(/Not measured/g)?.length, 2);
    assert.match(rows[2], /Unknown API/);
    assert.deepEqual(charts.find(chart => chart.kind === "BarChart")?.data, [
        { name: "Measured API", invocations: 1000, errors: 60 },
        { name: "Partial API", invocations: 200, errors: null },
    ]);
    assert.deepEqual(charts.find(chart => chart.kind === "Pie")?.data.map(({ name, value }) => ({ name, value })), [
        { name: "Active", value: 2 }, { name: "Unknown", value: 1 },
    ]);
});

test("measured zero stays zero and only backend ghost flags produce ghost status", () => {
    const zero = api({ id: "zero", name: "Zero API", invocations_7d: 0, error_rate_4xx: 0, error_rate_5xx: 0, latency_p99_ms: 0 });
    const { rows, charts } = renderPage([zero, { ...zero, id: "ghost", name: "Ghost API", is_ghost: true }]);
    assert.match(rows[0], />0</);
    assert.match(rows[0], /0\.0%/);
    assert.match(rows[0], /0ms/);
    assert.match(rows[0], />\s*Idle\s*</);
    assert.match(rows[1], />\s*Ghost\s*</);
    assert.doesNotMatch(rows.join(""), /Not measured|Unknown/);
    assert.deepEqual(charts.find(chart => chart.kind === "Pie")?.data.map(({ name, value }) => ({ name, value })), [
        { name: "Idle", value: 1 }, { name: "Ghost", value: 1 },
    ]);
});

test("unknown and non-finite values sort last in either direction for invocation and error metrics", () => {
    for (const sortField of ["invocations_7d", "error_rate_5xx"] as const) {
        for (const sortDir of ["asc", "desc"] as const) {
            const { rows } = renderPage([
                api(),
                api({ id: "invalid", name: "Invalid API", [sortField]: Number.NaN }),
                api({ id: "zero", name: "Zero API", [sortField]: 0 }),
                api({ id: "positive", name: "Positive API", [sortField]: 100 }),
            ], { sortField, sortDir });
            assert.match(rows[0], sortDir === "asc" ? /Zero API/ : /Positive API/);
            assert.match(rows[1], sortDir === "asc" ? /Positive API/ : /Zero API/);
            assert.match(rows[2], /Unknown API/);
            assert.match(rows[3], /Invalid API/);
            assert.doesNotMatch(rows.join(""), /NaN|Infinity/);
        }
    }
});

test("non-finite metrics are unmeasured and empty/search states remain available", () => {
    const { rows, charts } = renderPage([api({ invocations_7d: Infinity, error_rate_4xx: NaN, error_rate_5xx: Infinity, latency_p99_ms: NaN })]);
    assert.equal(rows[0].match(/Not measured/g)?.length, 3);
    assert.equal(charts.some(chart => chart.kind === "BarChart"), false);
    assert.match(renderPage([]).html, /No API Resources Detected/);
    assert.match(renderPage([api()], { searchQuery: "absent" }).html, /No APIs match your search/);
});
