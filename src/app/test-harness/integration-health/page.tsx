import { notFound } from "next/navigation";

import { IntegrationHealthHarnessClient } from "./integration-health-harness-client";

export default function IntegrationHealthHarnessPage() {
  if (process.env.NODE_ENV === "production") {
    notFound();
  }

  return <IntegrationHealthHarnessClient />;
}
