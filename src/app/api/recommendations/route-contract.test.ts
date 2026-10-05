import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadListRouteSource() {
    return readFile(new URL("./route.ts", import.meta.url), "utf8");
}

async function loadEvidenceRouteSource() {
    return readFile(new URL("./[recommendationId]/evidence/route.ts", import.meta.url), "utf8");
}

async function loadStateRouteSource() {
    return readFile(new URL("./[recommendationId]/state/route.ts", import.meta.url), "utf8");
}

async function loadProviderIngestRouteSource() {
    return readFile(new URL("./provider-ingest/route.ts", import.meta.url), "utf8");
}

async function loadVerificationRouteSource() {
    return readFile(new URL("./[recommendationId]/verification/route.ts", import.meta.url), "utf8");
}

async function loadAiEnrichmentRouteSource() {
    return readFile(new URL("./[recommendationId]/ai-enrichment/route.ts", import.meta.url), "utf8");
}

async function loadAiEnrichmentRunRouteSource() {
    return readFile(new URL("./ai-enrichment/run/route.ts", import.meta.url), "utf8");
}

async function loadEvidenceCardRouteSource() {
    return readFile(new URL("./[recommendationId]/evidence-card/route.ts", import.meta.url), "utf8");
}

test("recommendations list route proxies ledger reads through backend auth", async () => {
    const source = await loadListRouteSource();

    assert.match(source, /fetchWithBackendAuthFallback/);
    assert.match(source, /getBackendAuthContext/);
    assert.match(source, /hasBackendAuthCandidate/);
    assert.match(source, /\/api\/recommendations/);
    assert.match(source, /searchParams\.get\("integration_id"\)/);
    assert.match(source, /searchParams\.get\("state"\)/);
    assert.doesNotMatch(source, /createClient\(/);
    assert.doesNotMatch(source, /MONGODB_URI/);
    assert.doesNotMatch(source, /\.from\("recommendation_ledger"\)/);
});

test("recommendations evidence route keeps evidence access user-scoped through backend", async () => {
    const source = await loadEvidenceRouteSource();

    assert.match(source, /fetchWithBackendAuthFallback/);
    assert.match(source, /getBackendAuthContext/);
    assert.match(source, /\/api\/recommendations\/\$\{encodeURIComponent\(normalizedId\)\}\/evidence/);
    assert.doesNotMatch(source, /createClient\(/);
    assert.doesNotMatch(source, /\.from\("recommendation_evidence"\)/);
});

test("recommendations evidence-card route proxies evidence card requests through backend auth", async () => {
    const source = await loadEvidenceCardRouteSource();

    assert.match(source, /fetchWithBackendAuthFallback/);
    assert.match(source, /getBackendAuthContext/);
    assert.match(source, /hasBackendAuthCandidate/);
    assert.match(source, /\/api\/recommendations\/\$\{encodeURIComponent\(normalizedId\)\}\/evidence-card/);
    assert.doesNotMatch(source, /createClient\(/);
    assert.doesNotMatch(source, /MONGODB_URI/);
});

test("recommendations state route validates state before proxying mutation", async () => {
    const source = await loadStateRouteSource();

    assert.match(source, /ALLOWED_STATES/);
    assert.match(source, /isRecommendationState/);
    assert.match(source, /method: "POST"/);
    assert.match(source, /\/api\/recommendations\/\$\{encodeURIComponent\(normalizedId\)\}\/state/);
    assert.doesNotMatch(source, /createClient\(/);
    assert.doesNotMatch(source, /\.from\("recommendation_state_events"\)/);
});

test("recommendations provider-ingest route proxies Azure Advisor ingestion through backend auth", async () => {
    const source = await loadProviderIngestRouteSource();

    assert.match(source, /fetchWithBackendAuthFallback/);
    assert.match(source, /getBackendAuthContext/);
    assert.match(source, /hasBackendAuthCandidate/);
    assert.match(source, /\/api\/recommendations\/provider-ingest/);
    assert.match(source, /integration_id/);
    assert.match(source, /force_refresh/);
    assert.doesNotMatch(source, /ClientSecretCredential/);
    assert.doesNotMatch(source, /createClient\(/);
    assert.doesNotMatch(source, /MONGODB_URI/);
});

test("recommendations verification route proxies savings verification through backend auth", async () => {
    const source = await loadVerificationRouteSource();

    assert.match(source, /fetchWithBackendAuthFallback/);
    assert.match(source, /getBackendAuthContext/);
    assert.match(source, /hasBackendAuthCandidate/);
    assert.match(source, /\/api\/recommendations\/\$\{encodeURIComponent\(recommendationId\)\}\/verification/);
    assert.match(source, /pathSuffix/);
    assert.match(source, /method: "GET" \| "POST"/);
    assert.doesNotMatch(source, /createClient\(/);
    assert.doesNotMatch(source, /MONGODB_URI/);
});

test("recommendations AI enrichment routes proxy through backend auth", async () => {
    const detailSource = await loadAiEnrichmentRouteSource();
    const runSource = await loadAiEnrichmentRunRouteSource();

    assert.match(detailSource, /fetchWithBackendAuthFallback/);
    assert.match(detailSource, /getBackendAuthContext/);
    assert.match(detailSource, /\/api\/recommendations\/\$\{encodeURIComponent\(recommendationId\)\}\/ai-enrichment/);
    assert.match(detailSource, /"\/queue"/);
    assert.match(runSource, /fetchWithBackendAuthFallback/);
    assert.match(runSource, /getBackendAuthContext/);
    assert.match(runSource, /\/api\/recommendations\/ai-enrichment\/run/);
    assert.match(runSource, /queue_pending/);
    assert.match(runSource, /queue_limit/);
    assert.match(runSource, /background/);
    assert.doesNotMatch(detailSource, /createClient\(/);
    assert.doesNotMatch(runSource, /createClient\(/);
    assert.doesNotMatch(detailSource, /MONGODB_URI/);
    assert.doesNotMatch(runSource, /MONGODB_URI/);
});
