import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pageSource = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");
const loadingSource = readFileSync(new URL("./loading.tsx", import.meta.url), "utf8");
const routesSource = readFileSync(
    new URL("../../../../backend/app/api/routes.py", import.meta.url),
    "utf8"
);
const advisorSource = readFileSync(
    new URL("../../../../backend/app/core/multicloud_comparison.py", import.meta.url),
    "utf8"
);

const oldGlassBg = "bg-slate-900/" + "50";
const oldStaticBlur = "backdrop-blur-" + "xl";
const oldBox = "rounded-2xl border border-white/10 " + oldGlassBg;

test("migration advisor uses advanced recharts primitives without Tremor", () => {
    assert.ok(pageSource.includes('from "recharts"'));
    assert.ok(pageSource.includes("RadarChart"));
    assert.ok(pageSource.includes("ScatterChart"));
    // ROI chart accepts either bare LineChart or the upgraded ComposedChart
    // (line + dual-gradient Area for break-even visualisation).
    assert.ok(pageSource.includes("LineChart") || pageSource.includes("ComposedChart"));
    assert.ok(pageSource.includes("Sankey"));
    assert.ok(pageSource.includes("AnimatedCurrency"));
    assert.ok(pageSource.includes("cache: \"no-store\""));
    assert.ok(pageSource.includes("Request timed out while loading Migration Advisor."));
    assert.ok(!pageSource.includes("@tremor/react"));
    assert.ok(!pageSource.includes("catch (e: any)"));
});

test("migration advisor uses editorial layout instead of repeated glass panels", () => {
    assert.ok(pageSource.includes("<main className=\"px-4 py-8 md:px-8 lg:px-12"));
    assert.ok(pageSource.includes("mt-16"));
    assert.ok(pageSource.includes("bg-slate-900/20"));
    assert.ok(pageSource.includes("border-l-2 border-indigo-500/40 bg-indigo-500/5"));
    assert.ok(pageSource.includes("border-b border-white/5"));
    assert.ok(pageSource.includes("backdrop-blur-md"));
    assert.ok(!pageSource.includes("function ChartPanel"));
    assert.ok(!pageSource.includes("<ChartPanel"));
    assert.ok(!pageSource.includes("function EmptyChart"));
    assert.ok(!pageSource.includes("<EmptyChart"));
    assert.ok(!pageSource.includes(oldGlassBg));
    assert.ok(!pageSource.includes(oldStaticBlur));
    assert.ok(!pageSource.includes(oldBox));
    assert.ok(!pageSource.includes("border-dashed"));
    assert.ok(!pageSource.includes("font-black"));
    assert.ok(!pageSource.includes("tracking-[0.24em]"));
});

test("migration advisor loading state previews the unboxed structure", () => {
    assert.ok(loadingSource.includes("px-4 py-8 md:px-8 lg:px-12"));
    assert.ok(loadingSource.includes("mt-16"));
    assert.ok(loadingSource.includes("bg-slate-900/20"));
    assert.ok(loadingSource.includes("border-b border-white/5"));
    assert.ok(!loadingSource.includes(oldGlassBg));
    assert.ok(!loadingSource.includes(oldStaticBlur));
    assert.ok(!loadingSource.includes(oldBox));
    assert.ok(!loadingSource.includes("border border-white/10"));
    assert.ok(!loadingSource.includes("space-y-6"));
});

test("migration advisor backend is provider-aware and not response cached", () => {
    const startToken = "async def get_multicloud_comparison";
    const startIndex = routesSource.indexOf(startToken);
    assert.notEqual(startIndex, -1);
    const decoratorWindow = routesSource.slice(Math.max(0, startIndex - 160), startIndex);

    assert.ok(!decoratorWindow.includes("@cache_response"));
    assert.ok(routesSource.includes("active_integration_ids = await _get_active_integration_ids"));
    assert.ok(advisorSource.includes('"source_provider": source_provider'));
    assert.ok(advisorSource.includes('"PORTFOLIO"'));
    assert.ok(advisorSource.includes("provider_scores"));
    assert.ok(advisorSource.includes("migration_scatter"));
    assert.ok(advisorSource.includes("roi_curve"));
    assert.ok(advisorSource.includes("allocation_flow"));
});
