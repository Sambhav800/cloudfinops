import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadRouteSource() {
    return readFile(new URL("./[notificationId]/route.ts", import.meta.url), "utf8");
}

async function loadListRouteSource() {
    return readFile(new URL("./route.ts", import.meta.url), "utf8");
}

test("notification mutation route proxies through shared backend auth helper instead of direct Mongo", async () => {
    const source = await loadRouteSource();

    assert.match(source, /fetchWithBackendAuthFallback/);
    assert.match(source, /getBackendAuthContext/);
    assert.match(source, /\/api\/notifications\/\$\{encodeURIComponent\(normalizedId\)\}/);
    assert.doesNotMatch(source, /createClient\(/);
    assert.doesNotMatch(source, /\.from\("agent_notifications"\)/);
    assert.doesNotMatch(source, /MONGODB_URI/);
});

test("notification mutation route preserves PATCH and DELETE proxy handlers", async () => {
    const source = await loadRouteSource();

    assert.match(source, /export async function PATCH/);
    assert.match(source, /export async function DELETE/);
    assert.match(source, /proxyNotificationMutation\("PATCH"/);
    assert.match(source, /proxyNotificationMutation\("DELETE"/);
});

test("notifications list route proxies through shared backend auth helper instead of direct Mongo", async () => {
    const source = await loadListRouteSource();

    assert.match(source, /fetchWithBackendAuthFallback/);
    assert.match(source, /getBackendAuthContext/);
    assert.match(source, /\/api\/notifications/);
    assert.match(source, /searchParams\.get\("status"\)/);
    assert.doesNotMatch(source, /createClient\(/);
    assert.doesNotMatch(source, /\.from\("agent_notifications"\)/);
    assert.doesNotMatch(source, /MONGODB_URI/);
});
