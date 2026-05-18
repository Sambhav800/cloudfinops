"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Check } from "lucide-react";
import { EASE } from "@/components/landing/tokens";

export function FinalCTA() {
    return (
        <section className="relative overflow-hidden px-6 py-40">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_40%_at_50%_50%,rgba(99,102,241,0.18),transparent_70%)]" />
            <div
                className="pointer-events-none absolute inset-0 opacity-50 [mask-image:radial-gradient(ellipse_at_center,black_35%,transparent_78%)]"
                style={{
                    backgroundImage:
                        "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.04) 1px, transparent 0)",
                    backgroundSize: "32px 32px",
                }}
            />
            <div className="pointer-events-none absolute inset-x-0 top-0 z-0 overflow-hidden">
                <div className="h-px w-64 bg-gradient-to-r from-transparent via-indigo-400 to-transparent animate-[beam-sweep_6s_linear_infinite]" />
            </div>

            <motion.div
                initial={{ opacity: 0, y: 32 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.8, ease: EASE }}
                className="relative z-10 mx-auto max-w-4xl text-center"
            >
                <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.7, delay: 0.1, ease: EASE }}
                    className="mb-8 inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/[0.05] px-4 py-1.5 text-[12px] text-indigo-300"
                >
                    <span className="relative flex h-2.5 w-2.5 items-center justify-center">
                        <span className="absolute inset-0 rounded-full bg-indigo-400 opacity-60 animate-ping" />
                        <span className="relative h-2.5 w-2.5 rounded-full bg-indigo-400" />
                    </span>
                    Ready when you are
                </motion.div>

                <motion.h2
                    initial={{ opacity: 0, y: 32 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.8, delay: 0.18, ease: EASE }}
                    className="text-[56px] font-medium leading-[1.05] tracking-[-0.04em] text-white md:text-[72px]"
                >
                    Start understanding
                    <br />
                    <span className="text-zinc-500">your cloud bill today.</span>
                </motion.h2>

                <motion.p
                    initial={{ opacity: 0, y: 24 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.8, delay: 0.32, ease: EASE }}
                    className="mx-auto mt-6 max-w-xl text-[17px] leading-relaxed text-zinc-400"
                >
                    Free to start. Connect your first cloud account in under five minutes.
                    No credit card, no agents, no sales call required.
                </motion.p>

                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.8, delay: 0.46, ease: EASE }}
                    className="mt-10 flex flex-col justify-center gap-3 sm:flex-row"
                >
                    <Link
                        href="/login"
                        aria-label="Start free with CloudFinOps"
                        className="group inline-flex items-center justify-center gap-2 rounded-lg bg-white px-6 py-3 text-[15px] font-medium text-black transition hover:bg-zinc-200"
                    >
                        Start free
                        <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                    </Link>
                    <Link
                        href="/how-it-works"
                        aria-label="See how CloudFinOps works"
                        className="inline-flex items-center justify-center rounded-lg border border-white/[0.1] bg-white/[0.02] px-6 py-3 text-[15px] font-medium text-white transition hover:border-white/[0.2] hover:bg-white/[0.06]"
                    >
                        See how it works
                    </Link>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.8, delay: 0.58, ease: EASE }}
                    className="mt-10 flex flex-wrap justify-center gap-x-8 gap-y-3"
                >
                    {[
                        "Free tier, forever",
                        "Read-only IAM, always",
                        "Deploy in 5 minutes",
                    ].map((item) => (
                        <div key={item} className="flex items-center gap-2">
                            <Check className="h-3.5 w-3.5 text-emerald-400" />
                            <span className="text-[13px] text-zinc-500">{item}</span>
                        </div>
                    ))}
                </motion.div>
            </motion.div>
        </section>
    );
}
