'use client';

import { useState, useEffect } from 'react';
import { 
    Card, 
    Grid, 
    Title, 
    Text, 
    DonutChart, 
    Badge, 
    Table,
    TableHead,
    TableRow,
    TableHeaderCell,
    TableBody,
    TableCell
} from '@tremor/react';
import { 
    PiggyBank, 
    AlertTriangle, 
    TrendingUp, 
    Sparkles, 
    Calendar, 
    ArrowUpRight,
    ShieldCheck
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { CloudCommitment, FinanceCommitmentsResponse } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';
import Link from 'next/link';
import { formatInrCurrency, toDisplayInrAmount } from '@/lib/resources/contract';

const valueFormatter = (number: number) =>
    formatInrCurrency(toDisplayInrAmount(number, "USD"));

type CommitmentScenario = {
    label: string;
    commitment_pct: number;
    monthly_commitment_usd: number;
    monthly_saving_usd: number;
    annual_saving_usd: number;
    effective_discount_pct: number;
    over_commitment_risk_pct: number;
    risk_level: "Low" | "Medium" | "High";
    term_years: number;
};

type CommitmentRecommendationResponse = {
    status: "ready" | "insufficient_history" | "no_spend_data";
    message?: string | null;
    days_available?: number | null;
    analysis_basis_days?: number | null;
    forecast_eom_spend_usd?: number | null;
    scenarios?: CommitmentScenario[];
    recommended_scenario?: CommitmentScenario | null;
};

const surfaceClassName = "rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl shadow-2xl";
const tableSurfaceClassName = "overflow-hidden rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur-xl shadow-2xl";

function CommitmentsSkeleton() {
    return (
        <div className="space-y-8 animate-pulse">
            <Grid numItems={1} numItemsLg={3} className="gap-8">
                {[1, 2, 3].map((i) => (
                    <Card key={i} className={`${surfaceClassName} h-64`}>
                        <Skeleton className="h-6 w-32 bg-slate-800 mb-6" />
                        <div className="flex justify-center mb-6">
                            <Skeleton className="h-32 w-32 rounded-full bg-slate-800" />
                        </div>
                        <Skeleton className="h-4 w-full bg-slate-800" />
                    </Card>
                ))}
            </Grid>
            <div className="space-y-4">
                <Skeleton className="h-8 w-64 bg-slate-800" />
                <Card className={`${tableSurfaceClassName} p-0`}>
                    <div className="h-12 bg-white/5 border-b border-white/10" />
                    {[1, 2, 3, 4, 5].map((i) => (
                        <div key={i} className="h-16 border-b border-white/5 last:border-0" />
                    ))}
                </Card>
            </div>
        </div>
    );
}

export default function CommitmentsPage() {
    const [commitments, setCommitments] = useState<CloudCommitment[]>([]);
    const [recommendation, setRecommendation] = useState<CommitmentRecommendationResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const loadData = async () => {
            setLoading(true);
            setError(null);

            try {
                const [commitmentsResponse, recommendationResponse] = await Promise.all([
                    fetch("/api/finance/commitments", { cache: "no-store" }),
                    fetch("/api/finance/commitment-recommendation", { cache: "no-store" }),
                ]);

                if (!commitmentsResponse.ok) {
                    const payload = await commitmentsResponse.json().catch(() => ({}));
                    setError(
                        typeof payload?.detail === "string"
                            ? payload.detail
                            : "Failed to load commitments"
                    );
                    setCommitments([]);
                } else {
                    const payload = await commitmentsResponse.json() as FinanceCommitmentsResponse;
                    setCommitments(payload.commitments ?? []);
                }

                if (recommendationResponse.ok) {
                    const payload = await recommendationResponse.json();
                    setRecommendation(payload as CommitmentRecommendationResponse);
                } else {
                    setRecommendation(null);
                }
            } catch (requestError) {
                setError(
                    requestError instanceof Error
                        ? requestError.message
                        : "Failed to load commitments"
                );
            } finally {
                setLoading(false);
            }
        };
        void loadData();
    }, []);

    const formatCommitment = (item: CloudCommitment) => {
        const endDate = new Date(item.end_date);
        const now = new Date();
        const diffTime = endDate.getTime() - now.getTime();
        const daysRemaining = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        let status: 'Critical' | 'Warning' | 'Stable' = 'Stable';
        if (daysRemaining < 30) status = 'Critical';
        else if (daysRemaining < 90) status = 'Warning';

        return {
            ...item,
            daysRemaining,
            displayStatus: status,
            endDateStr: endDate.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
        };
    };

    const formattedCommitments = commitments.map(formatCommitment);
    const activeCommitments = formattedCommitments.filter(c => c.status === 'active');
    const hasCommitments = activeCommitments.length > 0;
    const recommendedScenario = recommendation?.status === 'ready'
        ? recommendation.recommended_scenario ?? null
        : null;
    const coveragePct = recommendedScenario?.commitment_pct ?? 0;
    const forecastSpend = recommendation?.forecast_eom_spend_usd ?? 0;
    const coveredSpend = recommendedScenario?.monthly_commitment_usd ?? 0;
    const uncoveredSpend = Math.max(forecastSpend - coveredSpend, 0);
    const hasCoverageData = Boolean(
        recommendation?.status === 'ready'
        && recommendedScenario
        && forecastSpend > 0
    );
    const coverageEmptyStateMessage = recommendation?.message
        || 'Connect a cloud account and run a scan to see coverage data';
    
    // Summary calculations
    const avgUtilization = activeCommitments.length > 0 
        ? Math.round(activeCommitments.reduce((acc, c) => acc + c.utilization_pct, 0) / activeCommitments.length)
        : 0;
    
    const totalMonthlySavings = activeCommitments.reduce((acc, c) => acc + c.savings_amount, 0);
    const totalWaste = activeCommitments.reduce((acc, c) => acc + (c.commitment_amount * (1 - c.utilization_pct / 100)), 0);

    const coverageData = hasCoverageData
        ? [
            { name: 'Covered Spend', value: coveredSpend },
            { name: 'On-Demand (Optimizable)', value: uncoveredSpend }
        ]
        : [];
    const historyDays = recommendation?.analysis_basis_days ?? recommendation?.days_available ?? 0;
    const gapAnalysisRows = hasCoverageData
        ? (recommendation?.scenarios ?? []).slice(0, 3).map((scenario) => {
            const tone = scenario.risk_level === 'High'
                ? 'rose'
                : scenario.risk_level === 'Medium'
                    ? 'amber'
                    : 'emerald';
            return {
                label: `${scenario.label} ${scenario.term_years}-year`,
                detail: scenario.label === recommendedScenario?.label
                    ? `${valueFormatter(scenario.monthly_commitment_usd)} / mo covered`
                    : `${valueFormatter(scenario.monthly_saving_usd)} / mo savings`,
                width: `${Math.min(scenario.commitment_pct, 100)}%`,
                barClassName: tone === 'rose'
                    ? 'bg-rose-500'
                    : tone === 'amber'
                        ? 'bg-amber-500'
                        : 'bg-emerald-500',
                textClassName: tone === 'rose'
                    ? 'text-rose-400'
                    : tone === 'amber'
                        ? 'text-amber-400'
                        : 'text-emerald-400',
            };
        })
        : [];

    return (
        <main className="p-6 md:p-10 w-full bg-slate-950 min-h-screen text-slate-200">
            {/* Force Chart Text to White */}
            <style jsx global>{`
                .recharts-text { fill: #ffffff !important; font-weight: 600 !important; font-size: 12px !important; }
                .recharts-cartesian-axis-tick-value { fill: #cbd5e1 !important; }
                .recharts-default-tooltip { background-color: #0f172a !important; border-color: #334155 !important; }
                span.tremor-content-emphasis { color: #ffffff !important; }
                p.tremor-content { color: #94a3b8 !important; }
                text[dominant-baseline="central"] { fill: #ffffff !important; font-size: 24px !important; font-weight: bold !important; }
            `}</style>

            <div className="mb-8">
                <div className="flex items-center gap-3 mb-2">
                    <div className="p-2 bg-emerald-500/20 rounded-lg text-emerald-400">
                        <PiggyBank className="w-6 h-6" />
                    </div>
                    <h1 className="text-white text-3xl font-bold">Commitment Command Center</h1>
                </div>
                <p className="text-slate-400 text-lg">
                    Manage Reserved Instances, Savings Plans, and automated discount coverage.
                </p>
            </div>

            <AnimatePresence mode="wait">
                {loading ? (
                    <motion.div
                        key="loading"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                    >
                        <CommitmentsSkeleton />
                    </motion.div>
                ) : error ? (
                    <motion.div
                        key="error"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="rounded-2xl border border-white/10 bg-slate-900/50 p-12 text-center backdrop-blur-xl"
                    >
                        <AlertTriangle className="w-12 h-12 text-rose-500 mx-auto mb-4" />
                        <Title className="text-white">Failed to load commitments</Title>
                        <Text className="text-slate-400 mt-2">{error}</Text>
                        <button 
                            onClick={() => window.location.reload()}
                            className="mt-6 px-6 py-2 bg-indigo-600 text-white rounded-xl font-bold hover:bg-indigo-500 transition-colors"
                        >
                            Retry
                        </button>
                    </motion.div>
                ) : (
                    <motion.div
                        key="content"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                    >
                        <Grid numItems={1} numItemsLg={3} className="gap-8 mb-8">
                            {/* Total Coverage Score */}
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.1 }}
                                className="lg:col-span-1"
                            >
                                <Card className={`${surfaceClassName} h-full`}>
                                    <div className="flex items-center justify-between mb-4">
                                        <Title className="text-white text-lg font-semibold flex items-center gap-2">
                                            Coverage Score
                                        </Title>
                                    </div>
                                    {hasCoverageData ? (
                                        <>
                                            <div className="relative flex h-48 items-center justify-center rounded-2xl border border-white/10 bg-slate-900">
                                                <DonutChart
                                                    className="h-full w-full text-white"
                                                    data={coverageData}
                                                    category="value"
                                                    index="name"
                                                    colors={["emerald", "slate"]}
                                                    variant="donut"
                                                    showAnimation={true}
                                                    showLabel={false}
                                                    valueFormatter={valueFormatter}
                                                />
                                                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                                                    <span className="text-3xl font-bold text-white">{coveragePct}%</span>
                                                    <span className="text-xs text-slate-400">Covered</span>
                                                </div>
                                            </div>
                                        </>
                                    ) : (
                                        <div className="flex items-center justify-center h-48">
                                            <p className="text-slate-500 text-sm text-center">
                                                {coverageEmptyStateMessage}
                                            </p>
                                        </div>
                                    )}
                                </Card>
                            </motion.div>

                            {/* Utilization Rate */}
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.2 }}
                                className="lg:col-span-1"
                            >
                                <Card className={`${surfaceClassName} h-full`}>
                                    <div className="flex items-center justify-between mb-6">
                                        <Title className="text-white text-lg font-semibold">Utilization Rate</Title>
                                        <div className="rounded-full bg-indigo-500/10 p-2">
                                            <TrendingUp className="w-4 h-4 text-indigo-400" />
                                        </div>
                                    </div>
                                    {hasCommitments ? (
                                        <>
                                            <div className="flex flex-col items-center justify-center py-4">
                                                <div className="text-6xl font-bold text-white mb-2">{avgUtilization}%</div>
                                                <Text className="text-slate-400 text-center px-4">
                                                    Percentage of paid commitments actively offsetting running resources.
                                                </Text>
                                            </div>
                                            <div className="mt-8 grid grid-cols-2 gap-4">
                                                <div className="rounded-2xl border border-white/10 bg-slate-900 p-4">
                                                    <Text className="text-slate-500 text-xs uppercase">Waste</Text>
                                                    <Title className="text-rose-400 text-lg">{valueFormatter(totalWaste)}</Title>
                                                </div>
                                                <div className="rounded-2xl border border-white/10 bg-slate-900 p-4">
                                                    <Text className="text-slate-500 text-xs uppercase">Savings</Text>
                                                    <Title className="text-emerald-400 text-lg">{valueFormatter(totalMonthlySavings)}</Title>
                                                </div>
                                            </div>
                                        </>
                                    ) : (
                                        <div className="flex items-center justify-center h-48">
                                            <p className="text-slate-500 text-sm text-center">
                                                Connect a cloud account and run a scan to see commitment utilization
                                            </p>
                                        </div>
                                    )}
                                </Card>
                            </motion.div>

                            {/* AI Copilot Recommendation */}
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.3 }}
                                className="lg:col-span-1"
                            >
                                <Card className="relative h-full overflow-hidden rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-indigo-900/30 to-slate-900/50 p-6 backdrop-blur-xl shadow-2xl">
                                    <div className="absolute -top-12 -right-12 w-32 h-32 bg-indigo-500/10 rounded-full blur-3xl"></div>
                                    
                                    <div className="flex items-center gap-2 mb-6">
                                        <div className="p-2 bg-indigo-500/20 rounded-lg text-indigo-300">
                                            <Sparkles className="w-5 h-5" />
                                        </div>
                                        <Title className="text-white text-lg font-semibold">AI Copilot</Title>
                                    </div>

                                    {hasCoverageData ? (
                                        <div className="space-y-4 relative z-10">
                                            <p className="text-white text-sm leading-relaxed">
                                                Your modeled commitment coverage sits at <span className="text-indigo-400 font-bold">{coveragePct}%</span>, leaving <span className="text-rose-400 font-bold">{valueFormatter(uncoveredSpend)}</span> forecasted on-demand spend.
                                            </p>
                                            <div className="rounded-xl bg-black/40 border border-white/10 p-4">
                                                <p className="text-sm text-slate-300">
                                                    <span className="text-emerald-400 font-medium">Recommendation:</span> Move toward the <span className="text-white font-medium">{recommendedScenario?.label}</span> scenario by committing <span className="text-white font-medium">{valueFormatter(recommendedScenario?.monthly_commitment_usd ?? 0)}/mo</span>. Estimated savings are <span className="text-emerald-400 font-medium">{valueFormatter(recommendedScenario?.monthly_saving_usd ?? 0)}/mo</span> at <span className="text-white font-medium">{recommendedScenario?.risk_level.toLowerCase() || 'low'}</span> over-commitment risk.
                                                </p>
                                            </div>
                                            <Link href="/dashboard/optimizer" className="inline-flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300 font-medium mt-2">
                                                View Optimizer Scenarios <ArrowUpRight className="w-4 h-4" />
                                            </Link>
                                        </div>
                                    ) : (
                                        <div className="flex items-center justify-center h-48">
                                            <p className="text-slate-400 text-sm text-center px-6">
                                                {coverageEmptyStateMessage}
                                            </p>
                                        </div>
                                    )}
                                </Card>
                            </motion.div>
                        </Grid>

                        {/* Expiring Soon Table */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.4 }}
                        >
                            <div className="flex items-center justify-between mb-6">
                                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                    <Calendar className="w-6 h-6 text-amber-400" />
                                    Commitment Inventory
                                </h2>
                                <div className="flex gap-2">
                                    {formattedCommitments.filter(c => c.displayStatus === 'Critical').length > 0 && (
                                        <Badge color="rose" className="bg-rose-500/10 border-rose-500/20 text-rose-400">
                                            {formattedCommitments.filter(c => c.displayStatus === 'Critical').length} Critical
                                        </Badge>
                                    )}
                                    {formattedCommitments.filter(c => c.displayStatus === 'Warning').length > 0 && (
                                        <Badge color="amber" className="bg-amber-500/10 border-amber-500/20 text-amber-400">
                                            {formattedCommitments.filter(c => c.displayStatus === 'Warning').length} Expiring Soon
                                        </Badge>
                                    )}
                                </div>
                            </div>

                            <Card className={`${tableSurfaceClassName} p-0`}>
                                <Table>
                                    <TableHead className="bg-white/5">
                                        <TableRow className="border-white/5 hover:bg-transparent">
                                            <TableHeaderCell className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Commitment ID</TableHeaderCell>
                                            <TableHeaderCell className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Service / Resource</TableHeaderCell>
                                            <TableHeaderCell className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Region</TableHeaderCell>
                                            <TableHeaderCell className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">End Date</TableHeaderCell>
                                            <TableHeaderCell className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Monthly Savings</TableHeaderCell>
                                            <TableHeaderCell className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Utilization</TableHeaderCell>
                                            <TableHeaderCell className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">Action</TableHeaderCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {formattedCommitments.length > 0 ? (
                                            formattedCommitments.map((item) => (
                                                <TableRow key={item.id} className="border-b border-white/5 transition-colors hover:bg-white/[0.03] group">
                                                    <TableCell className="px-4 py-3 font-mono text-slate-300">{item.id}</TableCell>
                                                    <TableCell className="px-4 py-3 text-slate-300">
                                                        <div>
                                                            <div className="text-white font-medium">{item.name}</div>
                                                            <div className="text-slate-500 text-xs">{item.type} • {item.coverage_type}</div>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="px-4 py-3 text-slate-400">{item.region || 'Global'}</TableCell>
                                                    <TableCell className="px-4 py-3">
                                                        <div className="text-slate-300">{item.endDateStr}</div>
                                                        <div className={`text-xs ${item.daysRemaining < 45 ? 'text-rose-400 font-bold' : 'text-slate-500'}`}>
                                                            {item.daysRemaining > 0 ? `${item.daysRemaining} days left` : 'Expired'}
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="px-4 py-3 font-mono text-emerald-400">
                                                        {valueFormatter(item.savings_amount)}
                                                    </TableCell>
                                                    <TableCell className="px-4 py-3">
                                                        <div className="flex items-center gap-2">
                                                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border
                                                                ${item.utilization_pct < 70 ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 
                                                                  item.utilization_pct < 90 ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 
                                                                  'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'}
                                                            `}>
                                                                {item.utilization_pct}%
                                                            </span>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="px-4 py-3 text-right">
                                                        <Link href={`/dashboard/simulator?id=${item.id}&action=renew`}>
                                                            <button className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-medium text-white transition hover:bg-indigo-500">
                                                                Simulate Renewal
                                                            </button>
                                                        </Link>
                                                    </TableCell>
                                                </TableRow>
                                            ))
                                        ) : (
                                            <TableRow>
                                                <TableCell colSpan={7} className="py-12 text-center text-sm text-slate-500">
                                                    Connect a cloud account and run a scan to see commitments.
                                                </TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </Card>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Coverage Gap Analysis */}
            <div className="mt-12">
                <div className="flex items-center gap-2 mb-6">
                    <ShieldCheck className="w-6 h-6 text-indigo-400" />
                    <h2 className="text-xl font-bold text-white">Coverage Gap Analysis</h2>
                </div>
                {hasCoverageData ? (
                    <Card className="rounded-2xl border border-white/10 bg-slate-900/50 p-8 backdrop-blur-xl shadow-2xl">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                            <div>
                                <h3 className="text-lg font-semibold text-white mb-2">High Uncovered Spend</h3>
                                <p className="text-slate-400 text-sm">
                                    CloudFinOps modeled these commitment baselines from {historyDays} days of billing history. The bars below compare commitment coverage against the current forecast anchor.
                                </p>
                            </div>
                            <div className="md:col-span-2 space-y-4">
                                {gapAnalysisRows.map((row) => (
                                    <div key={row.label} className="space-y-2">
                                        <div className="flex justify-between text-sm">
                                            <span className="text-white font-medium">{row.label}</span>
                                            <span className={row.textClassName}>{row.detail}</span>
                                        </div>
                                        <div className="w-full bg-slate-800 rounded-full h-2">
                                            <div className={`${row.barClassName} h-2 rounded-full`} style={{ width: row.width }}></div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </Card>
                ) : (
                    <Card className="rounded-2xl border border-white/10 bg-slate-900/50 p-8 text-center backdrop-blur-xl shadow-2xl">
                        <Text className="text-slate-400 max-w-2xl mx-auto">
                            {coverageEmptyStateMessage}
                        </Text>
                    </Card>
                )}
            </div>
        </main>
    );
}
