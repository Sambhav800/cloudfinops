import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const repoRoot = process.cwd();
const pageSource = readFileSync(join(repoRoot, "src/app/page.tsx"), "utf8");
const landingSource = readFileSync(join(repoRoot, "src/components/landing/landing-page.tsx"), "utf8");
const horizontalSource = readFileSync(
  join(repoRoot, "src/components/landing/horizontal-showcase.tsx"),
  "utf8",
);
const workflowSource = readFileSync(
  join(repoRoot, "src/components/landing/workflow-section.tsx"),
  "utf8",
);
const globalsSource = readFileSync(join(repoRoot, "src/app/globals.css"), "utf8");

test("page keeps the pinned horizontal showcase and workflow sections in the live composition", () => {
  assert.ok(pageSource.includes('import { LandingPage } from "@/components/landing/landing-page";'));
  assert.ok(pageSource.includes("<LandingPage />"));
  assert.ok(
    landingSource.includes('import { HorizontalShowcase } from "@/components/landing/horizontal-showcase";'),
    "landing composition should import the horizontal showcase section",
  );
  assert.ok(
    landingSource.includes('import { WorkflowSection } from "@/components/landing/workflow-section";'),
    "landing composition should import the workflow section",
  );

  const horizontalIndex = landingSource.indexOf("<HorizontalShowcase />");
  const unifyIndex = landingSource.indexOf("<FeatureUnify />");
  const workflowIndex = landingSource.indexOf("<WorkflowSection />");
  const bentoIndex = landingSource.indexOf("<CapabilitiesBento />");
  const metricsIndex = landingSource.indexOf("<Metrics />");

  assert.ok(horizontalIndex > -1 && horizontalIndex < unifyIndex, "horizontal showcase should appear before feature blocks");
  assert.ok(workflowIndex > unifyIndex && workflowIndex < bentoIndex, "workflow section should appear between feature blocks and the bento grid");
  assert.ok(bentoIndex > -1 && bentoIndex < metricsIndex, "capabilities bento should still appear before metrics");
  assert.equal(
    (pageSource + landingSource).includes("<IntegrationsMarquee />"),
    false,
    "page should no longer render the fake integrations marquee",
  );
});

test("horizontal showcase keeps the sticky desktop section and the stacked mobile fallback", () => {
  assert.ok(
    horizontalSource.includes('className="relative hidden h-[500vh] md:block"'),
    "desktop horizontal showcase should reserve 500vh of scroll distance",
  );
  assert.ok(
    horizontalSource.includes('className="sticky top-0 flex h-screen items-center overflow-hidden"'),
    "desktop horizontal showcase should pin a sticky full-screen viewport",
  );
  assert.ok(
    horizontalSource.includes("useSpring"),
    "horizontal showcase should spring-smooth the scroll progress",
  );
  assert.ok(
    horizontalSource.includes("md:hidden"),
    "horizontal showcase should render a mobile stacked fallback",
  );
  assert.ok(
    horizontalSource.includes("[index === 0 ? 1 : 0.22, 1, 1, 0.22]"),
    "first desktop panel should start fully readable instead of entering nearly invisible",
  );
  assert.ok(
    horizontalSource.includes("[index === 0 ? 1 : 0, 1]"),
    "first desktop panel bullets should be visible immediately when the sticky section pins",
  );
});

test("workflow section and marquee support styles stay available without forcing fake proof into the page", () => {
  assert.ok(
    workflowSource.includes("under ten minutes."),
    "workflow section should render the required title copy",
  );
  assert.ok(
    workflowSource.includes("border-dashed"),
    "workflow section should include dashed connector lines on desktop",
  );
  assert.ok(
    globalsSource.includes("@keyframes marquee"),
    "globals.css should define the marquee keyframes",
  );
  assert.ok(
    globalsSource.includes("@keyframes marquee-reverse"),
    "globals.css should define the reverse marquee keyframes",
  );
});
