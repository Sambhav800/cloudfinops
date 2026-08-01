import type { Metadata } from "next";
import { LandingPage } from "@/components/landing/landing-page";

export const metadata: Metadata = {
  title: "CloudFinOps — AI-Powered Cloud Cost Optimization for AWS, Azure & GCP",
  description:
    "CloudFinOps is an AI-powered FinOps platform that detects idle cloud resources, reduces waste by up to 30%, and automates governance across AWS, Azure, and GCP. Read-only, agentless, setup in 5 minutes.",
  alternates: { canonical: "/" },
};

const homeJsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "CloudFinOps",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  description:
    "AI-powered FinOps platform that detects idle cloud resources, reduces waste by up to 30%, and automates governance across AWS, Azure, and GCP.",
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "USD",
    description: "Free 7-day cloud audit",
  },
  featureList: [
    "AI-powered cost optimization",
    "Multi-cloud support (AWS, Azure, GCP)",
    "Read-only agentless scanning",
    "Real-time anomaly detection",
    "Governance automation",
    "Compliance reporting (SOC 2, ISO 27001, GDPR)",
  ],
};

export default function HomePage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(homeJsonLd) }}
      />
      <LandingPage />
    </>
  );
}
