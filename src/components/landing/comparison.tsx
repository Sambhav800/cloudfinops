"use client";

import { motion } from "framer-motion";
import { Check, X } from "lucide-react";
import { SectionHeading } from "@/components/landing/section-heading";
import { EASE } from "@/components/landing/tokens";

type ComparisonRow = {
    capability: string;
    cloudFinOps: string;
    legacy: string;
};

const ROWS: ComparisonRow[] = [
    {
        capability: "Bill PDF analysis",
        cloudFinOps: "AI-parsed line items in 30 seconds",
        legacy: "Manual CSV export only",
    },
    {
        capability: "GPU intelligence",
        cloudFinOps: "Ghost GPU detection, MIG advisor",
        legacy: "No GPU-specific tooling",
    },
    {
        capability: "Forecasting",
        cloudFinOps: "Holt-Winters with 92% accuracy",
        legacy: "Flat linear projection",
    },
    {
        capability: "Governance explainability",
        cloudFinOps: "Every violation explains itself",
        legacy: "Rule IDs with no context",
    },
    {
        capability: "Multi-cloud arbitrage",
        cloudFinOps: "Cross-cloud cost comparison built-in",
        legacy: "Single-cloud dashboards only",
    },
    {
        capability: "AI agent access",
        cloudFinOps: "MCP-enabled conversational layer",
        legacy: "Static dashboards",
    },
    {
        capability: "Deployment time",
        cloudFinOps: "5 minutes, read-only IAM",
        legacy: "Weeks of agent rollout",
    },
];

export function Comparison() {
    return (
        <section className="px-6 py-32">
            <div className="mx-auto max-w-7xl">
                <SectionHeading
                    eyebrow="BUILT DIFFERENT"
                    align="center"
                    title={
                        <>
                            Why engineers pick us
                            <span className="text-zinc-500"> over legacy cost tools.</span>
                        </>
                    }
                    description="Most cost tools stop at dashboards. CloudFinOps ships the intelligence layer that actually moves money."
                />

                <div className="mt-16 overflow-hidden rounded-2xl border border-white/[0.08] bg-gradient-to-b from-white/[0.02] to-transparent">
                    <div className="overflow-x-auto">
                        <table className="w-full min-w-[820px]">
                            <thead>
                                <tr className="border-b border-white/[0.06]">
                                    <th className="w-2/5 px-6 py-5 text-left text-[12px] font-medium uppercase tracking-wider text-zinc-500">
                                        Capability
                                    </th>
                                    <th className="px-6 py-5 text-left text-[12px] font-medium uppercase tracking-wider text-white">
                                        <span className="inline-flex items-center gap-2">
                                            <span className="h-2 w-2 rounded-full bg-indigo-400" />
                                            CloudFinOps
                                        </span>
                                    </th>
                                    <th className="px-6 py-5 text-left text-[12px] font-medium uppercase tracking-wider text-zinc-500">
                                        Legacy tools
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {ROWS.map((row, index) => (
                                    <motion.tr
                                        key={row.capability}
                                        initial={{ opacity: 0, y: 12 }}
                                        whileInView={{ opacity: 1, y: 0 }}
                                        viewport={{ once: true, margin: "-100px" }}
                                        transition={{
                                            duration: 0.55,
                                            delay: index * 0.08,
                                            ease: EASE,
                                        }}
                                        className="border-b border-white/[0.04] last:border-b-0"
                                    >
                                        <td className="px-6 py-5 text-[14px] font-medium text-zinc-300">
                                            {row.capability}
                                        </td>
                                        <td className="px-6 py-5 text-[14px] text-white">
                                            <div className="flex items-start gap-3">
                                                <motion.span
                                                    initial={{ scale: 0.6, opacity: 0 }}
                                                    whileInView={{ scale: 1, opacity: 1 }}
                                                    viewport={{ once: true, margin: "-100px" }}
                                                    transition={{
                                                        type: "spring",
                                                        stiffness: 260,
                                                        damping: 18,
                                                        delay: index * 0.08 + 0.12,
                                                    }}
                                                    className="mt-0.5 text-emerald-400"
                                                >
                                                    <Check className="h-4 w-4" />
                                                </motion.span>
                                                <span>{row.cloudFinOps}</span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-5 text-[14px] text-zinc-500">
                                            <span className="inline-flex items-start gap-3">
                                                <X className="mt-0.5 h-4 w-4 text-zinc-700" />
                                                <span>{row.legacy}</span>
                                            </span>
                                        </td>
                                    </motion.tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>
    );
}
