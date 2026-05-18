'use client';

import { Lightbulb, TrendingDown } from 'lucide-react';

import type { SimulatorFinding } from './cost-delta-view';
import { formatInrCurrency, toDisplayInrAmount } from '@/lib/resources/contract';

type BestPracticeFindingsProps = {
    findings: SimulatorFinding[];
};

const SEVERITY_STYLES: Record<string, string> = {
    critical: 'border-rose-500/25 bg-rose-500/15 text-rose-300',
    high: 'border-amber-500/25 bg-amber-500/15 text-amber-300',
    medium: 'border-indigo-500/25 bg-indigo-500/15 text-indigo-300',
    low: 'border-slate-500/25 bg-slate-500/15 text-slate-300',
};

function formatImpact(value: number | null): string {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        return 'Impact not verified';
    }

    return `${formatInrCurrency(toDisplayInrAmount(value, 'USD'), {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    })}/mo`;
}

export function BestPracticeFindings({ findings }: BestPracticeFindingsProps) {
    if (findings.length === 0) {
        return null;
    }

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl shadow-black/40">
            <div className="mb-5 flex items-start gap-3">
                <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/10 p-2 text-indigo-300">
                    <Lightbulb className="h-5 w-5" />
                </div>
                <div>
                    <h3 className="text-base font-semibold text-white">Best-Practice Findings</h3>
                    <p className="mt-1 text-sm text-slate-400">
                        Deterministic checks from Terraform attributes. Savings impact stays blank unless backed by exact pricing.
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                {findings.map((finding, index) => (
                    <div
                        key={`${finding.resource_address}-${finding.finding_id}-${index}`}
                        className="rounded-2xl border border-white/5 bg-slate-800/30 p-4"
                    >
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${SEVERITY_STYLES[finding.severity] ?? SEVERITY_STYLES.low}`}>
                                        {finding.severity}
                                    </span>
                                    <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                                        {finding.confidence} confidence
                                    </span>
                                </div>
                                <p className="mt-2 break-all text-sm font-semibold text-white">
                                    {finding.resource_address}
                                </p>
                                <p className="mt-1 text-xs text-slate-500">{finding.finding_id}</p>
                            </div>
                            <div className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2 text-sm text-slate-300">
                                <TrendingDown className="h-4 w-4 text-emerald-400" />
                                {formatImpact(finding.monthly_impact)}
                            </div>
                        </div>
                        <p className="mt-4 text-sm leading-6 text-slate-300">{finding.evidence}</p>
                        <p className="mt-3 rounded-xl border border-white/10 bg-slate-950/35 p-3 text-sm leading-6 text-slate-400">
                            {finding.remediation}
                        </p>
                    </div>
                ))}
            </div>
        </div>
    );
}
