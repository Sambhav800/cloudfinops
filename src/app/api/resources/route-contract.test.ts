import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadRouteSource() {
    return readFile(new URL("./route.ts", import.meta.url), "utf8");
}

test("resources route proxies through shared backend auth helper instead of direct database access", async () => {
    const source = await loadRouteSource();

    assert.match(source, /fetchWithBackendAuthFallback/);
    assert.match(source, /getBackendAuthContext/);
    assert.match(source, /hasBackendAuthCandidate/);
    assert.match(source, /\/api\/resources/);
    assert.match(source, /searchParams\.get\("integration_id"\)/);
    assert.doesNotMatch(source, /createClient\(/);
    assert.doesNotMatch(source, /MONGODB_URI/);
    assert.doesNotMatch(source, /\.from\("resources"\)/);
});
