"use client";

import { TrendingUp } from "lucide-react";
import { CommitmentEmptyState } from "./empty-state";

interface InvestmentReturnProps {
    totalCommitted: string;
    totalSavings: string;
    roi: number;
    avgUtilization: number;
    isEmpty: boolean;
}

export function InvestmentReturn({
    totalCommitted,
    totalSavings,
    roi,
    avgUtilization,
    isEmpty,
}: InvestmentReturnProps) {
    if (isEmpty) {
        return (
            <CommitmentEmptyState
                icon={TrendingUp}
                title="No commitment data"
                subtitle="Connect a cloud account to see investment returns."
            />
        );
    }

    const utilColor =
        avgUtilization >= 85
            ? "bg-emerald-500"
            : avgUtilization >= 70
              ? "bg-amber-500"
              : "bg-rose-500";
    const utilTextColor =
        avgUtilization >= 85
            ? "text-emerald-400"
            : avgUtilization >= 70
              ? "text-amber-400"
              : "text-rose-400";

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
            <p className="mb-4 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                Investment Return
            </p>

            <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl border border-white/5 bg-white/5 p-3">
                        <p className="text-[10px] uppercase tracking-wide text-slate-500">Invested</p>
                        <p className="mt-1 text-sm font-bold text-white">{totalCommitted}</p>
                    </div>
                    <div className="rounded-xl border border-emerald-500/10 bg-emerald-500/5 p-3">
                        <p className="text-[10px] uppercase tracking-wide text-emerald-600">Return</p>
                        <p className="mt-1 text-sm font-bold text-emerald-400">{totalSavings}</p>
                    </div>
                </div>

                <div className="rounded-xl border border-white/5 bg-white/5 p-3">
                    <div className="flex items-center justify-between">
                        <p className="text-[10px] uppercase tracking-wide text-slate-500">Net ROI</p>
                        <p className="text-lg font-bold text-indigo-400">{roi.toFixed(1)}%</p>
                    </div>
                </div>

                <div className="rounded-xl border border-white/5 bg-white/5 p-3">
                    <div className="mb-2 flex items-center justify-between">
                        <p className="text-[10px] uppercase tracking-wide text-slate-500">
                            Portfolio Utilization
                        </p>
                        <span className={`text-sm font-bold ${utilTextColor}`}>
                            {avgUtilization}%
                        </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                        <div
                            className={`h-full rounded-full ${utilColor} transition-all duration-700`}
                            style={{ width: `${Math.min(avgUtilization, 100)}%` }}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
