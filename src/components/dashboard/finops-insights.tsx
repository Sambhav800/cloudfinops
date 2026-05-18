'use client';

import { motion } from "framer-motion";
import { Leaf, Trees, Truck, Server, Network, ShieldCheck, BrainCircuit, TrendingUp } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { formatInrCurrency } from "@/lib/resources/contract";

interface FinOpsInsightsProps {
    stats: {
        monthlySavings: number;
        annualSavings: number;
        wasteSources: {
            idleEC2: number;
            orphanedEBS: number;
            unusedIPs: number;
        };
        confidence: {
            score: number;
        };
        carbon: {
            monthly: number;
            annual: number;
            trees: number;
            cars: number;
        };
        infraHealth: {
            idleEC2: number;
            unattachedEBS: number;
            unusedIPs: number;
        };
    } | null;
}

const CHART_COLORS = {
    spend: '#6366f1',
    savings: '#10b981',
    waste: '#f43f5e',
    warning: '#f59e0b',
    compute: '#06b6d4',
    database: '#8b5cf6',
    network: '#3b82f6',
    storage: '#84cc16',
    security: '#ef4444',
    other: '#94a3b8',
} as const;

const container = {
    hidden: { opacity: 0 },
    show: {
        opacity: 1,
        transition: {
            staggerChildren: 0.1
        }
    }
};

const item = {
    hidden: { y: 20, opacity: 0 },
    show: { y: 0, opacity: 1 }
};

function formatMoney(value: number): string {
    return formatInrCurrency(value, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });
}

