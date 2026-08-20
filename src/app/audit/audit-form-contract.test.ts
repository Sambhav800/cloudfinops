import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadAuditFormSource() {
    return readFile(new URL("./audit-form.tsx", import.meta.url), "utf8");
}

test("audit form posts anti-spam context with the public lead payload", async () => {
    const source = await loadAuditFormSource();

    assert.match(source, /formStartedAt/);
    assert.match(source, /name="website"/);
    assert.match(source, /website: formData\.get\("website"\)/);
});

test("audit form requires at least one cloud provider before submit", async () => {
    const source = await loadAuditFormSource();

    assert.match(source, /cloudProviders\.length === 0/);
    assert.match(source, /Select at least one cloud provider\./);
});

test("audit form success copy does not depend on thank-you email delivery", async () => {
    const source = await loadAuditFormSource();

    assert.match(source, /Our audit team has been notified\./);
    assert.doesNotMatch(source, /We&apos;ve sent a confirmation to your email\./);
});
