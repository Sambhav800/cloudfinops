import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const formSource = readFileSync(new URL("./connect-cloud-form.tsx", import.meta.url), "utf8");
const actionSource = readFileSync(new URL("../../app/actions/cloud.ts", import.meta.url), "utf8");

test("connect cloud form preserves the submitted provider after action failures", () => {
    assert.match(formSource, /type CloudActionState = \{ success: boolean; error\?: string; message\?: string; provider\?: Provider \}/);
    assert.match(formSource, /setProvider\(state\.provider\)/);
    assert.match(actionSource, /provider\?: CloudProvider/);
    assert.match(actionSource, /return failCloudConnect\(result\.error \|\| 'Failed to save integration', provider\)/);
});

test("connect cloud form renders provider fields from the controlled provider state", () => {
    assert.match(formSource, /value=\{provider\}/);
    assert.match(formSource, /onChange=\{\(e\) => setProvider\(e\.target\.value as Provider\)\}/);
    assert.match(formSource, /\{provider === 'aws' && \(/);
    assert.match(formSource, /\{provider === 'azure' && \(/);
    assert.match(formSource, /\{provider === 'gcp' && \(/);
});
