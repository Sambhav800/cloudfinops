import assert from "node:assert/strict";
import test from "node:test";

async function loadHelper() {
    return import(new URL("./bill-executive-report.ts", import.meta.url).href);
}

test("rejects malformed executive-report payloads with non-array findings", async () => {
    const { hasRenderableBillExecutiveReport, normalizeBillExecutiveReport } = await loadHelper();

    const normalized = normalizeBillExecutiveReport({
        headline: "Bad payload",
        findings: {},
        quick_wins: [],
        roadmap: [],
        cross_cloud_comparison: [],
        client_scripts: {
            opening: "Opening",
            explain_biggest_issue: "Explain",
            handle_objection: "Objection",
            closing: "Closing",
        },
    });

    assert.equal(normalized, null);
    assert.equal(hasRenderableBillExecutiveReport({ findings: {} }), false);
});

test("normalizes a valid executive-report payload into render-safe arrays", async () => {
    const { hasRenderableBillExecutiveReport, normalizeBillExecutiveReport } = await loadHelper();

    const normalized = normalizeBillExecutiveReport({
        headline: "Elastic Load Balancing is oversized",
        waste_grade: "C",
        waste_score: 25,
        waste_grade_explanation: "Grade C",
        total_spend: 865.79,
        existing_savings_active: 0,
        additional_savings_min: 278.44,
        additional_savings_max: 395.9,
        optimised_bill_min: 469.89,
        optimised_bill_max: 587.35,
        annual_savings_min: 3341.28,
        annual_savings_max: 4750.8,
        reduction_pct_min: 32,
        reduction_pct_max: 46,
        findings: [
            {
                rank: 1,
                service: "Elastic Load Balancing",
                monthly_cost: 209.2,
                pct_of_bill: 24.2,
                severity: "critical",
                title: "Load balancer spend is materially higher than a lean baseline",
                what_we_found: "Finding details",
                why_inefficient: "Reason details",
                how_to_fix: ["Step 1", "Step 2"],
                actions: [
                    {
                        name: "Consolidate ALBs",
                        difficulty: "Easy",
                        time_required: "45 minutes",
                        monthly_saving_min: 129.7,
                        monthly_saving_max: 171.54,
                        risk: "Low",
                        savings_source: "bill_line_exact_unit_price_delta",
                        validation_required: true,
                        calculation: "1,000 GB-Mo x ($0.114 - $0.0912)",
                        evidence_lines: ["p.3 line 7: gp2 bill row"],
                        confidence_reason: "Unit prices were read from the bill.",
                    },
                ],
                savings_source: "bill_line_exact_unit_price_delta",
                validation_required: true,
                calculation: "1,000 GB-Mo x ($0.114 - $0.0912)",
                evidence_lines: ["p.3 line 7: gp2 bill row"],
                confidence_reason: "Unit prices were read from the bill.",
                keep: false,
            },
        ],
        quick_wins: [{ action: "Consolidate ALBs", time: "45 minutes", saving: 171.54, risk: "Low" }],
        roadmap: [{ phase: "Phase 1", timeframe: "Week 1", actions: ["Consolidate ALBs"], expected_saving_min: 129.7, expected_saving_max: 171.54 }],
        cross_cloud_comparison: [{ service: "Load Balancing", aws_current: 209.2, aws_optimised: 79.5, gcp: 82.0, azure: 88.0 }],
        executive_summary: "Summary",
        client_scripts: {
            opening: "Opening",
            explain_biggest_issue: "Explain",
            handle_objection: "Objection",
            closing: "Closing",
        },
        implementation_timeline_days: 14,
        confidence: "high",
        benchmark_context: "Benchmark",
    });

    assert.ok(normalized);
    assert.equal(normalized?.findings.length, 1);
    assert.equal(normalized?.findings[0].calculation, "1,000 GB-Mo x ($0.114 - $0.0912)");
    assert.equal(normalized?.findings[0].validation_required, true);
    assert.deepEqual(normalized?.findings[0].evidence_lines, ["p.3 line 7: gp2 bill row"]);
    assert.equal(normalized?.findings[0].actions[0].savings_source, "bill_line_exact_unit_price_delta");
    assert.equal(normalized?.quick_wins.length, 1);
    assert.equal(normalized?.client_scripts.closing, "Closing");
    assert.equal(hasRenderableBillExecutiveReport(normalized), true);
});

test("derives waste grade from score when the payload grade is missing", async () => {
    const { normalizeBillExecutiveReport } = await loadHelper();

    const normalized = normalizeBillExecutiveReport({
        headline: "Headline",
        waste_score: 61,
        waste_grade_explanation: "Grade D explanation",
        total_spend: 100,
        existing_savings_active: 0,
        additional_savings_min: 10,
        additional_savings_max: 20,
        optimised_bill_min: 80,
        optimised_bill_max: 90,
        annual_savings_min: 120,
        annual_savings_max: 240,
        reduction_pct_min: 10,
        reduction_pct_max: 20,
        findings: [],
        quick_wins: [],
        roadmap: [],
        cross_cloud_comparison: [],
        executive_summary: "Summary",
        client_scripts: {
            opening: "Opening 100",
            explain_biggest_issue: "Explain 100",
            handle_objection: "Objection 100",
            closing: "Closing 100",
        },
        implementation_timeline_days: 3,
        confidence: "medium",
        benchmark_context: "Benchmark",
    });

    assert.equal(normalized?.waste_grade, "D");
});
