import type { Metadata } from "next";
import { Shield, Eye, Zap, Terminal, Cloud, Brain, ArrowRight } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About CloudFinOps — AI Cloud Cost Optimization Platform",
  description:
    "CloudFinOps is a bootstrapped, founder-led FinOps platform that helps mid-market teams find and eliminate wasted cloud spend across AWS, Azure, and GCP with read-only, agentless scanning.",
  alternates: { canonical: "/about" },
};

const aboutJsonLd = {
  "@context": "https://schema.org",
  "@type": "AboutPage",
  mainEntity: {
    "@type": "Organization",
    name: "CloudFinOps",
    url: "https://cloudfinops.solutions",
    description:
      "AI-powered FinOps platform that detects idle cloud resources, eliminates waste, and automates governance across AWS, Azure, and GCP.",
    foundingDate: "2025",
    foundingLocation: {
      "@type": "Place",
      name: "Zirakpur, Punjab, India",
    },
    founder: [
      {
        "@type": "Person",
        name: "Sambhav Pal",
        jobTitle: "Founder & CEO",
        knowsAbout: [
          "Cloud Computing",
          "FinOps",
          "SaaS",
          "Business Strategy",
          "Cost Optimization",
        ],
      },
      {
        "@type": "Person",
        name: "Nishant Jain",
        jobTitle: "Co-Founder & CTO",
        knowsAbout: [
          "Cloud Architecture",
          "AWS",
          "Azure",
          "GCP",
          "Full-Stack Engineering",
          "AI/ML",
          "Infrastructure Automation",
        ],
      },
    ],
    numberOfEmployees: {
      "@type": "QuantitativeValue",
      value: 5,
      unitText: "employees",
    },
    areaServed: "Worldwide",
    knowsAbout: [
      "Cloud Cost Optimization",
      "FinOps",
      "Cloud Governance",
      "Infrastructure Waste Detection",
    ],
  },
};

