"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform, useSpring } from "framer-motion";
import { Link, Search, Lightbulb, Activity } from "lucide-react";
import { clsx } from "clsx";

const steps = [
    {
        icon: Link,
        title: "Connect Your Cloud Accounts",
        description:
            "Securely connect your AWS, Azure, or GCP accounts. We use read-only access to analyze your infrastructure without making any changes.",
        features: [
            "Read-only secure access",
            "Multi-cloud support",
            "5-minute setup",
        ],
    },
    {
        icon: Search,
        title: "We Analyze Your Infrastructure",
        description:
            "Our AI-powered engine scans your entire cloud setup, analyzing usage patterns, identifying waste, and finding optimization opportunities.",
        features: [
            "AI-powered analysis",
            "Usage pattern detection",
            "Cost breakdown by service",
        ],
    },
    {
        icon: Lightbulb,
        title: "Get Actionable Recommendations",
        description:
            "Receive personalized, prioritized recommendations to reduce costs. Each suggestion includes estimated savings and implementation effort.",
        features: [
            "Prioritized by impact",
            "Clear savings estimates",
            "One-click implementation guides",
        ],
    },
    {
        icon: Activity,
        title: "Monitor & Optimize Continuously",
        description:
            "Track your savings over time with real-time dashboards. Get alerts for anomalies and new optimization opportunities as your infrastructure evolves.",
        features: [
            "Real-time monitoring",
            "Anomaly detection",
            "Continuous optimization",
        ],
    },
];

export function HowItWorks() {
    const containerRef = useRef<HTMLDivElement>(null);
    const { scrollYProgress } = useScroll({
        target: containerRef,
        offset: ["start center", "end center"],
    });

    // Smooth out the scroll progress
    const smoothProgress = useSpring(scrollYProgress, {
        stiffness: 100,
        damping: 30,
        restDelta: 0.001,
    });

    return (
        <section
            id="how-it-works"
            ref={containerRef}
            className="relative bg-black py-24 sm:py-32 overflow-hidden"
        >
            <div className="mx-auto max-w-7xl px-6 lg:px-8">
                <div className="mx-auto max-w-2xl text-center mb-20">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="text-primary font-semibold mb-2"
                    >
                        How CloudFinOps Works
                    </motion.h2>
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.1 }}
                        className="text-4xl font-bold text-white tracking-tight"
                    >
                        Connection to savings in <span className="text-gradient">48 hours</span>.
                    </motion.p>
                </div>

                <div className="relative">
                    {/* Central Laser Beam Line */}
                    <div className="absolute left-[20px] md:left-1/2 top-0 bottom-0 w-1 bg-white/10 -translate-x-1/2 rounded-full overflow-hidden">
                        <motion.div
                            className="w-full bg-gradient-to-b from-primary via-blue-500 to-purple-500 h-full origin-top"
                            style={{ scaleY: smoothProgress }}
                        />
                    </div>

                    {/* Glowing Head of the Laser */}
                    <motion.div
                        className="absolute left-[20px] md:left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-primary shadow-[0_0_20px_4px_rgba(0,210,255,0.6)] z-20"
                        style={{
                            top: useTransform(smoothProgress, [0, 1], ["0%", "100%"]),
                            opacity: useTransform(smoothProgress, [0, 0.05, 0.95, 1], [0, 1, 1, 0])
                        }}
                    />

                    <div className="space-y-24">
                        {steps.map((step, index) => (
                            <StepCard
                                key={step.title}
                                step={step}
                                index={index}
                            />
                        ))}
                    </div>
                </div>

                <div className="mt-24 text-center">
                    <a
                        href="/audit"
                        className="inline-block rounded-full bg-white px-10 py-4 text-lg font-bold text-black transition-all hover:scale-105 hover:shadow-[0_0_30px_rgba(255,255,255,0.3)]"
                    >
                        Start Saving Now
                    </a>
                </div>
            </div>
        </section>
    );
}

function StepCard({ step, index }: { step: any; index: number }) {
    const isEven = index % 2 === 0;

    return (
        <motion.div
            initial={{ opacity: 0, y: 50 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ margin: "-100px" }}
            transition={{ duration: 0.7, ease: "easeOut" }}
            className={clsx(
                "relative flex flex-col md:flex-row items-center gap-12 perspective-1000",
                isEven ? "" : "md:flex-row-reverse"
            )}
        >
            {/* Number Bubble on the Line */}
            <div className="absolute left-[20px] md:left-1/2 -translate-x-1/2 z-10">
                <div className="flex items-center justify-center w-12 h-12 rounded-full bg-black border-4 border-gray-800 text-white font-bold text-lg shadow-xl">
                    {index + 1}
                </div>
            </div>

            {/* Content Side */}
            <div className={clsx("flex-1 pl-16 md:pl-0", isEven ? "md:text-right md:pr-16" : "md:text-left md:pl-16")}>
                <div className={clsx("flex flex-col", isEven ? "md:items-end" : "md:items-start")}>
                    <div className="h-14 w-14 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center mb-6 text-primary">
                        <step.icon className="w-7 h-7" />
                    </div>
                    <h3 className="text-2xl font-bold text-white mb-4">{step.title}</h3>
                    <p className="text-gray-400 leading-relaxed mb-6">{step.description}</p>
                    <ul className={clsx("space-y-2", isEven ? "md:items-end" : "md:text-left")}>
                        {step.features.map((feat: string) => (
                            <li key={feat} className={clsx("text-sm text-gray-500 flex items-center gap-2", isEven ? "md:flex-row-reverse" : "")}>
                                <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                                {feat}
                            </li>
                        ))}
                    </ul>
                </div>
            </div>

            {/* Empty side for spacing in desktop */}
            <div className="flex-1 hidden md:block" />
        </motion.div>
    );
}
