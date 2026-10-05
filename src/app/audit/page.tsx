import type { Metadata } from "next";
import { AuditForm } from "./audit-form";

export const metadata: Metadata = {
  title: "Free 7-Day Cloud Audit — Discover Your Savings Potential",
  description:
    "Get a free expert analysis of your AWS, Azure, or GCP spending. Receive a cost analysis report, optimization recommendations, savings projection, and a 30-minute consultation.",
  alternates: { canonical: "/audit" },
};

export default function AuditPage() {
  return <AuditForm />;
}