export function FinOpsInsights({
    stats,
    activeProvider = 'all',
}: FinOpsInsightsProps & { activeProvider?: 'all' | 'aws' | 'azure' | 'gcp' }) {
    if (!stats) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                {[1, 2, 3, 4].map((card) => (
                    <div
                        key={card}
                        className="rounded-2xl border border-white/10 border-t-2 border-t-slate-700 bg-slate-900/50 p-6 backdrop-blur-xl"
                    >
                        <div className="mb-4 flex items-center gap-3">
                            <Skeleton className="h-10 w-10 rounded-xl bg-slate-800" />
                            <Skeleton className="h-5 w-32 bg-slate-800" />
                        </div>
                        <div className="space-y-3">
                            <Skeleton className="h-8 w-24 bg-slate-700" />
                            <Skeleton className="h-4 w-full bg-slate-800" />
                            <Skeleton className="h-4 w-5/6 bg-slate-800" />
                            <Skeleton className="h-4 w-2/3 bg-slate-800" />
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    const providerCosts =
        ((stats as { providerCosts?: Array<{ provider: string; savings: number }> }).providerCosts ?? []);
    const activeProviderStats =
        activeProvider === 'all'
            ? null
            : providerCosts.find((providerCost) => providerCost.provider.toLowerCase() === activeProvider) ?? null;
    const filteredStats = activeProvider === 'all'
        ? stats
        : {
            ...stats,
            monthlySavings: activeProviderStats?.savings ?? 0,
            annualSavings: (activeProviderStats?.savings ?? 0) * 12,
        };
    const totalResources = (stats as { totalResources?: number }).totalResources ?? 0;

    return (
        <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8"
        >
            {/* 1. Cost Optimization */}
            <motion.div variants={item} className="bg-slate-900/50 border border-white/10 border-t-2 border-t-emerald-500/50 border-l-2 border-l-emerald-500/50 rounded-2xl p-6 relative overflow-hidden group hover:border-emerald-500/50 transition-colors">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                    <TrendingUp className="w-24 h-24 text-emerald-500" />
                </div>
                <div className="relative z-10">
                    <div className="flex items-center gap-2 mb-4">
                        <div className="p-2 bg-emerald-500/15 rounded-lg">
                            <Server className="w-5 h-5 text-emerald-400" />
                        </div>
                        <h3 className="text-lg font-bold text-white">Cost Optimization</h3>
                    </div>

                    <div className="space-y-4">
                        <div>
                            <p className="text-slate-400 text-sm">Potential Monthly Savings</p>
                            <p className="text-2xl font-bold text-white">{formatMoney(filteredStats.monthlySavings)}</p>
                        </div>
                        <div>
                            <p className="text-slate-400 text-sm">Annualized Savings</p>
                            <p className="text-xl font-semibold text-emerald-400">{formatMoney(filteredStats.annualSavings)}</p>
                        </div>

                        <div className="pt-4 border-t border-white/5 space-y-2">
                            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Primary Waste Sources</p>
                            <div className="flex justify-between text-sm">
                                <span className="text-slate-300">Idle Instances</span>
                                <span className="text-white font-mono">{filteredStats.wasteSources.idleEC2}%</span>
                            </div>
                            <div className="flex justify-between text-sm">
                                <span className="text-slate-300">Orphaned Disks</span>
                                <span className="text-white font-mono">{filteredStats.wasteSources.orphanedEBS}%</span>
                            </div>
                            <div className="flex justify-between text-sm">
                                <span className="text-slate-300">Unused IPs</span>
                                <span className="text-white font-mono">{filteredStats.wasteSources.unusedIPs}%</span>
                            </div>
                        </div>
                    </div>
                </div>
            </motion.div>

            {/* 2. AI Confidence */}
            <motion.div variants={item} className="bg-slate-900/50 border border-white/10 border-t-2 border-t-violet-500/50 border-l-2 border-l-violet-500/50 rounded-2xl p-6 relative overflow-hidden group hover:border-violet-500/50 transition-colors">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                    <BrainCircuit className="w-24 h-24 text-violet-500" />
                </div>
                <div className="relative z-10">
                    <div className="flex items-center gap-2 mb-4">
                        <div className="p-2 bg-violet-500/15 rounded-lg">
                            <ShieldCheck className="w-5 h-5 text-violet-400" />
                        </div>
                        <h3 className="text-lg font-bold text-white">AI Confidence</h3>
                    </div>

                    <div className="space-y-4">
                        <div className="flex items-center gap-4">
                            <div className="relative w-20 h-20 flex items-center justify-center">
                                <svg className="transform -rotate-90 w-20 h-20">
                                    <circle cx="40" cy="40" r="36" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-slate-800" />
                                    <circle cx="40" cy="40" r="36" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-violet-500" strokeDasharray={`${filteredStats.confidence.score * 2.26} 226`} />
                                </svg>
                                <span className="absolute text-xl font-bold text-white">{filteredStats.confidence.score}%</span>
                            </div>
                            <div>
                                <p className="text-slate-400 text-sm">Source</p>
                                <p className="text-white font-medium">Latest backend scan</p>
                            </div>
                        </div>

                        <p className="text-sm text-slate-400 leading-relaxed">
                            Analysis based on CPU utilization, network traffic, disk I/O, and uptime patterns.
                        </p>
                        <div className="px-3 py-2 bg-violet-500/10 rounded-lg border border-violet-500/20">
                            <p className="text-xs text-violet-300">
                                High confidence indicates statistically strong waste patterns.
                            </p>
                        </div>
                    </div>
                </div>
            </motion.div>

            {/* 3. Sustainability */}
            <motion.div variants={item} className="bg-slate-900/50 border border-white/10 border-t-2 border-t-teal-500/50 border-l-2 border-l-teal-500/50 rounded-2xl p-6 relative overflow-hidden group hover:border-teal-500/50 transition-colors">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                    <Leaf className="w-24 h-24 text-teal-500" />
                </div>
                <div className="relative z-10">
                    <div className="flex items-center gap-2 mb-4">
                        <div className="p-2 bg-teal-500/15 rounded-lg">
                            <Trees className="w-5 h-5 text-teal-400" />
                        </div>
                        <h3 className="text-lg font-bold text-white">Sustainability</h3>
                    </div>

                    <div className="space-y-4">
                        <div>
                            <p className="text-slate-400 text-sm">Potential CO₂ Reduction</p>
                            <p className="text-2xl font-bold text-white">{filteredStats.carbon.monthly} tons <span className="text-sm font-normal text-slate-500">/ mo</span></p>
                        </div>
                        <div>
                            <p className="text-slate-400 text-sm">Annual CO₂ Reduction</p>
                            <p className="text-xl font-semibold text-teal-400">{filteredStats.carbon.annual} tons</p>
                        </div>

                        <div className="pt-4 border-t border-white/5 space-y-3">
                            <div className="flex items-center gap-3">
                                <Leaf className="w-8 h-8 text-teal-500/80" />
                                <div>
                                    <p className="text-sm text-white">Planting ~{filteredStats.carbon.trees} trees</p>
                                    <p className="text-xs text-slate-500">per month equivalent</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <Truck className="w-8 h-8 text-indigo-500/80" />
                                <div>
                                    <p className="text-sm text-white">Removing {filteredStats.carbon.cars} cars</p>
                                    <p className="text-xs text-slate-500">from road annually</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </motion.div>

            {/* 4. Infrastructure Health */}
            <motion.div variants={item} className="bg-slate-900/50 border border-white/10 border-t-2 border-t-blue-500/50 border-l-2 border-l-blue-500/50 rounded-2xl p-6 relative overflow-hidden group hover:border-blue-500/50 transition-colors">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                    <Server className="w-24 h-24 text-blue-500" />
                </div>
                <div className="relative z-10">
                    <div className="flex items-center gap-2 mb-4">
                        <div className="p-2 bg-blue-500/15 rounded-lg">
                            <Network className="w-5 h-5 text-blue-400" />
                        </div>
                        <h3 className="text-lg font-bold text-white">Infra Health</h3>
                    </div>

                    <div className="space-y-2">
                        <HealthItem label="Idle Instances" value={filteredStats.infraHealth.idleEC2} color={CHART_COLORS.waste} total={totalResources} />
                        <HealthItem label="Unattached EBS" value={filteredStats.infraHealth.unattachedEBS} color={CHART_COLORS.warning} total={totalResources} />
                        <HealthItem label="Unused Elastic IPs" value={filteredStats.infraHealth.unusedIPs} color={CHART_COLORS.network} total={totalResources} />
                    </div>

                    <div className="mt-6 pt-4 border-t border-white/5">
                        <div className="px-3 py-2 bg-indigo-500/10 rounded-lg border border-indigo-500/20">
                            <p className="text-xs text-indigo-300 flex items-center gap-2">
                                <ShieldCheck className="w-3 h-3" />
                                Read-only access • No production risk
                            </p>
                        </div>
                    </div>
                </div>
            </motion.div>
        </motion.div>
    );
}

function HealthItem({ label, value, color, total }: { label: string, value: number, color: string, total?: number }) {
    const width = total && total > 0
        ? `${Math.min((value / total) * 100, 100)}%`
        : value > 0
            ? `${Math.min(value * 10, 100)}%`
            : '0%';

    return (
        <div className="rounded-lg border border-white/5 bg-black/20 p-3">
            <div className="mb-1.5 flex items-center justify-between">
                <span className="text-sm text-slate-300">{label}</span>
                <span className="text-sm font-bold text-white">{value}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                <div
                    className="h-full rounded-full"
                    style={{
                        width,
                        backgroundColor: color,
                    }}
                />
            </div>
        </div>
    );
}
