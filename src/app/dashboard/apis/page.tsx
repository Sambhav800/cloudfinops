"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
    PieChart,
    Pie,
} from "recharts";
import {
    Webhook,
    Ghost,
    AlertTriangle,
    TrendingDown,
    ChevronDown,
    Terminal,
    Shield,
    Database,
    Zap,
    Search,
    ArrowUpDown,
    RefreshCw,
} from "lucide-react";

import { buildBackendAuthHeaders } from "@/app/api/_shared/fetch-with-backend-auth-fallback";
import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";

// ─── Chart Style Constants ───────────────────────────────────────────────────

const CHART_STYLE = {
    gridColor: "rgba(255,255,255,0.06)",
    tickColor: "#64748b",
    tooltipBg: "#0f172a",
    tooltipBorder: "rgba(255,255,255,0.1)",
    fontSize: 11,
} as const;

const CHART_COLORS = {
    invocations: "#6366f1",
    errors: "#f43f5e",
    latency: "#f59e0b",
    cache: "#10b981",
    ghost: "#ef4444",
    active: "#22c55e",
    shadow: "#a855f7",
    unknown: "#94a3b8",
} as const;

// ─── Types ────────────────────────────────────────────────────────────────────

type ApiResource = {
    id: string;
    name: string;
    api_type: string;
    stage_name: string;
    endpoint_type: string;
    invocations_7d: number | null;
    error_rate_4xx: number | null;
    error_rate_5xx: number | null;
    latency_p99_ms: number | null;
    cache_enabled: boolean;
    cache_hit_rate: number | null;
    monthly_cost: number;
    status: string;
    provider: string;
    region: string;
    is_ghost: boolean;
};

type GhostApi = {
    resource_id: string;
    name: string;
    api_type: string;
    stage_name: string;
    provider: string;
    monthly_cost: number;
    annual_cost: number;
    invocations_7d: number;
    ghost_reason: string;
    fix_command: string;
};

type CacheWaste = {
    resource_id: string;
    name: string;
    stage_name: string;
    provider: string;
    cache_hit_rate: number;
    cache_monthly_cost: number;
    wasted_monthly: number;
    recommendation: string;
};

type ApiReport = {
    api_resources: ApiResource[];
    ghost_apis: GhostApi[];
    cache_waste: CacheWaste[];
    shadow_apis: Array<{ name: string; service_type: string; provider: string; reason: string }>;
    cost_per_request_ranking: Array<{ name: string; provider: string; cost_per_1k_requests: number; monthly_invocations: number; monthly_cost: number }>;
    total_api_count: number;
    total_api_spend: number;
    total_api_waste: number;
    ghost_api_count: number;
    cache_waste_monthly: number;
    providers_detected: string[];
    ai_narrative: string;
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function isMeasured(value: unknown): value is number {
    return typeof value === "number" && Number.isFinite(value);
}

const fmt = (n: number) =>
    formatInrCurrency(toDisplayInrAmount(n, "USD"), { maximumFractionDigits: 0 });

const fmtCompact = (n: number): string => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return n.toFixed(0);
};

function Skeleton({ className }: { className: string }) {
    return <div className={`animate-pulse rounded-md bg-slate-800 ${className}`} />;
}

