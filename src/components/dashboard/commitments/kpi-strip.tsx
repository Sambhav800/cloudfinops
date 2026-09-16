"use client";

import { Gauge, TrendingUp, ShieldCheck, PiggyBank } from "lucide-react";
import type { CommitmentSummary } from "@/lib/api";
import { formatCommitmentMoney, formatCommitmentPercent, formatSavingsPeriod } from "@/lib/commitments/presentation";

export function CommitmentsKpiStrip({ summary }: { summary: CommitmentSummary }) {
    const cards = [
        { label: "Monthly commitment", value: formatCommitmentMoney(summary.monthly_commitment, summary.currency), subtitle: "Monthly equivalent", icon: PiggyBank },
        { label: "Measured savings", value: formatCommitmentMoney(summary.measured_savings, summary.currency), subtitle: formatSavingsPeriod(summary.savings_period_start, summary.savings_period_end), icon: TrendingUp },
        { label: "Utilization", value: formatCommitmentPercent(summary.utilization_pct), subtitle: "Provider measurement", icon: Gauge },
        { label: "Coverage", value: formatCommitmentPercent(summary.coverage_pct), subtitle: "Eligible spend coverage", icon: ShieldCheck },
    ];
    return (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {cards.map((card) => (
                <div key={card.label} className="min-w-0 rounded-2xl border border-white/10 bg-slate-900/50 p-5">
                    <div className="mb-3 flex items-center justify-between gap-2">
                        <p className="text-xs text-slate-400">{card.label}</p>
                        <card.icon className="h-4 w-4 shrink-0 text-indigo-400" />
                    </div>
                    <p className="break-words text-xl font-bold text-white">{card.value}</p>
                    <p className="mt-1 text-xs text-slate-400">{card.subtitle}</p>
                </div>
            ))}
        </div>
    );
}
