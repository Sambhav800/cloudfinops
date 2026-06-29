"use client";

import { ShieldCheck } from "lucide-react";
import { CommitmentEmptyState } from "./empty-state";

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

interface ScenarioComparisonProps {
    scenarios: CommitmentScenario[];
    recommendedLabel: string | null;
    formatMoney: (usd: number) => string;
    isEmpty: boolean;
    emptyMessage?: string;
}

const riskColors: Record<string, { bar: string; badge: string }> = {
    Low: { bar: "bg-emerald-500", badge: "border-emerald-500/20 bg-emerald-500/10 text-emerald-400" },
    Medium: { bar: "bg-amber-500", badge: "border-amber-500/20 bg-amber-500/10 text-amber-400" },
    High: { bar: "bg-rose-500", badge: "border-rose-500/20 bg-rose-500/10 text-rose-400" },
};

export function ScenarioComparison({
    scenarios,
    recommendedLabel,
    formatMoney,
    isEmpty,
    emptyMessage,
}: ScenarioComparisonProps) {
    if (isEmpty || scenarios.length === 0) {
        return (
            <div className="lg:col-span-2">
                <CommitmentEmptyState
                    icon={ShieldCheck}
                    title="No scenario data"
                    subtitle={emptyMessage || "Need at least 14 days of spend history for scenario modeling."}
                />
            </div>
        );
    }

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl lg:col-span-2">
            <p className="mb-4 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                Coverage Scenarios
            </p>

            <div className="space-y-3">
                {scenarios.map((scenario) => {
                    const isRecommended = scenario.label === recommendedLabel;
                    const colors = riskColors[scenario.risk_level] ?? riskColors.Medium;

                    return (
                        <div
                            key={`${scenario.label}-${scenario.term_years}`}
                            className={`rounded-xl border p-3 transition ${
                                isRecommended
                                    ? "border-indigo-500/40 bg-indigo-500/5"
                                    : "border-white/5 bg-white/[0.02]"
                            }`}
                        >
                            <div className="mb-2 flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-medium text-white">
                                        {scenario.label}
                                    </span>
                                    <span className="text-[10px] text-slate-500">
                                        {scenario.term_years}yr
                                    </span>
                                    {isRecommended && (
                                        <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-1.5 py-0.5 text-[9px] font-medium text-indigo-400">
                                            Recommended
                                        </span>
                                    )}
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-medium text-emerald-400">
                                        {formatMoney(scenario.monthly_saving_usd)}/mo
                                    </span>
                                    <span
                                        className={`rounded-md border px-1.5 py-0.5 text-[9px] font-medium ${colors.badge}`}
                                    >
                                        {scenario.risk_level}
                                    </span>
                                </div>
                            </div>
                            <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                                <div
                                    className={`h-full rounded-full ${colors.bar} transition-all duration-700`}
                                    style={{ width: `${Math.min(scenario.commitment_pct, 100)}%` }}
                                />
                            </div>
                            <p className="mt-1 text-[10px] text-slate-500">
                                {scenario.commitment_pct}% coverage &middot; {scenario.effective_discount_pct}% discount
                            </p>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
