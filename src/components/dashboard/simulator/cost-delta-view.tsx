'use client';

import { motion } from 'framer-motion';
import {
    AlertTriangle,
    Calculator,
    CheckCircle2,
    TrendingDown,
    TrendingUp,
} from 'lucide-react';

import { BestPracticeFindings } from './best-practice-findings';
import { CoverageBar } from './coverage-bar';
import { FamilySpendDonut } from './family-spend-donut';
import { MonthlyAnnualWaterfall } from './monthly-annual-waterfall';
import { PolicyStatusCard } from './policy-status-card';
import { ResourceCostBars } from './resource-cost-bars';
import { UnestimatedList } from './unestimated-list';
import { formatInrCurrency, toDisplayInrAmount } from '@/lib/resources/contract';

export type SimulatorPricingSource =
    | 'exact_api'
    | 'heuristic_estimate'
    | 'usage_based'
    | 'unsupported';

export type SimulatorConfidence = 'high' | 'medium' | 'low';

export interface SimulatorResourceItem {
    resource_address: string;
    resource_type: string;
    action: 'create' | 'update' | 'delete' | 'no-op' | string;
    provider: 'aws' | 'azure' | 'gcp' | 'generic' | string;
    region: string | null;
    resource_family: 'compute' | 'storage' | 'network' | 'database' | 'serverless' | 'kubernetes' | 'other' | string;
    before_monthly: number;
    after_monthly: number;
    delta_monthly: number;
    hourly_rate: number | null;
    pricing_source: SimulatorPricingSource;
    pricing_basis: string | null;
    confidence: SimulatorConfidence;
    notes: string | null;
    source_provenance: string | null;
    name?: string;
    type?: string;
    before?: number;
    after?: number;
}

export interface SimulatorUnestimatedResource {
    resource_address: string;
    resource_type: string;
    provider: string;
    region?: string | null;
    action: string;
    reason: string;
}

export interface SimulatorFinding {
    resource_address: string;
    finding_id: string;
    severity: 'critical' | 'high' | 'medium' | 'low';
    monthly_impact: number | null;
    annual_impact: number | null;
    evidence: string;
    remediation: string;
    confidence: SimulatorConfidence;
}

export interface SimulatorPolicyResult {
    status: 'pass' | 'warn' | 'fail';
    blocking_reasons: string[];
    warnings: string[];
    markdown_summary: string;
}

export interface SimulatorSummary {
    total_resources: number;
    priced_resources: number;
    exact_resources: number;
    exact_pricing_resources: number;
    estimated_resources: number;
    usage_based_resources: number;
    unsupported_resources: number;
    unestimated_resources: number;
}

export interface SimulatorData {
    schema_version?: '2026-04-simulator-v2';
    currency: string;
    monthly: {
        before: number;
        after: number;
        delta: number;
    };
    annual: {
        before: number;
        after: number;
        delta: number;
    };
    summary: SimulatorSummary;
    resources: SimulatorResourceItem[];
    unestimated_resources: SimulatorUnestimatedResource[];
    findings: SimulatorFinding[];
    policy: SimulatorPolicyResult | null;
    before: number;
    after: number;
    delta_monthly_cost: number;
}

interface CostDeltaViewProps {
    data?: SimulatorData | null;
    isLoading?: boolean;
}

