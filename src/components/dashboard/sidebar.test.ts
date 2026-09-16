import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const sidebarSource = readFileSync(new URL("./sidebar.tsx", import.meta.url), "utf8");
const securityPageSource = readFileSync(new URL("../../app/dashboard/security/page.tsx", import.meta.url), "utf8");
const alertsPageSource = readFileSync(new URL("../../app/dashboard/alerts/page.tsx", import.meta.url), "utf8");

test("sidebar preserves grouped navigation and links to current dashboard destinations", () => {
    for (const sectionName of ["Discover", "Govern", "Secure", "Intelligence"]) {
        assert.ok(sidebarSource.includes(`name: "${sectionName}"`));
    }

    for (const href of [
        "/dashboard",
        "/dashboard/resources",
        "/dashboard/totalbill",
        "/dashboard/multicloud",
        "/dashboard/pending-actions",
        "/dashboard/exclusions",
        "/dashboard/forecast",
        "/dashboard/commitments",
        "/dashboard/discount-manager",
        "/dashboard/reports",
        "/dashboard/governance",
        "/dashboard/security",
        "/dashboard/audit",
        "/dashboard/architecture",
        "/dashboard/arbitrage",
        "/dashboard/simulator",
        "/dashboard/gpu",
        "/dashboard/apis",
        "/dashboard/settings",
    ]) {
        assert.ok(sidebarSource.includes(`href: "${href}"`), `Missing navigation destination: ${href}`);
        assert.ok(existsSync(new URL(`../../app${href}/page.tsx`, import.meta.url)), `Missing page: ${href}`);
    }
    assert.ok(sidebarSource.includes("navigationSections.map((section, index) =>"));
    assert.ok(sidebarSource.includes("section.items.map((item) =>"));
    assert.ok(sidebarSource.includes("href={href}"));
});

test("legacy alerts route preserves access through the recommendations destination", () => {
    assert.ok(alertsPageSource.includes('import { redirect } from "next/navigation";'));
    assert.ok(alertsPageSource.includes('redirect("/dashboard/pending-actions");'));
    assert.ok(sidebarSource.includes('name: "Recommendations"'));
    assert.ok(sidebarSource.includes('href: "/dashboard/pending-actions"'));
});

test("sidebar retains workspace settings and Clerk sign-out controls", () => {
    assert.ok(sidebarSource.includes('key: "settings", name: "Settings", href: "/dashboard/settings"'));
    assert.ok(sidebarSource.includes("bottomNavigation.map((item) =>"));
    assert.ok(sidebarSource.includes("href={item.href}"));
    assert.ok(sidebarSource.includes('import { useClerk } from "@clerk/nextjs";'));
    assert.ok(sidebarSource.includes("const { signOut } = useClerk();"));
    assert.ok(sidebarSource.includes('onClick={() => signOut({ redirectUrl: "/" })}'));
    assert.ok(sidebarSource.includes('aria-label="Sign Out"'));
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
