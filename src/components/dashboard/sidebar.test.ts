import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const sidebarSource = readFileSync(new URL("./sidebar.tsx", import.meta.url), "utf8");
const securityPageSource = readFileSync(new URL("../../app/dashboard/security/page.tsx", import.meta.url), "utf8");

test("sidebar defines the requested grouped section labels and preserves existing dashboard routes", () => {
    for (const sectionName of ["Discover", "Govern", "Secure", "Intelligence"]) {
        assert.ok(sidebarSource.includes(`name: "${sectionName}"`));
    }

    for (const href of [
        "/dashboard",
        "/dashboard/resources",
        "/dashboard/totalbill",
        "/dashboard/multicloud",
        "/dashboard/pending-actions",
        "/dashboard/forecast",
        "/dashboard/commitments",
        "/dashboard/reports",
        "/dashboard/governance",
        "/dashboard/security",
        "/dashboard/audit",
        "/dashboard/architecture",
        "/dashboard/arbitrage",
        "/dashboard/simulator",
        "/dashboard/alerts",
        "/dashboard/gpu",
        "/dashboard/settings",
    ]) {
        assert.ok(sidebarSource.includes(`"${href}"`));
    }
});

test("sidebar bill scanner uses durable feature plus persisted-analysis state instead of session-only storage", () => {
    assert.ok(sidebarSource.includes('fetch("/api/user/features"'));
    assert.ok(sidebarSource.includes('fetch("/api/bill-analyses?limit=1"'));
    assert.ok(sidebarSource.includes('window.localStorage.getItem(LAST_ANALYSIS_STORAGE_KEY)'));
    assert.ok(sidebarSource.includes("const effectiveBillAnalysisId = persistedAnalysisId || latestBillAnalysisId;"));
    assert.ok(sidebarSource.includes("buildBillScanHref(effectiveBillAnalysisId)"));
    assert.ok(sidebarSource.includes("shouldEnableBillAnalysisNav({"));
    assert.equal(sidebarSource.includes("sessionStorage.getItem"), false);
    assert.ok(sidebarSource.includes("animate-pulse rounded-full bg-emerald-400"));
});

test("security page renders the live security view shell", () => {
    assert.ok(securityPageSource.includes('import { SecurityView } from "@/components/dashboard/security-view";'));
    assert.ok(securityPageSource.includes('import { getSecurityPosture } from "@/lib/dashboard/data";'));
    assert.ok(securityPageSource.includes("<SecurityView initialPosture={posture} />"));
    assert.equal(securityPageSource.includes("getGovernanceAnalysis"), false);
});
