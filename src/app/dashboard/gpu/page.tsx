"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import {
    Cpu,
    Ghost,
    Zap,
    IndianRupee,
    AlertTriangle,
    TrendingDown,
    ChevronDown,
    ChevronUp,
    Terminal,
    ExternalLink,
    Globe,
} from "lucide-react";

import { buildBackendAuthHeaders } from "@/app/api/_shared/fetch-with-backend-auth-fallback";
import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";
import { GpuUtilizationChart } from "./components/gpu-utilization-chart";
import { GpuCostForecast } from "./components/gpu-cost-forecast";
import { GpuWorkloadBadges } from "./components/gpu-workload-badges";
import { GpuHistoricalTrends } from "./components/gpu-historical-trends";

// ─── Types ────────────────────────────────────────────────────────────────────

type CloudCosts = Record<string, number | null>;

type GpuResource = {
    id: string;
    name: string;
    instance_type: string;
    gpu_type: string;
    gpu_count: number;
    monthly_cost: number;
    status: string;
    region: string;
    provider?: string;
    gpu_memory_utilization_pct: number | null;
    gpu_sm_occupancy_pct: number | null;
    gpu_optimization_insight: string;
    is_ghost: boolean;
    is_mig_candidate: boolean;
};

type GhostGpu = {
    resource_id: string;
    name: string;
    instance_type: string;
    gpu_type: string;
    monthly_cost: number;
    annual_cost: number;
    ghost_reason: string;
    fix_command: string;
};

type MigCandidate = {
    resource_id: string;
    name: string;
    instance_type: string;
    gpu_type: string;
    gpu_count: number;
    monthly_cost: number;
    mig_slices_possible: number;
    advice: string;
    enable_command: string;
};

type ArbitrageItem = {
    name: string;
    instance_type: string;
    gpu_type: string;
    current_cloud: string;
    current_monthly_cost: number;
    best_alternative_cloud: string;
    best_alternative_monthly_cost: number;
    savings: number;
    savings_pct: number;
    all_cloud_costs: CloudCosts;
    migration_complexity: string;
};

