"use client";

import { Activity, Lightbulb, Plug, Zap } from "lucide-react";
import { motion } from "framer-motion";
import { EASE } from "@/components/landing/tokens";

const WORKFLOW_STEPS = [
    {
        icon: Plug,
        title: "Connect your clouds",
        description: "Drop in read-only IAM credentials for AWS, Azure, and GCP. No agents.",
        timestamp: "~ 2 min",
    },
    {
        icon: Activity,
        title: "Sync completes",
        description: "Full inventory and cost data pulled, normalized, and indexed.",
        timestamp: "~ 5 min",
    },
    {
        icon: Lightbulb,
        title: "Review findings",
        description: "Ranked waste, anomalies, and rightsizing recommendations appear.",
        timestamp: "~ 1 min",
    },
    {
        icon: Zap,
        title: "Apply remediation",
        description: "One-click fixes, exported Terraform diffs, or approve-in-chat via agent.",
        timestamp: "ongoing",
    },
];

export function WorkflowSection() {
    return (
        <section className="px-6 py-32">
            <div className="mx-auto max-w-7xl">
                <div className="mx-auto max-w-3xl text-center">
                    <p className="mb-4 text-[11px] font-medium uppercase tracking-[0.2em] text-indigo-400">
                        The workflow
                    </p>
                    <h2 className="text-[40px] font-medium tracking-tight text-white md:text-[48px]">
                        From zero to actionable in
                        <br />
                        <span className="text-zinc-500">under ten minutes.</span>
                    </h2>
                    <p className="mx-auto mt-4 max-w-2xl text-[16px] leading-relaxed text-zinc-400">
                        A real deployment story, not a marketing funnel.
                    </p>
                </div>

                <div className="mt-20 grid grid-cols-1 gap-8 md:grid-cols-4">
                    {WORKFLOW_STEPS.map((step, index) => (
                        <motion.article
                            key={step.title}
                            initial={{ opacity: 0, y: 24 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true, margin: "-100px" }}
                            transition={{ duration: 0.7, delay: index * 0.12, ease: EASE }}
                            className="relative"
                        >
                            {index < WORKFLOW_STEPS.length - 1 ? (
                                <motion.div
                                    initial={{ scaleX: 0, opacity: 0 }}
                                    whileInView={{ scaleX: 1, opacity: 1 }}
                                    viewport={{ once: true, margin: "-100px" }}
                                    transition={{ duration: 0.8, delay: 0.35 + index * 0.12, ease: EASE }}
                                    className="absolute top-4 left-[calc(50%+1rem)] hidden h-0 w-[calc(100%-0.5rem)] origin-left border-t border-dashed border-white/[0.1] md:block"
                                />
                            ) : null}

                            <motion.div
                                initial={{ scale: 0.8 }}
                                whileInView={{ scale: [0.8, 1.05, 1] }}
                                viewport={{ once: true, margin: "-100px" }}
                                transition={{ duration: 0.7, delay: 0.12 + index * 0.1, ease: EASE }}
                                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/[0.1] bg-white/[0.04] text-[13px] font-medium text-zinc-400"
                            >
                                {index + 1}
                            </motion.div>

                            <div className="mt-6 flex h-12 w-12 items-center justify-center rounded-lg border border-indigo-500/20 bg-indigo-500/10 text-indigo-400">
                                <step.icon className="h-6 w-6" />
                            </div>

                            <h3 className="mt-6 text-[16px] font-medium text-white">{step.title}</h3>
                            <p className="mt-2 text-[13px] leading-relaxed text-zinc-400">{step.description}</p>
                            <div className="mt-4 inline-flex rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] text-zinc-500">
                                {step.timestamp}
                            </div>
                        </motion.article>
                    ))}
                </div>
            </div>
        </section>
    );
}
