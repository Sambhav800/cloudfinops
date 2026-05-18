import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const uploadFormSource = readFileSync(new URL("./bill-upload-form.tsx", import.meta.url), "utf8");
const uploadRouteSource = readFileSync(
    new URL("../../app/api/upload-bill/route.ts", import.meta.url),
    "utf8",
);

test("bill upload timeout budget allows backend parser and Gemini recovery", () => {
    assert.ok(uploadFormSource.includes("const uploadTimeoutMs = 240_000;"));
    assert.ok(uploadRouteSource.includes("const UPLOAD_TIMEOUT_MS = 240_000;"));
    assert.ok(!uploadFormSource.includes("55_000"));
    assert.ok(!uploadRouteSource.includes("55_000"));
});
