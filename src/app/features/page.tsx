import type { Metadata } from "next";
import { Zap, Shield, TrendingDown, Bell, BarChart3, Cloud, Lock, Bot } from "lucide-react";

export const metadata: Metadata = {
  title: "Features — Cloud Cost Optimization, Anomaly Detection & Governance",
  description:
    "Explore CloudFinOps features: AI-powered cost optimization, real-time anomaly detection, multi-cloud support (AWS, Azure, GCP), compliance-ready governance, and instant read-only setup.",
  alternates: { canonical: "/features" },
};

const featuresJsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "CloudFinOps",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "INR",
    description: "Free 7-day cloud audit with full platform access",
  },
  featureList: [
    "AI-powered cloud cost optimization with idle resource detection",
    "Real-time anomaly detection for billing surprises",
    "Financial reports and dashboards by team, project, or environment",
    "Multi-cloud support across AWS, Azure, and GCP",
    "Zero-trust read-only security architecture",
    "Machine learning recommendations from millions of configurations",
    "5-minute guided onboarding with no agents required",
    "SOC 2, GDPR, and DPDP Act 2023 compliance",
  ],
};

const features = [
    {
        icon: TrendingDown,
        title: "Cost Optimization",
        question: "How does CloudFinOps reduce cloud costs?",
        description: "Identify and eliminate wasted cloud spend with AI-powered recommendations. Our engine detects idle EC2 instances, orphaned EBS volumes, unattached Elastic IPs, oversized VMs, and missed reserved instance opportunities — prioritized by savings potential so you fix the biggest leaks first.",
    },
    {
        icon: Bell,
        title: "Anomaly Detection",
        question: "How does anomaly detection catch billing surprises?",
        description: "Real-time alerts when spending patterns deviate from your baseline. Holt-Winters time-series forecasting flags unexpected spikes before they compound into month-end shocks — whether it's a runaway autoscaler, a forgotten dev environment, or misconfigured data transfer.",
    },
    {
        icon: BarChart3,
        title: "Financial Reports",
        question: "What financial reporting does CloudFinOps provide?",
        description: "Comprehensive dashboards and exportable reports designed for both CFOs and platform engineers. Slice spend by team, project, environment, or tag. Track month-over-month trends, compare forecasted vs actual spend, and generate executive-ready PDFs for budget reviews.",
    },
    {
        icon: Cloud,
        title: "Multi-Cloud Support",
        question: "Which cloud providers does CloudFinOps support?",
        description: "Unified visibility across AWS, Microsoft Azure, and Google Cloud Platform from a single dashboard. Compare equivalent instance pricing across providers, identify arbitrage opportunities, and consolidate governance without switching between three different consoles.",
    },
    {
        icon: Lock,
        title: "Read-Only Security",
        question: "Is CloudFinOps safe for production environments?",
        description: "Zero-trust architecture using scoped, read-only IAM roles (AWS SecurityAudit, Azure Reader, GCP Viewer). We are technically incapable of modifying your infrastructure — the cloud provider APIs reject any write attempt. AES-256 encryption at rest, TLS 1.3 in transit.",
    },
    {
        icon: Bot,
        title: "AI-Powered Insights",
        question: "How does the AI analysis work?",
        description: "Google Gemini AI analyzes your resource configurations, utilization patterns, and cost data to generate contextual recommendations. Unlike static rule engines, the AI understands relationships between resources, predicts future spend trajectories, and explains the reasoning behind every suggestion.",
    },
    {
        icon: Zap,
        title: "Instant Setup",
        question: "How long does CloudFinOps take to set up?",
        description: "Connect your cloud accounts in under 5 minutes with guided onboarding. No agents to install, no code to deploy, no production risk. Cross-account role assumption (AWS STS), Service Principal creation (Azure), or Service Account binding (GCP) — each with copy-paste commands.",
    },
    {
        icon: Shield,
        title: "Compliance Ready",
        question: "What compliance standards does CloudFinOps meet?",
        description: "Built for regulated industries with SOC 2 Type II controls, ISO 27001 alignment, GDPR and CCPA compliance, India's DPDP Act 2023 adherence, and HIPAA-eligible infrastructure. Data deletion follows NIST SP 800-88 guidelines with cryptographic erasure after 30 days.",
    },
];

export default function FeaturesPage() {
    return (
        <div className="bg-black min-h-screen pt-24 pb-12">
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(featuresJsonLd) }}
            />
            <div className="mx-auto max-w-7xl px-6 lg:px-8">
                <div className="text-center mb-16">
                    <h1 className="text-4xl font-bold tracking-tight text-white sm:text-6xl mb-4">
                        Powerful Features for <span className="text-primary">Cloud FinOps</span>
                    </h1>
                    <p className="text-xl text-gray-400 max-w-3xl mx-auto">
                        Everything you need to take control of your cloud spending and optimize infrastructure costs.
                    </p>
                </div>

                <div className="grid md:grid-cols-2 gap-6">
                    {features.map((feature) => (
                        <div
                            key={feature.title}
                            className="bg-white/5 border border-white/10 rounded-2xl p-6 hover:border-primary/50 transition-all duration-300 hover:bg-white/[0.07]"
                        >
                            <div className="flex items-center gap-3 mb-3">
                                <div className="bg-primary/10 w-10 h-10 rounded-xl flex items-center justify-center shrink-0">
                                    <feature.icon className="h-5 w-5 text-primary" />
                                </div>
                                <h2 className="text-lg font-bold text-white">{feature.title}</h2>
                            </div>
                            <h3 className="text-sm font-medium text-gray-300 mb-2">{feature.question}</h3>
                            <p className="text-gray-400 text-sm leading-relaxed">{feature.description}</p>
                        </div>
                    ))}
                </div>

                <div className="mt-16 text-center">
                    <a
                        href="/audit"
                        className="inline-flex items-center gap-2 bg-primary text-black px-8 py-4 rounded-full font-bold hover:bg-primary/90 transition-colors"
                    >
                        <Zap className="h-5 w-5" />
                        Start Free Audit
                    </a>
                </div>
            </div>
        </div>
    );
}