type GpuReport = {
    gpu_resources: GpuResource[];
    ghost_gpus: GhostGpu[];
    mig_candidates: MigCandidate[];
    arbitrage: ArbitrageItem[];
    total_gpu_spend: number;
    total_gpu_waste: number;
    total_savings_available: number;
    annual_waste_if_unresolved: number;
    ai_narrative: string;
    providers_detected?: string[];
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const fmt = (n: number) =>
    formatInrCurrency(toDisplayInrAmount(n, "USD"), { minimumFractionDigits: 0, maximumFractionDigits: 0 });

const complexityColor: Record<string, string> = {
    Low: "text-green-300 border-green-500/30 bg-green-500/10",
    Medium: "text-yellow-300 border-yellow-500/30 bg-yellow-500/10",
    High: "text-red-300 border-red-500/30 bg-red-500/10",
};

const statusBadge = (r: GpuResource) => {
    if (r.is_ghost)
        return <span className="px-2 py-0.5 text-xs rounded-full bg-red-500/20 text-red-300 border border-red-500/40">👻 GHOST</span>;
    if (r.is_mig_candidate)
        return <span className="px-2 py-0.5 text-xs rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/40">MIG CANDIDATE</span>;
    return <span className="px-2 py-0.5 text-xs rounded-full bg-green-500/20 text-green-300 border border-green-500/40">ACTIVE</span>;
};

function CodeBlock({ code }: { code: string }) {
    const [copied, setCopied] = useState(false);
    return (
        <div className="relative rounded-lg bg-black/60 border border-white/10 mt-2">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-white/10">
                <Terminal className="h-3.5 w-3.5 text-gray-400" />
                <span className="text-xs text-gray-400">Fix command</span>
                <button
                    className="ml-auto text-xs text-blue-400 hover:text-blue-300"
                    onClick={() => { navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
                >
                    {copied ? "Copied!" : "Copy"}
                </button>
            </div>
            <pre className="p-3 text-xs text-green-300 overflow-x-auto whitespace-pre-wrap">{code}</pre>
        </div>
    );
}

function ExpandableCard({ children, title }: { children: React.ReactNode; title: React.ReactNode }) {
    const [open, setOpen] = useState(false);
    return (
        <div className="rounded-xl border border-white/10 bg-black/30">
            <button
                className="w-full flex items-center justify-between p-4 text-left"
                onClick={() => setOpen(!open)}
            >
                <div className="flex-1">{title}</div>
                {open ? <ChevronUp className="h-4 w-4 text-gray-400 flex-shrink-0" /> : <ChevronDown className="h-4 w-4 text-gray-400 flex-shrink-0" />}
            </button>
            {open && <div className="px-4 pb-4">{children}</div>}
        </div>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function GpuIntelligencePage() {
    const searchParams = useSearchParams();
    const integrationId = searchParams.get("integration_id") || undefined;

    const { getToken, userId } = useAuth();
    const [report, setReport] = useState<GpuReport | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [forecast, setForecast] = useState<any>(null);
    const [workloads, setWorkloads] = useState<any[]>([]);
    const [metricsHistory, setMetricsHistory] = useState<any[]>([]);
    const [providerFilter, setProviderFilter] = useState<string | null>(null);

    useEffect(() => {
        const url = integrationId
            ? `/api/gpu/summary?integration_id=${integrationId}`
            : "/api/gpu/summary";

        const loadData = async () => {
            try {
                let token = await getToken();
                if (!token) {
                    try {
                        token = await getToken({ template: "default" });
                    } catch {
                        token = null;
                    }
                }
                const requestUrl = typeof window === "undefined"
                    ? url
                    : new URL(url, window.location.origin).toString();
                const headers = buildBackendAuthHeaders(requestUrl, {
                    token,
                    userId: userId ?? null,
                });
                
                const r = await fetch(url, { headers });
                if (!r.ok) {
                    const errPayload = await r.json().catch(() => ({}));
                    throw new Error(errPayload.detail || errPayload.error || `HTTP ${r.status}`);
                }
                const data = await r.json();
                setReport(data);
            } catch (e: any) {
                setError(e.message || String(e));
            } finally {
                setLoading(false);
            }
        };

        void loadData();
    }, [integrationId, getToken, userId]);

    // Secondary data fetches (non-blocking)
    useEffect(() => {
        if (!report || report.gpu_resources.length === 0) return;

        const fetchSecondary = async () => {
            let token = await getToken();
            if (!token) {
                try { token = await getToken({ template: "default" }); } catch { token = null; }
            }
            const headers = buildBackendAuthHeaders(
                new URL("/api/gpu/forecast", window.location.origin).toString(),
                { token, userId: userId ?? null },
            );

            // Fetch forecast, workloads, and metrics in parallel
            const [forecastResp, workloadsResp] = await Promise.allSettled([
                fetch("/api/gpu/forecast", { headers }),
                fetch("/api/gpu/workloads", { headers }),
            ]);

            if (forecastResp.status === "fulfilled" && forecastResp.value.ok) {
                setForecast(await forecastResp.value.json());
            }
            if (workloadsResp.status === "fulfilled" && workloadsResp.value.ok) {
                const data = await workloadsResp.value.json();
                setWorkloads(data.workloads || []);
            }

            // Fetch metrics history for trends chart
            try {
                const metricsResp = await fetch("/api/gpu/metrics-history", { headers });
                if (metricsResp.ok) {
                    const metricsData = await metricsResp.json();
                    setMetricsHistory(metricsData.history || []);
                }
            } catch {}
        };

        void fetchSecondary();
    }, [report, getToken, userId]);

    if (loading) {
        return (
            <div className="min-h-[60vh] flex items-center justify-center">
                <div className="h-8 w-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-8 text-center text-red-400">
                <AlertTriangle className="h-8 w-8 mx-auto mb-3" />
                <p>Failed to load GPU data: {error}</p>
            </div>
        );
    }

    if (!report || report.gpu_resources.length === 0) {
        return (
            <div className="min-h-[60vh] flex flex-col items-center justify-center text-center gap-4 p-8">
                <div className="rounded-full bg-purple-500/10 p-4 border border-purple-500/20">
                    <Cpu className="h-8 w-8 text-purple-400" />
                </div>
                <h2 className="text-xl text-white font-semibold">No GPU Instances Detected</h2>
                <p className="text-gray-400 max-w-md text-sm">
                    No GPU instances (P3/P4/P5/G4/G5/Trainium/Inferentia) were found in your last scan.
                    Run a fresh scan or connect an AWS integration with GPU workloads.
                </p>
                <a href="/dashboard/settings" className="px-4 py-2 rounded-lg bg-purple-500 text-white text-sm hover:bg-purple-600 transition-colors">
                    Manage Integrations
                </a>
            </div>
        );
    }

    const { gpu_resources, ghost_gpus, mig_candidates, arbitrage,
        total_gpu_spend, total_gpu_waste, total_savings_available,
        annual_waste_if_unresolved, ai_narrative } = report;

    return (
        <div className="space-y-6 p-4 md:p-8">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <Cpu className="h-5 w-5 text-purple-400" />
                        <h1 className="text-2xl font-bold text-white">GPU Intelligence</h1>
                    </div>
                    <p className="text-sm text-gray-400">
                        Ghost GPU detection · MIG advisor · Specialized cloud arbitrage — not available in AWS Trusted Advisor
                    </p>
                </div>
                <span className="inline-flex items-center gap-2 rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1 text-xs text-purple-300">
                    <Zap className="h-3.5 w-3.5" />
                    Trusted Advisor doesn't do this
                </span>
            </div>

            {/* Hero stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="rounded-xl border border-white/10 bg-black/40 p-5">
                    <p className="text-xs text-gray-400 flex items-center gap-1"><IndianRupee className="h-3 w-3" /> Total GPU Spend</p>
                    <p className="text-2xl text-white font-bold mt-1">{fmt(total_gpu_spend)}</p>
                    <p className="text-xs text-gray-500 mt-1">/month · {gpu_resources.length} instance{gpu_resources.length !== 1 ? "s" : ""}</p>
                </div>
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <p className="text-xs text-red-300 flex items-center gap-1"><Ghost className="h-3 w-3" /> Ghost GPU Waste</p>
                    <p className="text-2xl text-white font-bold mt-1">{fmt(total_gpu_waste)}</p>
                    <p className="text-xs text-red-400 mt-1">{ghost_gpus.length} idle instance{ghost_gpus.length !== 1 ? "s" : ""}</p>
                </div>
                <div className="rounded-xl border border-orange-500/30 bg-orange-500/10 p-5">
                    <p className="text-xs text-orange-300 flex items-center gap-1"><AlertTriangle className="h-3 w-3" /> Annual Burn Rate</p>
                    <p className="text-2xl text-white font-bold mt-1">{fmt(annual_waste_if_unresolved)}</p>
                    <p className="text-xs text-orange-400 mt-1">if ghost GPUs unresolved</p>
                </div>
                <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-5">
                    <p className="text-xs text-green-300 flex items-center gap-1"><TrendingDown className="h-3 w-3" /> Max Monthly Savings</p>
                    <p className="text-2xl text-white font-bold mt-1">{fmt(total_savings_available)}</p>
                    <p className="text-xs text-green-400 mt-1">switching to cheapest GPU cloud</p>
                </div>
            </div>

            {/* Multi-cloud provider filter */}
            {report.providers_detected && report.providers_detected.length > 1 && (
                <div className="flex items-center gap-2">
                    <Globe className="h-4 w-4 text-slate-400" />
                    <span className="text-sm text-slate-400">Filter:</span>
                    <button
                        onClick={() => setProviderFilter(null)}
                        className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                            !providerFilter ? "bg-indigo-600 text-white" : "border border-white/10 text-slate-400 hover:text-white"
                        }`}
                    >
                        All
                    </button>
                    {report.providers_detected.map((p) => (
                        <button
                            key={p}
                            onClick={() => setProviderFilter(p)}
                            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                                providerFilter === p ? "bg-indigo-600 text-white" : "border border-white/10 text-slate-400 hover:text-white"
                            }`}
                        >
                            {p.toUpperCase()}
                        </button>
                    ))}
                </div>
            )}

            {/* AI Narrative */}
            {ai_narrative && (
                <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-5">
                    <div className="flex items-center gap-2 mb-2">
                        <Zap className="h-4 w-4 text-purple-400" />
                        <span className="text-sm font-semibold text-purple-300">AI Analysis</span>
                    </div>
                    <p className="text-sm text-gray-300 leading-relaxed">{ai_narrative}</p>
                </div>
            )}

            {/* Real-time utilization + Cost Forecast */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <GpuUtilizationChart
                    wsUrl={typeof window !== "undefined" ? `ws://${window.location.hostname}:8000` : ""}
                    userId={userId || ""}
                    token={userId || ""}
                />
                <GpuCostForecast forecast={forecast} />
            </div>

            {/* Workload Classification */}
            <GpuWorkloadBadges workloads={workloads} />

            {/* Historical Trends */}
            <GpuHistoricalTrends data={metricsHistory} />

            {/* Ghost GPU Alerts */}
            {ghost_gpus.length > 0 && (
                <div className="space-y-3">
                    <div className="flex items-center gap-2">
                        <Ghost className="h-5 w-5 text-red-400" />
                        <h2 className="text-white font-semibold">Ghost GPUs Detected</h2>
                        <span className="rounded-full bg-red-500/20 text-red-300 px-2 py-0.5 text-xs">{ghost_gpus.length}</span>
                    </div>
                    {ghost_gpus.map((g, i) => (
                        <ExpandableCard
                            key={g.resource_id || i}
                            title={
                                <div className="flex items-start justify-between gap-3 flex-wrap">
                                    <div>
                                        <p className="text-white font-medium">{g.name}</p>
                                        <p className="text-xs text-gray-400 mt-0.5">{g.instance_type} · {g.gpu_type}</p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-red-300 font-semibold">{fmt(g.monthly_cost)}/mo</p>
                                        <p className="text-xs text-red-500">{fmt(g.annual_cost)}/year burning</p>
                                    </div>
                                </div>
                            }
                        >
                            <p className="text-sm text-gray-300 mb-2">{g.ghost_reason}</p>
                            <CodeBlock code={g.fix_command} />
                        </ExpandableCard>
                    ))}
                </div>
            )}

            {/* MIG Partitioning Advisor */}
            {mig_candidates.length > 0 && (
                <div className="space-y-3">
                    <div className="flex items-center gap-2">
                        <Cpu className="h-5 w-5 text-purple-400" />
                        <h2 className="text-white font-semibold">MIG Partitioning Advisor</h2>
                        <span className="rounded-full bg-purple-500/20 text-purple-300 px-2 py-0.5 text-xs">{mig_candidates.length}</span>
                    </div>
                    <p className="text-sm text-gray-400">
                        These A100/H100 instances support NVIDIA MIG — one GPU can become up to 7 logical GPUs, multiplying utilization at zero extra cost.
                    </p>
                    {mig_candidates.map((m, i) => (
                        <ExpandableCard
                            key={m.resource_id || i}
                            title={
                                <div className="flex items-start justify-between gap-3 flex-wrap">
                                    <div>
                                        <p className="text-white font-medium">{m.name}</p>
                                        <p className="text-xs text-gray-400 mt-0.5">{m.instance_type} · {m.gpu_type} · {m.gpu_count} GPU{m.gpu_count > 1 ? "s" : ""}</p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-purple-300 font-semibold">{fmt(m.monthly_cost)}/mo</p>
                                        <p className="text-xs text-purple-400">{m.mig_slices_possible} MIG slices possible</p>
                                    </div>
                                </div>
                            }
                        >
                            <p className="text-sm text-gray-300 mb-2">{m.advice}</p>
                            <CodeBlock code={m.enable_command} />
                        </ExpandableCard>
                    ))}
                </div>
            )}

            {/* Specialized Cloud Arbitrage */}
            {arbitrage.length > 0 && (
                <div className="space-y-3">
                    <div className="flex items-center gap-2">
                        <TrendingDown className="h-5 w-5 text-green-400" />
                        <h2 className="text-white font-semibold">Specialized GPU Cloud Arbitrage</h2>
                    </div>
                    <p className="text-sm text-gray-400">
                        AWS charges a premium for GPU instances. Specialized GPU clouds offer 30–55% lower costs for the same hardware.
                    </p>
                    <div className="space-y-3">
                        {arbitrage.map((a, i) => (
                            <div key={i} className="rounded-xl border border-white/10 bg-black/30 p-5">
                                <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
                                    <div>
                                        <p className="text-white font-semibold">{a.name}</p>
                                        <p className="text-xs text-gray-400 mt-0.5">{a.instance_type} · {a.gpu_type}</p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-green-300 font-semibold">Save {fmt(a.savings)}/mo</p>
                                        <p className="text-xs text-gray-400">{a.savings_pct}% on {a.best_alternative_cloud}</p>
                                    </div>
                                </div>
                                {/* Cloud price comparison grid */}
                                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                                    {Object.entries(a.all_cloud_costs).map(([cloud, cost]) => {
                                        const isBest = cloud === a.best_alternative_cloud;
                                        const isCurrent = cloud === "AWS (On-Demand)";
                                        return (
                                            <div
                                                key={cloud}
                                                className={`rounded-lg p-3 text-center border ${isBest
                                                    ? "border-green-500/40 bg-green-500/10"
                                                    : isCurrent
                                                        ? "border-blue-500/30 bg-blue-500/10"
                                                        : "border-white/10 bg-white/5"
                                                    }`}
                                            >
                                                <p className={`text-xs font-medium mb-1 ${isBest ? "text-green-300" : isCurrent ? "text-blue-300" : "text-gray-400"}`}>
                                                    {isBest && "✓ "}
                                                    {cloud.replace(" (On-Demand)", "")}
                                                </p>
                                                {cost !== null ? (
                                                    <p className="text-white text-sm font-bold">{fmt(cost)}</p>
                                                ) : (
                                                    <p className="text-gray-500 text-xs">N/A</p>
                                                )}
                                                <p className="text-gray-500 text-xs">/mo</p>
                                            </div>
                                        );
                                    })}
                                </div>
                                <div className="flex items-center justify-between mt-3">
                                    <span className={`inline-block rounded border px-2 py-1 text-xs ${complexityColor[a.migration_complexity] || "border-white/20 text-gray-300"}`}>
                                        Migration: {a.migration_complexity} complexity
                                    </span>
                                    <a
                                        href={`https://lambdalabs.com/service/gpu-cloud`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                                    >
                                        Explore alternatives <ExternalLink className="h-3 w-3" />
                                    </a>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* GPU Instances Table */}
            <div className="space-y-2">
                <h2 className="text-white font-semibold">All GPU Instances</h2>
                <div className="rounded-xl border border-white/10 overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-white/10 bg-white/5">
                                    <th className="text-left px-4 py-3 text-xs text-gray-400 font-medium">Instance</th>
                                    <th className="text-left px-4 py-3 text-xs text-gray-400 font-medium">GPU</th>
                                    <th className="text-left px-4 py-3 text-xs text-gray-400 font-medium">Region</th>
                                    <th className="text-right px-4 py-3 text-xs text-gray-400 font-medium">Cost/mo</th>
                                    <th className="text-left px-4 py-3 text-xs text-gray-400 font-medium">SM Occ.</th>
                                    <th className="text-left px-4 py-3 text-xs text-gray-400 font-medium">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {gpu_resources.map((r, i) => (
                                    <tr key={r.id || i} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                                        <td className="px-4 py-3">
                                            <p className="text-white font-medium">{r.name}</p>
                                            <p className="text-xs text-gray-400">{r.instance_type}</p>
                                        </td>
                                        <td className="px-4 py-3 text-gray-300 text-xs">{r.gpu_type}</td>
                                        <td className="px-4 py-3 text-gray-400 text-xs">{r.region || "—"}</td>
                                        <td className="px-4 py-3 text-right text-white font-mono">{fmt(r.monthly_cost)}</td>
                                        <td className="px-4 py-3">
                                            {r.gpu_sm_occupancy_pct !== null ? (
                                                <div className="flex items-center gap-2">
                                                    <div className="w-12 bg-white/10 rounded-full h-1.5">
                                                        <div
                                                            className={`h-1.5 rounded-full ${Number(r.gpu_sm_occupancy_pct) < 20 ? "bg-red-400" : "bg-green-400"}`}
                                                            style={{ width: `${Math.min(Number(r.gpu_sm_occupancy_pct), 100)}%` }}
                                                        />
                                                    </div>
                                                    <span className="text-xs text-gray-400">{r.gpu_sm_occupancy_pct}%</span>
                                                </div>
                                            ) : (
                                                <span className="text-xs text-gray-500">—</span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3">{statusBadge(r)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Disclaimer */}
            <p className="text-xs text-gray-500 text-center border-t border-white/5 pt-4">
                GPU pricing from Lambda Labs, CoreWeave, JarvisLabs, and RunPod public rate cards (2025).
                Migration costs not included. Actual savings depend on reserved pricing and data egress.
            </p>
        </div>
    );
}
