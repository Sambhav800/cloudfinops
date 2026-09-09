/**
 * E2E smoke / contract tests for the free bill scanner page (/bill-scan).
 *
 * These tests verify the complete user journey:
 *   1. Landing — dropzone, privacy banner, accepted formats
 *   2. Processing state — progress bar, stage labels
 *   3. Teaser report — ALL services rendered (no 3-result cap), waste grade
 *      badges A–F, provider badges, risk-colored cards, headline metrics
 *   4. Conversion CTA — signup wall, value props, reset button
 *
 * Test runner: Node.js built-in test runner (node --test)
 * Strategy: Source-reading contract tests (same pattern used across the repo)
 *           + runtime logic verification via direct module imports.
 */

import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

/* ─── Source loaders ─── */

async function loadSource(relativePath: string): Promise<string> {
    return readFile(new URL(`../${relativePath}`, import.meta.url), "utf8");
}

async function loadFixture(relativePath: string): Promise<string> {
    return readFile(new URL(`./fixtures/${relativePath}`, import.meta.url), "utf8");
}

/* ═══════════════════════════════════════════════════════════════════════
 * PHASE 2A — Landing & Dropzone State
 * ═══════════════════════════════════════════════════════════════════════ */

test("bill-scan page shell renders hero, privacy banner, and dropzone", async () => {
    const pageSource = await loadSource("BillScanPage.tsx");

    // Hero headline and subtitle
    assert.match(pageSource, /Scan your cloud bill/);
    assert.match(pageSource, /Find the waste/);

    // Privacy banner import
    assert.match(pageSource, /PrivacyBanner/);

    // Dropzone import and usage
    assert.match(pageSource, /BillDropzone/);
    assert.match(pageSource, /onFileReady/);

    // Rate limit copy from constants
    assert.match(pageSource, /RATE_LIMIT_COPY/);

    // Trust signals at bottom
    assert.match(pageSource, /AWS · Azure · GCP supported/);
    assert.match(pageSource, /In-memory only — zero retention/);
    assert.match(pageSource, /No account needed/);
});