export default function AboutPage() {
    return (
        <div className="bg-black min-h-screen pt-28 pb-16">
            <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(aboutJsonLd) }}
            />
            <div className="mx-auto max-w-5xl px-6 lg:px-8">

                {/* Header */}
                <div className="text-center max-w-3xl mx-auto mb-24">
                    <h1 className="text-4xl md:text-5xl font-semibold text-white tracking-tight mb-6 leading-[1.1]">
                        We Find the Cloud Resources{" "}
                        <span className="text-gradient">You&apos;re Paying For but Not Using</span>
                    </h1>
                    <p className="text-lg text-gray-400 leading-relaxed max-w-2xl mx-auto">
                        CloudFinOps is an agentless, read-only platform that scans your AWS,
                        Azure, and GCP accounts to surface idle resources, cost anomalies,
                        and governance gaps — then gives you the exact commands to fix them.
                    </p>
                    <div className="flex flex-wrap justify-center gap-3 mt-8">
                        <span className="px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs text-gray-400">
                            Bootstrapped &amp; Founder-Led
                        </span>
                    </div>
                </div>

                {/* Problem & Solution */}
                <div className="grid md:grid-cols-2 gap-8 mb-28">
                    <div className="glass-card p-8">
                        <h2 className="text-2xl font-semibold text-white mb-5">The Problem</h2>
                        <p className="text-gray-400 leading-relaxed mb-4">
                            Industry benchmarks from Flexera and Gartner consistently show that
                            organizations waste <strong className="text-white">25-30% of their cloud spend</strong> on
                            idle VMs, orphaned disks, unattached IPs, and over-provisioned instances.
                        </p>
                        <p className="text-gray-400 leading-relaxed">
                            Enterprise tools like CloudHealth start around ₹3.1L/mo with annual contracts.
                            For companies spending ₹8L-₹83L/mo on cloud, there&apos;s no affordable
                            middle ground between expensive enterprise platforms and fragile scripts.
                        </p>
                    </div>

                    <div className="glass-card p-8">
                        <h2 className="text-2xl font-semibold text-white mb-5">What We Built</h2>
                        <p className="text-gray-400 leading-relaxed mb-6">
                            A read-only, agentless audit platform. You grant us scoped, read-only
                            IAM access — we scan your infrastructure with the cloud provider APIs and
                            run AI analysis using Google Gemini to generate prioritized, actionable recommendations.
                        </p>
                        <ul className="space-y-4">
                            <li className="flex items-start gap-3">
                                <div className="bg-primary/10 p-2 rounded-lg mt-0.5 shrink-0">
                                    <Eye className="h-4 w-4 text-primary" />
                                </div>
                                <div>
                                    <strong className="text-white text-sm block">Read-Only Access</strong>
                                    <span className="text-xs text-gray-500">We never modify, delete, or create resources in your account.</span>
                                </div>
                            </li>
                            <li className="flex items-start gap-3">
                                <div className="bg-primary/10 p-2 rounded-lg mt-0.5 shrink-0">
                                    <Shield className="h-4 w-4 text-primary" />
                                </div>
                                <div>
                                    <strong className="text-white text-sm block">Human-in-the-Loop</strong>
                                    <span className="text-xs text-gray-500">Every recommendation requires your explicit approval before action.</span>
                                </div>
                            </li>
                        </ul>
                    </div>
                </div>

                {/* How It Works */}
                <div className="mb-28">
                    <h2 className="text-2xl font-semibold text-white text-center mb-4">How It Works</h2>
                    <p className="text-sm text-gray-500 text-center mb-12 max-w-lg mx-auto">
                        Three steps. Minutes, not days.
                    </p>

                    <div className="grid md:grid-cols-3 gap-6">
                        {[
                            {
                                step: "01",
                                title: "Connect",
                                description: "Grant read-only IAM access to your AWS, Azure, or GCP account. No agents, no code changes, no production risk.",
                                icon: Cloud,
                            },
                            {
                                step: "02",
                                title: "Scan & Analyze",
                                description: "Our engine queries your cloud APIs and runs Gemini AI analysis to identify zombie VMs, orphaned storage, governance violations, and cost anomalies.",
                                icon: Brain,
                            },
                            {
                                step: "03",
                                title: "Act",
                                description: "Get a prioritized list of findings with estimated savings, CLI commands to execute fixes, and executive-ready reports — all reviewable before action.",
                                icon: Terminal,
                            },
                        ].map((item) => (
                            <div key={item.step} className="glass-card p-6 relative">
                                <span className="text-5xl font-bold text-white/5 absolute top-4 right-6">{item.step}</span>
                                <item.icon className="h-6 w-6 text-primary mb-4" />
                                <h3 className="text-lg font-semibold text-white mb-2">{item.title}</h3>
                                <p className="text-sm text-gray-400 leading-relaxed">{item.description}</p>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Tech Stack — Honest */}
                <div className="mb-28">
                    <h2 className="text-2xl font-semibold text-white text-center mb-4">Built With</h2>
                    <p className="text-sm text-gray-500 text-center mb-12 max-w-lg mx-auto">
                        Production-grade infrastructure. No prototype tools.
                    </p>

                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                        {[
                            { icon: Zap, title: "Next.js 15", sub: "Full-Stack Framework" },
                            { icon: Shield, title: "TypeScript", sub: "End-to-End Type Safety" },
                            { icon: Brain, title: "Google Gemini", sub: "AI Analysis Engine" },
                            { icon: Cloud, title: "AWS · Azure · GCP SDKs", sub: "Multi-Cloud Scanning" },
                            { icon: Terminal, title: "Python + FastAPI", sub: "Backend Scanner Engine" },
                            { icon: Eye, title: "MongoDB + Clerk", sub: "Database & Auth" },
                        ].map((item) => (
                            <div key={item.title} className="bg-white/[0.03] border border-white/[0.06] p-5 rounded-xl flex items-center gap-4 hover:bg-white/[0.06] transition-colors">
                                <item.icon className="h-5 w-5 text-primary shrink-0" />
                                <div>
                                    <h3 className="font-medium text-white text-sm">{item.title}</h3>
                                    <p className="text-[11px] text-gray-500 mt-0.5">{item.sub}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Founders */}
                <div className="mb-24">
                    <h2 className="text-2xl font-semibold text-white text-center mb-4">The Team</h2>
                    <p className="text-sm text-gray-500 text-center mb-12 max-w-lg mx-auto">
                        Two founders. One mission: make cloud cost intelligence accessible to every engineering team.
                    </p>

                    <div className="grid md:grid-cols-2 gap-6">
                        {/* Sambhav */}
                        <div className="glass-card p-8 md:p-10 relative overflow-hidden">
                            <div className="relative z-10">
                                <blockquote className="text-lg text-white font-light leading-relaxed mb-6">
                                    &quot;I built CloudFinOps because I saw mid-market teams spending more
                                    time fighting cloud bills than building product. Enterprise FinOps tools
                                    cost more than the waste they find.&quot;
                                </blockquote>
                                <div className="flex items-center gap-3">
                                    <div className="relative h-14 w-14 rounded-full overflow-hidden border border-white/10 shrink-0">
                                        <Image
                                            src="/images/team/founder.png"
                                            alt="Sambhav Pal, Founder & CEO of CloudFinOps"
                                            fill
                                            className="object-cover"
                                        />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-white">Sambhav Pal</div>
                                        <div className="text-xs text-gray-500">Founder &amp; CEO</div>
                                    </div>
                                </div>
                            </div>
                            <div className="absolute top-0 right-0 w-48 h-48 bg-primary/5 rounded-full blur-[100px] pointer-events-none" />
                        </div>

                        {/* Nishant */}
                        <div className="glass-card p-8 md:p-10 relative overflow-hidden">
                            <div className="relative z-10">
                                <blockquote className="text-lg text-white font-light leading-relaxed mb-6">
                                    &quot;I wanted to build a system where engineers get the same depth of
                                    infrastructure intelligence that only enterprises could afford-without
                                    sacrificing security or shipping speed.&quot;
                                </blockquote>
                                <div className="flex items-center gap-3">
                                    <div className="relative h-14 w-14 rounded-full overflow-hidden border border-white/10 shrink-0">
                                        <Image
                                            src="/images/team/nishant.png"
                                            alt="Nishant Jain, Co-Founder & CTO of CloudFinOps"
                                            fill
                                            className="object-cover"
                                        />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-white">Nishant Jain</div>
                                        <div className="text-xs text-gray-500">Co-Founder &amp; CTO</div>
                                    </div>
                                </div>
                            </div>
                            <div className="absolute top-0 right-0 w-48 h-48 bg-indigo-500/5 rounded-full blur-[100px] pointer-events-none" />
                        </div>
                    </div>
                </div>

                {/* CTA */}
                <div className="text-center">
                    <h2 className="text-2xl md:text-3xl font-semibold text-white mb-4">
                        See What You&apos;re Wasting
                    </h2>
                    <p className="text-gray-400 mb-8 max-w-lg mx-auto">
                        Run a free scan on your cloud account. No credit card, no commitments — just data.
                    </p>
                    <div className="flex flex-col sm:flex-row justify-center gap-4">
                        <Link
                            href="/audit"
                            className="inline-flex items-center justify-center gap-2 bg-primary text-white font-semibold py-3 px-8 rounded-lg hover:bg-primary/90 hover:scale-[1.02] transition-all"
                        >
                            Start Free Scan
                            <ArrowRight className="w-4 h-4" />
                        </Link>

                    </div>
                </div>
            </div>
        </div>
    );
}
