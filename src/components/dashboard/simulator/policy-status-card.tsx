'use client';

import { AlertTriangle, CheckCircle2, ShieldAlert, XCircle } from 'lucide-react';

import type { SimulatorPolicyResult } from './cost-delta-view';

type PolicyStatusCardProps = {
    policy: SimulatorPolicyResult | null;
};

const STATUS_COPY = {
    pass: {
        title: 'Policy passed',
        iconClass: 'text-emerald-400',
        cardClass: 'border-emerald-500/20 bg-emerald-500/10',
        badgeClass: 'border-emerald-500/20 bg-emerald-500/15 text-emerald-300',
    },
    warn: {
        title: 'Policy warnings',
        iconClass: 'text-amber-400',
        cardClass: 'border-amber-500/20 bg-amber-500/10',
        badgeClass: 'border-amber-500/20 bg-amber-500/15 text-amber-300',
    },
    fail: {
        title: 'Policy failed',
        iconClass: 'text-rose-400',
        cardClass: 'border-rose-500/20 bg-rose-500/10',
        badgeClass: 'border-rose-500/20 bg-rose-500/15 text-rose-300',
    },
} as const;

export function PolicyStatusCard({ policy }: PolicyStatusCardProps) {
    if (!policy) {
        return null;
    }

    const status = policy.status === 'fail' || policy.status === 'warn' ? policy.status : 'pass';
    const copy = STATUS_COPY[status];
    const Icon = status === 'pass' ? CheckCircle2 : status === 'warn' ? AlertTriangle : XCircle;
    const messages = status === 'fail' ? policy.blocking_reasons : policy.warnings;

    return (
        <div className={`rounded-2xl border p-5 shadow-2xl shadow-black/30 ${copy.cardClass}`}>
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="flex items-start gap-3">
                    <div className="rounded-xl border border-white/10 bg-slate-950/40 p-2">
                        <Icon className={`h-5 w-5 ${copy.iconClass}`} />
                    </div>
                    <div>
                        <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-base font-semibold text-white">{copy.title}</h3>
                            <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${copy.badgeClass}`}>
                                {status}
                            </span>
                        </div>
                        <p className="mt-1 text-sm text-slate-400">
                            Deterministic cost policy evaluation for this Terraform plan.
                        </p>
                    </div>
                </div>
                <ShieldAlert className="hidden h-6 w-6 text-slate-700 lg:block" />
            </div>

            {messages.length > 0 ? (
                <div className="mt-4 space-y-2">
                    {messages.map((message, index) => (
                        <div
                            key={`${message}-${index}`}
                            className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2 text-sm text-slate-300"
                        >
                            {message}
                        </div>
                    ))}
                </div>
            ) : (
                <p className="mt-4 rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2 text-sm text-slate-300">
                    All configured policy checks passed.
                </p>
            )}
        </div>
    );
}
