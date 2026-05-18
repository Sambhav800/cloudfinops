import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const repoRoot = process.cwd();
const pageSource = readFileSync(
  join(repoRoot, "src/app/page.tsx"),
  "utf8",
);
const heroSource = readFileSync(
  join(repoRoot, "src/components/hero.tsx"),
  "utf8",
);

test("landing page keeps the hero isolated in the dedicated Hero component", () => {
  assert.ok(
    pageSource.includes('import { Hero } from "@/components/hero";'),
    "page.tsx should import the dedicated Hero component",
  );
  assert.ok(
    pageSource.includes('import { LandingBackground } from "@/components/landing-background";'),
    "page.tsx should import the shared landing background contract",
  );
  assert.ok(
    pageSource.includes("<Hero />"),
    "page.tsx should render the dedicated Hero component",
  );
  assert.ok(
    pageSource.includes("<LandingBackground />"),
    "page.tsx should keep the shared ambient landing background layer",
  );
  assert.ok(
    !pageSource.includes('"use client";'),
    "page.tsx should remain a server page instead of a full client shell",
  );
});

test("landing page still exposes the expected below-the-fold anchors", () => {
  for (const anchor of ['id="features"', 'id="security"', 'id="docs"', 'id="pricing"']) {
    assert.ok(
      pageSource.includes(anchor),
      `page.tsx should preserve the ${anchor} section anchor`,
    );
  }
});

test("hero component owns the stronger premium message and interaction shell", () => {
  assert.ok(
    heroSource.startsWith('"use client";'),
    "hero.tsx should stay client-side for pointer interaction",
  );
  assert.ok(
    heroSource.includes("See every leak."),
    "hero headline should keep the sharper enterprise message",
  );
  assert.ok(
    heroSource.includes("CloudFinOps command core"),
    "hero should keep the control-plane composition",
  );
});
