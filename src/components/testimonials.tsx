"use client";

import { motion } from "framer-motion";
import { TrendingDown, AlertTriangle, Eye, IndianRupee } from "lucide-react";

const stats = [
    {
        icon: IndianRupee,
        value: "27%",
        label: "of cloud spend is wasted",
        source: "Flexera 2025 State of the Cloud Report",
        description: "Over a quarter of every rupee companies spend on cloud is thrown away on idle, oversized, or forgotten resources — every single month."
    },
    {
        icon: AlertTriangle,
        value: "₹3.69T",
        label: "wasted on cloud globally in 2025",
        source: "Harness FinOps in Focus 2025",
        description: "That's roughly ₹3.69 trillion burned annually on resources that deliver zero business value — equivalent to the GDP of a small country."
    },
    {
        icon: Eye,
        value: "66%",
        label: "of orgs waste on idle resources",
        source: "Flexera 2025 Cloud Optimization Survey",
        description: "Two-thirds of organizations report significant waste from idle and underused resources they don't even know exist."
    },
    {
        icon: TrendingDown,
        value: "21%",
        label: "of cloud budgets go untracked",
        source: "Harness FinOps in Focus 2025",
        description: "Most developers have zero visibility into real-time cost data — leading to purchasing decisions based on guesswork, not data."
    }
];

export function Testimonials() {
    return (
        <section className="py-24 bg-black relative overflow-hidden">
            <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-secondary/5 rounded-full blur-[120px] pointer-events-none" />

            <div className="mx-auto max-w-7xl px-6 lg:px-8 relative z-10">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="text-center mb-16"
                >
                    <span className="pill-badge mb-4">The Problem</span>
                    <h2 className="text-4xl md:text-5xl font-semibold text-white tracking-tight mt-4">
                        The Cloud Waste{" "}
                        <span className="text-gradient">Epidemic</span>
                    </h2>
                    <p className="mt-4 text-lg text-gray-400 max-w-2xl mx-auto">
                        These aren&apos;t our numbers. These are industry-reported facts that explain why we built CloudFinOps.
                    </p>
                </motion.div>

                {/* Stats Grid */}
                <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {stats.map((stat, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 40 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.5, delay: index * 0.1 }}
                            className="glass-card p-6 text-center group hover:border-primary/30 transition-all duration-300"
                        >
                            {/* Icon */}
                            <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-5 mx-auto group-hover:bg-primary/20 transition-colors">
                                <stat.icon className="w-6 h-6 text-primary" />
                            </div>

                            {/* Value */}
                            <div className="text-4xl font-bold text-white mb-2">
                                {stat.value}
                            </div>

                            {/* Label */}
                            <div className="text-sm font-medium text-gray-300 mb-4">
                                {stat.label}
                            </div>

                            {/* Description */}
                            <p className="text-xs text-gray-500 leading-relaxed mb-4">
                                {stat.description}
                            </p>

                            {/* Source */}
                            <div className="text-[10px] text-gray-600 uppercase tracking-wider border-t border-white/5 pt-3">
                                Source: {stat.source}
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
