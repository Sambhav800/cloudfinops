"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { FeatureTextBlock, MockupFrame } from "@/components/landing/features/shared";
import { EASE } from "@/components/landing/tokens";

const severityPills = [
    {
        label: "8 critical",
        className: "border-rose-500/20 bg-rose-500/10 text-rose-400",
    },
    {
        label: "14 high",
        className: "border-amber-500/20 bg-amber-500/10 text-amber-400",
    },
    {
        label: "32 medium",
        className: "border-white/[0.08] bg-white/[0.04] text-zinc-400",
    },
];

const rows = [
    {
        rule: "Untagged resource",
        resource: "i-0a3b21ef4cc",
        severity: "critical",
        severityClassName: "border-rose-500/20 bg-rose-500/10 text-rose-400",
        reasoning: "Missing required tag: cost-center",
    },
    {
        rule: "Budget exceeded",
        resource: "prod/billing-svc",
        severity: "critical",
        severityClassName: "border-rose-500/20 bg-rose-500/10 text-rose-400",
        reasoning: "Monthly budget exceeded by 34%",
    },
    {
        rule: "Public S3 bucket",
        resource: "legacy-reports-2019",
        severity: "high",
        severityClassName: "border-amber-500/20 bg-amber-500/10 text-amber-400",
        reasoning: "Bucket ACL allows public read",
    },
    {
        rule: "Oversized instance",
        resource: "vm-worker-eu-1",
        severity: "medium",
        severityClassName: "border-white/[0.08] bg-white/[0.04] text-zinc-300",
        reasoning: "CPU avg 4.2% over 30 days",
    },
    {
        rule: "Unencrypted volume",
        resource: "vol-88f2a7bd",
        severity: "high",
        severityClassName: "border-amber-500/20 bg-amber-500/10 text-amber-400",
        reasoning: "EBS volume lacks KMS encryption",
    },
];

export function FeatureGovernance() {
    const [highlightedRow, setHighlightedRow] = useState(0);

    useEffect(() => {
        const interval = window.setInterval(() => {
            setHighlightedRow(Math.floor(Math.random() * rows.length));
        }, 4000);

        return () => {
            window.clearInterval(interval);
        };
    }, []);

    return (
        <section className="px-6 py-32">
            <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-16 lg:grid-cols-12">
                <div className="lg:col-span-5">
                    <FeatureTextBlock
                        eyebrow="GOVERNANCE & COMPLIANCE"
                        title="Policy as code,"
                        titleMuted="that explains itself."
                        description="Enforce tagging, budget thresholds, and resource policies across every cloud. Every violation includes the rule, the reasoning, and the remediation — auditable and exportable."
                        items={[
                            "CIS, SOC 2, PCI-DSS framework mapping out of the box",
                            "Natural-language rule explanations for every violation",
                            "Smart office-hours enforcement for non-prod environments",
                            "Signed audit logs with cryptographic chain of custody",
                        ]}
                    />
                </div>

                <div className="lg:col-span-7">
                    <MockupFrame label="cloudfinops.solutions/governance">
                        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] p-4">
                            <p className="text-[13px] font-medium text-white">Active violations</p>
                            <div className="flex flex-wrap items-center gap-2">
                                {severityPills.map((pill, index) => (
                                    <motion.span
                                        key={pill.label}
                                        initial={{ opacity: 0, y: 8 }}
                                        whileInView={{ opacity: 1, y: 0 }}
                                        viewport={{ once: true, margin: "-100px" }}
                                        transition={{ duration: 0.4, delay: index * 0.08, ease: EASE }}
                                        className={`rounded-md border px-2 py-0.5 text-[11px] ${pill.className}`}
                                    >
                                        {pill.label}
                                    </motion.span>
                                ))}
                            </div>
                        </div>

                        <div className="overflow-hidden">
                            <table className="w-full">
                                <thead className="bg-white/[0.02]">
                                    <tr className="border-b border-white/[0.06]">
                                        {["Rule", "Resource", "Severity", "Reasoning"].map((heading) => (
                                            <th
                                                key={heading}
                                                className="px-4 py-2 text-left text-[10px] font-medium uppercase tracking-wider text-zinc-500"
                                            >
                                                {heading}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows.map((row, index) => (
                                        <motion.tr
                                            key={`${row.rule}-${row.resource}`}
                                            initial={{ opacity: 0, x: -8 }}
                                            whileInView={{ opacity: 1, x: 0 }}
                                            viewport={{ once: true, margin: "-100px" }}
                                            transition={{ duration: 0.45, delay: index * 0.08, ease: EASE }}
                                            animate={{
                                                backgroundColor:
                                                    highlightedRow === index
                                                        ? "rgba(99,102,241,0.05)"
                                                        : "rgba(0,0,0,0)",
                                            }}
                                            className="border-b border-white/[0.04] transition-colors hover:bg-white/[0.02]"
                                        >
                                            <td className="px-4 py-3 text-[12px] text-white">
                                                <span className="rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-1">
                                                    {row.rule}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 font-mono text-[12px] text-zinc-400">{row.resource}</td>
                                            <td className="px-4 py-3">
                                                <span className={`rounded-md border px-2 py-1 text-[11px] ${row.severityClassName}`}>
                                                    {row.severity}
                                                </span>
                                            </td>
                                            <td className="max-w-xs truncate px-4 py-3 text-[11px] italic text-zinc-500">{row.reasoning}</td>
                                        </motion.tr>
                                    ))}
                                </tbody>
                            </table>

                            <div className="flex items-center justify-between border-t border-white/[0.06] p-3">
                                <p className="text-[11px] text-zinc-500">Showing 5 of 54 violations</p>
                                <span className="text-[12px] text-indigo-400">Export audit log →</span>
                            </div>
                        </div>
                    </MockupFrame>
                </div>
            </div>
        </section>
    );
}
