import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadSource() {
    return readFile(new URL("./recommendation-ledger-view.tsx", import.meta.url), "utf8");
}

test("recommendation ledger view is backed by ledger APIs and shows trust evidence", async () => {
    const source = await loadSource();

    assert.match(source, /RecommendationLedgerView/);
    assert.match(source, /\/api\/recommendations\/\$\{encodeURIComponent\(recommendation\.id\)\}\/evidence/);
    assert.match(source, /\/api\/recommendations\/\$\{encodeURIComponent\(recommendation\.id\)\}\/evidence-card/);
    assert.match(source, /loadEvidenceCard/);
    assert.match(source, /\/api\/recommendations\/\$\{encodeURIComponent\(recommendation\.id\)\}\/state/);
    assert.match(source, /\/api\/recommendations\/provider-ingest/);
    assert.match(source, /\/api\/recommendations\/\$\{encodeURIComponent\(recommendation\.id\)\}\/verification/);
    assert.match(source, /\/api\/recommendations\/\$\{encodeURIComponent\(recommendation\.id\)\}\/ai-enrichment/);
    assert.match(source, /\/api\/recommendations\/ai-enrichment\/run/);
    assert.match(source, /Run AI enrichment/);
    assert.match(source, /background: true/);
    assert.match(source, /queue_limit: 50/);
    assert.match(source, /AI enrichment/);
    assert.match(source, /runAiEnrichmentForRecommendation/);
    assert.match(source, /ai_enrichment_status/);
    assert.match(source, /aiEnrichmentBadgeClass/);
    assert.match(source, /force_refresh: true/);
    assert.match(source, /Refresh Azure Advisor/);
    assert.match(source, /summarizeProviderCheck/);
    assert.match(source, /Savings verification/);
    assert.match(source, /runSavingsVerification/);
    assert.match(source, /verification_status/);
    assert.match(source, /realized_monthly_savings/);
    assert.match(source, /Evidence Chain/);
    assert.match(source, /Pricing basis/);
    assert.match(source, /provider_agreement_status/);
    assert.match(source, /providerAgreementBadgeClass/);
    assert.match(source, /pricing_computed_at/);
    assert.match(source, /trust_score/);
    assert.match(source, /claimable_monthly_savings/);
    assert.match(source, /savings_estimate_status/);
    assert.match(source, /quality_status/);
    assert.match(source, /Not claimed/);
    assert.doesNotMatch(source, /recommendation\.estimated_monthly_savings,\s*resolveSourceCurrency/);
    assert.doesNotMatch(source, /\/api\/notifications/);
    assert.doesNotMatch(source, /sessionStorage/);
});
