import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadViewSource() {
    return readFile(new URL("./bill-analysis-view.tsx", import.meta.url), "utf8");
}

test("bill analysis view no longer exposes a raw source bill link to end users", async () => {
    const source = await loadViewSource();

    assert.doesNotMatch(source, /Open source bill/);
    assert.doesNotMatch(source, /\/api\/bill-analyses\/\$\{encodeURIComponent\(currentAnalysisId\)\}\/source-file/);
});

test("bill analysis view still communicates private raw-bill retention when archival exists", async () => {
    const source = await loadViewSource();

    assert.match(source, /Retained privately/);
    assert.match(source, /internal analysis, audit, and reprocessing/);
});
