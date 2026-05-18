"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { EASE } from "@/components/landing/tokens";

type FeatureTextBlockProps = {
    eyebrow: string;
    title: string;
    titleMuted: string;
    description: string;
    items: string[];
    className?: string;
};

type MockupFrameProps = {
    label: string;
    children: ReactNode;
    className?: string;
};

export function FeatureTextBlock({
    eyebrow,
    title,
    titleMuted,
    description,
    items,
    className = "",
}: FeatureTextBlockProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.7, ease: EASE }}
            className={className}
        >
            <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-indigo-400">{eyebrow}</p>
            <h2 className="mt-4 text-[40px] font-medium leading-[1.1] tracking-tight text-white lg:text-[48px]">
                {title}
                <br />
                <span className="text-zinc-500">{titleMuted}</span>
            </h2>
            <p className="mt-6 max-w-md text-[16px] leading-relaxed text-zinc-400">{description}</p>
            <div className="mt-8 space-y-4">
                {items.map((item, index) => (
                    <motion.div
                        key={item}
                        initial={{ opacity: 0, y: 18 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.55, delay: index * 0.08, ease: EASE }}
                        className="flex items-start gap-3"
                    >
                        <div className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border border-indigo-500/20 bg-indigo-500/10">
                            <Check className="h-3 w-3 text-indigo-400" />
                        </div>
                        <p className="text-[14px] leading-relaxed text-zinc-300">{item}</p>
                    </motion.div>
                ))}
            </div>
        </motion.div>
    );
}

export function MockupFrame({ label, children, className = "" }: MockupFrameProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.8, ease: EASE }}
            className={`overflow-hidden rounded-xl border border-white/[0.08] bg-gradient-to-b from-[#0c0d12] to-[#07080c] shadow-[0_40px_80px_-20px_rgba(0,0,0,0.6),0_0_0_1px_rgba(255,255,255,0.05)] ${className}`}
        >
            <div className="relative flex h-8 items-center gap-2 border-b border-white/[0.06] bg-white/[0.02] px-3">
                <span className="h-2 w-2 rounded-full bg-[#ff5f57]" />
                <span className="h-2 w-2 rounded-full bg-[#febc2e]" />
                <span className="h-2 w-2 rounded-full bg-[#28c840]" />
                <div className="absolute left-1/2 -translate-x-1/2 rounded-md border border-white/[0.06] bg-white/[0.04] px-3 py-1 text-[11px] text-zinc-500">
                    {label}
                </div>
            </div>
            {children}
        </motion.div>
    );
}
