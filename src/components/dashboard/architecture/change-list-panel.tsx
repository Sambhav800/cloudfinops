'use client';

import {
    Trash2, ArrowDownRight, Shield, Plus, Lock, Eye, AlertTriangle,
} from 'lucide-react';
import type { ProposedResult, ChangeItem } from '@/lib/architecture-types';
import { formatInrCurrency, toDisplayInrAmount } from '@/lib/resources/contract';

const CHANGE_ICONS: Record<string, React.ElementType> = {
    terminate: Trash2,
    downsize: ArrowDownRight,
    migrate: ArrowDownRight,
    enable_multi_az: Plus,
    add_replica: Plus,
    add_monitoring: Eye,
    tighten_security: Lock,
    enable_encryption: Shield,
};

const RISK_COLORS: Record<string, string> = {
    low: 'border border-emerald-500/20 bg-emerald-500/10 text-emerald-400',
    medium: 'border border-amber-500/20 bg-amber-500/10 text-amber-400',
    high: 'border border-rose-500/20 bg-rose-500/10 text-rose-400',
};

function proposalSourceCurrency(provider: string): string {
    return provider.trim().toLowerCase() === 'gcp' ? 'INR' : 'USD';
}

function formatProposalMoney(value: number, provider: string): string {
    return formatInrCurrency(toDisplayInrAmount(Math.abs(value), proposalSourceCurrency(provider)), {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

interface Props {
    proposed: ProposedResult;
    provider: string;
}

export function ChangeListPanel({ proposed, provider }: Props) {
    const isSavings = proposed.estimated_savings > 0;

    return (
        <div className="mt-3 overflow-hidden rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur-xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/10 bg-slate-900/60 px-4 py-3">
                <div className="flex items-center gap-2">
                    {proposed.mode === 'cost_optimized' ? (
                        <ArrowDownRight className="w-4 h-4 text-emerald-400" />
                    ) : (
                        <Shield className="w-4 h-4 text-indigo-400" />
                    )}
                    <span className="text-sm text-white font-medium">
                        {proposed.mode === 'cost_optimized' ? 'Cost-Optimized' : 'Reliability / Security'} Changes
                    </span>
                    <span className="text-xs text-slate-500">
                        ({proposed.change_list.length} change{proposed.change_list.length !== 1 ? 's' : ''})
                    </span>
                </div>
                <div className={`text-sm font-semibold ${isSavings ? 'text-emerald-400' : 'text-amber-400'}`}>
                    Est. {isSavings ? 'savings' : 'added cost'}: {formatProposalMoney(proposed.estimated_savings, provider)}/mo
                </div>
            </div>

            {/* Change List */}
            <div className="divide-y divide-white/[0.03]">
                {proposed.change_list.map((change, i) => {
                    const Icon = CHANGE_ICONS[change.change_type] ?? AlertTriangle;
                    const riskStyle = RISK_COLORS[change.risk_level] ?? RISK_COLORS.medium;

                    return (
                        <div key={i} className="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-white/[0.03]">
                            <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${change.monthly_savings > 0 ? 'text-emerald-400' : 'text-amber-400'
                                }`} />
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="rounded-full border border-white/10 bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase text-slate-400">
                                        {change.change_type.replace(/_/g, ' ')}
                                    </span>
                                    <span className="text-xs text-white font-medium truncate">{change.resource_name}</span>
                                    <span className="text-[10px] text-slate-600 font-mono">{change.resource_id}</span>
                                </div>
                                <p className="text-xs text-slate-400 mb-1">
                                    {change.current_state} → {change.proposed_state}
                                </p>
                                <p className="text-[10px] text-slate-500">{change.reasoning}</p>
                            </div>
                            <div className="flex flex-col items-end gap-1 shrink-0">
                                <span className={`text-xs font-medium ${change.monthly_savings > 0 ? 'text-emerald-400' : 'text-amber-400'
                                    }`}>
                                    {change.monthly_savings > 0 ? '-' : '+'}{formatProposalMoney(change.monthly_savings, provider)}/mo
                                </span>
                                <span className={`rounded-full px-1.5 py-0.5 text-[9px] ${riskStyle}`}>
                                    {change.risk_level} risk
                                </span>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Risk tradeoffs */}
            {proposed.risk_tradeoffs && (
                <div className="border-t border-white/10 bg-slate-950/30 px-4 py-3">
                    <p className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">Risk Assessment</p>
                    <p className="text-xs text-slate-400 leading-relaxed">{proposed.risk_tradeoffs}</p>
                </div>
            )}

            {/* Warnings */}
            {proposed.warnings.length > 0 && (
                <div className="px-4 py-2 border-t border-amber-500/10 bg-amber-500/5">
                    {proposed.warnings.map((w, i) => (
                        <p key={i} className="text-[10px] text-amber-400">{w.message}</p>
                    ))}
                </div>
            )}
        </div>
    );
}
