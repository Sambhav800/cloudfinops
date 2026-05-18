import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadSource() {
    return readFile(new URL("./security-view.tsx", import.meta.url), "utf8");
}

test("security view renders the expected dashboard sections and recharts primitives", async () => {
    const source = await loadSource();

    assert.match(source, /SecurityPosture/);
    assert.doesNotMatch(source, /GovernanceData/);
    assert.doesNotMatch(source, /normalizeViolations/);
    assert.match(source, /Live posture from security policies, permission alerts, and scanned resources/);
    assert.match(source, /Security Score/);
    assert.match(source, /Critical/);
    assert.match(source, /High/);
    assert.match(source, /Open Issues/);
    assert.match(source, /Coverage/);
    assert.match(source, /Findings by Severity/);
    assert.match(source, /Findings by Category/);
    assert.match(source, /Active Findings/);
    assert.match(source, /Exposed Resources/);
    assert.match(source, /ResponsiveContainer/);
    assert.match(source, /BarChart/);
    assert.match(source, /SEVERITY_COLORS/);
    assert.match(source, /PROVIDER_COLORS/);
    assert.match(source, /border-t-2/);
});
