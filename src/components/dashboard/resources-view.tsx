'use client';

import { useState } from "react";
import { formatInrCurrency, type CostStatus, type NormalizedStatus } from "@/lib/resources/contract";
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    Cell,
} from 'recharts';
import {
    Server,
    Cloud,
    Database,
    HardDrive,
    Cpu,
    Search,
    AlertOctagon,
    MapPin,
    ShieldAlert,
    Layers
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const resourceTypeIcons: Record<string, typeof Server> = {
    EC2: Server,
    RDS: Database,
    S3: HardDrive,
    EBS: HardDrive,
    EKS: Cpu,
    ElastiCache: Database,
    "Virtual Machine": Server,
    "Managed Disk": HardDrive,
    "Public IP Address": Cloud,
    "Network Security Group": ShieldAlert,
    "Network Interface": Layers,
    "Blob Storage": HardDrive,
};

const PROVIDER_COLORS: Record<string, string> = {
    aws: '#FF9900',
    azure: '#0078D4',
    gcp: '#4285F4',
};

const TYPE_COLORS: Record<string, string> = {
    Compute: '#06b6d4',
    Storage: '#84cc16',
    Database: '#8b5cf6',
    Network: '#3b82f6',
    Other: '#94a3b8',
};

const CATEGORY_COLORS: Record<string, string> = {
    Compute: '#06b6d4',
    Storage: '#84cc16',
    Database: '#8b5cf6',
    Network: '#3b82f6',
    Other: '#94a3b8',
};

const CHART_STYLE = {
    backgroundColor: 'transparent',
    fontSize: 11,
    tickColor: '#475569',
    gridColor: 'rgba(255,255,255,0.06)',
    tooltipBg: '#0f172a',
    tooltipBorder: 'rgba(255,255,255,0.1)',
};

const PROVIDER_BADGE_STYLES = {
    aws: { bg: 'bg-amber-500/15', text: 'text-amber-400', label: 'AWS' },
    azure: { bg: 'bg-blue-500/15', text: 'text-blue-400', label: 'Azure' },
    gcp: { bg: 'bg-red-500/15', text: 'text-red-400', label: 'GCP' },
} as const;
const RESOURCE_LEVEL_COST_UNAVAILABLE_LABEL = 'No resource-level cost match';
type ResourceTab = 'costTracked' | 'all' | 'zombie' | 'shadow' | 'orphaned';

interface Resource {
    id: string;
    resource_name: string;
    resource_type: string;
    provider: string;
    region: string;
    monthly_cost: number;
    monthly_cost_available: boolean;
    cost_status: CostStatus;
    cost_label: string;
    annual_cost_label: string;
    utilization: number | null;
    status: NormalizedStatus;
    waste_type: string | null;
    created_by: string;
    region_compliance: string;
    cpu_utilization?: number;
    memory_utilization?: number;
    storage_utilization?: number;
    metadata?: any;
}

function categorizeResourceType(resourceType: string) {
    const raw = (resourceType || '').toLowerCase();
    if (
        raw.includes('instance') ||
        raw.includes('ec2') ||
        raw.includes('vm') ||
        raw.includes('compute')
    ) {
        return 'compute';
    }

    if (
        raw.includes('disk') ||
        raw.includes('ebs') ||
        raw.includes('storage') ||
        raw.includes('bucket')
    ) {
        return 'storage';
    }

    if (
        raw.includes('sql') ||
        raw.includes('rds') ||
        raw.includes('database') ||
        raw.includes('cosmos')
    ) {
        return 'database';
    }

    if (
        raw.includes('network') ||
        raw.includes('vpc') ||
        raw.includes('subnet') ||
        raw.includes('ip') ||
        raw.includes('lb') ||
        raw.includes('balancer')
    ) {
        return 'network';
    }

    return 'other';
}

function UtilizationBar({ value, label }: { value: number; label: string }) {
    const color = value < 30 ? 'bg-emerald-500' : value < 70 ? 'bg-amber-500' : 'bg-rose-500';
    return (
        <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400 w-8">{label}</span>
            <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden min-w-[60px]">
                <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${value}%` }} />
            </div>
            <span className="text-white font-mono w-8 text-right">{value}%</span>
        </div>
    );
}

function CompactMetrics({ resource }: { resource: Resource }) {
    const type = resource.resource_type || '';
    const meta = resource.metadata || {};

    if (type.includes('Virtual Machine') || type.includes('VM')) {
        const cpu = resource.cpu_utilization || meta.cpu_utilization_avg || 0;
        const ram = resource.memory_utilization || meta.memory_utilization_avg || 0;
        return (
            <div className="space-y-1 min-w-[120px]">
                <UtilizationBar value={cpu} label="CPU" />
                <UtilizationBar value={ram} label="RAM" />
            </div>
        );
    }

    if (type.includes('Disk')) {
        const size = meta.disk_size_gb;
        const orphaned = meta.is_orphaned;
        return (
            <span className="text-xs text-slate-400">
                {size ? `${size} GB` : '—'}
                {orphaned && <span className="text-rose-400 ml-1">• Orphaned</span>}
            </span>
        );
    }

    if (type.includes('IP')) {
        return (
            <span className="text-xs font-mono text-indigo-400">
                {meta.ip_address || '—'}
            </span>
        );
    }

    return <span className="text-xs text-slate-500">—</span>;
}

function getStatusBadge(status: NormalizedStatus) {
    if (status === 'zombie') {
        return <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/20 bg-rose-500/10 px-2.5 py-1 text-xs font-medium text-rose-400"><AlertOctagon className="h-3.5 w-3.5" />Zombie</span>;
    }
    if (status === 'waste') {
        return <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-400"><AlertOctagon className="h-3.5 w-3.5" />Waste</span>;
    }
    if (status === 'non_compliant') {
        return <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/20 bg-rose-500/10 px-2.5 py-1 text-xs font-medium text-rose-400"><ShieldAlert className="h-3.5 w-3.5" />Non-Compliant</span>;
    }
    if (status === 'unknown') {
        return <span className="inline-flex items-center rounded-full border border-slate-500/20 bg-slate-500/10 px-2.5 py-1 text-xs font-medium text-slate-400">Unknown</span>;
    }
    return <span className="inline-flex items-center rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-400">Healthy</span>;
}

function getCostTextClass(status: CostStatus) {
    if (status === 'actual') {
        return 'text-emerald-400';
    }
    if (status === 'no_direct_charge') {
        return 'text-slate-400';
    }
    return 'text-amber-400';
}

function getCostSortRank(status: CostStatus) {
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

function toSearchText(value: unknown): string {
    if (typeof value === 'string') {
        return value.toLowerCase();
    }
    if (value == null) {
        return '';
    }
    return String(value).toLowerCase();
}

function toDisplayText(value: unknown, fallback: string): string {
    if (typeof value === 'string') {
        const trimmed = value.trim();
        return trimmed || fallback;
    }
    if (value == null) {
        return fallback;
    }
    const normalized = String(value).trim();
    return normalized || fallback;
}

function isCostTrackedResource(resource: Resource): boolean {
    return resource.cost_status === 'actual' || resource.cost_status === 'catalog_estimate';
}

export function ResourcesView({ initialResources }: { initialResources: Resource[] }) {
    const [searchQuery, setSearchQuery] = useState("");
    const [activeTab, setActiveTab] = useState<ResourceTab>('costTracked');
    const typeCounts = initialResources.reduce((acc: Record<string, number>, resource: Resource) => {
        const categoryKey = categorizeResourceType(resource.resource_type);
        const label = categoryKey.charAt(0).toUpperCase() + categoryKey.slice(1);
        acc[label] = (acc[label] || 0) + 1;
        return acc;
    }, {} as Record<string, number>);
    const typeCountData = Object.entries(
        initialResources.reduce((acc: Record<string, number>, resource: Resource) => {
            const categoryKey = categorizeResourceType(resource.resource_type);
            acc[categoryKey] = (acc[categoryKey] || 0) + 1;
            return acc;
        }, {} as Record<string, number>)
    )
        .map(([name, count]: [string, number]) => ({ name, count }))
        .sort((left: { name: string; count: number }, right: { name: string; count: number }) => right.count - left.count);
    const providers = ['aws', 'azure', 'gcp'];
    const typeKeys = ['compute', 'storage', 'database', 'network', 'other'];
    const byCloudData = providers
        .filter((provider: string) =>
            initialResources.some((resource: Resource) => (resource.provider || '').toLowerCase() === provider)
        )
        .map((provider: string) => {
            const providerResources = initialResources.filter(
                (resource: Resource) => (resource.provider || '').toLowerCase() === provider
            );
            const row: Record<string, string | number> = { provider };
            typeKeys.forEach((type: string) => {
                row[type] = providerResources.filter(
                    (resource: Resource) => categorizeResourceType(resource.resource_type) === type
                ).length;
            });
            return row;
        });

    const normalizedSearchQuery = toSearchText(searchQuery);
    const filteredResources = initialResources.filter((resource: Resource) =>
        toSearchText(resource.resource_name).includes(normalizedSearchQuery) ||
        toSearchText(resource.created_by).includes(normalizedSearchQuery)
    );

    const zombies = filteredResources.filter((resource) =>
        resource.status === 'zombie' || resource.status === 'waste' || resource.status === 'non_compliant'
    );
    const costTracked = filteredResources.filter(isCostTrackedResource);
    const shadowIT = filteredResources.filter(r => r.region_compliance === 'shadow_it');
    const orphaned = filteredResources.filter((resource) => {
        const type = (resource.resource_type || '').toLowerCase();
        const wasteType = (resource.waste_type || '').toLowerCase();
        return (type.includes('disk') || type.includes('ebs') || type.includes('storage'))
            && (wasteType.includes('orphan') || resource.status === 'waste' || resource.status === 'zombie');
    });

    const tabs: Array<{ id: ResourceTab; label: string; count: number; icon: typeof Server }> = [
        { id: 'costTracked', label: 'Cost Tracked', count: costTracked.length, icon: Server },
        { id: 'all', label: 'All Inventory', count: filteredResources.length, icon: Layers },
        { id: 'zombie', label: 'Zombie Assets', count: zombies.length, icon: AlertOctagon },
        { id: 'shadow', label: 'Shadow IT', count: shadowIT.length, icon: MapPin },
        { id: 'orphaned', label: 'Orphaned Storage', count: orphaned.length, icon: HardDrive },
    ];

    const currentData =
        activeTab === 'costTracked' ? costTracked
            : activeTab === 'all' ? filteredResources
                : activeTab === 'zombie' ? zombies
                    : activeTab === 'shadow' ? shadowIT
                        : orphaned;
    const visibleResources = [...currentData].sort((left, right) => {
        const rankDiff = getCostSortRank(left.cost_status) - getCostSortRank(right.cost_status);
        if (rankDiff !== 0) {
            return rankDiff;
        }
        return toDisplayText(left.resource_name, 'Unknown resource').localeCompare(
            toDisplayText(right.resource_name, 'Unknown resource')
        );
    });

    return (
        <div className="bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
            {/* Header */}
            <div className="p-5 border-b border-white/10 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <h3 className="text-lg font-semibold text-white">Detailed Inventory</h3>
                <div className="relative w-full sm:w-72">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                        type="text"
                        placeholder="Search resources..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full rounded-xl border border-white/10 bg-slate-900 py-2 pl-10 pr-4 text-sm text-white placeholder:text-slate-500 transition-all focus:border-indigo-500 focus:outline-none"
                    />
                </div>
            </div>

            <div className="px-5 pt-4">
                <div className="flex flex-wrap gap-3 mb-4">
                    {Object.entries(typeCounts)
                        .sort((left: [string, number], right: [string, number]) => right[1] - left[1])
                        .map(([type, count]: [string, number]) => (
                            <div
                                key={type}
                                className="flex items-center gap-2 rounded-xl border border-white/10 bg-slate-900/50 px-3 py-2"
                            >
                                <span
                                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                                    style={{ backgroundColor: TYPE_COLORS[type] ?? '#94a3b8' }}
                                />
                                <span className="text-white text-sm font-medium">{count}</span>
                                <span className="text-slate-500 text-xs">{type}</span>
                            </div>
                        ))}
                </div>
            </div>

            <div className="px-5 pb-4">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                    <div className="bg-slate-900/50 border border-white/10 rounded-2xl p-5">
                        <h3 className="text-white font-semibold mb-4">Resources by Type</h3>
                        {typeCountData.length === 0 ? (
                            <div className="flex items-center justify-center h-[180px] rounded-xl bg-white/[0.02] border border-white/5 border-dashed">
                                <p className="text-slate-500 text-sm">No resources found yet</p>
                            </div>
                        ) : (
                            <ResponsiveContainer width="100%" height={180}>
                                <BarChart
                                    data={typeCountData}
                                    margin={{ top: 4, right: 8, left: 0, bottom: 4 }}
                                >
                                    <CartesianGrid
                                        strokeDasharray="3 3"
                                        stroke={CHART_STYLE.gridColor}
                                        vertical={false}
                                    />
                                    <XAxis
                                        dataKey="name"
                                        tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }}
                                        axisLine={false}
                                        tickLine={false}
                                        tickFormatter={(value: string) =>
                                            value.charAt(0).toUpperCase() + value.slice(1)
                                        }
                                    />
                                    <YAxis
                                        allowDecimals={false}
                                        tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }}
                                        axisLine={false}
                                        tickLine={false}
                                        width={28}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: CHART_STYLE.tooltipBg,
                                            border: `1px solid ${CHART_STYLE.tooltipBorder}`,
                                            borderRadius: '10px',
                                            fontSize: '12px',
                                        }}
                                        cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                                    />
                                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                                        {typeCountData.map((entry: { name: string; count: number }, index: number) => (
                                            <Cell
                                                key={index}
                                                fill={
                                                    CATEGORY_COLORS[
                                                        entry.name.charAt(0).toUpperCase() + entry.name.slice(1)
                                                    ] ?? '#94a3b8'
                                                }
                                            />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>

                    <div className="bg-slate-900/50 border border-white/10 rounded-2xl p-5">
                        <h3 className="text-white font-semibold mb-4">Resources by Cloud</h3>
                        {byCloudData.length === 0 ? (
                            <div className="flex items-center justify-center h-[180px] rounded-xl bg-white/[0.02] border border-white/5 border-dashed">
                                <p className="text-slate-500 text-sm">No cloud resources found yet</p>
                            </div>
                        ) : (
                            <ResponsiveContainer width="100%" height={180}>
                                <BarChart
                                    data={byCloudData}
                                    margin={{ top: 4, right: 8, left: 0, bottom: 4 }}
                                >
                                    <CartesianGrid
                                        strokeDasharray="3 3"
                                        stroke={CHART_STYLE.gridColor}
                                        vertical={false}
                                    />
                                    <XAxis
                                        dataKey="provider"
                                        tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }}
                                        axisLine={false}
                                        tickLine={false}
                                        tickFormatter={(value: string) => value.toUpperCase()}
                                    />
                                    <YAxis
                                        allowDecimals={false}
                                        tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }}
                                        axisLine={false}
                                        tickLine={false}
                                        width={28}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: CHART_STYLE.tooltipBg,
                                            border: `1px solid ${CHART_STYLE.tooltipBorder}`,
                                            borderRadius: '10px',
                                            fontSize: '12px',
                                        }}
                                        cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                                    />
                                    <Legend wrapperStyle={{ fontSize: '11px', color: '#64748b' }} />
                                    {typeKeys.map((type: string) => (
                                        <Bar
                                            key={type}
                                            dataKey={type}
                                            stackId="a"
                                            fill={
                                                CATEGORY_COLORS[
                                                    type.charAt(0).toUpperCase() + type.slice(1)
                                                ] ?? '#94a3b8'
                                            }
                                            radius={type === 'other' ? [4, 4, 0, 0] : [0, 0, 0, 0]}
                                            name={type.charAt(0).toUpperCase() + type.slice(1)}
                                        />
                                    ))}
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <div className="px-5">
                <div className="flex w-fit flex-wrap gap-1.5 rounded-xl border border-white/10 bg-slate-900 p-1">
                    {tabs.map((tab) => {
                        const isActive = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`relative z-10 flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-300 ${isActive
                                    ? 'border border-indigo-500/30 bg-indigo-600/20 text-indigo-400'
                                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-white'
                                    }`}
                            >
                                <span className="relative z-10 flex items-center gap-1.5">
                                    <tab.icon className="w-3.5 h-3.5" />
                                    <span className="hidden sm:inline">{tab.label}</span>
                                    <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${isActive ? 'bg-indigo-500/10 text-indigo-300' : 'bg-slate-800 text-slate-400'}`}>
                                        {tab.count}
                                    </span>
                                </span>
                            </button>
                        )
                    })}
                </div>
            </div>

            {/* Table */}
            <div className="p-5">
                <AnimatePresence mode="wait">
                    <motion.div
                        key={activeTab}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        transition={{ duration: 0.2 }}
                    >
                        {activeTab === 'shadow' && (
                            <div className="mb-4 flex items-center gap-3 rounded-2xl border border-rose-500/20 border-l-4 border-l-rose-500 bg-rose-500/10 p-3">
                                <ShieldAlert className="w-4 h-4 text-rose-500 shrink-0" />
                                <p className="text-rose-400 text-xs">
                                    <span className="font-bold">Compliance Warning:</span> These resources are running outside your primary region.
                                </p>
                            </div>
                        )}

                        <div className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-900/40">
                            <table className="w-full text-left min-w-[980px]">
                                <thead>
                                    <tr className="border-b border-white/10 text-[11px] uppercase tracking-wider text-slate-500 bg-white/5">
                                        <th className="px-4 py-3 font-medium">Resource</th>
                                        <th className="px-4 py-3 font-medium">Type</th>
                                        <th className="px-4 py-3 font-medium">Region</th>
                                        <th className="px-4 py-3 font-medium">Owner</th>
                                        <th className="px-4 py-3 font-medium">Compliance</th>
                                        <th className="px-4 py-3 font-medium">Details</th>
                                        <th className="px-4 py-3 font-medium text-right">Cost Signal</th>
                                        <th className="px-4 py-3 font-medium text-right">Annual Signal</th>
                                        <th className="px-4 py-3 font-medium text-center">Status</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5 text-sm">
                                    {visibleResources.length === 0 ? (
                                        <tr>
                                            <td colSpan={9} className="px-4 py-12 text-center text-slate-500">
                                                No resources found for this category.
                                            </td>
                                        </tr>
                                    ) : (
                                        visibleResources.map((resource) => {
                                            const Icon = resourceTypeIcons[resource.resource_type] || Cloud;
                                            const resourceName = toDisplayText(resource.resource_name, 'Unknown resource');
                                            const resourceType = toDisplayText(resource.resource_type, 'Unknown type');
                                            const providerStyle = PROVIDER_BADGE_STYLES[
                                                (resource.provider || '').toLowerCase() as keyof typeof PROVIDER_BADGE_STYLES
                                            ] ?? { bg: 'bg-slate-500/15', text: 'text-slate-400', label: '?' };
                                            const owner = resource.metadata?.tags?.Owner
                                                || resource.metadata?.tags?.owner
                                                || resource.metadata?.tags?.Team
                                                || resource.metadata?.tags?.team
                                                || '—';
                                            const costStatus = resource.cost_status || 'unavailable';
                                            const monthlyCostLabel = resource.cost_label
                                                || (resource.monthly_cost_available ? formatInrCurrency(resource.monthly_cost) : RESOURCE_LEVEL_COST_UNAVAILABLE_LABEL);
                                            const annualCostLabel = resource.annual_cost_label
                                                || (resource.monthly_cost_available
                                                    ? `${formatInrCurrency(resource.monthly_cost * 12, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}/yr`
                                                    : RESOURCE_LEVEL_COST_UNAVAILABLE_LABEL);
                                            return (
                                                <tr key={resource.id} className="hover:bg-white/[0.03] transition-colors group">
                                                    <td className="px-4 py-3 max-w-[220px]">
                                                        <div className="flex items-center gap-2.5">
                                                            <div className="p-1.5 bg-slate-800 rounded-lg shrink-0">
                                                                <Icon className="h-3.5 w-3.5 text-emerald-400" />
                                                            </div>
                                                            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide ${providerStyle.bg} ${providerStyle.text}`}>
                                                                {providerStyle.label}
                                                            </span>
                                                            <span className="text-white font-medium truncate text-sm" title={resourceName}>
                                                                {resourceName}
                                                            </span>
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <span className="inline-flex rounded-full border border-white/10 bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                                                            {resourceType}
                                                        </span>
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <span className="inline-flex items-center gap-1 text-xs text-slate-300">
                                                            <MapPin className="w-3 h-3 text-slate-500" />
                                                            {resource.region}
                                                        </span>
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <span className="text-slate-300 text-sm">{owner}</span>
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        {resource.region_compliance === 'shadow_it' ? (
                                                            <span className="inline-flex px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 text-[10px] font-medium border border-rose-500/20">
                                                                Shadow IT
                                                            </span>
                                                        ) : (
                                                            <span className="inline-flex px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-medium border border-emerald-500/20">
                                                                Compliant
                                                            </span>
                                                        )}
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <CompactMetrics resource={resource} />
                                                    </td>
                                                    <td className="px-4 py-3 text-right">
                                                        <span className={`font-mono text-sm ${getCostTextClass(costStatus)}`}>
                                                            {monthlyCostLabel}
                                                        </span>
                                                    </td>
                                                    <td className="px-4 py-3 text-right">
                                                        <span className="text-slate-400 text-xs">
                                                            {annualCostLabel}
                                                        </span>
                                                    </td>
                                                    <td className="px-4 py-3 text-center">
                                                        {getStatusBadge(resource.status)}
                                                    </td>
                                                </tr>
                                            );
                                        })
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </motion.div>
                </AnimatePresence>
            </div>
        </div>
    );
}
