import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const settingsSource = readFileSync(new URL("./settings-view.tsx", import.meta.url), "utf8");

test("settings modals use a centered viewport overlay with scroll-safe panels", () => {
    assert.ok(settingsSource.includes("const modalOverlayClassName ="));
    assert.ok(settingsSource.includes("fixed inset-0 z-[200] grid place-items-center overflow-y-auto"));
    assert.ok(settingsSource.includes("const modalPanelBaseClassName ="));
    assert.ok(settingsSource.includes("my-auto max-h-[calc(100vh-2rem)]"));
    assert.ok(settingsSource.includes("overscroll-contain"));
    assert.ok(!settingsSource.includes("!fixed !inset-0"));
    assert.ok(!settingsSource.includes("transform-none"));
});

test("settings modals render outside blurred settings surfaces", () => {
    assert.ok(settingsSource.includes("backdrop-blur-xl"));
    assert.ok(
        settingsSource.includes(
            "            </div>\n\n            {addAccountMode === \"selection\" && ("
        )
    );
});

test("bill scanning and access-key modals share the centered modal contract", () => {
    assert.ok(settingsSource.includes('addAccountMode === "deep-scan"'));
    assert.ok(settingsSource.includes('addAccountMode === "bill-upload"'));
    assert.ok(settingsSource.includes("<ConnectCloudForm onCancel={() => setAddAccountMode(null)} />"));
    assert.ok(settingsSource.includes("<BillUploadForm onCancel={() => setAddAccountMode(null)} />"));
    assert.ok(settingsSource.includes('className={`${modalPanelBaseClassName} max-w-md`}'));
    assert.ok(settingsSource.includes('className={`${modalPanelBaseClassName} max-w-lg`}'));
});
