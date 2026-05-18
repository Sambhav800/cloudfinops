import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadSource() {
    return readFile(new URL("./data.ts", import.meta.url), "utf8");
}

function getFunctionBody(source: string, functionName: string): string {
    const startToken = `export async function ${functionName}`;
    const startIndex = source.indexOf(startToken);
    assert.notEqual(startIndex, -1, `${functionName} should exist`);

    const bodyStart = source.indexOf("{", startIndex);
    assert.notEqual(bodyStart, -1, `${functionName} should have a body`);

    let depth = 0;
    for (let index = bodyStart; index < source.length; index += 1) {
        const char = source[index];
        if (char === "{") depth += 1;
        if (char === "}") {
            depth -= 1;
            if (depth === 0) {
                return source.slice(bodyStart + 1, index);
            }
        }
    }

    throw new Error(`Could not extract ${functionName} body`);
}

test("getPendingActions reads pending-action data from backend notifications instead of direct Mongo", async () => {
    const source = await loadSource();
    const body = getFunctionBody(source, "getPendingActions");

    assert.match(body, /getBackendNotifications\(/);
    assert.match(body, /dedupePendingActionNotifications/);
    assert.doesNotMatch(body, /\.from\('agent_notifications'\)/);
});

test("getAllAlerts reads alert data from backend notifications instead of direct Mongo", async () => {
    const source = await loadSource();
    const body = getFunctionBody(source, "getAllAlerts");

    assert.match(body, /getBackendNotifications\(/);
    assert.match(body, /dedupeAlertNotifications/);
    assert.doesNotMatch(body, /\.from\('agent_notifications'\)/);
});

test("getReports reads report data from backend reports instead of notification metadata fallbacks", async () => {
    const source = await loadSource();
    const body = getFunctionBody(source, "getReports");

    assert.match(body, /getBackendReports\(/);
    assert.match(body, /mapBackendReportToReportItem/);
    assert.doesNotMatch(body, /\.contains\('metadata', \{ is_report: true \}\)/);
});

test("getGovernanceAnalysis reads governance data from the backend analysis route instead of direct Mongo scan-history reads", async () => {
    const source = await loadSource();
    const body = getFunctionBody(source, "getGovernanceAnalysis");

    assert.match(body, /getBackendGovernanceAnalysis\(/);
    assert.match(body, /mapBackendGovernanceAnalysis\(/);
    assert.doesNotMatch(body, /\.from\('cloud_integrations'\)/);
    assert.doesNotMatch(body, /\.from\('scan_history'\)/);
});

test("getSecurityPosture reads security posture from the dedicated backend route", async () => {
    const source = await loadSource();
    const body = getFunctionBody(source, "getSecurityPosture");

    assert.match(body, /getBackendSecurityPosture\(/);
    assert.match(body, /mapBackendSecurityPosture\(/);
    assert.doesNotMatch(body, /getBackendGovernanceAnalysis\(/);
    assert.doesNotMatch(body, /GovernanceData/);
    assert.doesNotMatch(body, /\.from\('policy_violations'\)/);
});

test("mapBackendGovernanceAnalysis preserves security-specific governance arrays from the shared backend payload", async () => {
    const source = await loadSource();

    assert.match(source, /agentNotifications:\s*Array\.isArray\(response\.agentNotifications\)/);
    assert.match(source, /resources:\s*Array\.isArray\(response\.resources\)/);
    assert.match(source, /policyViolations:\s*Array\.isArray\(response\.policyViolations\)/);
    assert.match(source, /mapBackendGovernancePolicyViolation/);
    assert.match(source, /mapBackendGovernanceAgentNotification/);
    assert.match(source, /mapBackendGovernanceSecurityResource/);
});

test("getGovernancePolicies reads governance policies from the backend policies route instead of direct Mongo", async () => {
    const source = await loadSource();
    const body = getFunctionBody(source, "getGovernancePolicies");

    assert.match(body, /getBackendGovernancePolicies\(/);
    assert.match(body, /mapBackendGovernancePolicyToItem/);
    assert.doesNotMatch(body, /\.from\('governance_policies'\)/);
    assert.doesNotMatch(body, /getDb\(/);
});

test("getRecentAlerts reads recent alerts from backend notifications instead of direct Mongo notifications", async () => {
    const source = await loadSource();
    const body = getFunctionBody(source, "getRecentAlerts");

    assert.match(body, /getBackendNotifications\(/);
    assert.match(body, /dedupeAlertNotifications/);
    assert.doesNotMatch(body, /\.from\('agent_notifications'\)/);
    assert.doesNotMatch(body, /getDb\(/);
});

test("getTopResources derives waste resources from backend-backed resource helpers instead of direct Mongo resources reads", async () => {
    const source = await loadSource();
    const body = getFunctionBody(source, "getTopResources");

    assert.match(body, /getAllResources\(/);
    assert.doesNotMatch(body, /\.from\('resources'\)/);
    assert.doesNotMatch(body, /getNormalizedResources\(/);
    assert.doesNotMatch(body, /getDb\(/);
});

test("getActiveArchitectureIntegrations reads active architecture integrations from the backend integrations contract", async () => {
    const source = await loadSource();
    const body = getFunctionBody(source, "getActiveArchitectureIntegrations");

    assert.match(body, /getBackendIntegrations\(/);
    assert.doesNotMatch(body, /\.from\('cloud_integrations'\)/);
    assert.doesNotMatch(body, /getDb\(/);
});

test("getActiveAwsIntegration is derived from active architecture integrations instead of querying cloud_integrations directly", async () => {
    const source = await loadSource();
    const body = getFunctionBody(source, "getActiveAwsIntegration");

    assert.match(body, /getActiveArchitectureIntegrations\(/);
    assert.doesNotMatch(body, /\.from\('cloud_integrations'\)/);
    assert.doesNotMatch(body, /getDb\(/);
});
