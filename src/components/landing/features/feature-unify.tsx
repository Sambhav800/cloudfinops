"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { FeatureTextBlock, MockupFrame } from "@/components/landing/features/shared";
import { EASE, COLORS } from "@/components/landing/tokens";

const providers = [
    {
        badge: "AWS",
        badgeClassName: "bg-[#FF9900]",
        name: "Amazon Web Services",
        meta: "4 accounts · 127 resources",
        width: "68%",
        cost: "₹48.5L",
        color: COLORS.aws,
    },
    {
        badge: "Az",
        badgeClassName: "bg-[#0078D4]",
        name: "Microsoft Azure",
        meta: "3 subscriptions · 89 resources",
        width: "42%",
        cost: "₹23.4L",
        color: COLORS.azure,
    },
    {
        badge: "GCP",
        badgeClassName: "bg-[#4285F4]",
        name: "Google Cloud Platform",
        meta: "2 projects · 111 resources",
        width: "55%",
        cost: "₹31.3L",
        color: COLORS.gcp,
    },
];

export function FeatureUnify() {
    return (
        <section id="features" className="px-6 py-32">
            <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-16 lg:grid-cols-12">
                <div className="lg:col-span-5">
                    <FeatureTextBlock
                        eyebrow="UNIFIED VISIBILITY"
                        title="Every cloud, every rupee,"
                        titleMuted="in a single pane."
                        description="Connect AWS, Azure, and GCP in under five minutes. See unified cost breakdowns, tag coverage, and resource inventory across providers — without switching tabs."
                        items={[
                            "Agent-less read-only IAM — no infrastructure to deploy",
                            "Hourly sync across all three hyperscalers",
                            "Normalized cost taxonomy and unit metrics",
                            "Per-tag, per-team, per-environment rollups",
                        ]}
                    />
                </div>

                <div className="lg:col-span-7">
                    <MockupFrame label="cloudfinops.solutions/resources">
                        <div className="border-b border-white/[0.06] p-4">
                            <div className="flex items-center justify-between gap-4">
                                <p className="text-[13px] font-medium text-white">Multi-cloud overview</p>
                                <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.06] bg-white/[0.02] px-3 py-1">
                                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                                    <span className="text-[11px] text-zinc-500">Synced 2 min ago</span>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-4 p-5">
                            {providers.map((provider, index) => (
                                <motion.div
                                    key={provider.name}
                                    initial={{ opacity: 0, y: 16 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    viewport={{ once: true, margin: "-100px" }}
                                    transition={{ duration: 0.55, delay: index * 0.15, ease: EASE }}
                                    className="flex flex-wrap items-center gap-4 rounded-lg border border-white/[0.06] bg-white/[0.02] p-4"
                                >
                                    <div className={`flex h-10 w-10 items-center justify-center rounded-lg text-[14px] font-semibold text-black ${provider.badgeClassName}`}>
                                        {provider.badge}
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <p className="text-[14px] font-medium text-white">{provider.name}</p>
                                        <p className="text-[11px] text-zinc-500">{provider.meta}</p>
                                    </div>
                                    <div className="w-full max-w-48 flex-1">
                                        <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.04]">
                                            <motion.div
                                                initial={{ width: 0 }}
                                                whileInView={{ width: provider.width }}
                                                viewport={{ once: true, margin: "-100px" }}
                                                transition={{ duration: 0.8, delay: 0.4 + index * 0.15, ease: EASE }}
                                                className="h-full rounded-full"
                                                style={{ backgroundColor: provider.color }}
                                            />
                                        </div>
                                    </div>
                                    <div className="text-[14px] font-medium tabular-nums text-white">{provider.cost}</div>
                                </motion.div>
                            ))}

                            <motion.div
                                initial={{ opacity: 0, y: 16 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true, margin: "-100px" }}
                                transition={{ duration: 0.55, delay: 1.0, ease: EASE }}
                                className="mt-2 flex flex-wrap items-center gap-3 rounded-lg border border-indigo-500/20 bg-indigo-500/[0.03] p-4"
                            >
                                <Sparkles className="h-4 w-4 text-indigo-400" />
                                <p className="flex-1 text-[13px] text-zinc-300">
                                    Cost anomaly detected on GCP — BigQuery slot usage up 34%
                                </p>
                                <span className="text-[12px] text-indigo-400">Investigate →</span>
                            </motion.div>
                        </div>
                    </MockupFrame>
                </div>
            </div>
        </section>
    );
}
