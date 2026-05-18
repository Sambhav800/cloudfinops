import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadSource() {
    return readFile(new URL("./actions-list.tsx", import.meta.url), "utf8");
}

test("pending actions list adds a simulate modal backed by existing resources and fix-generation endpoints", async () => {
    const source = await loadSource();

    assert.match(source, /Simulate/);
    assert.match(source, /shouldRenderActionDescription/);
    assert.match(source, /\/api\/resources/);
    assert.match(source, /\/api\/pending-actions\/generate-fix/);
    assert.match(source, /\/api\/pending-actions\/execute/);
    assert.match(source, /Current state/);
    assert.match(source, /Proposed state/);
    assert.match(source, /Projected savings/);
    assert.match(source, /Risk label/);
    assert.match(source, /CLI preview/);
    assert.match(source, /Execute Later/);
    assert.match(source, /Copy Command/);
    assert.match(source, /Mark Done/);
    assert.match(source, /formatActionLabel\(action\.action_type\)/);
});
