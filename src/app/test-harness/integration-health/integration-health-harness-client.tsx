"use client";

import { IntegrationHealthPanel } from "@/components/dashboard/integration-health-panel";

const stubGetToken = async () => "test-token";

export function IntegrationHealthHarnessClient() {
  return (
    <main
      className="min-h-screen bg-slate-950 p-8 pt-24"
      data-testid="harness-root"
    >
      <IntegrationHealthPanel getToken={stubGetToken} />
    </main>
  );
}
