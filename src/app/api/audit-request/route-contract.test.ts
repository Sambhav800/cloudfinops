import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadRouteSource() {
    return readFile(new URL("./route.ts", import.meta.url), "utf8");
}

test("audit-request route lazy-loads Mongo and email helpers inside POST", async () => {
    const source = await loadRouteSource();

    assert.match(source, /export const runtime = 'nodejs'/);
    assert.match(source, /await import\('@\/lib\/mongodb\/client'\)/);
    assert.match(source, /await import\('@\/lib\/emails\/audit-emails'\)/);
    assert.doesNotMatch(source, /^import\s+\{\s*createClient\s*\}\s+from\s+['"]@\/lib\/mongodb\/client['"]/m);
    assert.doesNotMatch(source, /^import\s+\{[^}]*sendThankYouEmail[^}]*\}\s+from\s+['"]@\/lib\/emails\/audit-emails['"]/m);
});

test("audit-request route preserves the POST validation and response contract", async () => {
    const source = await loadRouteSource();

    assert.match(source, /export async function POST/);
    assert.match(source, /if \(!firstName \|\| !lastName \|\| !email\)/);
    assert.match(source, /Please provide a valid email address\./);
    assert.match(source, /Your audit request has been received!/);
});
