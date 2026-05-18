import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadSimulatorFile(name: string) {
    return readFile(new URL(`./${name}`, import.meta.url), "utf8");
}

test("simulator surface has no legacy Tremor imports", async () => {
    const legacyImport = "@" + "tremor/react";
    const files = [
        "cost-delta-view.tsx",
        "shift-left-simulator.tsx",
        "resource-cost-bars.tsx",
        "family-spend-donut.tsx",
        "coverage-bar.tsx",
        "monthly-annual-waterfall.tsx",
        "unestimated-list.tsx",
        "policy-status-card.tsx",
        "best-practice-findings.tsx",
    ];

    for (const file of files) {
        const source = await loadSimulatorFile(file);
        assert.equal(source.includes(legacyImport), false, `${file} must not import the legacy chart library`);
    }
});

test("cost delta view renders v2 coverage, charts, and unestimated resource disclosure", async () => {
    const source = await loadSimulatorFile("cost-delta-view.tsx");

    assert.match(source, /Pricing Coverage/);
    assert.match(source, /exact_resources/);
    assert.match(source, /estimated_resources/);
    assert.match(source, /usage_based_resources/);
    assert.match(source, /unestimated_resources/);
    assert.match(source, /CoverageBar/);
    assert.match(source, /MonthlyAnnualWaterfall/);
    assert.match(source, /FamilySpendDonut/);
    assert.match(source, /ResourceCostBars/);
    assert.match(source, /UnestimatedList/);
    assert.match(source, /PolicyStatusCard/);
    assert.match(source, /BestPracticeFindings/);
    assert.match(source, /findings/);
    assert.match(source, /policy/);
    assert.match(source, /No priced resources found/);
    assert.match(source, /border-t-2/);
});

test("chart components use recharts for simulator result visuals", async () => {
    const bars = await loadSimulatorFile("resource-cost-bars.tsx");
    const donut = await loadSimulatorFile("family-spend-donut.tsx");
    const waterfall = await loadSimulatorFile("monthly-annual-waterfall.tsx");

    assert.match(bars, /from 'recharts'/);
    assert.match(bars, /BarChart/);
    assert.match(donut, /from 'recharts'/);
    assert.match(donut, /PieChart/);
    assert.match(waterfall, /from 'recharts'/);
    assert.match(waterfall, /BarChart/);
});

test("shift-left simulator keeps upload visible and renders real commitment context", async () => {
    const source = await loadSimulatorFile("shift-left-simulator.tsx");

    assert.match(source, /X-Simulator-Version|simulateTerraformCost|Run Cost Simulation/);
    assert.match(source, /Renewal scenario/);
    assert.match(source, /\/api\/finance\/commitments/);
    assert.match(source, /Terraform plan input remains separate/);
    assert.match(source, /Paste JSON/);
    assert.match(source, /Upload File/);
    assert.doesNotMatch(source, /terraform show -json[\s\S]*commitmentData/);
});

test("shift-left simulator uses a broad top-input then full-width analysis layout", async () => {
    const source = await loadSimulatorFile("shift-left-simulator.tsx");
    const waterfall = await loadSimulatorFile("monthly-annual-waterfall.tsx");

    assert.doesNotMatch(source, /grid grid-cols-1 gap-8 xl:grid-cols-2/);
    assert.match(source, /<section className="space-y-6">/);
    assert.match(source, /lg:min-h-\[420px\]/);
    assert.match(waterfall, /Monthly impact/);
    assert.match(waterfall, /Annual impact/);
    assert.doesNotMatch(waterfall, /Current monthly/);
});
