"use client";

import { motion } from "framer-motion";
import { CheckCircle, Code, Zap } from "lucide-react";

const steps = [
    {
        step: 1,
        title: "Deep-Dive Regional Scanning",
        description: "We initiate a secure, encrypted handshake with your AWS environment, scanning all 17+ commercial regions—detecting shadow IT, zombie resources, and unattached volumes that standard tools miss.",
        icon: CheckCircle,
        visual: (
            <div className="space-y-3">
                <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded border border-primary bg-primary/20 flex items-center justify-center text-[10px] text-primary">✓</div>
                    <span className="text-sm text-gray-300 font-mono">IAM Encryption Handshake</span>
                </div>
                <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded border border-primary bg-primary/20 flex items-center justify-center text-[10px] text-primary">✓</div>
                    <span className="text-sm text-gray-300 font-mono">Global Region Discovery</span>
                </div>
                <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded border border-primary bg-primary/20 flex items-center justify-center text-[10px] text-primary">✓</div>
                    <span className="text-sm text-gray-300 font-mono">Resource Inventory</span>
                </div>
                <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded border border-red-500/50 bg-red-500/10 flex items-center justify-center text-[10px] text-red-500">!</div>
                    <span className="text-sm text-red-400 font-mono">Shadow IT Detected</span>
                </div>
            </div>
        )
    },
    {
        step: 2,
        title: "Algorithmic Cost Intelligence",
        description: "Our engine doesn’t just see costs; it understands usage. We analyze EC2 utilization, EBS attachments, and traffic patterns to calculate precise waste, potential savings, and your carbon footprint.",
        icon: Code,
        visual: (
            <div className="font-mono text-xs space-y-1">
                <div className="text-gray-500 border-b border-white/5 pb-1 mb-1">─── Scan Results ─────────────</div>
                <div className="flex justify-between"><span className="text-gray-400">Resources Scanned</span><span className="text-white">247</span></div>
                <div className="flex justify-between"><span className="text-gray-400">Zombie VMs Found</span><span className="text-red-400">3</span></div>
                <div className="flex justify-between"><span className="text-gray-400">Orphaned Disks</span><span className="text-orange-400">5</span></div>
                <div className="flex justify-between"><span className="text-gray-400">Monthly Waste</span><span className="text-red-400">₹1.94L/mo</span></div>
                <div className="flex justify-between"><span className="text-gray-400">Carbon Impact</span><span className="text-green-400">1.2t CO₂</span></div>
                <div className="text-gray-500 border-t border-white/5 pt-1 mt-1">─── Estimated Savings ────────</div>
                <div className="flex justify-between"><span className="text-gray-400">Annual</span><span className="text-primary font-semibold">₹23.3L</span></div>
            </div>
        )
    },
    {
        step: 3,
        title: "One-Click Financial Governance",
        description: "Turn insights into action. We generate a compliant, board-ready financial snapshot and provide one-click remediation workflows to reclaim budget instantly without disrupting engineering flow.",
        icon: Zap,
        visual: (
            <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-white/5 pb-2">
                    <span className="text-xs text-gray-400 font-mono">Policy Check</span>
                    <span className="text-xs text-green-400 font-mono">PASSED</span>
                </div>
                <div className="flex items-center justify-between border-b border-white/5 pb-2">
                    <span className="text-xs text-gray-400 font-mono">Cost Projection</span>
                    <span className="text-xs text-primary font-mono">-35% SPEND</span>
                </div>
                <div className="flex items-center gap-4 mt-3">
                    <div className="h-8 px-3 rounded bg-primary/20 border border-primary/30 flex items-center justify-center">
                        <span className="text-primary text-xs font-medium">REMEDIATE</span>
                    </div>
                    <div className="flex-1 h-px bg-white/10" />
                    <div className="w-8 h-8 rounded-full bg-green-500/20 border border-green-500/30 flex items-center justify-center">
                        <span className="text-green-500 text-xs">✓</span>
                    </div>
                </div>
            </div>
        )
    }
];

export function ProcessSection() {
    return (
        <section className="py-24 bg-black relative overflow-hidden">
            {/* Background glow */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-primary/5 rounded-full blur-[150px] pointer-events-none" />

            <div className="mx-auto max-w-7xl px-6 lg:px-8 relative z-10">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="text-center mb-16"
                >
                    <h2 className="text-4xl md:text-5xl font-semibold text-white tracking-tight">
                        Bank-Grade Security Meets{" "}
                        <span className="text-gradient">Deep-Tech Analysis</span>
                    </h2>
                    <p className="mt-4 text-lg text-gray-400 max-w-2xl mx-auto">
                        We don't just skim the surface. Our engine performs a deep-dive architectural scan to identify wasted spend, security risks, and optimization opportunities that others miss.
                    </p>
                </motion.div>

                {/* Steps Grid */}
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {steps.map((step, index) => (
                        <motion.div
                            key={step.step}
                            initial={{ opacity: 0, y: 40 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.6, delay: index * 0.15 }}
                            className="glass-card p-6 relative group hover:border-primary/30 transition-colors duration-300"
                        >
                            <div className="absolute top-4 right-4 opacity-50 text-xs font-mono text-gray-600">
                                0{step.step}
                            </div>

                            <div className="mb-4 w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center text-primary group-hover:bg-primary/10 group-hover:scale-110 transition-all duration-300">
                                <step.icon className="w-5 h-5" />
                            </div>

                            <h3 className="text-xl font-semibold text-white mb-3 bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
                                {step.title}
                            </h3>

                            <p className="text-sm text-gray-400 mb-6 leading-relaxed">
                                {step.description}
                            </p>

                            <div className="bg-black/80 border border-white/10 rounded-xl p-4 min-h-[140px] flex flex-col justify-center">
                                {step.visual}
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
