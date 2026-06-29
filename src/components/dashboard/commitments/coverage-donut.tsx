"use client";

import { ShieldCheck } from "lucide-react";
import { CommitmentEmptyState } from "./empty-state";

interface CoverageDonutProps {
    coveragePct: number;
    coveredSpend: string;
    uncoveredSpend: string;
    isEmpty: boolean;
    emptyMessage?: string;
}

export function CoverageDonut({
    coveragePct,
    coveredSpend,
    uncoveredSpend,
    isEmpty,
    emptyMessage,
}: CoverageDonutProps) {
    if (isEmpty) {
        return (
            <CommitmentEmptyState
                icon={ShieldCheck}
                title="No coverage data"
                subtitle={emptyMessage || "Connect a cloud account and run a scan to see coverage."}
            />
        );
    }

    const radius = 52;
    const circumference = 2 * Math.PI * radius;
    const coveredDash = (coveragePct / 100) * circumference;
    const scoreColor =
        coveragePct >= 70 ? "text-emerald-400" : coveragePct >= 40 ? "text-amber-400" : "text-rose-400";
    const strokeColor =
        coveragePct >= 70 ? "#34d399" : coveragePct >= 40 ? "#fbbf24" : "#f87171";

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
            <p className="mb-4 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                Coverage Score
            </p>

            <div className="flex flex-col items-center">
                <div className="relative h-32 w-32">
                    <svg className="h-32 w-32 -rotate-90" viewBox="0 0 120 120">
                        <circle
                            cx="60"
                            cy="60"
                            r={radius}
                            fill="none"
                            stroke="rgba(255,255,255,0.05)"
                            strokeWidth="10"
                        />
                        <circle
                            cx="60"
                            cy="60"
                            r={radius}
                            fill="none"
                            stroke={strokeColor}
                            strokeWidth="10"
                            strokeLinecap="round"
                            strokeDasharray={circumference}
                            strokeDashoffset={circumference - coveredDash}
                            style={{ transition: "stroke-dashoffset 1s ease-in-out" }}
                        />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className={`text-3xl font-bold ${scoreColor}`}>
                            {coveragePct}%
                        </span>
                        <span className="text-[10px] uppercase tracking-wider text-slate-500">
                            Covered
                        </span>
                    </div>
                </div>

                <div className="mt-4 w-full space-y-2">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <span className="h-2 w-2 rounded-full bg-emerald-400" />
                            <span className="text-xs text-slate-400">Committed</span>
                        </div>
                        <span className="text-xs font-medium text-white">{coveredSpend}</span>
                    </div>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <span className="h-2 w-2 rounded-full bg-slate-600" />
                            <span className="text-xs text-slate-400">On-Demand</span>
                        </div>
                        <span className="text-xs font-medium text-white">{uncoveredSpend}</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
