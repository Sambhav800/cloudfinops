"use client";

import { motion } from "framer-motion";
import { ShieldCheck, Zap, Leaf, ScanSearch, Terminal, Lock } from "lucide-react";

const benefits = [
    {
        icon: Lock,
        title: "Zero-Trust, Read-Only Access",
        description: "We never write to your infrastructure. Read-only IAM roles with AES-256-GCM encrypted credentials ensure your environment stays untouched."
    },
    {
        icon: Zap,
        title: "60-Second Time to Value",
        description: "Connect your cloud account, get your first scan results, and see exactly where money is being wasted — all in under a minute. No onboarding calls."
    },
    {
        icon: ScanSearch,
        title: "17-Region Deep Scan",
        description: "We don't just check your primary region. Our scanner sweeps all 17+ AWS commercial regions to find shadow IT and zombie resources hiding in regions you forgot existed."
    },
    {
        icon: Terminal,
        title: "AI Fix Scripts, Not Just Reports",
        description: "Other tools give you a PDF. We give you the exact AWS CLI command to fix each issue — copy, paste, execute. Actionable from the first scan."
    },
    {
        icon: Leaf,
        title: "Carbon-Aware Optimization",
        description: "Every scan calculates the CO₂ footprint of your cloud waste. Optimize for cost and sustainability simultaneously — a metric ESG teams actually care about."
    },
    {
        icon: ShieldCheck,
        title: "Tenant-Isolated by Design",
        description: "Tenant-Level Security in MongoDB ensures your data is cryptographically isolated from every other customer. No shared dashboards, no data leakage — ever."
    }
];

export function BenefitsGrid() {
    return (
        <section className="py-24 bg-black relative overflow-hidden">
            <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary/5 rounded-full blur-[150px] pointer-events-none" />

            <div className="mx-auto max-w-7xl px-6 lg:px-8 relative z-10">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="text-center mb-16"
                >
                    <span className="pill-badge mb-4">Why Us</span>
                    <h2 className="text-4xl md:text-5xl font-semibold text-white tracking-tight mt-4">
                        What Makes CloudFinOps{" "}
                        <span className="text-gradient">Different</span>
                    </h2>
                    <p className="mt-4 text-lg text-gray-400 max-w-2xl mx-auto">
                        The difference: we give you CLI commands, not PDFs. Here&apos;s what sets us apart.
                    </p>
                </motion.div>

                {/* Grid */}
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {benefits.map((benefit, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 40 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.5, delay: index * 0.1 }}
                            className="group glass-card p-6 hover:border-primary/30 transition-all duration-300"
                        >
                            <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
                                <benefit.icon className="w-6 h-6 text-primary" />
                            </div>

                            <h3 className="text-lg font-semibold text-white mb-2">
                                {benefit.title}
                            </h3>

                            <p className="text-sm text-gray-400 leading-relaxed">
                                {benefit.description}
                            </p>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
