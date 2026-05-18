'use client';

import { useState } from 'react';
import {
    ResponsiveContainer,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
} from 'recharts';
import { AlertOctagon, AlertCircle, Database, MapPin, Server, Layers } from 'lucide-react';
import { motion } from 'framer-motion';

import { formatInrCurrency } from '@/lib/resources/contract';

// --- Types ---
interface DashboardStats {
    totalSpend: number;
}

interface WasteCategory {
    category_name: string;
    value: number;
}

interface DailySpend {
    date: string;
    amount: number;
}

interface ResourceItem {
    id: string;
    name: string;
    type: string;
    region: string;
    cost: number;
    costLabel?: string;
    costStatus?: 'actual' | 'catalog_estimate' | 'unavailable' | 'no_direct_charge';
    provider?: string;
    status: string;
    risk?: string;
    metadata?: Record<string, unknown>;
    cpu_utilization?: number;
    memory_utilization?: number;
}

interface InventoryData {
    zombieAssets: ResourceItem[];
    orphanedStorage: ResourceItem[];
    shadowIT: ResourceItem[];
}

type InventoryTab = 'all' | 'zombie' | 'shadow' | 'orphaned';

interface DashboardOverviewProps {
    stats: DashboardStats | null;
    resources: ResourceItem[]; // Specific list
    wasteData: WasteCategory[];
    spendData: DailySpend[];
    inventory?: InventoryData; // New Prop
}

const CHART_STYLE = {
    backgroundColor: 'transparent',
    fontSize: 11,
    tickColor: '#475569',
    gridColor: 'rgba(255,255,255,0.06)',
    tooltipBg: '#0f172a',
    tooltipBorder: 'rgba(255,255,255,0.1)',
};

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

const WASTE_CATEGORY_COLORS: Record<string, string> = {
    'Zombie Resources': CHART_COLORS.waste,
    'Wasted Resources': '#fb923c',
    'Idle Resources': CHART_COLORS.warning,
    'Oversized Resources': '#a78bfa',
    'Orphaned Storage': CHART_COLORS.storage,
    'Unused IPs': CHART_COLORS.network,
};

const PROVIDER_BADGE_META: Record<string, { dotClassName: string; label: string; pillClassName: string }> = {
    aws: {
        label: 'AWS',
        dotClassName: 'bg-amber-400',
        pillClassName: 'border-amber-500/20 bg-amber-500/10 text-amber-300',
    },
    azure: {
        label: 'Azure',
        dotClassName: 'bg-sky-400',
        pillClassName: 'border-sky-500/20 bg-sky-500/10 text-sky-300',
    },
    gcp: {
        label: 'GCP',
        dotClassName: 'bg-blue-400',
        pillClassName: 'border-blue-500/20 bg-blue-500/10 text-blue-300',
    },
};

const valueFormatter = (number: number) => formatInrCurrency(number);
const compactValueFormatter = (number: number) =>
    formatInrCurrency(number, {
        notation: 'compact',
        minimumFractionDigits: 0,
        maximumFractionDigits: 1,
    });

function getInventoryCostClass(status?: ResourceItem['costStatus']) {
    if (status === 'actual') {
        return 'text-emerald-400';
    }
    if (status === 'no_direct_charge') {
        return 'text-slate-400';
    }
    return 'text-amber-400';
}

function getInventoryCostRank(status?: ResourceItem['costStatus']) {
    if (status === 'actual') {
        return 0;
    }
    if (status === 'catalog_estimate') {
        return 1;
    }
    if (status === 'unavailable') {
        return 2;
    }
    return 3;
}

function getProviderMeta(provider?: string) {
    return PROVIDER_BADGE_META[String(provider || '').toLowerCase()] ?? {
        label: 'Unknown',
        dotClassName: 'bg-slate-400',
        pillClassName: 'border-slate-500/20 bg-slate-500/10 text-slate-300',
    };
}

