import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadNextConfigSource() {
    return readFile(new URL("../next.config.ts", import.meta.url), "utf8");
}

test("backend API rewrite is fallback-only so app API routes win first", async () => {
    const source = await loadNextConfigSource();
    const rewritesStart = source.indexOf("async rewrites()");
    const rewritesBlock = rewritesStart >= 0 ? source.slice(rewritesStart) : "";

    assert.match(rewritesBlock, /fallback:\s*\[/);
    assert.match(rewritesBlock, /source:\s*'\/api\/:path\*'/);
    assert.match(rewritesBlock, /source:\s*'\/ws\/:path\*'/);
    assert.doesNotMatch(rewritesBlock, /return\s*\[/);
});
