import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const repoRoot = process.cwd();
const pageSource = readFileSync(
  join(repoRoot, "src/app/page.tsx"),
  "utf8",
);
const landingPageSource = readFileSync(
  join(repoRoot, "src/components/landing/landing-page.tsx"),
  "utf8",
);
const heroCopySource = readFileSync(
  join(repoRoot, "src/components/landing/hero-copy.tsx"),
  "utf8",
);

test("landing page is a server component that renders the client LandingPage", () => {
  assert.ok(
    pageSource.includes('import { LandingPage } from "@/components/landing/landing-page"'),
    "page.tsx should import the LandingPage client component",
  );
  assert.ok(
    pageSource.includes("<LandingPage />"),
    "page.tsx should render the LandingPage component",
  );
  assert.ok(
    !pageSource.includes('"use client"'),
    "page.tsx should remain a server component for metadata export",
  );
});

test("page.tsx exports metadata with structured data", () => {
  assert.ok(
    pageSource.includes("export const metadata"),
    "page.tsx should export Next.js metadata",
  );
  assert.ok(
    pageSource.includes("application/ld+json"),
    "page.tsx should include JSON-LD structured data",
  );
});

test("landing page client component includes core sections", () => {
  assert.ok(
    landingPageSource.includes('"use client"'),
    "landing-page.tsx should be a client component",
  );
  assert.ok(
    landingPageSource.includes("<Hero />"),
    "landing-page.tsx should render the Hero component",
  );
  assert.ok(
    landingPageSource.includes("<Footer />"),
    "landing-page.tsx should render the Footer component",
  );
});

test("hero copy includes CloudFinOps definition for AEO", () => {
  assert.ok(
    heroCopySource.includes("CloudFinOps is"),
    "hero-copy.tsx should include a definition sentence for answer engines",
  );
});
