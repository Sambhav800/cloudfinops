import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadSource() {
    return readFile(new URL("./bill-executive-report.tsx", import.meta.url), "utf8");
}

test("bill executive report roadmap actions no longer use raw action strings as React keys", async () => {
    const source = await loadSource();

    assert.doesNotMatch(source, /key=\{action\}/);
    assert.match(source, /key=\{\`\$\{phaseKey\}-action-\$\{actionIndex\}\`\}/);
});

test("source-grounded bill reports do not render fake savings plans", async () => {
    const source = await loadSource();

    assert.match(source, /verification_status === "source_grounded_unverified_savings"/);
    assert.match(source, /verification_status === "bill_line_rule_estimate"/);
    assert.match(source, /No verified quick wins are claimed from this bill alone/);
    assert.match(source, /No roadmap is generated from source-only bill evidence/);
    assert.match(source, /Cross-cloud comparison is hidden/);
});

test("bill-line estimates render evidence, calculation, and validation labels", async () => {
    const source = await loadSource();

    assert.match(source, /Estimated From Bill Lines/);
    assert.match(source, /Requires validation/);
    assert.match(source, /Savings Basis/);
    assert.match(source, /Bill Evidence/);
    assert.match(source, /finding\.calculation \|\| primaryAction\?\.calculation/);
    assert.match(source, /finding\.evidence_lines\?\.length/);
    assert.match(source, /Validation required before execution/);
});

test("bill executive report finding cards use composite render keys so duplicate service names stay isolated", async () => {
    const source = await loadSource();

    assert.match(source, /function getFindingRenderKey\(finding: BillExecutiveFinding, index: number\)/);
    assert.match(source, /const findingKey = getFindingRenderKey\(finding, index\);/);
    assert.match(source, /expandedFindings\[findingKey\]/);
    assert.match(source, /onToggle=\{\(\) => toggleFinding\(findingKey\)\}/);
});

test("bill executive report cross-cloud and roadmap phase rows include index suffixes for duplicate labels", async () => {
    const source = await loadSource();

    assert.match(source, /const phaseKey = \`\$\{phase\.phase\}-\$\{index\}\`;/);
    assert.match(source, /key=\{phaseKey\}/);
    assert.match(source, /key=\{\`\$\{row\.service\}-\$\{index\}\`\}/);
});