function CodeBlock({ code }: { code: string }) {
    const [copied, setCopied] = useState(false);
    return (
        <div className="relative rounded-xl bg-black/70 border border-white/10 mt-3 overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/10 bg-white/[0.02]">
                <Terminal className="h-3.5 w-3.5 text-slate-500" />
                <span className="text-xs text-slate-500 font-medium">Remediation</span>
                <button
                    className="ml-auto rounded-md border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-slate-300 hover:bg-white/10 transition-colors"
                    onClick={() => { navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
                >
                    {copied ? "Copied!" : "Copy"}
                </button>
            </div>
            <pre className="p-4 text-xs text-emerald-300/90 overflow-x-auto whitespace-pre-wrap leading-relaxed font-mono">{code}</pre>
        </div>
    );
}

function ExpandableCard({ children, title, defaultOpen = false }: { children: React.ReactNode; title: React.ReactNode; defaultOpen?: boolean }) {
    const [open, setOpen] = useState(defaultOpen);
    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur-sm overflow-hidden transition-all">
            <button className="w-full flex items-center justify-between p-5 text-left hover:bg-white/[0.02] transition-colors" onClick={() => setOpen(!open)}>
                <div className="flex-1">{title}</div>
                <div className={`ml-3 rounded-lg border border-white/10 bg-white/5 p-1.5 transition-transform ${open ? "rotate-180" : ""}`}>
                    <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
                </div>
            </button>
            {open && <div className="px-5 pb-5 border-t border-white/5 pt-4">{children}</div>}
        </div>
    );
}

// ─── Sub-Components ──────────────────────────────────────────────────────────

function TrafficDistributionChart({ resources }: { resources: ApiResource[] }) {
    const chartData = useMemo(() => {
        const sorted = [...resources]
            .filter((r): r is ApiResource & { invocations_7d: number } => isMeasured(r.invocations_7d) && r.invocations_7d > 0)
            .sort((a, b) => b.invocations_7d - a.invocations_7d)
            .slice(0, 8);
        return sorted.map(r => ({
            name: r.name.length > 20 ? r.name.slice(0, 18) + "…" : r.name,
            invocations: r.invocations_7d,
            errors: isMeasured(r.error_rate_5xx) ? Math.round(r.invocations_7d * (r.error_rate_5xx / 100)) : null,
        }));
    }, [resources]);

    if (chartData.length === 0) return null;

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6">
            <div className="mb-4 flex items-center justify-between">
                <div>
                    <h3 className="text-sm font-semibold text-white">Traffic Distribution (7-Day)</h3>
                    <p className="text-xs text-slate-500 mt-0.5">Top APIs by invocation volume</p>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-500">
                    <div className="flex items-center gap-1.5">
                        <div className="h-2 w-2 rounded-full bg-indigo-500" />
                        <span>Invocations</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="h-2 w-2 rounded-full bg-rose-500" />
                        <span>5xx Errors</span>
                    </div>
                </div>
            </div>
            <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} margin={{ top: 4, right: 0, left: 0, bottom: 4 }} barGap={2}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.gridColor} vertical={false} />
                    <XAxis
                        dataKey="name"
                        tick={{ fill: CHART_STYLE.tickColor, fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                    />
                    <YAxis
                        tick={{ fill: CHART_STYLE.tickColor, fontSize: CHART_STYLE.fontSize }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(v) => fmtCompact(v)}
                        width={50}
                    />
                    <Tooltip
                        contentStyle={{ backgroundColor: CHART_STYLE.tooltipBg, border: `1px solid ${CHART_STYLE.tooltipBorder}`, borderRadius: "12px", fontSize: "12px" }}
                        labelStyle={{ color: "#94a3b8" }}
                        formatter={(value: unknown, name: string) => [isMeasured(value) ? value.toLocaleString() : "Not measured", name === "invocations" ? "Invocations" : "5xx Errors"]}
                    />
                    <Bar dataKey="invocations" radius={[4, 4, 0, 0]} fill={CHART_COLORS.invocations} fillOpacity={0.85} />
                    <Bar dataKey="errors" radius={[4, 4, 0, 0]} fill={CHART_COLORS.errors} fillOpacity={0.7} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}

function StatusBreakdownDonut({ resources }: { resources: ApiResource[] }) {
    const data = useMemo(() => {
        const ghost = resources.filter(r => r.is_ghost).length;
        const active = resources.filter(r => !r.is_ghost && isMeasured(r.invocations_7d) && r.invocations_7d > 100).length;
        const low = resources.filter(r => !r.is_ghost && isMeasured(r.invocations_7d) && r.invocations_7d <= 100 && r.invocations_7d > 0).length;
        const idle = resources.filter(r => !r.is_ghost && r.invocations_7d === 0).length;
        const unknown = resources.filter(r => !r.is_ghost && !isMeasured(r.invocations_7d)).length;
        return [
            { name: "Active", value: active, color: CHART_COLORS.active },
            { name: "Low Traffic", value: low, color: CHART_COLORS.latency },
            { name: "Idle", value: idle, color: "#64748b" },
            { name: "Ghost", value: ghost, color: CHART_COLORS.ghost },
            { name: "Unknown", value: unknown, color: CHART_COLORS.unknown },
        ].filter(d => d.value > 0);
    }, [resources]);

    if (data.length === 0) return null;

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6">
            <h3 className="text-sm font-semibold text-white mb-4">API Health Breakdown</h3>
            <div className="flex items-center gap-6">
                <ResponsiveContainer width={140} height={140}>
                    <PieChart>
                        <Pie
                            data={data}
                            cx="50%"
                            cy="50%"
                            innerRadius={42}
                            outerRadius={62}
                            paddingAngle={3}
                            dataKey="value"
                            strokeWidth={0}
                        >
                            {data.map((entry, idx) => (
                                <Cell key={idx} fill={entry.color} />
                            ))}
                        </Pie>
                    </PieChart>
                </ResponsiveContainer>
                <div className="flex-1 space-y-2.5">
                    {data.map((d, i) => (
                        <div key={i} className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: d.color }} />
                                <span className="text-xs text-slate-400">{d.name}</span>
                            </div>
                            <span className="text-sm font-semibold text-white">{d.value}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

function CostEfficiencyChart({ ranking }: { ranking: ApiReport["cost_per_request_ranking"] }) {
    const chartData = useMemo(() =>
        ranking.slice(0, 6).map(r => ({
            name: r.name.length > 16 ? r.name.slice(0, 14) + "…" : r.name,
            cost: r.cost_per_1k_requests,
            provider: r.provider,
        })),
    [ranking]);

    if (chartData.length === 0) return null;

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6">
            <div className="mb-4">
                <h3 className="text-sm font-semibold text-white">Cost Per 1K Requests</h3>
                <p className="text-xs text-slate-500 mt-0.5">Most expensive APIs (higher = less efficient)</p>
            </div>
            <ResponsiveContainer width="100%" height={180}>
                <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.gridColor} horizontal={false} />
                    <XAxis
                        type="number"
                        tick={{ fill: CHART_STYLE.tickColor, fontSize: CHART_STYLE.fontSize }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(v) => `$${v.toFixed(3)}`}
                    />
                    <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fill: CHART_STYLE.tickColor, fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        width={110}
                    />
                    <Tooltip
                        contentStyle={{ backgroundColor: CHART_STYLE.tooltipBg, border: `1px solid ${CHART_STYLE.tooltipBorder}`, borderRadius: "12px", fontSize: "12px" }}
                        formatter={(value: number) => [`$${value.toFixed(4)} / 1K requests`, "Cost"]}
                    />
                    <Bar dataKey="cost" radius={[0, 4, 4, 0]} fill={CHART_COLORS.latency} fillOpacity={0.8} barSize={18} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ApiIntelligencePage() {
    const searchParams = useSearchParams();
    const integrationId = searchParams.get("integration_id") || undefined;
    const { getToken, userId } = useAuth();
    const [report, setReport] = useState<ApiReport | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [sortField, setSortField] = useState<"invocations_7d" | "monthly_cost" | "error_rate_5xx">("invocations_7d");
    const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

    useEffect(() => {
        const url = integrationId ? `/api/apis/summary?integration_id=${integrationId}` : "/api/apis/summary";

        const loadData = async () => {
            try {
                let token = await getToken();
                if (!token) { try { token = await getToken({ template: "default" }); } catch { token = null; } }
                const headers = buildBackendAuthHeaders(
                    typeof window === "undefined" ? url : new URL(url, window.location.origin).toString(),
                    { token, userId: userId ?? null },
                );
                const r = await fetch(url, { headers });
                if (!r.ok) {
                    const errPayload = await r.json().catch(() => ({}));
                    throw new Error(errPayload.detail || `HTTP ${r.status}`);
                }
                setReport(await r.json());
            } catch (e: unknown) {
                setError(e instanceof Error ? e.message || String(e) : String(e));
            } finally {
                setLoading(false);
            }
        };
        void loadData();
    }, [integrationId, getToken, userId]);

    const filteredApis = useMemo(() => {
        if (!report) return [];
        const filtered = report.api_resources.filter(r =>
            r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            r.provider.toLowerCase().includes(searchQuery.toLowerCase()) ||
            r.api_type.toLowerCase().includes(searchQuery.toLowerCase())
        );
        filtered.sort((a, b) => {
            const aVal = a[sortField];
            const bVal = b[sortField];
            if (!isMeasured(aVal)) return isMeasured(bVal) ? 1 : 0;
            if (!isMeasured(bVal)) return -1;
            return sortDir === "desc" ? bVal - aVal : aVal - bVal;
        });
        return filtered;
    }, [report, searchQuery, sortField, sortDir]);

    // ─── Loading State ───────────────────────────────────────────────────────
    if (loading) {
        return (
            <div className="space-y-6 p-4 md:p-8">
                <div className="flex items-center gap-3">
                    <Skeleton className="h-6 w-6 rounded-lg" />
                    <Skeleton className="h-7 w-48" />
                </div>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    {[1, 2, 3, 4].map(i => (
                        <div key={i} className="rounded-2xl border border-white/10 bg-slate-900/40 p-5">
                            <Skeleton className="h-3 w-20" />
                            <Skeleton className="mt-3 h-7 w-24" />
                            <Skeleton className="mt-2 h-3 w-32" />
                        </div>
                    ))}
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <Skeleton className="h-72 rounded-2xl" />
                    <Skeleton className="h-72 rounded-2xl" />
                </div>
                <Skeleton className="h-64 rounded-2xl" />
            </div>
        );
    }

    // ─── Error State ─────────────────────────────────────────────────────────
    if (error) {
        return (
            <div className="p-8">
                <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-6 text-center">
                    <AlertTriangle className="h-8 w-8 mx-auto mb-3 text-rose-400" />
                    <p className="text-sm text-rose-300">{error}</p>
                    <button
                        onClick={() => { setError(null); setLoading(true); }}
                        className="mt-4 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-white hover:bg-white/10 transition-colors"
                    >
                        <RefreshCw className="h-3 w-3 inline mr-1.5" />Retry
                    </button>
                </div>
            </div>
        );
    }

    // ─── Empty State ─────────────────────────────────────────────────────────
    if (!report || report.total_api_count === 0) {
        return (
            <div className="min-h-[60vh] flex flex-col items-center justify-center text-center gap-5 p-8">
                <div className="rounded-2xl bg-indigo-500/10 p-5 border border-indigo-500/20">
                    <Webhook className="h-10 w-10 text-indigo-400" />
                </div>
                <h2 className="text-xl text-white font-bold">No API Resources Detected</h2>
                <p className="text-slate-400 max-w-lg text-sm leading-relaxed">
                    No API Gateways, API Management instances, or Cloud Endpoints were found.
                    Ensure your cloud integrations have the <code className="text-indigo-300 bg-indigo-500/10 px-1.5 py-0.5 rounded text-xs">apigateway:GET</code> permission
                    and re-run a scan.
                </p>
                <a href="/dashboard/settings" className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors">
                    Manage Integrations
                </a>
            </div>
        );
    }

    const { ghost_apis, cache_waste, shadow_apis, cost_per_request_ranking,
        total_api_count, total_api_spend, total_api_waste, ghost_api_count,
        cache_waste_monthly, ai_narrative, api_resources } = report;

    // ─── Render ──────────────────────────────────────────────────────────────
    return (
        <div className="space-y-6 p-4 md:p-8">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                    <div className="flex items-center gap-2.5 mb-1">
                        <div className="rounded-lg bg-indigo-500/10 p-1.5">
                            <Webhook className="h-5 w-5 text-indigo-400" />
                        </div>
                        <h1 className="text-2xl font-bold text-white">API Intelligence</h1>
                    </div>
                    <p className="text-sm text-slate-500">
                        Ghost detection · Cache analysis · Shadow APIs · Cost efficiency · {total_api_count} resources tracked
                    </p>
                </div>
                {report.providers_detected.length > 0 && (
                    <div className="flex gap-1.5">
                        {report.providers_detected.map((p) => (
                            <span key={p} className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 uppercase tracking-wider">
                                {p}
                            </span>
                        ))}
                    </div>
                )}
            </div>

            {/* Hero Stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="rounded-2xl border border-white/10 border-t-2 border-t-indigo-500/60 bg-slate-900/50 p-5 backdrop-blur-sm">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500 flex items-center gap-1.5">
                        <Database className="h-3 w-3" /> Total APIs
                    </p>
                    <p className="mt-2 text-3xl font-bold text-white">{total_api_count}</p>
                    <p className="mt-1 text-xs text-slate-500">{fmt(total_api_spend)}/mo total spend</p>
                </div>
                <div className="rounded-2xl border border-rose-500/20 border-t-2 border-t-rose-500/60 bg-slate-900/50 p-5 backdrop-blur-sm">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-rose-400 flex items-center gap-1.5">
                        <Ghost className="h-3 w-3" /> Ghost APIs
                    </p>
                    <p className="mt-2 text-3xl font-bold text-white">{ghost_api_count}</p>
                    <p className="mt-1 text-xs text-rose-400/80">{fmt(total_api_waste)}/mo wasted</p>
                </div>
                <div className="rounded-2xl border border-amber-500/20 border-t-2 border-t-amber-500/60 bg-slate-900/50 p-5 backdrop-blur-sm">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-400 flex items-center gap-1.5">
                        <TrendingDown className="h-3 w-3" /> Cache Waste
                    </p>
                    <p className="mt-2 text-3xl font-bold text-white">{fmt(cache_waste_monthly)}</p>
                    <p className="mt-1 text-xs text-amber-400/80">{cache_waste.length} with &lt;5% hit rate</p>
                </div>
                <div className="rounded-2xl border border-purple-500/20 border-t-2 border-t-purple-500/60 bg-slate-900/50 p-5 backdrop-blur-sm">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-purple-400 flex items-center gap-1.5">
                        <Shield className="h-3 w-3" /> Shadow APIs
                    </p>
                    <p className="mt-2 text-3xl font-bold text-white">{shadow_apis.length}</p>
                    <p className="mt-1 text-xs text-purple-400/80">bypassing gateway</p>
                </div>
            </div>

            {/* AI Narrative */}
            {ai_narrative && (
                <div className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-500/5 to-purple-500/5 p-5">
                    <div className="flex items-center gap-2 mb-2">
                        <div className="rounded-md bg-indigo-500/10 p-1">
                            <Zap className="h-3.5 w-3.5 text-indigo-400" />
                        </div>
                        <span className="text-xs font-semibold text-indigo-300 uppercase tracking-wider">AI Analysis</span>
                    </div>
                    <p className="text-sm text-slate-300 leading-relaxed">{ai_narrative}</p>
                </div>
            )}

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <TrafficDistributionChart resources={api_resources} />
                <StatusBreakdownDonut resources={api_resources} />
            </div>

            {/* Cost Efficiency Chart */}
            {cost_per_request_ranking.length > 0 && (
                <CostEfficiencyChart ranking={cost_per_request_ranking} />
            )}

            {/* Ghost API Alerts */}
            {ghost_apis.length > 0 && (
                <div className="space-y-3">
                    <div className="flex items-center gap-2.5">
                        <Ghost className="h-5 w-5 text-rose-400" />
                        <h2 className="text-base font-semibold text-white">Ghost APIs</h2>
                        <span className="rounded-full bg-rose-500/15 text-rose-300 px-2.5 py-0.5 text-xs font-medium">{ghost_apis.length} detected</span>
                    </div>
                    {ghost_apis.map((g, i) => (
                        <ExpandableCard
                            key={g.resource_id || i}
                            title={
                                <div className="flex items-start justify-between gap-4 flex-wrap">
                                    <div>
                                        <p className="text-white font-medium">{g.name}</p>
                                        <p className="text-xs text-slate-500 mt-1">
                                            {g.api_type} · {g.provider.toUpperCase()}
                                            {g.stage_name && ` · Stage: ${g.stage_name}`}
                                        </p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-rose-300 font-bold">{fmt(g.monthly_cost)}<span className="text-xs font-normal text-slate-500">/mo</span></p>
                                        <p className="text-xs text-slate-500 mt-0.5">{g.invocations_7d} calls/7d</p>
                                    </div>
                                </div>
                            }
                        >
                            <p className="text-sm text-slate-400">{g.ghost_reason}</p>
                            <CodeBlock code={g.fix_command} />
                        </ExpandableCard>
                    ))}
                </div>
            )}

            {/* Cache Waste Table */}
            {cache_waste.length > 0 && (
                <div className="space-y-3">
                    <div className="flex items-center gap-2.5">
                        <TrendingDown className="h-5 w-5 text-amber-400" />
                        <h2 className="text-base font-semibold text-white">Cache Waste Analysis</h2>
                    </div>
                    <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/40">
                        <div className="overflow-x-auto">
                            <table className="w-full min-w-[700px] text-sm">
                                <thead className="border-b border-white/5 bg-white/[0.02]">
                                    <tr className="text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                                        <th className="px-5 py-3.5">API Endpoint</th>
                                        <th className="px-5 py-3.5">Hit Rate</th>
                                        <th className="px-5 py-3.5">Cache Cost</th>
                                        <th className="px-5 py-3.5">Monthly Waste</th>
                                        <th className="px-5 py-3.5">Action</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {cache_waste.map((c, i) => (
                                        <tr key={i} className="border-t border-white/5 hover:bg-white/[0.02] transition-colors">
                                            <td className="px-5 py-4">
                                                <p className="font-medium text-white">{c.name}</p>
                                                <p className="text-xs text-slate-500 mt-0.5">{c.provider.toUpperCase()}</p>
                                            </td>
                                            <td className="px-5 py-4">
                                                <span className="rounded-full bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 text-xs font-medium text-rose-300">
                                                    {c.cache_hit_rate}%
                                                </span>
                                            </td>
                                            <td className="px-5 py-4 text-slate-400">{fmt(c.cache_monthly_cost)}/mo</td>
                                            <td className="px-5 py-4 font-semibold text-amber-300">{fmt(c.wasted_monthly)}/mo</td>
                                            <td className="px-5 py-4">
                                                <span className="text-xs text-indigo-400">Disable cache</span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}

            {/* Shadow APIs */}
            {shadow_apis.length > 0 && (
                <div className="space-y-3">
                    <div className="flex items-center gap-2.5">
                        <Shield className="h-5 w-5 text-purple-400" />
                        <h2 className="text-base font-semibold text-white">Shadow APIs</h2>
                        <span className="rounded-full bg-purple-500/15 text-purple-300 px-2.5 py-0.5 text-xs font-medium">Compliance Risk</span>
                    </div>
                    <div className="space-y-2">
                        {shadow_apis.map((s, i) => (
                            <div key={i} className="rounded-2xl border border-purple-500/15 bg-purple-500/5 p-4 flex items-center justify-between gap-4">
                                <div>
                                    <p className="text-white font-medium">{s.name}</p>
                                    <p className="text-xs text-slate-500 mt-0.5">{s.service_type} · {s.provider.toUpperCase()}</p>
                                    <p className="text-xs text-slate-400 mt-1.5">{s.reason}</p>
                                </div>
                                <span className="shrink-0 rounded-lg bg-purple-500/10 border border-purple-500/20 px-3 py-1.5 text-xs font-medium text-purple-300">
                                    No Gateway
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Full API Inventory Table */}
            <div className="space-y-3">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                    <h2 className="text-base font-semibold text-white">API Inventory</h2>
                    <div className="flex items-center gap-3">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
                            <input
                                type="text"
                                placeholder="Search APIs..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="rounded-xl border border-white/10 bg-white/5 pl-9 pr-4 py-2 text-xs text-white placeholder:text-slate-600 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/30 w-48"
                            />
                        </div>
                        <button
                            onClick={() => setSortDir(sortDir === "desc" ? "asc" : "desc")}
                            className="rounded-xl border border-white/10 bg-white/5 p-2 text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
                        >
                            <ArrowUpDown className="h-3.5 w-3.5" />
                        </button>
                    </div>
                </div>
                <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/40">
                    <div className="overflow-x-auto">
                        <table className="w-full min-w-[920px] text-sm">
                            <thead className="border-b border-white/5 bg-white/[0.02]">
                                <tr className="text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                                    <th className="px-5 py-3.5">API Endpoint</th>
                                    <th className="px-5 py-3.5">Type</th>
                                    <th className="px-5 py-3.5">Provider</th>
                                    <th className="px-5 py-3.5 cursor-pointer hover:text-white" onClick={() => { setSortField("invocations_7d"); setSortDir(sortDir === "desc" ? "asc" : "desc"); }}>
                                        7d Invocations {sortField === "invocations_7d" && (sortDir === "desc" ? "↓" : "↑")}
                                    </th>
                                    <th className="px-5 py-3.5 cursor-pointer hover:text-white" onClick={() => { setSortField("error_rate_5xx"); setSortDir(sortDir === "desc" ? "asc" : "desc"); }}>
                                        Error Rate {sortField === "error_rate_5xx" && (sortDir === "desc" ? "↓" : "↑")}
                                    </th>
                                    <th className="px-5 py-3.5">Latency p99</th>
                                    <th className="px-5 py-3.5">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredApis.map((r, i) => (
                                    <tr key={i} className="border-t border-white/5 hover:bg-white/[0.02] transition-colors">
                                        <td className="px-5 py-4">
                                            <p className="font-medium text-white">{r.name}</p>
                                            <p className="text-xs text-slate-500 mt-0.5">{r.region}</p>
                                        </td>
                                        <td className="px-5 py-4">
                                            <span className="rounded-md bg-slate-800 px-2 py-0.5 text-xs text-slate-300">{r.api_type}</span>
                                        </td>
                                        <td className="px-5 py-4 text-xs font-medium text-slate-400 uppercase">{r.provider}</td>
                                        <td className="px-5 py-4 font-mono text-slate-300">{isMeasured(r.invocations_7d) ? r.invocations_7d.toLocaleString() : "Not measured"}</td>
                                        <td className="px-5 py-4">
                                            {!isMeasured(r.error_rate_5xx) ? (
                                                <span className="text-xs text-slate-500">Not measured</span>
                                            ) : r.error_rate_5xx > 5 ? (
                                                <span className="rounded-full bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 text-xs font-medium text-rose-300">
                                                    {r.error_rate_5xx.toFixed(1)}%
                                                </span>
                                            ) : (
                                                <span className="text-xs text-slate-500">{r.error_rate_5xx.toFixed(1)}%</span>
                                            )}
                                        </td>
                                        <td className="px-5 py-4 text-xs text-slate-400">
                                            {isMeasured(r.latency_p99_ms) ? `${r.latency_p99_ms.toFixed(0)}ms` : "Not measured"}
                                        </td>
                                        <td className="px-5 py-4">
                                            {r.is_ghost ? (
                                                <span className="rounded-full bg-rose-500/10 border border-rose-500/30 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-rose-300">
                                                    Ghost
                                                </span>
                                            ) : !isMeasured(r.invocations_7d) ? (
                                                <span className="rounded-full bg-slate-700/50 border border-slate-600/30 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                                    Unknown
                                                </span>
                                            ) : r.invocations_7d === 0 ? (
                                                <span className="rounded-full bg-slate-700/50 border border-slate-600/30 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                                    Idle
                                                </span>
                                            ) : (
                                                <span className="rounded-full bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-300">
                                                    Active
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                                {filteredApis.length === 0 && (
                                    <tr>
                                        <td colSpan={7} className="px-5 py-12 text-center text-sm text-slate-500">
                                            No APIs match your search.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
