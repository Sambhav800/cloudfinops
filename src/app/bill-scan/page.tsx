import type { Metadata } from "next";
import { BillScanPage } from "@/features/bill-scan/BillScanPage";

export const metadata: Metadata = {
  title: "Free Cloud Bill Scanner — CloudFinOps",
  description:
    "Drop your AWS, Azure, or GCP billing export and get an instant waste grade, savings estimate, and top findings. No signup required.",
};

/**
 * Public route: /bill-scan
 *
 * This page is intentionally unauthenticated. Clerk middleware only
 * protects /dashboard/* routes (see src/middleware.ts), so no auth
 * guard is needed here.
 */
export default function BillScanRoute() {
  return <BillScanPage />;
}
