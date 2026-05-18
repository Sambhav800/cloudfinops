import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadCardSource() {
    return readFile(new URL("./savings-copilot-card.tsx", import.meta.url), "utf8");
}

test("savings copilot card uses pending notifications and existing action endpoints only", async () => {
    const source = await loadCardSource();

    assert.match(source, /Savings Copilot/);
    assert.match(source, /AI-identified optimizations ready for review/);
    assert.match(source, /\/api\/notifications\?status=pending/);
    assert.match(source, /cost_optimization/);
    assert.match(source, /recommendation\.estimatedSavings > 0/);
    assert.match(source, /\/api\/pending-actions\/generate-fix/);
    assert.match(source, /\/api\/pending-actions\/execute/);
    assert.match(source, /\/api\/pending-actions\/reject/);
    assert.match(source, /Simulate/);
    assert.match(source, /Approve/);
    assert.match(source, /Dismiss/);
});
