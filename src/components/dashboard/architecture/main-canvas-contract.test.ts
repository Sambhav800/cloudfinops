import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadSource() {
    return readFile(new URL("./main-canvas.tsx", import.meta.url), "utf8");
}

test("main canvas surfaces architecture evidence notes for inferred topology and cost provenance", async () => {
    const source = await loadSource();

    assert.match(source, /function buildEvidenceNote/);
    assert.match(source, /warning\.type === 'inferred_relationships'/);
    assert.match(source, /warning\.type === 'estimated_cost_data'/);
    assert.match(source, /\[proposed\?\.risk_tradeoffs, evidenceNote\]\.filter\(Boolean\)\.join\(' '\)/);
    assert.match(source, /supportingText: evidenceNote \?\?/);
});
