"use client";

import { motion } from "framer-motion";
import { useState, useRef } from "react";
import { ChevronLeft, ChevronRight, Rocket, TrendingUp, Cpu, ShieldCheck, Globe } from "lucide-react";

const useCases = [
    {
        title: "The Bootstrapped Builder",
        subtitle: "For Startups @ Seed/Series A",
        description: "Extend your runway by preventing bill shock before it happens. Our anomaly detection catches accidental spend spikes instantly, keeping your burn rate predictable.",
        icon: Rocket,
        stats: [
            { label: "Setup Time", value: "5 Mins" },
            { label: "Runway Impact", value: "Up to 4 Mo." },
            { label: "Bill Shock", value: "Near-Zero" },
        ],
        accent: "blue"
    },
    {
        title: "The Hyper-Growth Scaleup",
        subtitle: "For Series B+ & Pre-IPO",
        description: "Tame microservices sprawl without slowing down dev velocity. Automated tagging and zombie resource killing ensure your unit economics stay healthy as you scale.",
        icon: TrendingUp,
        stats: [
            { label: "Cloud Waste", value: "Up to 40%" },
            { label: "Eng. Time Saved", value: "~15-20hrs" },
            { label: "Compliance", value: "100%" },
        ],
        accent: "purple"
    },
    {
        title: "The AI Innovator",
        subtitle: "For AI/ML & Data Platforms",
        description: "Maximize GPU utilization and leverage spot instance arbitrage. Train larger models for less by automatically managing expensive compute lifecycles with zero downtime.",
        icon: Cpu,
        stats: [
            { label: "GPU Idle Time", value: "< 10%" },
            { label: "Training Cost", value: "Up to 50%" },
            { label: "Spot Uptime", value: "High" },
        ],
        accent: "pink"
    },
    {
        title: "The Compliance-First Enterprise",
        subtitle: "For Regulated Industries & Government",
        description: "Enforce region lockdowns, resource tagging policies, and encryption audits automatically. Generate board-ready governance reports that keep auditors happy and CFOs informed.",
        icon: ShieldCheck,
        stats: [
            { label: "Policy Checks", value: "5 Auto" },
            { label: "Audit Time", value: "Up to 80%" },
            { label: "Compliance", value: "94%+" },
        ],
        accent: "green"
    },
    {
        title: "The Multi-Cloud Operator",
        subtitle: "For Platform & DevOps Teams",
        description: "Stop juggling three dashboards. Unify cost visibility across AWS, Azure, and GCP into a single pane. Detect shadow IT across every provider and region from one scan.",
        icon: Globe,
        stats: [
            { label: "Providers", value: "3 Clouds" },
            { label: "Regions Scanned", value: "17+" },
            { label: "Shadow IT Found", value: "Day 1" },
        ],
        accent: "cyan"
    }
];

export function CaseStudies() {
    const scrollRef = useRef<HTMLDivElement>(null);
    const [canScrollLeft, setCanScrollLeft] = useState(false);
    const [canScrollRight, setCanScrollRight] = useState(true);

    const scroll = (direction: "left" | "right") => {
        if (scrollRef.current) {
            const scrollAmount = 400; // Adjusted for better scroll experience
            scrollRef.current.scrollBy({
                left: direction === "left" ? -scrollAmount : scrollAmount,
                behavior: "smooth"
            });
        }
    };

    const handleScroll = () => {
        if (scrollRef.current) {
            const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current;
            setCanScrollLeft(scrollLeft > 0);
            setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 10);
        }
    };

    return (
        <section className="py-24 bg-black relative overflow-hidden">
            <div className="mx-auto max-w-7xl px-6 lg:px-8 relative z-10">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="text-center mb-16"
                >
                    <span className="pill-badge mb-4">Target Architectures</span>
                    <h2 className="text-4xl md:text-5xl font-semibold text-white tracking-tight mt-4">
                        Engineered for Every{" "}
                        <span className="text-gradient">Stage of Growth</span>
                    </h2>
                    <p className="mt-4 text-lg text-gray-400 max-w-2xl mx-auto">
                        Whether you're bootstrapping a SaaS or training LLMs, our engine adapts to your infrastructure needs.
                    </p>
                </motion.div>

                {/* Cards Grid (Responsive: Stack on mobile, Grid on desktop if few, Carousel if many - sticking to horizontal scroll for consistency with original design but improved) */}
                <div className="relative group">
                    {/* Scroll Indicators - Only show if content overflows (managed by state) */}
                    <div className="hidden md:flex items-center justify-end gap-2 mb-4 px-4">
                        <button
                            onClick={() => scroll("left")}
                            disabled={!canScrollLeft}
                            className={`p-2 rounded-full border border-white/10 transition-all ${canScrollLeft ? "bg-white/10 hover:bg-white/20 text-white" : "text-gray-600 opacity-50 cursor-not-allowed"}`}
                        >
                            <ChevronLeft className="w-5 h-5" />
                        </button>
                        <button
                            onClick={() => scroll("right")}
                            disabled={!canScrollRight}
                            className={`p-2 rounded-full border border-white/10 transition-all ${canScrollRight ? "bg-white/10 hover:bg-white/20 text-white" : "text-gray-600 opacity-50 cursor-not-allowed"}`}
                        >
                            <ChevronRight className="w-5 h-5" />
                        </button>
                    </div>

                    <div
                        ref={scrollRef}
                        onScroll={handleScroll}
                        className="flex gap-6 overflow-x-auto scrollbar-hide pb-8 px-4 cursor-grab active:cursor-grabbing snap-x snap-mandatory"
                    >
                        {useCases.map((useCase, index) => (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, x: 40 }}
                                whileInView={{ opacity: 1, x: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.5, delay: index * 0.1 }}
                                className="flex-shrink-0 w-[90vw] md:w-[450px] snap-center"
                            >
                                <div className="glass-card h-full p-8 relative overflow-hidden group hover:border-primary/50 transition-colors duration-300">
                                    {/* Abstract Background Shape */}
                                    <div className={`absolute -top-20 -right-20 w-64 h-64 bg-${useCase.accent}-500/10 rounded-full blur-[80px] group-hover:bg-${useCase.accent}-500/20 transition-all duration-500`} />

                                    <div className="relative z-10">
                                        {/* Icon & Title */}
                                        <div className="flex items-start justify-between mb-6">
                                            <div>
                                                <div className="p-3 bg-white/5 rounded-lg w-fit mb-4">
                                                    <useCase.icon className="w-6 h-6 text-white" />
                                                </div>
                                                <h3 className="text-2xl font-semibold text-white mb-1">
                                                    {useCase.title}
                                                </h3>
                                                <p className="text-sm font-medium text-primary uppercase tracking-wider">
                                                    {useCase.subtitle}
                                                </p>
                                            </div>
                                        </div>

                                        <p className="text-gray-400 leading-relaxed mb-8 min-h-[80px]">
                                            {useCase.description}
                                        </p>

                                        {/* Stats Grid */}
                                        <div className="grid grid-cols-3 gap-4 py-6 border-t border-white/10">
                                            {useCase.stats.map((stat, i) => (
                                                <div key={i}>
                                                    <div className="text-xl font-bold text-white mb-1">{stat.value}</div>
                                                    <div className="text-xs text-gray-500">{stat.label}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    );
}
