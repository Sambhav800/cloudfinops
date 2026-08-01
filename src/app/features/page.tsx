import type { Metadata } from "next";
import { Zap, Shield, TrendingDown, Bell, BarChart3, Cloud, Lock, Bot } from "lucide-react";

export const metadata: Metadata = {
  title: "Features — Cloud Cost Optimization, Anomaly Detection & Governance",
  description:
    "Explore CloudFinOps features: AI-powered cost optimization, real-time anomaly detection, multi-cloud support (AWS, Azure, GCP), compliance-ready governance, and instant read-only setup.",
  alternates: { canonical: "/features" },
};

const features = [
    {
        icon: TrendingDown,
        title: "Cost Optimization",
        description: "Identify and eliminate wasted cloud spend with AI-powered recommendations. Detect idle resources, rightsizing opportunities, and reserved instance savings."
    },
    {
        icon: Bell,
        title: "Anomaly Detection",
        description: "Real-time alerts when spending patterns deviate from normal. Catch billing surprises before they become expensive mistakes."
    },
    {
        icon: BarChart3,
        title: "Financial Reports",
        description: "Comprehensive dashboards and reports for CFOs and engineering teams. Track spending by team, project, or environment."
    },
    {
        icon: Cloud,
        title: "Multi-Cloud Support",
        description: "Unified visibility across AWS and Azure. Compare costs, optimize workloads, and make data-driven decisions."
    },
    {
        icon: Lock,
        title: "Read-Only Security",
        description: "Zero-trust architecture with read-only access. We never modify your infrastructure—only analyze and recommend."
    },
    {
        icon: Bot,
        title: "AI-Powered Insights",
        description: "Machine learning models trained on millions of cloud configurations to provide actionable, personalized recommendations."
    },
    {
        icon: Zap,
        title: "Instant Setup",
        description: "Connect your cloud accounts in minutes with our guided onboarding. No agents to install, no complex configurations."
    },
    {
        icon: Shield,
        title: "Compliance Ready",
        description: "Built for enterprises with SOC 2 alignment, GDPR compliance, and DPDP Act 2023 adherence."
    }
];

export default function FeaturesPage() {
    return (
        <div className="bg-black min-h-screen pt-24 pb-12">
            <div className="mx-auto max-w-7xl px-6 lg:px-8">
                <div className="text-center mb-16">
                    <h1 className="text-4xl font-bold tracking-tight text-white sm:text-6xl mb-4">
                        Powerful Features for <span className="text-primary">Cloud FinOps</span>
                    </h1>
                    <p className="text-xl text-gray-400 max-w-3xl mx-auto">
                        Everything you need to take control of your cloud spending and optimize infrastructure costs.
                    </p>
                </div>

                <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {features.map((feature) => (
                        <div
                            key={feature.title}
                            className="bg-white/5 border border-white/10 rounded-2xl p-6 hover:border-primary/50 transition-all duration-300 hover:bg-white/[0.07]"
                        >
                            <div className="bg-primary/10 w-12 h-12 rounded-xl flex items-center justify-center mb-4">
                                <feature.icon className="h-6 w-6 text-primary" />
                            </div>
                            <h2 className="text-lg font-bold text-white mb-2">{feature.title}</h2>
                            <p className="text-gray-400 text-sm">{feature.description}</p>
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