function formatMonthlyAmount(value: number, currency = 'USD'): string {
    return formatInrCurrency(toDisplayInrAmount(value, currency), {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function formatAnnualAmount(value: number, currency = 'USD'): string {
    return `${formatInrCurrency(toDisplayInrAmount(value, currency), {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    })}/yr`;
}

function getPricingSourceBadge(source: SimulatorPricingSource): {
    label: string;
    className: string;
} {
    switch (source) {
        case 'exact_api':
            return {
                label: 'Exact',
                className: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20',
            };
        case 'heuristic_estimate':
            return {
                label: 'Estimated',
                className: 'bg-amber-500/15 text-amber-400 border border-amber-500/20',
            };
        case 'usage_based':
            return {
                label: 'Usage-Based',
                className: 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/20',
            };
        default:
            return {
                label: 'Unsupported',
                className: 'bg-slate-500/15 text-slate-400 border border-white/10',
            };
    }
}

function getProviderBadge(provider: string): {
    label: string;
    className: string;
} {
    const normalized = provider.toLowerCase();
    if (normalized === 'aws') {
        return {
            label: 'AWS',
            className: 'bg-amber-500/15 text-amber-400 border border-amber-500/20',
        };
    }
    if (normalized === 'azure') {
        return {
            label: 'Azure',
            className: 'bg-sky-500/15 text-sky-400 border border-sky-500/20',
        };
    }
    if (normalized === 'gcp') {
        return {
            label: 'GCP',
            className: 'bg-blue-500/15 text-blue-400 border border-blue-500/20',
        };
    }
    return {
        label: provider ? provider.toUpperCase() : 'GENERIC',
        className: 'bg-slate-500/15 text-slate-400 border border-white/10',
    };
}

function StatCard({
    label,
    value,
    detail,
    accentClass,
    valueClass = 'text-white',
}: {
    label: string;
    value: string;
    detail: string;
    accentClass: string;
    valueClass?: string;
}) {
    return (
        <div className={`min-w-0 rounded-2xl border border-white/10 border-t-2 ${accentClass} bg-slate-900/50 p-5 shadow-2xl shadow-black/40 sm:p-6`}>
            <p className="text-sm text-slate-400">{label}</p>
            <p className={`mt-2 break-words text-[clamp(1.35rem,2vw,1.875rem)] font-semibold leading-tight ${valueClass}`}>
                {value}
            </p>
            <p className="mt-1 text-sm text-slate-500">{detail}</p>
        </div>
    );
}

export function CostDeltaView({ data, isLoading }: CostDeltaViewProps) {
    if (isLoading) {
        return (
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
            >
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
                    {[1, 2, 3, 4].map((item) => (
                        <div
                            key={item}
                            className="h-32 animate-pulse rounded-2xl border border-white/10 border-t-2 border-t-indigo-500/60 bg-slate-900/50 p-6 shadow-2xl shadow-black/40"
                        >
                            <div className="h-4 w-32 rounded bg-slate-800" />
                            <div className="mt-4 h-8 w-24 rounded bg-slate-700/50" />
                        </div>
                    ))}
                </div>
                <div className="h-96 animate-pulse rounded-2xl border border-white/10 bg-slate-900/50 p-8 shadow-2xl shadow-black/40">
                    <div className="mb-8 h-6 w-48 rounded bg-slate-800" />
                    <div className="space-y-4">
                        {[1, 2, 3].map((item) => (
                            <div key={item} className="h-24 w-full rounded-2xl bg-slate-800/40" />
                        ))}
                    </div>
                </div>
            </motion.div>
        );
    }

    if (!data) {
        return (
            <div className="flex h-64 flex-col items-center justify-center rounded-2xl border border-white/10 bg-slate-900/50 p-8 text-center shadow-2xl shadow-black/40">
                <Calculator className="mb-4 h-12 w-12 text-slate-600" />
                <h3 className="text-base font-semibold text-white">Awaiting Simulation</h3>
                <p className="mt-2 max-w-md text-sm text-slate-400">
                    Upload or paste a Terraform plan to see exact pricing matches,
                    heuristic estimates, and unsupported resources in one view.
                </p>
            </div>
        );
    }

    const delta = data.monthly.delta;
    const sourceCurrency = data.currency || 'USD';
    const percentChange =
        data.monthly.before > 0
            ? ((delta / data.monthly.before) * 100).toFixed(1)
            : delta > 0
              ? '100.0'
              : '0.0';
    const isIncrease = delta > 0;
    const modeledResources = Math.max(data.summary.total_resources, 1);
    const exactCoverage = Math.round((data.summary.exact_resources / modeledResources) * 100);
    const sortedResources = [...data.resources].sort(
        (left, right) => Math.abs(right.delta_monthly) - Math.abs(left.delta_monthly),
    );
    const maxDelta = Math.max(
        ...sortedResources.map((resource) => Math.abs(resource.delta_monthly)),
        1,
    );
    const hasMixedCoverage =
        data.summary.estimated_resources > 0 ||
        data.summary.usage_based_resources > 0 ||
        data.summary.unestimated_resources > 0;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
        >
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard
                    label="Current Monthly Cost"
                    value={formatMonthlyAmount(data.monthly.before, sourceCurrency)}
                    detail={formatAnnualAmount(data.annual.before, sourceCurrency)}
                    accentClass="border-t-slate-500/70"
                />
                <StatCard
                    label="Projected Monthly Cost"
                    value={formatMonthlyAmount(data.monthly.after, sourceCurrency)}
                    detail={formatAnnualAmount(data.annual.after, sourceCurrency)}
                    accentClass="border-t-indigo-500/70"
                />
                <div className={`min-w-0 rounded-2xl border border-white/10 border-t-2 ${isIncrease ? 'border-t-rose-500/70' : 'border-t-emerald-500/70'} bg-slate-900/50 p-5 shadow-2xl shadow-black/40 sm:p-6`}>
                    <p className="text-sm text-slate-400">Monthly Delta</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                        <p className={`break-words text-[clamp(1.35rem,2vw,1.875rem)] font-semibold leading-tight ${isIncrease ? 'text-rose-400' : 'text-emerald-400'}`}>
                            {isIncrease ? '+' : ''}
                            {formatMonthlyAmount(delta, sourceCurrency)}
                        </p>
                        <span
                            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
                                isIncrease
                                    ? 'border border-rose-500/20 bg-rose-500/15 text-rose-400'
                                    : 'border border-emerald-500/20 bg-emerald-500/15 text-emerald-400'
                            }`}
                        >
                            {isIncrease ? (
                                <TrendingUp className="h-3.5 w-3.5" />
                            ) : (
                                <TrendingDown className="h-3.5 w-3.5" />
                            )}
                            {percentChange}%
                        </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-500">
                        {formatAnnualAmount(Math.abs(data.annual.delta), sourceCurrency)} annual swing
                    </p>
                </div>
                <StatCard
                    label="Pricing Coverage"
                    value={`${exactCoverage}%`}
                    detail={`${data.summary.exact_resources} exact, ${data.summary.estimated_resources} estimated`}
                    accentClass="border-t-amber-500/70"
                />
            </div>

            <div className={`rounded-2xl border p-5 shadow-2xl shadow-black/30 ${
                hasMixedCoverage
                    ? 'border-amber-500/15 bg-amber-500/5'
                    : 'border-emerald-500/15 bg-emerald-500/5'
            }`}>
                <div className="flex items-start gap-3">
                    {hasMixedCoverage ? (
                        <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-400" />
                    ) : (
                        <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-400" />
                    )}
                    <div className="space-y-1">
                        <p className="font-medium text-white">
                            {hasMixedCoverage ? 'Pricing coverage includes estimates' : 'Exact pricing coverage is strong'}
                        </p>
                        <p className="text-sm text-slate-400">
                            CloudFinOps priced{' '}
                            <span className="text-white">{data.summary.priced_resources}</span> of{' '}
                            <span className="text-white">{data.summary.total_resources}</span> resources,
                            including <span className="text-white">{data.summary.exact_resources}</span> exact
                            matches, <span className="text-white">{data.summary.estimated_resources}</span>{' '}
                            estimates, and <span className="text-white">{data.summary.usage_based_resources}</span>{' '}
                            usage-based rows.{' '}
                            <span className="text-white">{data.summary.unestimated_resources}</span> resources
                            were not priced and are listed below.
                        </p>
                    </div>
                </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl shadow-black/40">
                <CoverageBar summary={data.summary} />
            </div>

            <PolicyStatusCard policy={data.policy} />

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                <div className="min-w-0 rounded-2xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl shadow-black/40">
                    <div className="mb-5">
                        <h3 className="text-base font-semibold text-white">Monthly And Annual Impact</h3>
                        <p className="mt-1 text-sm text-slate-400">
                            Current and projected cost impact from the priced resources.
                        </p>
                    </div>
                    <MonthlyAnnualWaterfall data={data} />
                </div>
                <div className="min-w-0 rounded-2xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl shadow-black/40">
                    <div className="mb-5">
                        <h3 className="text-base font-semibold text-white">Projected Spend By Family</h3>
                        <p className="mt-1 text-sm text-slate-400">
                            Spend mix across compute, storage, network, database, and other families.
                        </p>
                    </div>
                    <FamilySpendDonut resources={data.resources} />
                </div>
            </div>

            <BestPracticeFindings findings={data.findings} />

            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl shadow-black/40">
                <div className="mb-5 flex flex-col gap-2 xl:flex-row xl:items-start xl:justify-between">
                    <div>
                        <h3 className="text-base font-semibold text-white">Resource Cost Delta</h3>
                        <p className="mt-1 text-sm text-slate-400">
                            Before and after cost by resource, sorted by monthly impact.
                        </p>
                    </div>
                    <p className="text-xs text-slate-500">
                        {data.summary.priced_resources} of {data.summary.total_resources} resources priced
                    </p>
                </div>
                {data.resources.length === 0 ? (
                    <div className="flex h-48 items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-6 text-center">
                        <div className="space-y-2">
                            <Calculator className="mx-auto h-10 w-10 text-slate-700" />
                            <p className="text-slate-400">No priced resources found in this plan.</p>
                            <p className="text-sm text-slate-500">
                                Unsupported resources are still listed below with the reason pricing was skipped.
                            </p>
                        </div>
                    </div>
                ) : (
                    <ResourceCostBars resources={data.resources} />
                )}
            </div>

            <UnestimatedList resources={data.unestimated_resources} />

            {sortedResources.length > 0 ? (
                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl shadow-black/40">
                    <div className="mb-5">
                        <h3 className="text-base font-semibold text-white">Resource Details</h3>
                        <p className="mt-1 text-sm text-slate-400">
                            Exact, estimated, and usage-based rows remain labeled by source.
                        </p>
                    </div>
                    <div className="space-y-4">
                        {sortedResources.map((resource, index) => {
                            const deltaWidth = Math.max(
                                8,
                                Math.round((Math.abs(resource.delta_monthly) / maxDelta) * 100),
                            );
                            const sourceBadge = getPricingSourceBadge(resource.pricing_source);
                            const providerBadge = getProviderBadge(resource.provider);

                            return (
                                <div
                                    key={`${resource.resource_address}-${index}`}
                                    className="space-y-3 rounded-2xl border border-white/5 bg-slate-800/30 p-4 transition-all hover:bg-slate-800/45"
                                >
                                    <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                                        <div className="min-w-0">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <p className="break-all text-sm font-medium text-white">
                                                    {resource.resource_address}
                                                </p>
                                                <span
                                                    className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${providerBadge.className}`}
                                                >
                                                    {providerBadge.label}
                                                </span>
                                                <span
                                                    className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${sourceBadge.className}`}
                                                >
                                                    {sourceBadge.label}
                                                </span>
                                                <span className="inline-flex rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                                                    {resource.resource_family}
                                                </span>
                                            </div>
                                            <p className="mt-1 break-all text-xs text-slate-500">
                                                {resource.resource_type} / {resource.region ?? 'global'} / {resource.action}
                                            </p>
                                            {resource.notes ? (
                                                <p className="mt-2 text-xs leading-5 text-slate-400">
                                                    {resource.notes}
                                                </p>
                                            ) : null}
                                        </div>

                                        <div className="text-left xl:text-right">
                                            <p className="font-mono text-sm text-slate-300">
                                                {formatMonthlyAmount(resource.before_monthly, sourceCurrency)} -&gt;{' '}
                                                {formatMonthlyAmount(resource.after_monthly, sourceCurrency)}
                                            </p>
                                            <p
                                                className={`mt-1 text-xs ${
                                                    resource.delta_monthly > 0
                                                        ? 'text-rose-400'
                                                        : resource.delta_monthly < 0
                                                          ? 'text-emerald-400'
                                                          : 'text-slate-500'
                                                }`}
                                            >
                                                {resource.delta_monthly > 0 ? '+' : ''}
                                                {formatMonthlyAmount(resource.delta_monthly, sourceCurrency)} / mo /{' '}
                                                {formatAnnualAmount(Math.abs(resource.delta_monthly) * 12, sourceCurrency)}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="h-2 overflow-hidden rounded-full bg-slate-950/70">
                                        <div
                                            className={`h-full rounded-full ${
                                                resource.delta_monthly > 0
                                                    ? 'bg-rose-500/80'
                                                    : resource.delta_monthly < 0
                                                      ? 'bg-emerald-500/80'
                                                      : 'bg-slate-600'
                                            }`}
                                            style={{ width: `${deltaWidth}%` }}
                                        />
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            ) : null}
        </motion.div>
    );
}
