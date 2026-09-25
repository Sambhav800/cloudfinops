/**
 * Playwright test harness page for IntegrationHealthPanel.
 *
 * Accessed via GET /test-harness/integration-health?fixture=<name>
 * The fixture name is read from the query string, the matching JSON
 * payload is fetched from /test-fixtures/<name>.json (served as a
 * static Next.js route), and the API call is intercepted by the test.
 *
 * This page lives outside any auth-guarded layout so Playwright can
 * reach it without Clerk.
 */
"use client";

import { IntegrationHealthPanel } from "@/components/dashboard/integration-health-panel";

// Provide a stub getToken so the component doesn't need Clerk in tests
const stubGetToken = async () => "test-token";

export default function IntegrationHealthHarnessPage() {
  return (
    <main
      className="min-h-screen bg-gray-950 p-8"
      data-testid="harness-root"
    >
      <IntegrationHealthPanel getToken={stubGetToken} />
    </main>
  );
}
