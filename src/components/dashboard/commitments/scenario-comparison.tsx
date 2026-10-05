"use client";

import type { CommitmentScenario } from "@/lib/api";
import { formatCommitmentDate, formatCommitmentMoney, formatCommitmentPercent } from "@/lib/commitments/presentation";

export function ScenarioComparison({ scenarios, currency }: { scenarios: CommitmentScenario[]; currency: string }) {
    return (
        <div className="min-w-0 rounded-2xl border border-white/10 bg-slate-900/50 p-6 lg:col-span-2">
            <h3 className="mb-4 text-sm font-semibold text-white">Provider alternatives</h3>
            {scenarios.length === 0 ? <p className="text-sm text-slate-400">No alternatives available.</p> : (
                <ul className="divide-y divide-white/10">
                    {scenarios.map((scenario) => (
                        <li key={`${scenario.integration_id}-${scenario.term_years}-${scenario.recommendation_id}`} className="space-y-2 py-3 text-xs">
                            <p className="break-words font-medium text-white">{scenario.label} ({scenario.term_years}-year)</p>
                            <p className="break-all text-slate-400">Account: {scenario.account_id || "Not measured"}</p>
                            <p className="break-all text-slate-400">Integration: {scenario.integration_id}</p>
                            <p className="text-slate-300">Monthly commitment: {formatCommitmentMoney(scenario.monthly_commitment_usd, currency)}</p>
                            <p className="text-emerald-400">Estimated monthly savings: {formatCommitmentMoney(scenario.monthly_saving_usd, currency)}</p>
                            <p className="text-slate-400">Estimated savings %: {formatCommitmentPercent(scenario.provider_estimated_savings_pct)}</p>
                            <p className="text-slate-400">Risk: Not measured</p>
                            <p className="text-slate-500">Generated: {formatCommitmentDate(scenario.generated_at, true)}</p>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
