"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, ShieldCheck, Clock, CreditCard } from "lucide-react";

export function CTABanner() {
    return (
        <section className="py-24 bg-black relative overflow-hidden">
            {/* Large purple glow behind */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-primary/20 rounded-full blur-[150px] pointer-events-none" />
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[300px] bg-secondary/15 rounded-full blur-[100px] pointer-events-none" />

            <div className="mx-auto max-w-4xl px-6 lg:px-8 relative z-10">
                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="text-center"
                >
                    <h2 className="text-4xl md:text-5xl lg:text-6xl font-semibold text-white tracking-tight leading-[1.1]">
                        Stop Guessing.{" "}
                        <span className="text-gradient">Start Scanning.</span>
                    </h2>

                    <p className="mt-6 text-lg text-gray-400 max-w-xl mx-auto">
                        Connect your cloud account, run your first scan, and see exactly what you&apos;re wasting — with the CLI commands to fix it. No setup calls, no onboarding decks.
                    </p>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.2 }}
                        className="mt-10"
                    >
                        <Link
                            href="/audit"
                            className="group inline-flex items-center gap-2 rounded-md bg-primary px-8 py-4 text-lg font-semibold text-white transition-all hover:bg-primary/90 hover:scale-105 shadow-lg shadow-primary/25"
                        >
                            Run Your Free Scan
                            <ArrowRight className="w-5 h-5 transition-transform group-hover:translate-x-1" />
                        </Link>
                    </motion.div>

                    {/* Trust Signals */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        whileInView={{ opacity: 1 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5, delay: 0.4 }}
                        className="mt-8 flex items-center justify-center gap-6 text-sm text-gray-500"
                    >
                        <span className="flex items-center gap-1.5">
                            <CreditCard className="w-4 h-4" />
                            No credit card
                        </span>
                        <span className="flex items-center gap-1.5">
                            <ShieldCheck className="w-4 h-4" />
                            Read-only access
                        </span>
                        <span className="flex items-center gap-1.5">
                            <Clock className="w-4 h-4" />
                            Results in minutes
                        </span>
                    </motion.div>
                </motion.div>
            </div>
        </section>
    );
}
