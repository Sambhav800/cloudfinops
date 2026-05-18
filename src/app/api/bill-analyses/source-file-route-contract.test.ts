import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadRouteSource() {
    return readFile(new URL("./[analysisId]/source-file/route.ts", import.meta.url), "utf8");
}

test("bill source file route is intentionally disabled for end-user access", async () => {
    const source = await loadRouteSource();

    assert.match(source, /return NextResponse\.json/);
    assert.match(source, /detail:\s*"Not found"/);
    assert.match(source, /status:\s*404/);
    assert.match(source, /Cache-Control/);
    assert.doesNotMatch(source, /fetchWithBackendAuthFallback/);
    assert.doesNotMatch(source, /getBackendAuthContext/);
    assert.doesNotMatch(source, /response\.arrayBuffer\(\)/);
    assert.doesNotMatch(source, /createClient\(/);
    assert.doesNotMatch(source, /\.from\("bill_analyses"\)/);
    assert.doesNotMatch(source, /MONGODB_URI/);
});

test("bill source file route keeps the same-origin path dark instead of proxying downloads", async () => {
    const source = await loadRouteSource();

    assert.match(source, /export async function GET/);
    assert.doesNotMatch(source, /Content-Disposition/);
    assert.doesNotMatch(source, /new NextResponse\(buffer/);
});
