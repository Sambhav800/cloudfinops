"use client";

import { motion } from "framer-motion";
import { Percent, TrendingUp, ShieldCheck, AlertTriangle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

interface KpiStripProps {
    esr: number;
    monthlySavings: string;
    coverageRate: number;
    waste: string;
    wastePct: number;
    isLoading: boolean;
    isEmpty: boolean;
}

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const item = {
    hidden: { opacity: 0, y: 16 },
    show: { opacity: 1, y: 0 },
};

export function CommitmentsKpiStrip({
    esr,
    monthlySavings,
    coverageRate,
    waste,
    wastePct,
    isLoading,
    isEmpty,
}: KpiStripProps) {
    if (isLoading) {
        return (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (
                    <div
                        key={i}
                        className="rounded-2xl border border-white/10 bg-gradient-to-br from-slate-900/60 to-slate-900/40 p-5"
                    >
                        <Skeleton className="mb-3 h-4 w-20 bg-slate-800" />
                        <Skeleton className="mb-2 h-8 w-28 bg-slate-800" />
                        <Skeleton className="h-3 w-32 bg-slate-800" />
                    </div>
                ))}
            </div>
        );
    }

    if (isEmpty) {
        return (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                    { label: "Savings Rate", icon: Percent },
                    { label: "Monthly Savings", icon: TrendingUp },
                    { label: "Coverage", icon: ShieldCheck },
                    { label: "Waste", icon: AlertTriangle },
                ].map((card) => (
                    <div
                        key={card.label}
                        className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-center"
                    >
                        <card.icon className="mb-2 h-5 w-5 text-slate-600" />
                        <p className="text-xs text-slate-500">{card.label}</p>
                    </div>
                ))}
            </div>
        );
    }

    const cards = [
        {
            label: "Effective Savings Rate",
            value: `${esr.toFixed(1)}%`,
            subtitle: "discount rate achieved",
            color: "emerald",
            icon: Percent,
        },
        {
            label: "Monthly Savings",
            value: monthlySavings,
            subtitle: "vs on-demand pricing",
            color: "emerald",
            icon: TrendingUp,
        },
        {
            label: "Coverage Rate",
            value: `${coverageRate}%`,
            subtitle: "of eligible spend committed",
            color: "indigo",
            icon: ShieldCheck,
        },
        {
            label: "Commitment Waste",
            value: waste,
            subtitle: `${wastePct.toFixed(1)}% underutilized`,
            color: "rose",
            icon: AlertTriangle,
        },
    ];

    const accentMap: Record<string, string> = {
        emerald: "border-t-emerald-500/60",
        indigo: "border-t-indigo-500/60",
        amber: "border-t-amber-500/60",
        rose: "border-t-rose-500/60",
    };

    const textMap: Record<string, string> = {
        emerald: "text-emerald-400",
        indigo: "text-indigo-400",
        amber: "text-amber-400",
        rose: "text-rose-400",
    };

    const iconBgMap: Record<string, string> = {
        emerald: "bg-emerald-500/10 text-emerald-400",
        indigo: "bg-indigo-500/10 text-indigo-400",
        amber: "bg-amber-500/10 text-amber-400",
        rose: "bg-rose-500/10 text-rose-400",
    };

    return (
        <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
        >
            {cards.map((card) => (
                <motion.div
                    key={card.label}
                    variants={item}
                    className={`rounded-2xl border border-white/10 border-t-2 ${accentMap[card.color]} bg-gradient-to-br from-slate-900/60 to-slate-900/40 p-5`}
                >
                    <div className="mb-3 flex items-center justify-between">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                            {card.label}
                        </p>
                        <div className={`rounded-lg p-1.5 ${iconBgMap[card.color]}`}>
                            <card.icon className="h-3.5 w-3.5" />
                        </div>
                    </div>
                    <p className={`text-2xl font-bold ${textMap[card.color]}`}>
                        {card.value}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">{card.subtitle}</p>
                </motion.div>
            ))}
        </motion.div>
    );
}
