import assert from "node:assert/strict";
import test from "node:test";

async function loadHelper() {
    return import(new URL("./bill-analysis-client-state.ts", import.meta.url).href);
}

test("enables Bill Scan navigation when a persisted analysis id exists", async () => {
    const { shouldEnableBillAnalysisNav } = await loadHelper();

    assert.equal(
        shouldEnableBillAnalysisNav({
            featureEnabled: false,
            persistedAnalysisId: "analysis-123",
            pathname: "/dashboard/settings",
        }),
        true,
    );
});

test("enables Bill Scan navigation when the durable bill-analysis feature is enabled", async () => {
    const { shouldEnableBillAnalysisNav } = await loadHelper();

    assert.equal(
        shouldEnableBillAnalysisNav({
            featureEnabled: true,
            persistedAnalysisId: null,
            pathname: "/dashboard/settings",
        }),
        true,
    );
});

test("builds Bill Scan href with the last persisted analysis id", async () => {
    const { buildBillScanHref } = await loadHelper();

    assert.equal(
        buildBillScanHref("analysis-123"),
        "/dashboard/arbitrage?id=analysis-123&tab=executive",
    );
    assert.equal(buildBillScanHref(null), "/dashboard/arbitrage?tab=executive");
});

test("parses and validates the persisted bill-analysis snapshot payload", async () => {
    const {
        BILL_ANALYSIS_REPORT_CONTRACT_VERSION,
        parsePersistedBillAnalysisSnapshot,
        snapshotMatchesAnalysisId,
    } = await loadHelper();

    const snapshot = parsePersistedBillAnalysisSnapshot(
        JSON.stringify({
            analysisId: "analysis-456",
            savedAt: "2026-03-22T12:00:00.000Z",
            version: BILL_ANALYSIS_REPORT_CONTRACT_VERSION,
            data: {
                id: "analysis-456",
                filename: "invoice.pdf",
            },
        }),
    ) as {
        analysisId: string;
        data: {
            id: string;
            filename: string;
        };
        savedAt: string;
    } | null;

    assert.ok(snapshot);
    assert.equal(snapshot.analysisId, "analysis-456");
    assert.equal(snapshot.data.filename, "invoice.pdf");
    assert.equal(snapshotMatchesAnalysisId(snapshot, "analysis-456"), true);
    assert.equal(snapshotMatchesAnalysisId(snapshot, "analysis-999"), false);
});

test("rejects persisted bill-analysis snapshots from an older contract version", async () => {
    const { parsePersistedBillAnalysisSnapshot } = await loadHelper();

    const snapshot = parsePersistedBillAnalysisSnapshot(
        JSON.stringify({
            analysisId: "analysis-456",
            savedAt: "2026-03-22T12:00:00.000Z",
            version: "2026-03-22-old-contract",
            data: {
                id: "analysis-456",
                filename: "invoice.pdf",
            },
        }),
    );

    assert.equal(snapshot, null);
});

test("detects whether a bill analysis carries the current report contract version", async () => {
    const { hasCurrentBillAnalysisContract } = await loadHelper();

    assert.equal(
        hasCurrentBillAnalysisContract({
            source_metadata: {
                report_contract_version: "2026-04-28-bill-line-rule-estimate-v5",
            },
        }),
        true,
    );
    assert.equal(hasCurrentBillAnalysisContract({ source_metadata: {} }), false);
});
