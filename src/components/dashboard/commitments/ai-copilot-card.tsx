"use client";

import { Sparkles, ArrowUpRight } from "lucide-react";
import Link from "next/link";

interface CommitmentScenario {
    label: string;
    commitment_pct: number;
    monthly_commitment_usd: number;
    monthly_saving_usd: number;
    annual_saving_usd: number;
    effective_discount_pct: number;
    over_commitment_risk_pct: number;
    risk_level: "Low" | "Medium" | "High";
    term_years: number;
}

interface AiCopilotCardProps {
    recommendedScenario: CommitmentScenario | null;
    uncoveredSpend: string;
    coveragePct: number;
    analysisDays: number;
    formatMoney: (usd: number) => string;
    isEmpty: boolean;
    emptyMessage?: string;
}

export function AiCopilotCard({
    recommendedScenario,
    uncoveredSpend,
    coveragePct,
    analysisDays,
    formatMoney,
    isEmpty,
    emptyMessage,
}: AiCopilotCardProps) {
    return (
        <div className="relative overflow-hidden rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-indigo-900/30 to-slate-900/50 p-6 backdrop-blur-xl lg:col-span-3">
            <div className="absolute -right-12 -top-12 h-32 w-32 rounded-full bg-indigo-500/10 blur-3xl" />

            <div className="relative z-10">
                <div className="mb-5 flex items-center gap-2">
                    <div className="rounded-lg bg-indigo-500/20 p-2 text-indigo-300">
                        <Sparkles className="h-4 w-4" />
                    </div>
                    <h3 className="text-sm font-bold text-white">AI Copilot</h3>
                    <span className="ml-auto rounded-full border border-indigo-500/20 bg-indigo-500/10 px-2 py-0.5 text-[9px] font-medium text-indigo-300">
                        Powered by CloudFinOps Intelligence
                    </span>
                </div>

                {isEmpty ? (
                    <div className="flex h-40 items-center justify-center">
                        <p className="max-w-sm text-center text-sm text-slate-400">
                            {emptyMessage || "Connect a cloud account and run a scan to see AI recommendations."}
                        </p>
                    </div>
                ) : recommendedScenario ? (
                    <div className="space-y-4">
                        <p className="text-sm leading-relaxed text-slate-300">
                            Based on{" "}
                            <span className="font-medium text-white">{analysisDays} days</span> of spend
                            history, your modeled commitment coverage sits at{" "}
                            <span className="font-bold text-indigo-400">{coveragePct}%</span>, leaving{" "}
                            <span className="font-bold text-rose-400">{uncoveredSpend}</span> forecasted
                            on-demand spend optimizable.
                        </p>

                        <div className="rounded-xl border border-white/10 bg-black/30 p-4">
                            <div className="mb-2 flex items-center gap-2">
                                <span className="text-[10px] font-semibold uppercase tracking-wider text-indigo-400">
                                    Recommended
                                </span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">
                                    {recommendedScenario.label} &middot; {recommendedScenario.term_years}-year
                                </span>
                            </div>
                            <div className="grid grid-cols-3 gap-4">
                                <div>
                                    <p className="text-[10px] text-slate-500">Monthly Commit</p>
                                    <p className="mt-0.5 text-sm font-bold text-white">
                                        {formatMoney(recommendedScenario.monthly_commitment_usd)}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] text-slate-500">Monthly Savings</p>
                                    <p className="mt-0.5 text-sm font-bold text-emerald-400">
                                        {formatMoney(recommendedScenario.monthly_saving_usd)}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] text-slate-500">Annual Impact</p>
                                    <p className="mt-0.5 text-sm font-bold text-emerald-400">
                                        {formatMoney(recommendedScenario.annual_saving_usd)}
                                    </p>
                                </div>
                            </div>
                            <div className="mt-3 flex items-center gap-2">
                                <span className="text-[10px] text-slate-500">Risk:</span>
                                <span
                                    className={`rounded-md border px-2 py-0.5 text-[10px] font-medium ${
                                        recommendedScenario.risk_level === "Low"
                                            ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                                            : recommendedScenario.risk_level === "Medium"
                                              ? "border-amber-500/20 bg-amber-500/10 text-amber-400"
                                              : "border-rose-500/20 bg-rose-500/10 text-rose-400"
                                    }`}
                                >
                                    {recommendedScenario.risk_level} ({recommendedScenario.over_commitment_risk_pct.toFixed(0)}%)
                                </span>
                                <span className="text-[10px] text-slate-500">
                                    Effective discount: {recommendedScenario.effective_discount_pct}%
                                </span>
                            </div>
                        </div>

                        <Link
                            href="/dashboard/optimizer"
                            className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-400 transition hover:text-indigo-300"
                        >
                            View Optimizer Scenarios
                            <ArrowUpRight className="h-3.5 w-3.5" />
                        </Link>
                    </div>
                ) : null}
            </div>
        </div>
    );
}
