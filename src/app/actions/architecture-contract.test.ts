import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadSource() {
    return readFile(new URL("./architecture.ts", import.meta.url), "utf8");
}

test("architecture actions do not import the mock architecture fixtures into the live action path", async () => {
    const source = await loadSource();

    assert.doesNotMatch(source, /architecture-mock/);
    assert.doesNotMatch(source, /mockGraphResponse/);
    assert.doesNotMatch(source, /mockProposedResult/);
});

test("getGraphAction always delegates to the backend graph helper instead of a mock env switch", async () => {
    const source = await loadSource();

    assert.match(source, /export async function getGraphAction[\s\S]*?getArchitectureGraph\(/);
    assert.doesNotMatch(source, /NEXT_PUBLIC_USE_MOCK_ARCH/);
    assert.doesNotMatch(source, /mockGraphResponse/);
});

test("generateProposedAction always delegates to the backend proposed helper instead of canned mock output", async () => {
    const source = await loadSource();

    assert.match(source, /export async function generateProposedAction[\s\S]*?generateProposedArchitecture\(/);
    assert.doesNotMatch(source, /NEXT_PUBLIC_USE_MOCK_ARCH/);
    assert.doesNotMatch(source, /mockProposedResult/);
    assert.doesNotMatch(source, /setTimeout/);
});
