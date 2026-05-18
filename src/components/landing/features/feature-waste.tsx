"use client";

import { motion } from "framer-motion";
import { FeatureTextBlock, MockupFrame } from "@/components/landing/features/shared";
import { EASE } from "@/components/landing/tokens";

const savingsBars = [
    { label: "Idle compute", amount: "₹6.16L", width: "100%" },
    { label: "Orphaned storage", amount: "₹4.47L", width: "72%" },
    { label: "Oversized VMs", amount: "₹2.59L", width: "58%" },
    { label: "Unused LBs", amount: "₹1.28L", width: "34%" },
    { label: "Old snapshots", amount: "₹64.7K", width: "21%" },
];

const actionItems = [
    { color: "bg-indigo-400", label: "Terminate 8 idle EC2 instances" },
    { color: "bg-emerald-400", label: "Downsize gke-prod-west nodepool" },
    { color: "bg-rose-400", label: "Delete 34 orphaned EBS volumes" },
    { color: "bg-amber-400", label: "Snapshot and archive 2TB bucket" },
];

export function FeatureWaste() {
    return (
        <section className="px-6 py-32">
            <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-16 lg:grid-cols-12">
                <div className="lg:order-2 lg:col-span-5">
                    <FeatureTextBlock
                        eyebrow="WASTE ELIMINATION"
                        title="Stop paying for infra"
                        titleMuted="you never use."
                        description="CloudFinOps continuously scans for idle, oversized, and forgotten resources. Every finding comes with an impact score, an effort rating, and a one-click remediation path."
                        items={[
                            "Zombie asset detection across 40+ resource types",
                            "Rightsizing recommendations backed by 30-day utilization",
                            "Orphaned storage, unattached volumes, idle load balancers",
                            "Holt-Winters forecasting prevents budget overruns",
                        ]}
                        className="lg:pl-8"
                    />
                </div>

                <div className="lg:order-1 lg:col-span-7">
                    <MockupFrame label="cloudfinops.solutions/savings">
                        <div className="flex items-center justify-between border-b border-white/[0.06] p-4">
                            <p className="text-[13px] font-medium text-white">Savings opportunities</p>
                            <div className="flex items-center gap-2">
                                <span className="rounded-md bg-white/[0.08] px-2 py-1 text-[11px] text-white">Active (12)</span>
                                <span className="px-2 py-1 text-[11px] text-zinc-500">Dismissed</span>
                            </div>
                        </div>

                        <div className="grid grid-cols-12 gap-4 p-4">
                            <div className="col-span-12 rounded-lg border border-white/[0.06] bg-white/[0.02] p-4 lg:col-span-7">
                                <p className="text-[12px] text-zinc-400">Potential monthly savings</p>
                                <p className="mt-1 text-[24px] font-medium tabular-nums text-white">₹15.1L</p>
                                <p className="mt-0.5 text-[11px] text-emerald-400">+₹3.49L vs last scan</p>

                                <div className="mt-4 space-y-3">
                                    {savingsBars.map((bar, index) => (
                                        <div key={bar.label} className="grid grid-cols-[88px_minmax(0,1fr)_56px] items-center gap-3">
                                            <span className="text-[11px] text-zinc-400">{bar.label}</span>
                                            <div className="h-3 overflow-hidden rounded-r-sm rounded-l-sm bg-white/[0.04]">
                                                <motion.div
                                                    initial={{ width: 0 }}
                                                    whileInView={{ width: bar.width }}
                                                    viewport={{ once: true, margin: "-100px" }}
                                                    transition={{ duration: 0.7, delay: index * 0.1, ease: EASE }}
                                                    className="h-full rounded-r-sm bg-emerald-500"
                                                />
                                            </div>
                                            <span className="text-right text-[11px] tabular-nums text-zinc-300">{bar.amount}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="col-span-12 rounded-lg border border-white/[0.06] bg-white/[0.02] p-4 lg:col-span-5">
                                <p className="text-[12px] text-zinc-400">Ready to apply</p>
                                <div className="mt-2 flex items-end gap-2">
                                    <p className="text-[24px] font-medium text-white">12</p>
                                    <p className="pb-1 text-[11px] text-zinc-500">actions queued</p>
                                </div>

                                <div className="my-3 border-t border-white/[0.04]" />

                                <div className="space-y-1">
                                    {actionItems.map((item, index) => (
                                        <motion.div
                                            key={item.label}
                                            initial={{ opacity: 0, y: 8 }}
                                            whileInView={{ opacity: 1, y: 0 }}
                                            viewport={{ once: true, margin: "-100px" }}
                                            transition={{ duration: 0.45, delay: 0.55 + index * 0.08, ease: EASE }}
                                            className="flex items-center gap-2 py-2"
                                        >
                                            <span className={`h-4 w-4 rounded-sm ${item.color}`} />
                                            <span className="min-w-0 flex-1 truncate text-[12px] text-zinc-300">{item.label}</span>
                                            <span className="text-[12px] text-zinc-600">→</span>
                                        </motion.div>
                                    ))}
                                </div>

                                <motion.button
                                    type="button"
                                    initial={{ opacity: 0, scale: 0.95 }}
                                    whileInView={{ opacity: 1, scale: 1 }}
                                    viewport={{ once: true, margin: "-100px" }}
                                    transition={{ duration: 0.4, delay: 0.95, ease: EASE }}
                                    className="mt-3 w-full rounded-md bg-white py-2 text-center text-[12px] font-medium text-black"
                                >
                                    Apply all →
                                </motion.button>
                            </div>
                        </div>
                    </MockupFrame>
                </div>
            </div>
        </section>
    );
}