// --- Components ---

function _EmptyState({ title, subtitle, icon: Icon }: { title: string, subtitle: string, icon: React.ElementType }) {
    return (
        <div className="flex h-60 flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/5 p-6 text-center">
            <div className="mb-3 rounded-full bg-white/5 p-3">
                <Icon className="w-6 h-6 text-slate-400" />
            </div>
            <h4 className="text-white font-medium">{title}</h4>
            <p className="text-slate-500 text-sm mt-1">{subtitle}</p>
        </div>
    );
}

export function DashboardOverview({
    stats,
    resources,
    wasteData,
    spendData,
    inventory,
    activeProvider = 'all',
}: DashboardOverviewProps & { activeProvider?: 'all' | 'aws' | 'azure' | 'gcp' }) {
    const [activeTab, setActiveTab] = useState<InventoryTab>('all');
    const providerCosts =
        ((stats as { providerCosts?: Array<{ provider: string; spend: number }> } | null)?.providerCosts ?? []);
    const filteredStats = activeProvider === 'all'
        ? stats
        : stats
            ? {
                ...stats,
                totalSpend: providerCosts.find(
                    (providerCost) => providerCost.provider.toLowerCase() === activeProvider
                )?.spend ?? 0,
            }
            : null;
    const matchesActiveProvider = (provider?: string) =>
        activeProvider === 'all' || String(provider || '').toLowerCase() === activeProvider;
    const filteredInventory = inventory
        ? {
            zombieAssets: inventory.zombieAssets.filter((resource) =>
                matchesActiveProvider(resource.provider)
            ),
            orphanedStorage: inventory.orphanedStorage.filter((resource) =>
                matchesActiveProvider(resource.provider)
            ),
            shadowIT: inventory.shadowIT.filter((resource) =>
                matchesActiveProvider(resource.provider)
            ),
        }
        : undefined;
    const filteredResourceList = resources.filter((resource) =>
        matchesActiveProvider(resource.provider)
    );
    const spendChartData = spendData.map((entry) => ({
        date: String(entry.date || '').slice(-5),
        spend: Number(entry.amount || 0),
    }));
    const sortedWasteData = wasteData
        .filter((item: WasteCategory) => item.value > 0)
        .sort((left: WasteCategory, right: WasteCategory) => right.value - left.value);
    const visibleWasteData = sortedWasteData.slice(0, 6);
    const hasWaste = visibleWasteData.length > 0;
    const maxWasteValue = Math.max(...visibleWasteData.map((item: WasteCategory) => item.value), 1);
    const totalWasteExposure = sortedWasteData.reduce((total, item) => total + item.value, 0);
    const wasteExposureShare = filteredStats && filteredStats.totalSpend > 0
        ? Math.round((totalWasteExposure / filteredStats.totalSpend) * 1000) / 10
        : null;

    // Aggregate risky resources for filtered tabs
    const riskyResources = [
        ...(filteredInventory?.zombieAssets || []).map(r => ({ ...r, category: 'zombie' })),
        ...(filteredInventory?.shadowIT || []).map(r => ({ ...r, category: 'shadow' })),
        ...(filteredInventory?.orphanedStorage || []).map(r => ({ ...r, category: 'orphaned' }))
    ];

    // For "All Resources" tab, show ALL resources (passed from props), not just risky ones
    const displayResources = filteredResourceList.length > 0 ? filteredResourceList : riskyResources;

    const filteredResources = activeTab === 'all'
        ? displayResources
        : activeTab === 'zombie'
            ? (filteredInventory?.zombieAssets || [])
            : activeTab === 'shadow'
                ? (filteredInventory?.shadowIT || [])
                : (filteredInventory?.orphanedStorage || []);
    const visibleResources = [...filteredResources].sort((left, right) => {
        const rankDiff = getInventoryCostRank(left.costStatus) - getInventoryCostRank(right.costStatus);
        if (rankDiff !== 0) {
            return rankDiff;
        }
        return String(left.name || '').localeCompare(String(right.name || ''));
    });

    const tabs: Array<{ count: number; icon: React.ElementType; id: InventoryTab; label: string }> = [
        { id: 'all', label: 'All Resources', count: displayResources.length, icon: Layers },
        { id: 'zombie', label: 'Zombie Assets', count: filteredInventory?.zombieAssets?.length || 0, icon: AlertOctagon },
        { id: 'shadow', label: 'Shadow IT', count: filteredInventory?.shadowIT?.length || 0, icon: MapPin },
        { id: 'orphaned', label: 'Orphaned Storage', count: filteredInventory?.orphanedStorage?.length || 0, icon: Database },
    ];

    return (
        <div className="space-y-8">
            {/* Force Chart Text to White */}
            <style jsx global>{`
                .recharts-text { fill: #cbd5e1 !important; font-weight: 600 !important; font-size: 12px !important; }
                .recharts-cartesian-axis-tick-value { fill: #cbd5e1 !important; }
                .recharts-cartesian-grid line { stroke: rgba(255, 255, 255, 0.08) !important; }
                .recharts-default-tooltip { background-color: #0f172a !important; border-color: #334155 !important; }
            `}</style>

            {/* Charts Section */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">

                {/* Waste Distribution */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-2xl"
                    style={{ minHeight: '320px' }}
                >
                    <div className="h-full">
                        <div className="flex items-center justify-between mb-6">
                            <div>
                                <div className="flex items-center gap-2 text-lg font-semibold text-white">
                                    <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
                                        Live
                                    </span>
                                    <h3>Waste Distribution</h3>
                                </div>
                                <p className="text-xs text-slate-400">Optimization opportunities ranked by wasted monthly cost</p>
                            </div>
                        </div>

                        <div className="mt-4 space-y-4">
                            {hasWaste ? (
                                <>
                                    <div className="flex items-end justify-between rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
                                        <div>
                                            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                                                Estimated Waste Exposure
                                            </p>
                                            <p className="mt-2 text-3xl font-bold text-white">
                                                {valueFormatter(totalWasteExposure)}
                                            </p>
                                        </div>
                                        <p className="max-w-[180px] text-right text-xs text-slate-500">
                                            {wasteExposureShare !== null
                                                ? `${wasteExposureShare}% of current spend is mapped to waste categories.`
                                                : 'Calculated from the waste distribution already loaded for this dashboard.'}
                                        </p>
                                    </div>

                                    <div className="space-y-4">
                                        {visibleWasteData.map((item: WasteCategory, index: number) => {
                                            const color = WASTE_CATEGORY_COLORS[item.category_name] ?? CHART_COLORS.other;
                                            const width = Math.round((item.value / maxWasteValue) * 100);

                                            return (
                                                <div key={`${item.category_name}-${index}`} className="space-y-1">
                                                    <div className="flex items-center justify-between">
                                                        <span className="max-w-[160px] truncate text-xs text-slate-400">
                                                            {item.category_name}
                                                        </span>
                                                        <span className="ml-2 flex-shrink-0 text-xs font-mono text-white">
                                                            {valueFormatter(item.value)}
                                                        </span>
                                                    </div>
                                                    <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                                                        <div
                                                            className="h-full rounded-full transition-all duration-700"
                                                            style={{ width: `${width}%`, backgroundColor: color }}
                                                        />
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>

                                    {sortedWasteData.length > visibleWasteData.length && (
                                        <p className="text-xs text-slate-500">
                                            and {sortedWasteData.length - visibleWasteData.length} more
                                        </p>
                                    )}
                                </>
                            ) : (
                                <_EmptyState
                                    title="No waste detected"
                                    subtitle="Run a scan to identify optimization opportunities."
                                    icon={Layers}
                                />
                            )}
                        </div>
                    </div>
                </motion.div>

                {/* Daily Spend Trend */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-2xl"
                    style={{ minHeight: '320px' }}
                >
                    <div className="flex h-full flex-col">
                        <div className="flex items-center justify-between mb-2">
                            <div>
                                <h3 className="text-white font-semibold">Daily Spend Trend</h3>
                                <p className="text-slate-500 text-xs mt-0.5">
                                    Portfolio spend over time
                                </p>
                            </div>
                            <span className="flex items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-1 text-xs text-emerald-400">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                Live
                            </span>
                        </div>

                        {spendChartData.length === 0 ? (
                            <div className="mt-4 flex flex-1 items-center justify-center rounded-xl border border-dashed border-white/5 bg-white/[0.02]">
                                <p className="text-slate-500 text-sm">
                                    No spend history yet — run a scan to populate
                                </p>
                            </div>
                        ) : (
                            <div className="mt-4 flex-1 min-h-[240px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart
                                        data={spendChartData}
                                        margin={{ top: 4, right: 8, left: 8, bottom: 0 }}
                                    >
                                        <defs>
                                            <linearGradient id="spendGradient" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="#6366f1" stopOpacity={0.02} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid
                                            strokeDasharray="3 3"
                                            stroke={CHART_STYLE.gridColor}
                                            vertical={false}
                                        />
                                        <XAxis
                                            dataKey="date"
                                            tick={{ fill: CHART_STYLE.tickColor, fontSize: CHART_STYLE.fontSize }}
                                            axisLine={false}
                                            tickLine={false}
                                            interval="preserveStartEnd"
                                        />
                                        <YAxis
                                            tick={{ fill: CHART_STYLE.tickColor, fontSize: CHART_STYLE.fontSize }}
                                            axisLine={false}
                                            tickLine={false}
                                            tickFormatter={(value: number) => compactValueFormatter(value)}
                                            width={52}
                                        />
                                        <Tooltip
                                            contentStyle={{
                                                backgroundColor: CHART_STYLE.tooltipBg,
                                                border: `1px solid ${CHART_STYLE.tooltipBorder}`,
                                                borderRadius: '12px',
                                                fontSize: '12px',
                                            }}
                                            labelStyle={{ color: '#94a3b8' }}
                                            itemStyle={{ color: '#fff' }}
                                            formatter={(value: number) => [valueFormatter(Number(value)), 'Spend']}
                                        />
                                        <Area
                                            type="monotone"
                                            dataKey="spend"
                                            stroke="#6366f1"
                                            strokeWidth={2.5}
                                            fill="url(#spendGradient)"
                                            dot={false}
                                            activeDot={{ r: 4, fill: '#6366f1' }}
                                        />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        )}
                    </div>
                </motion.div>
            </div>

            {/* Inventory Intelligence Table */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
            >
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <Server className="w-6 h-6 text-emerald-400" />
                        Inventory Intelligence
                    </h2>
                </div>

                {/* Animated Tabs */}
                <div className="flex flex-wrap gap-2 mb-6 p-1 bg-white/5 rounded-xl border border-white/10 w-fit">
                    {tabs.map((tab) => {
                        const isActive = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`
                                    relative px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300
                                    flex items-center gap-2 z-10
                                    ${isActive ? 'text-white' : 'text-slate-400 hover:text-white hover:bg-white/5'}
                                `}
                            >
                                {isActive && (
                                    <motion.div
                                        layoutId="activeTab"
                                        className="absolute inset-0 bg-indigo-600 rounded-lg shadow-lg shadow-indigo-500/20"
                                        transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                                    />
                                )}
                                <span className="relative z-10 flex items-center gap-2">
                                    <tab.icon className="w-4 h-4" />
                                    {tab.label}
                                    <span className={`
                                        text-xs px-1.5 py-0.5 rounded-full 
                                        ${isActive ? 'bg-white/20 text-white' : 'bg-white/10 text-slate-400'}
                                    `}>
                                        {tab.count}
                                    </span>
                                </span>
                            </button>
                        )
                    })}
                </div>

                <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50 shadow-2xl backdrop-blur-xl">
                    <div className="overflow-x-auto">
                        <table className="w-full min-w-[1080px] table-fixed text-left border-collapse">
                            <thead>
                                <tr className="border-b border-white/10 bg-white/[0.03] text-xs uppercase tracking-wider text-slate-500">
                                    <th className="w-[30%] p-4 font-medium">Resource</th>
                                    <th className="w-[12%] p-4 font-medium">Provider</th>
                                    <th className="w-[22%] p-4 font-medium">Type</th>
                                    <th className="w-[13%] p-4 font-medium">Region</th>
                                    <th className="w-[11%] p-4 font-medium">Status</th>
                                    <th className="w-[12%] p-4 font-medium text-right">Cost Signal</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5 text-sm">
                                {visibleResources.length > 0 ? visibleResources.map((item) => {
                                    const providerMeta = getProviderMeta(item.provider);

                                    return (
                                        <motion.tr
                                            key={item.id}
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            className="group transition-colors hover:bg-white/[0.03]"
                                        >
                                            <td className="p-4">
                                                <div className="min-w-[220px]">
                                                    <p className="truncate font-medium text-slate-200 transition-colors group-hover:text-white">
                                                        {item.name || item.id}
                                                    </p>
                                                    <p className="mt-1 truncate text-xs font-mono text-slate-500">
                                                        {item.id}
                                                    </p>
                                                </div>
                                            </td>
                                            <td className="p-4">
                                                <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${providerMeta.pillClassName}`}>
                                                    <span className={`h-1.5 w-1.5 rounded-full ${providerMeta.dotClassName}`} />
                                                    {providerMeta.label}
                                                </span>
                                            </td>
                                            <td className="p-4 text-slate-400">
                                                <span className="inline-flex max-w-[220px] items-center rounded-full border border-white/10 bg-slate-800/70 px-2.5 py-1 text-xs font-medium text-slate-300">
                                                    {item.type}
                                                </span>
                                            </td>
                                            <td className="p-4 text-slate-400">
                                                <div className="flex items-center gap-2">
                                                    <span>{item.region}</span>
                                                    {activeTab === 'shadow' ? <AlertCircle className="h-3 w-3 text-amber-500" /> : null}
                                                </div>
                                            </td>
                                            <td className="p-4">
                                                <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${item.status === 'Healthy' || item.risk === 'Low'
                                                    ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-500'
                                                    : item.status === 'Shadow IT'
                                                        ? 'border-amber-500/20 bg-amber-500/10 text-amber-500'
                                                        : item.status === 'Orphaned'
                                                            ? 'border-orange-500/20 bg-orange-500/10 text-orange-500'
                                                            : 'border-rose-500/20 bg-rose-500/10 text-rose-500'}
                                            `}>
                                                    {item.status === 'Healthy' ? 'Healthy' : (item.risk || item.status)}
                                                </span>
                                            </td>
                                            <td className={`p-4 text-right font-mono ${getInventoryCostClass(item.costStatus)}`}>
                                                {item.costLabel || valueFormatter(item.cost)}
                                            </td>
                                        </motion.tr>
                                    );
                                }) : (
                                    <tr>
                                        <td colSpan={6} className="p-12 text-center text-slate-500">
                                            <div className="flex flex-col items-center gap-3">
                                                <div className="p-3 bg-white/5 rounded-full">
                                                    <CheckCircleIcon className="w-8 h-8 text-emerald-500/50" />
                                                </div>
                                                <p>No issues found in this category.</p>
                                            </div>
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </motion.div>
        </div>
    );
}

// Icon Helper
function CheckCircleIcon({ className }: { className?: string }) {
    return (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <path d="m9 11 3 3L22 4" />
        </svg>
    )
}
