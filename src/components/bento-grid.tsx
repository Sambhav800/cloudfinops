"use client";

import { motion } from "framer-motion";
import {
    Sparkles,
} from "lucide-react";
import { SpotlightCard } from "@/components/ui/spotlight-card";
import { MiniChart, TerminalMockup } from "@/components/ui/bento-visuals";

export function BentoGrid() {
    return (
        <section className="py-24 sm:py-32 bg-black relative overflow-hidden">

            {/* Background Mesh for Detail */}
            <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-5 pointer-events-none" />

            {/* Subtle Purple Glow */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-primary/10 rounded-full blur-[150px] pointer-events-none" />

            <div className="mx-auto max-w-7xl px-6 lg:px-8 relative z-10">
                <div className="mx-auto max-w-2xl text-center mb-16">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                    >
                        <span className="pill-badge mb-4">Our Services</span>
                        <h2 className="text-3xl sm:text-5xl font-semibold text-white tracking-tight mt-4">
                            AI Solutions That Take Your{" "}
                            <span className="text-gradient">Business to the Next Level</span>
                        </h2>
                        <p className="mt-4 text-gray-400 text-lg max-w-xl mx-auto">
                            We design, develop, and implement automation tools that help you work smarter, not harder
                        </p>
                    </motion.div>
                </div>

                {/* The Grid: 4 columns, dense layout */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 auto-rows-[250px]">

                    {/* 1. Primary Feature: AI Anomaly Detection (2x2) */}
                    <SpotlightCard className="md:col-span-2 md:row-span-2 p-0 overflow-hidden glass-card" spotlightColor="rgba(129, 74, 200, 0.3)">
                        <div className="p-8 h-full flex flex-col justify-between relative z-10">
                            <div>
                                <span className="text-xs font-medium text-primary uppercase tracking-widest">Workflow Automation</span>
                                <h3 className="text-2xl font-semibold text-white mt-2 mb-2">Automate repetitive tasks</h3>
                                <p className="text-base text-gray-400 max-w-sm">
                                    We help you streamline internal operations by automating manual workflows like data entry, reporting, and approval chains.
                                </p>
                            </div>
                            {/* Visual: Live Chart */}
                            <div className="mt-8 border border-white/10 rounded-xl bg-black/50 overflow-hidden relative">
                                <div className="absolute top-2 left-4 text-[10px] text-gray-500 font-mono">LIVE SPEND ANALYSIS</div>
                                <MiniChart />
                            </div>
                        </div>
                        {/* Background Glow */}
                        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/20 blur-[80px] rounded-full pointer-events-none" />
                    </SpotlightCard>

                    {/* 2. AI Assistant (1x2) */}
                    <SpotlightCard className="md:col-span-2 md:row-span-2 p-6 flex flex-col glass-card" spotlightColor="rgba(129, 74, 200, 0.2)">
                        <span className="text-xs font-medium text-primary uppercase tracking-widest">AI Assistant</span>
                        <h3 className="text-2xl font-semibold text-white mt-2 mb-2">Delegate Daily Tasks</h3>
                        <p className="text-sm text-gray-400 mb-6 flex-grow max-w-md">
                            From managing calendars to drafting emails and summarizing meetings, our AI assistants work around the clock to keep your business running smarter and faster.
                        </p>
                        {/* Visual: Chat Interface */}
                        <div className="mt-auto border border-white/10 rounded-xl bg-black/50 p-4">
                            <div className="flex items-center gap-3 mb-3">
                                <div className="w-8 h-8 rounded-full bg-primary/30 flex items-center justify-center">
                                    <Sparkles className="w-4 h-4 text-primary" />
                                </div>
                                <div>
                                    <p className="text-xs text-gray-500">What can I help with?</p>
                                </div>
                            </div>
                            <div className="flex gap-2">
                                <span className="text-xs bg-white/5 border border-white/10 rounded-full px-3 py-1 text-gray-400">Summaries</span>
                                <span className="text-xs bg-white/5 border border-white/10 rounded-full px-3 py-1 text-gray-400">Scheduling</span>
                                <span className="text-xs bg-white/5 border border-white/10 rounded-full px-3 py-1 text-gray-400">Many more</span>
                            </div>
                        </div>
                    </SpotlightCard>

                    {/* 3. Custom Projects (2x1) */}
                    <SpotlightCard className="md:col-span-2 md:row-span-1 p-6 flex flex-row items-center justify-between glass-card" spotlightColor="rgba(129, 74, 200, 0.2)">
                        <div className="max-w-[280px]">
                            <span className="text-xs font-medium text-primary uppercase tracking-widest">Custom Projects</span>
                            <h3 className="text-lg font-semibold text-white mt-2 mb-1">Build Smarter Systems</h3>
                            <p className="text-xs text-gray-400">
                                Whether you&apos;re starting from scratch or enhancing an existing system, we offer strategic consulting and develop custom AI projects aligned with your unique goals.
                            </p>
                            <div className="flex gap-2 mt-3">
                                <span className="text-xs bg-white/5 border border-white/10 rounded-full px-3 py-1 text-gray-400">Strategy</span>
                                <span className="text-xs bg-white/5 border border-white/10 rounded-full px-3 py-1 text-gray-400">Custom AI</span>
                                <span className="text-xs bg-white/5 border border-white/10 rounded-full px-3 py-1 text-gray-400">Consulting</span>
                            </div>
                        </div>
                        <div className="flex-grow h-24 ml-6 border border-white/5 rounded-lg overflow-hidden relative opacity-80">
                            <div className="absolute inset-x-0 bottom-0 top-1/2 bg-primary/10 border-t border-primary/30" />
                            <div className="absolute left-1/4 bottom-0 w-8 h-[60%] bg-primary/40 rounded-t-sm" />
                            <div className="absolute left-2/4 bottom-0 w-8 h-[80%] bg-secondary/40 rounded-t-sm" />
                            <div className="absolute left-3/4 bottom-0 w-8 h-[40%] bg-primary/30 rounded-t-sm" />
                        </div>
                    </SpotlightCard>

                    {/* 4. Sales & Marketing (2x1) */}
                    <SpotlightCard className="md:col-span-2 md:row-span-1 p-0 overflow-hidden glass-card" spotlightColor="rgba(223, 122, 254, 0.2)">
                        <div className="flex h-full">
                            <div className="p-6 flex-shrink-0 w-1/2 flex flex-col justify-center">
                                <span className="text-xs font-medium text-secondary uppercase tracking-widest">Sales & Marketing</span>
                                <h3 className="text-lg font-semibold text-white mt-2">Boost Revenue</h3>
                                <p className="text-xs text-gray-400 mt-2">
                                    AI-powered lead generation, customer insights, and marketing automation.
                                </p>
                            </div>
                            <div className="w-1/2 h-full border-l border-white/10">
                                <TerminalMockup />
                            </div>
                        </div>
                    </SpotlightCard>

                </div>
            </div>
        </section>
    );
}
