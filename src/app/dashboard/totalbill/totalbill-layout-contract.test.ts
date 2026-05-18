import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pageSource = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");
const experienceSource = readFileSync(
    new URL("../../../components/dashboard/total-bill-experience.tsx", import.meta.url),
    "utf8"
);
const routesSource = readFileSync(
    new URL("../../../../backend/app/api/routes.py", import.meta.url),
    "utf8"
);

test("total bill page keeps backend auth fetch server-side and delegates chart rendering", () => {
    assert.ok(pageSource.includes("getBackendAuthContext"));
    assert.ok(pageSource.includes("fetchWithBackendAuthFallback"));
    assert.ok(pageSource.includes('cache: "no-store"'));
    assert.ok(pageSource.includes("TotalBillExperience"));
});

test("total bill advanced visuals use recharts and backend-owned fields", () => {
    assert.ok(experienceSource.includes('from "recharts"'));
    assert.ok(experienceSource.includes("AreaChart"));
    assert.ok(experienceSource.includes("Treemap"));
    assert.ok(experienceSource.includes("Sankey"));
    assert.ok(experienceSource.includes("daily_provider_spend_30d"));
    assert.ok(experienceSource.includes("heatmap_days"));
    assert.ok(experienceSource.includes("provider_forecasts"));
    assert.ok(experienceSource.includes("service_hierarchy"));
    assert.ok(experienceSource.includes("spend_flows"));
    assert.ok(experienceSource.includes("SpendOrbitHero"));
    assert.ok(experienceSource.includes("ProviderAllocationStrip"));
    assert.ok(experienceSource.includes("TrendForecastChart"));
    assert.ok(experienceSource.includes("Cost Topology Theater"));
    assert.ok(experienceSource.includes("DailySpendHeatmap"));
    assert.ok(experienceSource.includes("ProviderDetailCards"));
    assert.ok(experienceSource.includes("TopServicesTable"));
    assert.ok(!experienceSource.includes("KpiCard"));
    assert.ok(!experienceSource.includes("bg-slate-900/50"));
    assert.ok(!experienceSource.includes("backdrop-blur-xl"));
    assert.ok(!experienceSource.includes("@tremor/react"));
});

test("total bill page uses unboxed error and loading states", () => {
    const loadingSource = readFileSync(new URL("./loading.tsx", import.meta.url), "utf8");

    assert.ok(pageSource.includes("max-w-prose text-sm leading-relaxed text-slate-400"));
    assert.ok(!pageSource.includes("rounded-2xl border border-white/10 bg-slate-900/50"));
    assert.ok(!pageSource.includes("backdrop-blur-xl"));
    assert.ok(loadingSource.includes("bg-slate-900/20"));
    assert.ok(loadingSource.includes("border-b border-white/5"));
    assert.ok(!loadingSource.includes("rounded-2xl border border-white/10"));
    assert.ok(!loadingSource.includes("backdrop-blur-xl"));
});

test("total bill backend widens the existing route with visual payloads", () => {
    assert.ok(routesSource.includes("build_totalbill_visuals"));
    assert.ok(routesSource.includes("history_by_integration"));
    assert.ok(routesSource.includes("get_daily_spend_history"));
});
