"use client";

import type { CommitmentSummary } from "@/lib/api";
import { formatCommitmentPercent } from "@/lib/commitments/presentation";

export function InvestmentReturn({ summary }: { summary: CommitmentSummary }) {
    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
            <h3 className="mb-4 text-sm font-semibold text-white">Portfolio measurements</h3>
            <dl className="space-y-4 text-sm">
                <div className="flex flex-wrap justify-between gap-2">
                    <dt className="text-slate-400">Active commitments</dt>
                    <dd className="text-white">{summary.active_count}</dd>
                </div>
                <div className="flex flex-wrap justify-between gap-2">
                    <dt className="text-slate-400">Measurement status</dt>
                    <dd className="capitalize text-white">{summary.measurement_status}</dd>
                </div>
                <div className="flex flex-wrap justify-between gap-2">
                    <dt className="text-slate-400">Utilization</dt>
                    <dd className="text-white">{formatCommitmentPercent(summary.utilization_pct)}</dd>
                </div>
            </dl>
        </div>
    );
}
