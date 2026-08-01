import type { Metadata } from "next";
import { CloudCog, ScanSearch, LineChart, Sparkles, ArrowRight } from "lucide-react";

export const metadata: Metadata = {
  title: "How It Works — Connect, Scan & Optimize Your Cloud in 4 Steps",
  description:
    "Learn how CloudFinOps works: connect your AWS or Azure account with read-only access, get AI-powered scanning, receive prioritized savings recommendations, and optimize continuously.",
  alternates: { canonical: "/how-it-works" },
};

const steps = [
    {
        number: "01",
        icon: CloudCog,
        title: "Connect Your Cloud",
        description: "Securely connect your AWS or Azure accounts using read-only IAM roles. No agents required, no infrastructure changes needed.",
        details: [
            "Cross-account role assumption (AWS STS)",
            "Service Principal with Reader role (Azure)",
            "Zero-trust, read-only architecture",
            "Setup completed in under 5 minutes"
        ]
    },
    {
        number: "02",
        icon: ScanSearch,
        title: "Automated Scanning",
        description: "Our AI-powered engine analyzes your entire cloud infrastructure, identifying optimization opportunities and cost anomalies.",
        details: [
            "Resource utilization analysis",
            "Idle resource detection",
            "Reserved instance recommendations",
            "Tag compliance checking"
        ]
    },
    {
        number: "03",
        icon: LineChart,
        title: "Get Actionable Insights",
        description: "Receive prioritized recommendations with estimated savings. Each insight includes step-by-step implementation guidance.",
        details: [
            "ROI-prioritized recommendations",
            "One-click implementation scripts",
            "Risk assessment for each change",
            "Historical trend analysis"
        ]
    },
    {
        number: "04",
        icon: Sparkles,
        title: "Save & Optimize",
        description: "Implement changes at your pace with our human-in-the-loop approval system. Track savings and continuously optimize.",
        details: [
            "Approval workflows for teams",
            "Savings tracking dashboard",
            "Continuous monitoring",
            "Monthly optimization reports"
        ]
    }
];

const howToJsonLd = {
  "@context": "https://schema.org",
  "@type": "HowTo",
  name: "How to Optimize Cloud Costs with CloudFinOps",
  description:
    "Four simple steps to start saving on your cloud infrastructure costs using CloudFinOps AI-powered platform.",
  totalTime: "PT10M",
  step: [
    {
      "@type": "HowToStep",
      position: 1,
      name: "Connect Your Cloud",
      text: "Securely connect your AWS or Azure accounts using read-only IAM roles. No agents required, no infrastructure changes needed. Setup completed in under 5 minutes.",
    },
    {
      "@type": "HowToStep",
      position: 2,
      name: "Automated Scanning",
      text: "Our AI-powered engine analyzes your entire cloud infrastructure, identifying optimization opportunities, idle resources, and cost anomalies.",
    },
    {
      "@type": "HowToStep",
      position: 3,
      name: "Get Actionable Insights",
      text: "Receive prioritized recommendations with estimated savings. Each insight includes step-by-step implementation guidance and risk assessment.",
    },
    {
      "@type": "HowToStep",
      position: 4,
      name: "Save & Optimize",
      text: "Implement changes at your pace with human-in-the-loop approval system. Track savings and continuously optimize with monthly reports.",
    },
  ],
};

export default function HowItWorksPage() {
    return (
        <div className="bg-black min-h-screen pt-24 pb-12">
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(howToJsonLd) }}
            />
            <div className="mx-auto max-w-5xl px-6 lg:px-8">
                <div className="text-center mb-16">
                    <h1 className="text-4xl font-bold tracking-tight text-white sm:text-6xl mb-4">
                        How It Works
                    </h1>
                    <p className="text-xl text-gray-400 max-w-3xl mx-auto">
                        Four simple steps to start saving on your cloud infrastructure costs.
                    </p>
                </div>

                <div className="space-y-12">
                    {steps.map((step, index) => (
                        <div key={step.number} className="relative">
                            <div className="bg-white/5 border border-white/10 rounded-2xl p-8 hover:border-primary/30 transition-all">
                                <div className="flex flex-col md:flex-row gap-6">
                                    <div className="flex-shrink-0">
                                        <div className="bg-primary/10 w-16 h-16 rounded-2xl flex items-center justify-center">
                                            <step.icon className="h-8 w-8 text-primary" />
                                        </div>
                                        <div className="text-5xl font-bold text-white/10 mt-2">{step.number}</div>
                                    </div>
                                    <div className="flex-1">
                                        <h3 className="text-2xl font-bold text-white mb-3">{step.title}</h3>
                                        <p className="text-gray-400 mb-4">{step.description}</p>
                                        <ul className="grid md:grid-cols-2 gap-2">
                                            {step.details.map((detail) => (
                                                <li key={detail} className="flex items-center gap-2 text-sm text-gray-300">
                                                    <ArrowRight className="h-4 w-4 text-primary flex-shrink-0" />
                                                    {detail}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>
                            </div>
                            {index < steps.length - 1 && (
                                <div className="absolute left-8 top-full h-12 w-px bg-gradient-to-b from-primary/50 to-transparent hidden md:block" />
                            )}
                        </div>
                    ))}
                </div>

                <div className="mt-16 text-center">
                    <a
                        href="/audit"
                        className="inline-flex items-center gap-2 bg-primary text-black px-8 py-4 rounded-full font-bold hover:bg-primary/90 transition-colors"
                    >
                        Get Started Free
                        <ArrowRight className="h-5 w-5" />
                    </a>
                </div>
            </div>
        </div>
    );
}
