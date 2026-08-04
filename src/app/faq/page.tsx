import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

export const metadata: Metadata = {
  title: "FAQ — Cloud Cost Optimization Questions Answered",
  description:
    "Frequently asked questions about CloudFinOps: how cloud cost optimization works, pricing, security, multi-cloud support, and getting started with your free audit.",
  alternates: { canonical: "/faq" },
};

const faqs = [
  {
    question: "What is CloudFinOps?",
    answer:
      "CloudFinOps is an AI-powered FinOps platform that scans your AWS, Azure, and GCP accounts to detect idle resources, cost anomalies, and governance gaps. It provides prioritized recommendations with estimated savings and exact CLI commands to fix issues — all through read-only, agentless access.",
  },
  {
    question: "How does cloud cost optimization work?",
    answer:
      "Cloud cost optimization identifies resources you're paying for but not fully using. CloudFinOps connects to your cloud accounts via read-only IAM roles, scans infrastructure using provider APIs, and runs AI analysis (Google Gemini) to surface zombie VMs, orphaned storage, unattached IPs, over-provisioned instances, and missing reserved instance opportunities. You get actionable recommendations ranked by savings potential.",
  },
  {
    question: "Is my cloud account safe with CloudFinOps?",
    answer:
      "Yes. CloudFinOps uses a zero-trust, read-only architecture. We never modify, delete, or create resources in your account. Access is granted through scoped read-only IAM roles (AWS SecurityAudit, Azure Reader, GCP Viewer). The system is technically incapable of making changes — any write attempt is rejected by cloud provider APIs. Data is encrypted with AES-256-GCM at rest and TLS 1.3 in transit.",
  },
  {
    question: "Which cloud providers does CloudFinOps support?",
    answer:
      "CloudFinOps supports all three major cloud providers: Amazon Web Services (AWS), Microsoft Azure, and Google Cloud Platform (GCP). You can manage costs across all three from a single unified dashboard with cross-cloud comparison and optimization recommendations.",
  },
  {
    question: "How much can I save on my cloud bill?",
    answer:
      "Industry benchmarks from Flexera and Gartner show organizations waste 25-30% of their cloud spend on idle and over-provisioned resources. CloudFinOps customers typically identify 15-30% savings within the first scan. Actual savings depend on your infrastructure size and current optimization level.",
  },
  {
    question: "How long does it take to set up CloudFinOps?",
    answer:
      "Setup takes under 5 minutes. You grant read-only IAM access to your cloud account — no agents to install, no code changes, no production risk. Once connected, the first scan completes within minutes and you immediately see findings with estimated savings.",
  },
  {
    question: "What is FinOps?",
    answer:
      "FinOps (Cloud Financial Operations) is a practice that brings financial accountability to cloud spending. It combines systems, best practices, and culture to help organizations understand cloud costs, make data-driven decisions, and maximize the business value of cloud. CloudFinOps automates the technical side of FinOps — detection, analysis, and recommendation — so your team can focus on decisions.",
  },
  {
    question: "How is CloudFinOps different from enterprise FinOps tools?",
    answer:
      "Enterprise tools like CloudHealth start around $4,000/month with annual contracts. CloudFinOps is designed for mid-market teams spending $10K-$100K/month on cloud who need professional optimization without enterprise pricing. We're bootstrapped, founder-led, and focused on delivering value from day one with a free 7-day audit.",
  },
  {
    question: "Do I need to install any agents or software?",
    answer:
      "No. CloudFinOps is completely agentless. It connects to your cloud provider APIs using standard read-only IAM roles. There's nothing to install, no code changes required, and zero impact on your production workloads.",
  },
  {
    question: "What compliance standards does CloudFinOps meet?",
    answer:
      "CloudFinOps infrastructure is aligned with SOC 2 Type II controls and ISO 27001:2022 standards. We comply with GDPR, CCPA, India's DPDP Act 2023, and are HIPAA-eligible. Data deletion follows NIST SP 800-88 guidelines with cryptographic erasure after 30 days.",
  },
];

const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: faqs.map((faq) => ({
    "@type": "Question",
    name: faq.question,
    acceptedAnswer: {
      "@type": "Answer",
      text: faq.answer,
    },
  })),
};

const breadcrumbJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    {
      "@type": "ListItem",
      position: 1,
      name: "Home",
      item: "https://cloudfinops.solutions",
    },
    {
      "@type": "ListItem",
      position: 2,
      name: "FAQ",
      item: "https://cloudfinops.solutions/faq",
    },
  ],
};

export default function FAQPage() {
  return (
    <div className="bg-black min-h-screen pt-24 pb-12">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />
      <div className="mx-auto max-w-4xl px-6 lg:px-8">
        <div className="text-center mb-16">
          <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl mb-4">
            Frequently Asked Questions
          </h1>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto">
            Everything you need to know about cloud cost optimization with
            CloudFinOps.
          </p>
        </div>

        <div className="space-y-6">
          {faqs.map((faq) => (
            <div
              key={faq.question}
              className="bg-white/5 border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-colors"
            >
              <h2 className="text-lg font-semibold text-white mb-3">
                {faq.question}
              </h2>
              <p className="text-gray-400 leading-relaxed">{faq.answer}</p>
            </div>
          ))}
        </div>

        <div className="mt-16 text-center">
          <p className="text-gray-400 mb-6">
            Still have questions? Get a free cloud audit and we&apos;ll walk you
            through everything.
          </p>
          <Link
            href="/audit"
            className="inline-flex items-center gap-2 bg-primary text-black px-8 py-4 rounded-full font-bold hover:bg-primary/90 transition-colors"
          >
            Start Free Audit
            <ArrowRight className="h-5 w-5" />
          </Link>
        </div>
      </div>
    </div>
  );
}
