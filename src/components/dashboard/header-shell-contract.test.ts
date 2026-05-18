import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const headerSource = readFileSync(new URL("./header.tsx", import.meta.url), "utf8");

test("header route launcher no longer ships mock resource search entries", () => {
    assert.ok(headerSource.includes("Route Launcher"));
    assert.ok(!headerSource.includes("Mock resources"));
    assert.ok(!headerSource.includes("prod-web-server-01"));
    assert.ok(!headerSource.includes("main-postgres-db"));
});

test("header shell exposes real dashboard destinations and route-aware page context", () => {
    assert.ok(headerSource.includes('pageTitle: "Portfolio Command Center"'));
    assert.ok(headerSource.includes('pageTitle: "Resource Inventory"'));
    assert.ok(headerSource.includes('pageTitle: "Budget Copilot"'));
    assert.ok(headerSource.includes('pageTitle: "Architecture Workspace"'));
    assert.ok(headerSource.includes("Jump to a dashboard view"));
    assert.ok(headerSource.includes("Open alert center"));
});

test("header shell defines a fallback workspace context and keyboard shortcut affordance", () => {
    assert.ok(headerSource.includes("const DEFAULT_ROUTE_META ="));
    assert.ok(headerSource.includes('pageTitle: "CloudFinOps Workspace"'));
    assert.ok(headerSource.includes('if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k")'));
    assert.ok(headerSource.includes("Ctrl/⌘ K"));
});
