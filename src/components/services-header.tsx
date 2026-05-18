"use client";

import { motion } from "framer-motion";

export function ServicesHeader() {
    return (
        <section className="relative overflow-hidden pt-8 pb-24" style={{
            background: 'linear-gradient(to bottom, rgba(86, 104, 160, 0.12) 0%, rgba(12, 16, 25, 0.76) 26%, rgba(5, 7, 12, 0) 100%)'
        }}>
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(186,150,94,0.08),transparent_42%),radial-gradient(circle_at_50%_6%,rgba(104,122,178,0.12),transparent_58%)] pointer-events-none" />
            <div className="absolute -top-20 left-1/2 -translate-x-1/2 w-[820px] h-[380px] rounded-full blur-[170px] bg-[rgba(90,106,158,0.08)] pointer-events-none" />
            <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-b from-transparent via-white/3 to-transparent pointer-events-none" />

            <div className="mx-auto max-w-4xl px-6 lg:px-8 relative z-10">
                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="text-center"
                >
                    <span className="pill-badge mb-6">What We Actually Build</span>

                    <h2 className="text-4xl md:text-5xl lg:text-6xl font-semibold text-white tracking-tight mt-6 leading-[1.1]">
                        Every Feature, Powered by{" "}
                        <span className="text-gradient">Real AI Intelligence</span>
                    </h2>

                    <p className="mt-6 text-lg text-gray-400 max-w-2xl mx-auto">
                        From multi-cloud scanning to AI-driven governance — every capability below is live, tested, and shipping value to real teams.
                    </p>
                </motion.div>
            </div>
        </section>
    );
}
