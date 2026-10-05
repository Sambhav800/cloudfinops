import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

async function loadRouteSource() {
    return readFile(new URL("./route.ts", import.meta.url), "utf8");
}

test("audit-request route lazy-loads Mongo and email helpers inside POST", async () => {
    const source = await loadRouteSource();

    assert.match(source, /export const runtime = 'nodejs'/);
    assert.match(source, /await import\('@\/lib\/mongodb\/client'\)/);
    assert.match(source, /await import\('@\/lib\/emails\/audit-emails'\)/);
    assert.doesNotMatch(source, /^import\s+\{\s*createClient\s*\}\s+from\s+['"]@\/lib\/mongodb\/client['"]/m);
    assert.doesNotMatch(source, /^import\s+\{[^}]*sendThankYouEmail[^}]*\}\s+from\s+['"]@\/lib\/emails\/audit-emails['"]/m);
});

test("audit-request route preserves the POST validation and response contract", async () => {
    const source = await loadRouteSource();

    assert.match(source, /export async function POST/);
    assert.match(source, /'firstName', 'First name', 80, true/);
    assert.match(source, /'jobTitle', 'Job title', 120, true/);
    assert.match(source, /At least one cloud provider is required\./);
    assert.match(source, /Please provide a valid email address\./);
    assert.match(source, /Please provide a valid company website\./);
    assert.match(source, /Your audit request has been received!/);
});

test("audit-request route treats persistence and internal delivery as hard pipeline steps", async () => {
    const source = await loadRouteSource();

    assert.match(source, /lead_notification_status: 'pending'/);
    assert.match(source, /thank_you_status: 'pending'/);
    assert.match(source, /sendLeadNotificationEmail/);
    assert.match(source, /delivery_failed/);
    assert.doesNotMatch(source, /Promise\.allSettled/);
    assert.doesNotMatch(source, /DB persistence is best-effort/);
});

test("audit-request route has basic public-form spam hardening", async () => {
    const source = await loadRouteSource();

    assert.match(source, /HONEYPOT_FIELD = 'website'/);
    assert.match(source, /MIN_FORM_AGE_MS/);
    assert.match(source, /shouldSilentlyAcceptSpam/);
});
