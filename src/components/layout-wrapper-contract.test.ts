import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const repoRoot = process.cwd();
const layoutWrapperSource = readFileSync(
  join(repoRoot, "src/components/layout-wrapper.tsx"),
  "utf8",
);

test("layout wrapper does not inject the global navbar on the landing page", () => {
  assert.ok(
    layoutWrapperSource.includes('const isHome = pathname === "/";'),
    "layout wrapper should explicitly detect the home route",
  );
  assert.ok(
    layoutWrapperSource.includes("const showMarketingShell = !isDashboard && !isHome;"),
    "layout wrapper should derive a single marketing-shell flag from dashboard and home routes",
  );
  assert.ok(
    layoutWrapperSource.includes("{showMarketingShell ? <Navbar /> : null}"),
    "layout wrapper should skip the marketing Navbar on the home route",
  );
  assert.ok(
    layoutWrapperSource.includes("{showMarketingShell ? <Footer /> : null}"),
    "layout wrapper should skip the marketing Footer on the home route",
  );
});

test("layout wrapper still keeps dashboard pages free of the public shell", () => {
  assert.ok(
    layoutWrapperSource.includes('const isDashboard = pathname?.startsWith("/dashboard");'),
    "layout wrapper should still detect dashboard routes",
  );
  assert.ok(
    layoutWrapperSource.includes("{isDashboard ? ( // Don't show navbar and footer on dashboard pages"),
    "dashboard shell exclusion should remain intact",
  );
});

test("layout wrapper now routes public pages through the landing shell", () => {
  assert.ok(
    layoutWrapperSource.includes('import { Footer } from "@/components/landing/footer";'),
    "layout wrapper should use the landing footer on public pages",
  );
  assert.ok(
    layoutWrapperSource.includes('import { Navbar } from "@/components/landing/navbar";'),
    "layout wrapper should use the landing navbar on public pages",
  );
});
