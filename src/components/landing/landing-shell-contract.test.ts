import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const repoRoot = process.cwd();
const navbarSource = readFileSync(
  join(repoRoot, "src/components/landing/navbar.tsx"),
  "utf8",
);
const footerSource = readFileSync(
  join(repoRoot, "src/components/landing/footer.tsx"),
  "utf8",
);
const heroCopySource = readFileSync(
  join(repoRoot, "src/components/landing/hero-copy.tsx"),
  "utf8",
);
const bentoSource = readFileSync(
  join(repoRoot, "src/components/landing/features/capabilities-bento.tsx"),
  "utf8",
);

test("landing navbar swaps auth controls based on signed-in state and includes the logo asset", () => {
  assert.ok(
    navbarSource.includes('src="/images/logo/wh-logo.png"'),
    "landing navbar should use the product logo asset",
  );
  assert.ok(
    navbarSource.includes("SignedIn"),
    "landing navbar should render an authenticated state",
  );
  assert.ok(
    navbarSource.includes("SignedOut"),
    "landing navbar should render a signed-out state",
  );
  assert.ok(
    navbarSource.includes("UserButton"),
    "landing navbar should expose the Clerk user button when signed in",
  );
  assert.ok(
    navbarSource.includes('href="/dashboard"'),
    "landing navbar should link signed-in users to the dashboard",
  );
});

test("hero primary CTA swaps from start free to dashboard based on auth state", () => {
  assert.ok(
    heroCopySource.includes("SignedIn"),
    "hero copy should render a signed-in state",
  );
  assert.ok(
    heroCopySource.includes("SignedOut"),
    "hero copy should render a signed-out state",
  );
  assert.ok(
    heroCopySource.includes('href="/dashboard"'),
    "hero copy should send signed-in users to the dashboard",
  );
  assert.ok(
    heroCopySource.includes(">Start free<"),
    "hero copy should keep the signed-out start-free CTA",
  );
});

test("landing hero and footer stay honest about proof links", () => {
  assert.equal(
    heroCopySource.includes("TRUSTED BY ENGINEERING TEAMS AT"),
    false,
    "hero should not render fake trust copy",
  );
  assert.equal(
    heroCopySource.includes("VERTEX LABS"),
    false,
    "hero should not render fake customer wordmarks",
  );
  assert.ok(
    footerSource.includes('src="/images/logo/wh-logo.png"'),
    "landing footer should use the product logo asset",
  );
  assert.ok(
    footerSource.includes("CloudFinOps"),
    "landing footer should render the CloudFinOps wordmark",
  );
  assert.equal(
    footerSource.match(/\{ label: "Security", href: "\/security" \}/g)?.length ?? 0,
    1,
    "footer should include the security link only once",
  );
});

test("bill scanner capability card clips its contents and loops the scan animation", () => {
  assert.ok(
    bentoSource.includes("function BillScannerViz()"),
    "capabilities bento should define the bill scanner visualization",
  );
  assert.ok(
    bentoSource.includes("overflow-hidden rounded-md"),
    "bill scanner visualization should clip its inner document surface",
  );
  assert.ok(
    bentoSource.includes("repeat: Infinity"),
    "bill scanner scan line should loop continuously",
  );
  assert.ok(
    bentoSource.includes("bg-gradient-to-t from-[#0c0d12] to-transparent"),
    "bill scanner visualization should fade out cleanly inside the card",
  );
});
