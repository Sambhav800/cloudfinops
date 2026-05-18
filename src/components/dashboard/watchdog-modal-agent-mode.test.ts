import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadModalSource() {
    return readFile(new URL("./watchdog-modal.tsx", import.meta.url), "utf8");
}

async function loadStatusProxySource() {
    return readFile(new URL("../../app/api/agents/status/route.ts", import.meta.url), "utf8");
}

test("watchdog modal renders the agent mode header and all three Clousy agent pills", async () => {
    const source = await loadModalSource();

    assert.match(source, /Agent Mode/);
    assert.match(source, /Savings Agent/);
    assert.match(source, /Governance Agent/);
    assert.match(source, /Bill Agent/);
    assert.match(source, /fetch\("\/api\/agents\/status"/);
    assert.match(source, /buildScopedMessage\(selectedAgent, msgText\)/);
});

test("agents status proxy forwards to the backend agent status endpoint", async () => {
    const source = await loadStatusProxySource();

    assert.match(source, /\/api\/agents\/status/);
    assert.match(source, /fetchWithBackendAuthFallback/);
    assert.match(source, /Failed to load agent status/);
});