test("dropzone validates accepted file types and enforces size limits", async () => {
    const dropzoneSource = await loadSource("components/BillDropzone.tsx");

    // File input with accepted extensions
    assert.match(dropzoneSource, /accept=\{ACCEPTED_EXTENSIONS\.join/);

    // Validation function
    assert.match(dropzoneSource, /validateFile/);

    // Size check against MAX_FILE_BYTES
    assert.match(dropzoneSource, /MAX_FILE_BYTES/);

    // Format badges shown in UI
    assert.match(dropzoneSource, /"PDF"/);
    assert.match(dropzoneSource, /"CSV"/);
    assert.match(dropzoneSource, /"XLSX"/);

    // Drag & drop handlers
    assert.match(dropzoneSource, /onDragOver/);
    assert.match(dropzoneSource, /onDragLeave/);
    assert.match(dropzoneSource, /onDrop/);

    // Aria accessibility
    assert.match(dropzoneSource, /aria-label/);
    assert.match(dropzoneSource, /aria-disabled/);

    // Unsupported format error message
    assert.match(dropzoneSource, /Unsupported format/);

    // File too large error message
    assert.match(dropzoneSource, /File is too large/);
});

test("constants define correct accepted extensions and size limits", async () => {
    const constants = await import(new URL("../constants.ts", import.meta.url).href);

    assert.deepEqual(constants.ACCEPTED_EXTENSIONS, [".csv", ".xlsx", ".xls", ".pdf"]);
    assert.equal(constants.MAX_FILE_BYTES, 20 * 1024 * 1024);
    assert.equal(constants.MAX_FILE_SIZE_LABEL, "20 MB");
    assert.equal(constants.PUBLIC_UPLOAD_ENDPOINT, "/api/scan/public-upload");
    assert.equal(constants.UPLOAD_TIMEOUT_MS, 60_000);

    // All 5 processing stages present
    assert.equal(constants.PROCESSING_STAGES.length, 5);
    assert.match(constants.PROCESSING_STAGES[0], /Uploading/);
    assert.match(constants.PROCESSING_STAGES[4], /Generating/);
});

/* ═══════════════════════════════════════════════════════════════════════
 * PHASE 2B — Processing State
 * ═══════════════════════════════════════════════════════════════════════ */

test("processing state renders progress bar with accessible aria attributes", async () => {
    const processingSource = await loadSource("components/ProcessingState.tsx");

    // Progress bar with ARIA attributes
    assert.match(processingSource, /role="progressbar"/);
    assert.match(processingSource, /aria-valuenow/);
    assert.match(processingSource, /aria-valuemin/);
    assert.match(processingSource, /aria-valuemax/);

    // References PROCESSING_STAGES from constants
    assert.match(processingSource, /PROCESSING_STAGES/);

    // Animated spinner elements
    assert.match(processingSource, /animate-spin/);
    assert.match(processingSource, /animate-pulse/);

    // User-facing timing estimate
    assert.match(processingSource, /10–30 seconds/);
});

test("BillScanPage transitions through status states: idle → uploading → results | error", async () => {
    const pageSource = await loadSource("BillScanPage.tsx");

    // State machine: idle, uploading, results, error
    assert.match(pageSource, /status: "idle"/);
    assert.match(pageSource, /status: "uploading"/);
    assert.match(pageSource, /status: "results"/);
    assert.match(pageSource, /status: "error"/);

    // Uploading triggers ProcessingState
    assert.match(pageSource, /state\.status === "uploading"/);
    assert.match(pageSource, /<ProcessingState/);

    // Results triggers TeaserReport + ConversionCTA
    assert.match(pageSource, /state\.status === "results"/);
    assert.match(pageSource, /<TeaserReport/);
    assert.match(pageSource, /<ConversionCTA/);

    // Error state shows retry button
    assert.match(pageSource, /state\.status === "error"/);
    assert.match(pageSource, /bill-scan-retry-btn/);
    assert.match(pageSource, /Scan failed/);
    assert.match(pageSource, /Try a different file/);
});

/* ═══════════════════════════════════════════════════════════════════════
 * PHASE 2C — TeaserReport: ALL services rendered (no 3-result cap)
 * ═══════════════════════════════════════════════════════════════════════ */

test("TeaserReport renders ALL findings without any artificial cap — the old 3-result limit is gone", async () => {
    const reportSource = await loadSource("components/TeaserReport.tsx");

    // The report maps over ALL findings without .slice() on top_findings_teaser
    // The only .slice() present is on by_category (top 8 categories), NOT on findings
    assert.match(reportSource, /data\.top_findings_teaser\.map/);

    // There should be NO .slice() applied to top_findings_teaser before rendering
    assert.doesNotMatch(reportSource, /top_findings_teaser\.slice\(/);
    assert.doesNotMatch(reportSource, /top_findings_teaser\s*\.\s*slice\s*\(/);

    // The heading says "Complete Service-Level Analysis" — not "Top 3" or limited
    assert.match(reportSource, /Complete Service-Level Analysis/);

    // Shows the count of services rendered
    assert.match(reportSource, /data\.top_findings_teaser\.length/);
    assert.match(reportSource, /services · sorted by cost impact/);
});

test("TeaserReport fixture with 8 services produces 8 finding entries in the data", async () => {
    const { makeTeaserPayload } = await import(
        new URL("./fixtures/mock-teaser-payloads.ts", import.meta.url).href
    );

    const payload = makeTeaserPayload();

    // The fixture has exactly 8 services
    assert.equal(payload.top_findings_teaser.length, 8);

    // Verify all 8 service names are present
    const serviceNames = payload.top_findings_teaser.map(
        (f: { service: string }) => f.service,
    );
    assert.ok(serviceNames.includes("Amazon EC2"));
    assert.ok(serviceNames.includes("Amazon RDS"));
    assert.ok(serviceNames.includes("Amazon S3"));
    assert.ok(serviceNames.includes("Amazon CloudFront"));
    assert.ok(serviceNames.includes("Elastic Load Balancing"));
    assert.ok(serviceNames.includes("Amazon DynamoDB"));
    assert.ok(serviceNames.includes("AWS Lambda"));
    assert.ok(serviceNames.includes("NAT Gateway"));
});

test("backend _redact_and_build_teaser does NOT cap findings — iterates ALL raw_services", async () => {
    const backendSource = await readFile(
        new URL("../../../../backend/app/api/routes.py", import.meta.url),
        "utf8",
    );

    // The comment explicitly says "no artificial cap"
    assert.match(backendSource, /Build enriched findings for ALL services — no artificial cap/);

    // Iterates ALL raw_services in a for loop
    assert.match(backendSource, /for svc in raw_services:/);

    // top_findings_teaser is assigned without artificial slice
    assert.doesNotMatch(backendSource, /"top_findings_teaser":\s*top_findings\[:\d+\]/);
    assert.match(backendSource, /"top_findings_teaser":\s*top_findings\b/);
});

/* ═══════════════════════════════════════════════════════════════════════
 * PHASE 2D — Waste Grade Badges (A/B/C/D/F)
 * ═══════════════════════════════════════════════════════════════════════ */

test("waste grade constants define all 5 grades with correct color tokens and descriptions", async () => {
    const constants = await import(new URL("../constants.ts", import.meta.url).href);

    const grades = ["A", "B", "C", "D", "F"];
    for (const grade of grades) {
        const meta = constants.WASTE_GRADE_META[grade];
        assert.ok(meta, `Missing WASTE_GRADE_META entry for grade "${grade}"`);
        assert.equal(meta.label, grade);
        assert.ok(meta.color.startsWith("text-"), `Grade ${grade} color should be a text- token`);
        assert.ok(meta.bg.length > 0, `Grade ${grade} bg should not be empty`);
        assert.ok(meta.description.length > 0, `Grade ${grade} description should not be empty`);
    }

    // Verify specific color mappings
    assert.match(constants.WASTE_GRADE_META["A"].color, /emerald/);
    assert.match(constants.WASTE_GRADE_META["B"].color, /teal/);
    assert.match(constants.WASTE_GRADE_META["C"].color, /amber/);
    assert.match(constants.WASTE_GRADE_META["D"].color, /orange/);
    assert.match(constants.WASTE_GRADE_META["F"].color, /rose/);
});

test("TeaserReport renders waste grade badge with dynamic color from WASTE_GRADE_META", async () => {
    const reportSource = await loadSource("components/TeaserReport.tsx");

    // Imports and uses WASTE_GRADE_META
    assert.match(reportSource, /WASTE_GRADE_META/);

    // Renders the grade letter
    assert.match(reportSource, /data\.waste_grade/);

    // Shows the grade description
    assert.match(reportSource, /gradeMeta\.description/);

    // Uses dynamic color class
    assert.match(reportSource, /gradeMeta\.color/);
    assert.match(reportSource, /gradeMeta\.bg/);
});

test("mock payload factory produces valid payloads for all 5 waste grades", async () => {
    const { makeTeaserPayloadForGrade } = await import(
        new URL("./fixtures/mock-teaser-payloads.ts", import.meta.url).href
    );

    for (const grade of ["A", "B", "C", "D", "F"] as const) {
        const payload = makeTeaserPayloadForGrade(grade);
        assert.equal(payload.waste_grade, grade);
        assert.ok(payload.waste_grade_label.length > 0);
        assert.ok(payload.estimated_monthly_savings_min >= 0);
        assert.ok(payload.estimated_monthly_savings_max >= payload.estimated_monthly_savings_min);
    }
});

/* ═══════════════════════════════════════════════════════════════════════
 * PHASE 2E — Provider & Headline Metrics
 * ═══════════════════════════════════════════════════════════════════════ */

test("TeaserReport resolves provider labels for all supported providers", async () => {
    const reportSource = await loadSource("components/TeaserReport.tsx");

    // Provider label map
    assert.match(reportSource, /Amazon Web Services/);
    assert.match(reportSource, /Microsoft Azure/);
    assert.match(reportSource, /Google Cloud Platform/);
    assert.match(reportSource, /Cloud Provider/);    // generic fallback

    // Renders provider label in header
    assert.match(reportSource, /providerLabel/);
});

test("TeaserReport renders headline metrics: spend, savings, rows parsed, services detected", async () => {
    const reportSource = await loadSource("components/TeaserReport.tsx");

    // Monthly spend metric card
    assert.match(reportSource, /Monthly Spend/);
    assert.match(reportSource, /data\.total_analyzed_spend/);

    // Monthly savings range
    assert.match(reportSource, /Est\. Monthly Savings/);
    assert.match(reportSource, /data\.estimated_monthly_savings_min/);
    assert.match(reportSource, /data\.estimated_monthly_savings_max/);

    // Rows parsed badge
    assert.match(reportSource, /rows parsed/);
    assert.match(reportSource, /data\.rows_parsed/);

    // Services detected badge
    assert.match(reportSource, /services detected/);
    assert.match(reportSource, /data\.total_services_detected/);

    // Annual savings calculation
    assert.match(reportSource, /annualSavingsMin/);
    assert.match(reportSource, /annualSavingsMax/);
});

/* ═══════════════════════════════════════════════════════════════════════
 * PHASE 2F — Risk-Colored Cards
 * ═══════════════════════════════════════════════════════════════════════ */

test("TeaserReport uses risk-colored card styling: rose for high, amber for medium, emerald for low", async () => {
    const reportSource = await loadSource("components/TeaserReport.tsx");

    // RISK_COLORS mapping exists
    assert.match(reportSource, /RISK_COLORS/);

    // High risk → rose
    assert.match(reportSource, /border-rose-500/);
    assert.match(reportSource, /bg-rose-500/);
    assert.match(reportSource, /text-rose-400/);

    // Medium risk → amber
    assert.match(reportSource, /border-amber-500/);
    assert.match(reportSource, /bg-amber-500/);
    assert.match(reportSource, /text-amber-400/);

    // Low risk → emerald
    assert.match(reportSource, /border-emerald-500/);
    assert.match(reportSource, /bg-emerald-500/);
    assert.match(reportSource, /text-emerald-400/);

    // FindingCard renders risk level badge
    assert.match(reportSource, /finding\.risk_level/);
    assert.match(reportSource, /risk\.dot/);
    assert.match(reportSource, /risk\.text/);
    assert.match(reportSource, /risk\.border/);
});

test("mock fixtures include findings with all three risk levels", async () => {
    const { makeTeaserPayload } = await import(
        new URL("./fixtures/mock-teaser-payloads.ts", import.meta.url).href
    );

    const payload = makeTeaserPayload();
    const riskLevels = new Set(
        payload.top_findings_teaser.map((f: { risk_level: string }) => f.risk_level),
    );

    assert.ok(riskLevels.has("high"), "Fixtures should include high-risk findings");
    assert.ok(riskLevels.has("medium"), "Fixtures should include medium-risk findings");
    assert.ok(riskLevels.has("low"), "Fixtures should include low-risk findings");
});

/* ═══════════════════════════════════════════════════════════════════════
 * PHASE 2G — Conversion CTA
 * ═══════════════════════════════════════════════════════════════════════ */

test("ConversionCTA renders signup wall with correct IDs and signup link", async () => {
    const ctaSource = await loadSource("components/ConversionCTA.tsx");

    // Container ID for e2e targeting
    assert.match(ctaSource, /id="bill-scan-cta"/);

    // Signup CTA link with correct ID
    assert.match(ctaSource, /id="bill-scan-signup-cta"/);
    assert.match(ctaSource, /href="\/login"/);

    // CTA copy
    assert.match(ctaSource, /Your full report is ready/);
    assert.match(ctaSource, /Sign up free/);
    assert.match(ctaSource, /No credit card/);

    // Value propositions
    assert.match(ctaSource, /Full resource inventory/);
    assert.match(ctaSource, /Executable CLI fix scripts/);
    assert.match(ctaSource, /Cross-cloud pricing tables/);
    assert.match(ctaSource, /Continuous monitoring/);
    assert.match(ctaSource, /AI recommendations/);
});

test("BillScanPage shows 'Scan a different file' reset button alongside results", async () => {
    const pageSource = await loadSource("BillScanPage.tsx");

    // Reset button in results state
    assert.match(pageSource, /bill-scan-another-btn/);
    assert.match(pageSource, /Scan a different file/);
    assert.match(pageSource, /handleReset/);
});

/* ═══════════════════════════════════════════════════════════════════════
 * PHASE 2H — Enriched report sections (urgency, quick win, cross-cloud)
 * ═══════════════════════════════════════════════════════════════════════ */

test("TeaserReport renders urgency banner, quick win, and cross-cloud hint when present", async () => {
    const reportSource = await loadSource("components/TeaserReport.tsx");

    // Urgency banner — annual waste
    assert.match(reportSource, /annual_waste_so_far/);
    assert.match(reportSource, /burned/);
    assert.match(reportSource, /cost_of_waiting_30d/);

    // Quick win section
    assert.match(reportSource, /quick_win/);
    assert.match(reportSource, /Free Quick Win/);
    assert.match(reportSource, /data\.quick_win\.title/);
    assert.match(reportSource, /data\.quick_win\.saving_estimate/);

    // Cross-cloud hint
    assert.match(reportSource, /cross_cloud_hint/);
    assert.match(reportSource, /data\.cross_cloud_hint\.message/);

    // Spend distribution section
    assert.match(reportSource, /Spend Distribution/);
    assert.match(reportSource, /data\.by_category/);

    // "Unlock with free account" section
    assert.match(reportSource, /Unlock with free account/);
});

test("sample CSV fixture contains multiple services for end-to-end parsing validation", async () => {
    const csv = await loadFixture("sample-aws-bill.csv");
    const lines = csv.trim().split("\n");

    // Header + at least 6 data rows
    assert.ok(lines.length >= 7, `CSV should have at least 7 lines (header + 6 services), got ${lines.length}`);

    // Header row
    assert.match(lines[0], /Service/);
    assert.match(lines[0], /Cost/);
    assert.match(lines[0], /Category/);

    // Verify specific services are present
    const content = csv.toLowerCase();
    assert.ok(content.includes("ec2"), "CSV should include EC2");
    assert.ok(content.includes("rds"), "CSV should include RDS");
    assert.ok(content.includes("s3"), "CSV should include S3");
    assert.ok(content.includes("cloudfront"), "CSV should include CloudFront");
});

/* ═══════════════════════════════════════════════════════════════════════
 * PHASE 2I — publicScan API client contract
 * ═══════════════════════════════════════════════════════════════════════ */

test("publicScan API client uses correct endpoint and handles all error codes", async () => {
    const scanSource = await loadSource("api/publicScan.ts");

    // Uses the constant endpoint, not a hardcoded string
    assert.match(scanSource, /PUBLIC_UPLOAD_ENDPOINT/);

    // Sends FormData with the file
    assert.match(scanSource, /new FormData/);
    assert.match(scanSource, /payload\.append\("file", file\)/);

    // AbortController with timeout
    assert.match(scanSource, /AbortController/);
    assert.match(scanSource, /UPLOAD_TIMEOUT_MS/);

    // Handles 429 rate limit
    assert.match(scanSource, /response\.status === 429/);
    assert.match(scanSource, /free scan limit/i);

    // Handles AbortError
    assert.match(scanSource, /AbortError/);
    assert.match(scanSource, /timed out/i);

    // Returns typed TeaserReportPayload
    assert.match(scanSource, /TeaserReportPayload/);
});
