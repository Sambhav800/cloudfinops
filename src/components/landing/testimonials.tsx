"use client";

import { motion } from "framer-motion";
import { Quote } from "lucide-react";
import { SectionHeading } from "@/components/landing/section-heading";
import { EASE } from "@/components/landing/tokens";

type Testimonial = {
    quote: string;
    initials: string;
    name: string;
    role: string;
    avatarClassName: string;
    delay: number;
};

const TESTIMONIALS: Testimonial[] = [
    {
        quote:
            "We cut our GCP BigQuery spend 38% in the first two weeks. The anomaly detection caught a runaway query pattern our on-call rotation kept missing.",
        initials: "PK",
        name: "Priya Kulkarni",
        role: "Staff SRE · Fintech Series C",
        avatarClassName: "from-indigo-500 to-purple-500",
        delay: 0,
    },
    {
        quote:
            "The Terraform simulator alone paid for the platform. We caught a ₹11.6L/month oversight in a proposed EKS upgrade before it hit prod.",
        initials: "MC",
        name: "Marcus Chen",
        role: "Platform Lead · AI Infra Startup",
        avatarClassName: "from-emerald-500 to-teal-500",
        delay: 0.12,
    },
    {
        quote:
            "The governance layer actually explains why a rule fired. Our auditors stopped asking us for context because the context ships with the violation.",
        initials: "AK",
        name: "Anika Kapoor",
        role: "Head of Cloud · Enterprise SaaS",
        avatarClassName: "from-amber-500 to-rose-500",
        delay: 0.24,
    },
];

export function Testimonials() {
    return (
        <section className="px-6 py-32">
            <div className="mx-auto max-w-7xl">
                <SectionHeading
                    eyebrow="WHAT ENGINEERS SAY"
                    title={
                        <>
                            Teams ship faster{" "}
                            <span className="text-zinc-500">when they understand the bill.</span>
                        </>
                    }
                />

                <div className="mt-16 grid grid-cols-1 gap-6 md:grid-cols-3">
                    {TESTIMONIALS.map((item) => (
                        <motion.article
                            key={item.name}
                            initial={{ opacity: 0, y: 32 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true, margin: "-100px" }}
                            transition={{ duration: 0.75, delay: item.delay, ease: EASE }}
                            className="group rounded-xl border border-white/[0.08] bg-gradient-to-b from-white/[0.03] to-transparent p-8 transition-all duration-300 hover:border-white/[0.15]"
                        >
                            <motion.div
                                initial={{ opacity: 0 }}
                                whileInView={{ opacity: 1 }}
                                viewport={{ once: true, margin: "-100px" }}
                                transition={{
                                    duration: 0.6,
                                    delay: item.delay + 0.3,
                                    ease: EASE,
                                }}
                            >
                                <Quote className="h-5 w-5 rotate-180 text-indigo-400" />
                            </motion.div>

                            <p className="mt-4 text-[15px] leading-relaxed text-zinc-200">
                                {item.quote}
                            </p>

                            <div className="mt-6 border-t border-white/[0.06]" />

                            <div className="mt-6 flex items-center gap-3">
                                <div
                                    className={`flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br text-[13px] font-semibold text-white transition-transform duration-300 group-hover:scale-105 ${item.avatarClassName}`}
                                >
                                    {item.initials}
                                </div>
                                <div>
                                    <div className="text-[13px] font-medium text-white">{item.name}</div>
                                    <div className="text-[12px] text-zinc-500">{item.role}</div>
                                </div>
                            </div>
                        </motion.article>
                    ))}
                </div>
            </div>
        </section>
    );
}
