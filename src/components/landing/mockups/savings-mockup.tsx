"use client";

import { motion } from "framer-motion";
import { COLORS, EASE } from "@/components/landing/tokens";

const barHeights = [20, 28, 24, 34, 30, 42, 38, 48, 44, 56, 52, 64];

export function SavingsMockup() {
    return (
        <div className="overflow-hidden rounded-xl border border-white/[0.08] bg-gradient-to-b from-[#0c0d12] to-[#07080c] shadow-[0_30px_60px_-15px_rgba(0,0,0,0.8),0_0_0_1px_rgba(255,255,255,0.05)] backdrop-blur-xl">
            <div className="flex h-8 items-center justify-between border-b border-white/[0.06] bg-white/[0.02] px-3">
                <span className="text-[12px] font-medium text-zinc-300">Savings realized</span>
                <span className="rounded border border-emerald-500/20 bg-emerald-500/10 px-1.5 py-0.5 text-[11px] text-emerald-400">
                    +42%
                </span>
            </div>
            <div className="p-3">
                <p className="text-[28px] font-medium text-white tabular-nums">₹35.0L</p>
                <p className="mt-0.5 text-[11px] text-zinc-500">12-week trend</p>

                <svg viewBox="0 0 240 80" className="mt-4 h-24 w-full" aria-label="Savings realized bar chart" role="img">
                    {barHeights.map((height, index) => {
                        const x = index * 20;
                        const y = 80 - height;
                        const opacity = 0.35 + index * 0.05;

                        return (
                            <motion.rect
                                key={`${index}-${height}`}
                                x={x}
                                width="14"
                                rx="2"
                                initial={{ y: 80, height: 0 }}
                                animate={{ y, height }}
                                transition={{ duration: 0.65, delay: index * 0.04, ease: EASE }}
                                fill={COLORS.accent}
                                opacity={Math.min(opacity, 1)}
                            />
                        );
                    })}
                </svg>
            </div>
        </div>
    );
}
