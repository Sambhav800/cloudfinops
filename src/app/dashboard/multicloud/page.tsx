"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import {
    AlertTriangle,
    ArrowRight,
    GitCompare,
    Info,
    Target,
    TrendingDown,
} from "lucide-react";
import {
    Area,
    CartesianGrid,
    Cell,
    ComposedChart,
    Label,
    Line,
    PolarAngleAxis,
    PolarGrid,
    PolarRadiusAxis,
    Radar,
    RadarChart,
    ReferenceLine,
    ResponsiveContainer,
    Sankey,
    Scatter,
    ScatterChart,
    Tooltip,
    XAxis,
    YAxis,
    ZAxis,
} from "recharts";

import { buildBackendAuthHeaders } from "@/app/api/_shared/fetch-with-backend-auth-fallback";
import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";

const PROVIDER_COLORS = { aws: "#FF9900", azure: "#0078D4", gcp: "#4285F4" };
const CHART_STYLE = {
    gridColor: "rgba(255,255,255,0.06)",
    tickColor: "#475569",
    tooltipBg: "#0f172a",
};

type Risk = "Low" | "Medium" | "High";

type CategoryData = {
    current_spend: number;
    aws: number;
    gcp: number;
    azure: number;
    cheapest_cloud: string;
    cheapest_cost: number;
    savings: number;
    savings_pct: number;
    source_service: string;
    aws_equivalent: string;
    gcp_equivalent: string;
    azure_equivalent: string;
    migration_risk: Risk;
    resource_count?: number;
};

type RecommendedMove = {
    category: string;
    from_cloud: string;
    to_cloud: string;
    monthly_savings: number;
    annual_savings?: number;
    savings_pct: number;
    migration_risk: Risk;
    risk_score?: number;
    workload_size?: number;
    resource_count?: number;
    one_time_migration_cost?: number;
    break_even_months?: number | null;
    from_service: string;
    to_service: string;
};

type ProviderScore = {
    cloud: string;
    compute_price: number;
    storage: number;
    network: number;
    gpu: number;
    regions: number;
    commitments: number;
    score_source: string;
};

type MigrationScatterPoint = {
    name: string;
    category: string;
    risk_score: number;
    monthly_savings: number;
    annual_savings: number;
    workload_size: number;
    from_cloud: string;
    to_cloud: string;
    migration_risk: Risk;
};

type RoiPoint = {
    month: number;
    net_value: number;
    cumulative_savings: number;
    one_time_migration_cost: number;
};

type AllocationFlow = {
    nodes: { name: string }[];
    links: { source: string; target: string; value: number }[];
};

type MulticloudReport = {
    source_provider: string;
    by_category: Record<string, CategoryData>;
    recommended_moves: RecommendedMove[];
    total_current_spend: number;
    total_best_case_spend: number;
    total_potential_savings: number;
    savings_pct: number;
    current_total_spend?: number;
    optimized_total_spend?: number;
    monthly_delta?: number;
    annual_delta?: number;
    provider_scores?: ProviderScore[];
    migration_scatter?: MigrationScatterPoint[];
    roi_curve?: RoiPoint[];
    roi_break_even_month?: number | null;
    allocation_flow?: AllocationFlow;
    advisor_notes?: string[];
    disclaimer: string;
};

type SankeyData = {
    nodes: { name: string }[];
    links: { source: number; target: number; value: number }[];
};

const fmt = (value: number) =>
    formatInrCurrency(toDisplayInrAmount(value || 0, "USD"), { minimumFractionDigits: 0, maximumFractionDigits: 0 });

function providerColor(provider: string) {
    const normalized = provider.trim().toLowerCase();
    if (normalized === "aws" || normalized === "azure" || normalized === "gcp") {
        return PROVIDER_COLORS[normalized];
    }
    return "#818cf8";
}

function providerColorByName(name: string) {
    const upper = (name || "").trim().toUpperCase();
    if (upper === "AWS") return PROVIDER_COLORS.aws;
    if (upper === "AZURE") return PROVIDER_COLORS.azure;
    if (upper === "GCP") return PROVIDER_COLORS.gcp;
    return "#818cf8";
}

function riskClassName(risk: Risk) {
    if (risk === "Low") return "bg-emerald-500/10 text-emerald-300";
    if (risk === "High") return "bg-rose-500/10 text-rose-300";
    return "bg-amber-500/10 text-amber-300";
}

function buildRadarData(scores: ProviderScore[]) {
    const byCloud = new Map(scores.map((score) => [score.cloud, score]));
    const axes = [
        ["Compute", "compute_price"],
        ["Storage", "storage"],
        ["Network", "network"],
        ["GPU", "gpu"],
        ["Regions", "regions"],
        ["Commitments", "commitments"],
    ] as const;

    return axes.map(([axis, key]) => ({
        axis,
        AWS: byCloud.get("AWS")?.[key] ?? 0,
        GCP: byCloud.get("GCP")?.[key] ?? 0,
        AZURE: byCloud.get("AZURE")?.[key] ?? 0,
    }));
}

function buildSankeyData(flow?: AllocationFlow): SankeyData {
    const nodeIndex = new Map<string, number>();
    const nodes: { name: string }[] = [];
    const ensureNode = (name: string) => {
        const existing = nodeIndex.get(name);
        if (existing !== undefined) return existing;
        const next = nodes.length;
        nodeIndex.set(name, next);
        nodes.push({ name });
        return next;
    };

    const links = (flow?.links || [])
        .filter((link) => link.value > 0)
        .map((link) => ({
            source: ensureNode(link.source),
            target: ensureNode(link.target),
            value: link.value,
        }));

    return { nodes, links };
}

function AnimatedCurrency({ value }: { value: number }) {
    const [displayValue, setDisplayValue] = useState(0);

    useEffect(() => {
        const duration = 700;
        const startedAt = performance.now();
        let frame = 0;

        const tick = (now: number) => {
            const progress = Math.min((now - startedAt) / duration, 1);
            setDisplayValue(value * progress);
            if (progress < 1) {
                frame = requestAnimationFrame(tick);
            }
        };

        frame = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(frame);
    }, [value]);

    return <>{fmt(displayValue)}</>;
}

type TooltipPayloadEntry = {
    name?: string | number;
    value?: number | string;
    color?: string;
    stroke?: string;
    fill?: string;
    dataKey?: string | number;
    payload?: Record<string, unknown>;
};

function CustomTooltip({
    active,
    payload,
    label,
    variant = "default",
}: {
    active?: boolean;
    payload?: TooltipPayloadEntry[];
    label?: string | number;
    variant?: "default" | "scatter" | "currency";
}) {
    if (!active || !payload || payload.length === 0) return null;

    if (variant === "scatter") {
        const point = payload[0]?.payload as Partial<MigrationScatterPoint> | undefined;
        if (!point) return null;
        const dot = providerColorByName(point.to_cloud || "");
        return (
            <div className="rounded-xl border border-white/10 bg-slate-950/95 p-3 shadow-2xl backdrop-blur-md">
                <p className="text-sm font-semibold text-white">{point.category || point.name}</p>
                <div className="mt-2 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between gap-6">
                        <span className="text-slate-400">Monthly savings</span>
                        <span className="font-semibold text-emerald-300">{fmt(Number(point.monthly_savings ?? 0))}</span>
                    </div>
                    <div className="flex items-center justify-between gap-6">
                        <span className="text-slate-400">Risk score</span>
                        <span className="font-medium text-white">{Math.round(Number(point.risk_score ?? 0))}/100</span>
                    </div>
                    <div className="flex items-center justify-between gap-6">
                        <span className="text-slate-400">Workload size</span>
                        <span className="font-medium text-white">{Number(point.workload_size ?? 0).toFixed(0)}</span>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-6 border-t border-white/10 pt-2">
                        <span className="text-slate-400">Move</span>
                        <span className="flex items-center gap-1.5 font-medium">
                            <span style={{ color: providerColorByName(point.from_cloud || "") }}>{point.from_cloud}</span>
                            <ArrowRight className="h-3 w-3 text-slate-500" />
                            <span className="flex items-center gap-1" style={{ color: dot }}>
                                <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: dot }} />
                                {point.to_cloud}
                            </span>
                        </span>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="rounded-xl border border-white/10 bg-slate-950/95 p-3 shadow-2xl backdrop-blur-md">
            {label !== undefined && label !== "" && (
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-white">
                    {variant === "currency" && typeof label === "number" ? `Month ${label}` : label}
                </p>
            )}
            <div className="space-y-1.5 text-xs">
                {payload.map((entry, index) => {
                    const dot = entry.color || entry.stroke || entry.fill || "#818cf8";
                    const numeric = Number(entry.value ?? 0);
                    return (
                        <div key={`${entry.dataKey ?? entry.name ?? index}`} className="flex items-center justify-between gap-6">
                            <span className="flex items-center gap-2 text-slate-300">
                                <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: dot }} />
                                {entry.name}
                            </span>
                            <span className="font-semibold text-white">{fmt(numeric)}</span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function CustomLegend({ items }: { items: { name: string; color: string }[] }) {
    return (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-2 text-xs text-slate-400">
            {items.map((item) => (
                <span key={item.name} className="inline-flex items-center gap-1.5">
                    <span
                        className="inline-block h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: item.color, boxShadow: `0 0 8px ${item.color}66` }}
                    />
                    <span className="font-medium text-slate-200">{item.name}</span>
                </span>
            ))}
        </div>
    );
}

type SankeyNodeProps = {
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    index?: number;
    payload?: { name?: string; depth?: number };
    containerWidth?: number;
};

function CustomSankeyNode(props: SankeyNodeProps) {
    const { x = 0, y = 0, width = 12, height = 0, payload, containerWidth = 0 } = props;
    const name = payload?.name || "";
    const fill = providerColorByName(name);
    const isLeftSide = containerWidth > 0 ? x + width / 2 < containerWidth / 2 : (payload?.depth ?? 0) === 0;
    const labelX = isLeftSide ? x + width + 8 : x - 8;
    const textAnchor = isLeftSide ? "start" : "end";

    return (
        <g>
            <rect
                x={x}
                y={y}
                width={width}
                height={height}
                rx={4}
                ry={4}
                fill={fill}
                fillOpacity={0.85}
            />
            <text
                x={labelX}
                y={y + height / 2}
                textAnchor={textAnchor}
                dominantBaseline="middle"
                fontSize={12}
                fontWeight={600}
                fill="#ffffff"
            >
                {name}
            </text>
        </g>
    );
}

export default function MulticloudPage() {
    const searchParams = useSearchParams();
    const integrationId = searchParams.get("integration_id") || undefined;

    const { getToken, userId } = useAuth();
    const [report, setReport] = useState<MulticloudReport | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const url = integrationId
            ? `/api/multicloud/comparison?integration_id=${encodeURIComponent(integrationId)}`
            : "/api/multicloud/comparison";

        const loadData = async () => {
            setLoading(true);
            setError(null);
            const controller = new AbortController();
            const timeout = window.setTimeout(() => controller.abort(), 15000);

            try {
                let token = await getToken();
                if (!token) {
                    try {
                        token = await getToken({ template: "default" });
                    } catch {
                        token = null;
                    }
                }
                const requestUrl = new URL(url, window.location.origin).toString();
                const headers = buildBackendAuthHeaders(requestUrl, {
                    token,
                    userId: userId ?? null,
                });

                const response = await fetch(url, { headers, signal: controller.signal, cache: "no-store" });
                if (!response.ok) {
                    const errPayload = await response.json().catch(() => ({}));
                    const detail = typeof errPayload.detail === "string"
                        ? errPayload.detail
                        : typeof errPayload.error === "string"
                            ? errPayload.error
                            : `HTTP ${response.status}`;
                    throw new Error(detail);
                }
                setReport(await response.json() as MulticloudReport);
            } catch (caught) {
                const message = caught instanceof DOMException && caught.name === "AbortError"
                    ? "Request timed out while loading Migration Advisor."
                    : caught instanceof Error
                        ? caught.message
                        : "Failed to load Migration Advisor.";
                setError(message);
            } finally {
                window.clearTimeout(timeout);
                setLoading(false);
            }
        };

        void loadData();
    }, [integrationId, getToken, userId]);

    const radarData = useMemo(() => buildRadarData(report?.provider_scores || []), [report?.provider_scores]);
    const sankeyData = useMemo(() => buildSankeyData(report?.allocation_flow), [report?.allocation_flow]);
    const scatterData = report?.migration_scatter || [];
    const roiData = report?.roi_curve || [];
    const moves = report?.recommended_moves || [];
    const categories = report?.by_category || {};

    const scatterMidpoint = useMemo(() => {
        if (scatterData.length === 0) return 0;
        const max = Math.max(...scatterData.map((point) => point.monthly_savings || 0));
        return max / 2;
    }, [scatterData]);

    const topMoveKey = useMemo(() => {
        if (moves.length === 0) return null;
        let best = moves[0];
        for (const move of moves) {
            if (move.monthly_savings > best.monthly_savings) best = move;
        }
        return `${best.category}-${best.from_cloud}-${best.to_cloud}`;
    }, [moves]);

    if (loading) {
        return (
            <main className="animate-pulse px-4 py-8 md:px-8 lg:px-12">
                <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <div className="h-3 w-36 rounded bg-slate-800/70" />
                        <div className="mt-4 h-7 w-72 rounded bg-slate-800/60" />
                        <div className="mt-3 h-4 w-full max-w-prose rounded bg-slate-800/40" />
                    </div>
                    <div className="grid w-full grid-cols-1 gap-6 sm:grid-cols-3 lg:max-w-2xl">
                        {[1, 2, 3].map((item) => (
                            <div key={item} className="h-20 rounded-lg bg-slate-900/20" />
                        ))}
                    </div>
                </div>
                <div className="mt-16 grid grid-cols-1 gap-6 xl:grid-cols-2">
                    <div className="h-[360px] rounded-xl bg-slate-900/20" />
                    <div className="h-[360px] rounded-xl bg-slate-900/20" />
                </div>
                <div className="mt-16 h-[340px] rounded-xl bg-slate-900/20" />
                <div className="mt-16 overflow-hidden rounded-xl bg-slate-900/20">
                    <div className="h-11 bg-slate-800/30" />
                    {[1, 2, 3, 4].map((item) => (
                        <div key={item} className="h-14 border-b border-white/5" />
                    ))}
                </div>
            </main>
        );
    }

    if (error) {
        return (
            <main className="min-h-screen bg-slate-950 px-4 py-8 md:px-8 lg:px-12">
                <h1 className="text-2xl font-semibold tracking-tight text-white">Migration Advisor</h1>
                <p className="mt-2 max-w-prose text-sm leading-relaxed text-slate-400">
                    CloudFinOps could not load your multi-cloud migration analysis. Refresh the page or verify the backend connection.
                </p>
                <div className="mt-6 flex max-w-prose gap-3 rounded-r-lg border-l-2 border-rose-500/50 bg-rose-500/5 px-4 py-3 text-sm text-rose-300">
                    <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                    <span>{error}</span>
                </div>
            </main>
        );
    }

    if (!report || Object.keys(categories).length === 0) {
        return (
            <main className="flex min-h-[60vh] flex-col items-center justify-center px-4 py-8 text-center md:px-8 lg:px-12">
                <div className="rounded-full bg-indigo-500/5 p-4">
                    <GitCompare className="h-8 w-8 text-indigo-400" />
                </div>
                <h1 className="mt-4 text-2xl font-semibold tracking-tight text-white">No Migration Advisor Data</h1>
                <p className="mt-2 max-w-prose text-sm leading-relaxed text-slate-400">
                    Run a cloud scan first. Migration Advisor uses live-scanned resource costs and deterministic provider multipliers.
                </p>
                <a href="/dashboard/settings" className="mt-6 rounded-xl bg-indigo-600 px-4 py-2 text-sm text-white transition-colors hover:bg-indigo-500">
                    Connect Cloud and Scan
                </a>
            </main>
        );
    }

    const currentSpend = report.current_total_spend ?? report.total_current_spend;
    const optimizedSpend = report.optimized_total_spend ?? report.total_best_case_spend;
    const monthlyDelta = report.monthly_delta ?? report.total_potential_savings;
    const annualDelta = report.annual_delta ?? monthlyDelta * 12;
    const maxMoveSavings = Math.max(...moves.map((move) => move.monthly_savings), 1);

    const radarLegendItems = [
        { name: "AWS", color: PROVIDER_COLORS.aws },
        { name: "GCP", color: PROVIDER_COLORS.gcp },
        { name: "Azure", color: PROVIDER_COLORS.azure },
    ];

    return (
        <main className="px-4 py-8 md:px-8 lg:px-12 animate-in fade-in duration-500">
            <section className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <p className="text-sm font-medium uppercase tracking-wider text-slate-400">Migration Advisor</p>
                    <h1 className="mt-3 text-2xl font-semibold tracking-tight text-white">
                        Current to optimized cloud allocation
                    </h1>
                    <p className="mt-4 max-w-prose text-sm leading-relaxed text-slate-400">
                        Provider-aware migration analysis from scoped live resources. Estimates stay labeled and do not replace actual billing totals.
                    </p>
                </div>
                <div className="text-[10px] font-medium text-slate-500">
                    Scope: <span className="text-slate-300">{report.source_provider}</span>
                </div>
            </section>

            <section className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-3">
                <article>
                    <p className="text-xs text-slate-500">Current Monthly</p>
                    <p className="mt-2 text-3xl font-semibold tracking-tight text-white tabular-nums">
                        <AnimatedCurrency value={currentSpend} />
                    </p>
                    <p className="mt-2 text-xs text-slate-500">{fmt(currentSpend * 12)} annualized current allocation</p>
                </article>
                <article>
                    <p className="text-xs text-slate-500">Optimized Monthly</p>
                    <div className="mt-2 flex items-center gap-3">
                        <span className="text-3xl font-semibold tracking-tight text-white tabular-nums">
                            <AnimatedCurrency value={optimizedSpend} />
                        </span>
                        <ArrowRight className="h-5 w-5 text-slate-500" />
                    </div>
                    <p className="mt-2 text-xs text-slate-500">{fmt(optimizedSpend * 12)} projected annual optimized run rate</p>
                </article>
                <article className="rounded-r-lg border-l-2 border-indigo-500/40 bg-indigo-500/5 px-5 py-4">
                    <p className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                        <TrendingDown className="h-3.5 w-3.5 text-emerald-300" />
                        Animated Delta
                    </p>
                    <p className="mt-2 text-3xl font-semibold tracking-tight text-emerald-300 tabular-nums">
                        <AnimatedCurrency value={monthlyDelta} />
                    </p>
                    <p className="mt-2 text-xs text-slate-500">{fmt(annualDelta)} annual potential at {report.savings_pct}% reduction</p>
                </article>
            </section>

            <section className="mt-16">
                <h2 className="text-sm font-medium uppercase tracking-wider text-slate-400">Capability and risk</h2>
                <p className="mt-4 max-w-prose text-sm leading-relaxed text-slate-400">
                    Six-axis provider scoring and the migration bubble map separate rate-card attractiveness from execution risk.
                </p>

                <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
                    <div>
                        <div className="mb-4">
                            <h3 className="text-sm font-medium text-white">Provider Capability Radar</h3>
                            <p className="mt-1 text-sm text-slate-500">Six-axis rate-card score, not a replacement for actual billing.</p>
                        </div>
                        <div className="h-[360px] rounded-xl bg-slate-900/20 p-4">
                        {radarData.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <RadarChart data={radarData}>
                                    <PolarGrid stroke={CHART_STYLE.gridColor} />
                                    <PolarAngleAxis dataKey="axis" tick={{ fill: "#cbd5e1", fontSize: 12 }} />
                                    <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: CHART_STYLE.tickColor, fontSize: 10 }} />
                                    <Radar dataKey="AWS" stroke={PROVIDER_COLORS.aws} fill={PROVIDER_COLORS.aws} fillOpacity={0.18} />
                                    <Radar dataKey="GCP" stroke={PROVIDER_COLORS.gcp} fill={PROVIDER_COLORS.gcp} fillOpacity={0.16} />
                                    <Radar dataKey="AZURE" stroke={PROVIDER_COLORS.azure} fill={PROVIDER_COLORS.azure} fillOpacity={0.14} />
                                    <Tooltip content={<CustomTooltip />} />
                                </RadarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-500">
                                Provider scoring is unavailable for this scan.
                            </div>
                        )}
                        </div>
                        {radarData.length > 0 && <CustomLegend items={radarLegendItems} />}
                    </div>

                    <div>
                        <div className="mb-4">
                            <h3 className="text-sm font-medium text-white">Risk by Savings</h3>
                            <p className="mt-1 text-sm text-slate-500">Each bubble is a migration candidate: risk on x, monthly savings on y, workload size as area.</p>
                        </div>
                        <div className="h-[360px] rounded-xl bg-slate-900/20 p-4">
                        {scatterData.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <ScatterChart margin={{ top: 16, right: 24, bottom: 16, left: 8 }}>
                                    <defs>
                                        <filter id="bubbleGlow" x="-50%" y="-50%" width="200%" height="200%">
                                            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                                            <feMerge>
                                                <feMergeNode in="coloredBlur" />
                                                <feMergeNode in="SourceGraphic" />
                                            </feMerge>
                                        </filter>
                                    </defs>
                                    <CartesianGrid stroke={CHART_STYLE.gridColor} />
                                    <XAxis type="number" dataKey="risk_score" name="Risk" domain={[0, 100]} tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }} />
                                    <YAxis type="number" dataKey="monthly_savings" name="Savings" tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }} tickFormatter={(value) => fmt(Number(value))} width={86} />
                                    <ZAxis type="number" dataKey="workload_size" range={[90, 420]} />
                                    <Tooltip cursor={{ strokeDasharray: "3 3" }} content={<CustomTooltip variant="scatter" />} />
                                    <ReferenceLine x={50} stroke="rgba(148,163,184,0.25)" strokeDasharray="4 4">
                                        <Label value="medium risk" position="top" fill="#475569" fontSize={10} />
                                    </ReferenceLine>
                                    {scatterMidpoint > 0 && (
                                        <ReferenceLine y={scatterMidpoint} stroke="rgba(148,163,184,0.25)" strokeDasharray="4 4" />
                                    )}
                                    <ReferenceLine x={5} stroke="transparent">
                                        <Label value="Quick wins" position="insideTopLeft" fill="#64748b" fontSize={10} fontStyle="italic" />
                                    </ReferenceLine>
                                    <ReferenceLine x={95} stroke="transparent">
                                        <Label value="Big bets" position="insideTopRight" fill="#64748b" fontSize={10} fontStyle="italic" />
                                    </ReferenceLine>
                                    <ReferenceLine y={0} stroke="transparent">
                                        <Label value="Easy wins" position="insideBottomLeft" fill="#64748b" fontSize={10} fontStyle="italic" />
                                        <Label value="Skip" position="insideBottomRight" fill="#64748b" fontSize={10} fontStyle="italic" />
                                    </ReferenceLine>
                                    <Scatter data={scatterData} name="Migrations">
                                        {scatterData.map((point) => (
                                            <Cell key={point.name} fill={providerColor(point.to_cloud)} fillOpacity={0.78} style={{ filter: "url(#bubbleGlow)" }} />
                                        ))}
                                    </Scatter>
                                </ScatterChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-500">
                                No migration candidates have positive estimated savings yet.
                            </div>
                        )}
                        </div>
                        {scatterData.length > 0 && <CustomLegend items={radarLegendItems} />}
                    </div>
                </div>
            </section>

            <section className="mt-16">
                <h2 className="text-sm font-medium uppercase tracking-wider text-slate-400">Return path</h2>
                <p className="mt-4 max-w-prose text-sm leading-relaxed text-slate-400">
                    Break-even timing and allocation flow connect migration economics to target-cloud placement.
                </p>

                <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[0.95fr_1.05fr]">
                    <div>
                        <div className="mb-4">
                            <h3 className="text-sm font-medium text-white">ROI Break-Even</h3>
                            <p className="mt-1 text-sm text-slate-500">Projected cumulative net value after estimated one-time migration cost.</p>
                        </div>
                        <div className="h-[340px] rounded-xl bg-slate-900/20 p-4">
                        {roiData.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <ComposedChart data={roiData}>
                                    <defs>
                                        <linearGradient id="roiPositiveFill" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="0%" stopColor="#34d399" stopOpacity={0.35} />
                                            <stop offset="100%" stopColor="#34d399" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient id="roiNegativeFill" x1="0" y1="1" x2="0" y2="0">
                                            <stop offset="0%" stopColor="#f43f5e" stopOpacity={0.3} />
                                            <stop offset="100%" stopColor="#f43f5e" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid stroke={CHART_STYLE.gridColor} vertical={false} />
                                    <XAxis
                                        dataKey="month"
                                        tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }}
                                        tickFormatter={(value) => `M${value}`}
                                    />
                                    <YAxis tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }} tickFormatter={(value) => fmt(Number(value))} width={88} />
                                    <Tooltip content={<CustomTooltip variant="currency" />} />
                                    <ReferenceLine y={0} stroke="rgba(255,255,255,0.25)" />
                                    {report.roi_break_even_month && (
                                        <ReferenceLine x={report.roi_break_even_month} stroke="#34d399" strokeDasharray="4 4">
                                            <Label
                                                value={`Break-even: month ${report.roi_break_even_month}`}
                                                position="top"
                                                fill="#34d399"
                                                fontSize={11}
                                                fontWeight={600}
                                            />
                                        </ReferenceLine>
                                    )}
                                    <Area
                                        type="monotone"
                                        dataKey={((point: RoiPoint) => (point.net_value >= 0 ? point.net_value : 0)) as unknown as string}
                                        stroke="none"
                                        fill="url(#roiPositiveFill)"
                                        isAnimationActive
                                        legendType="none"
                                        name="Positive area"
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey={((point: RoiPoint) => (point.net_value < 0 ? point.net_value : 0)) as unknown as string}
                                        stroke="none"
                                        fill="url(#roiNegativeFill)"
                                        isAnimationActive
                                        legendType="none"
                                        name="Negative area"
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="net_value"
                                        name="Net value"
                                        stroke="#34d399"
                                        strokeWidth={3}
                                        dot={false}
                                        activeDot={{ r: 5, fill: "#34d399", stroke: "#0f172a", strokeWidth: 2 }}
                                    />
                                </ComposedChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-500">
                                ROI curve needs at least one positive-savings migration candidate.
                            </div>
                        )}
                        </div>
                    </div>

                    <div>
                        <div className="mb-4">
                            <h3 className="text-sm font-medium text-white">Allocation Flow</h3>
                            <p className="mt-1 text-sm text-slate-500">Current provider allocation to projected optimized allocation.</p>
                        </div>
                        <div className="h-[340px] rounded-xl bg-slate-900/20 p-4">
                        {sankeyData.nodes.length > 0 && sankeyData.links.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <Sankey
                                    data={sankeyData}
                                    nodePadding={22}
                                    nodeWidth={14}
                                    link={{ stroke: "rgba(255,255,255,0.10)", strokeOpacity: 1 }}
                                    node={<CustomSankeyNode />}
                                    margin={{ top: 12, right: 80, bottom: 12, left: 80 }}
                                >
                                    <Tooltip content={<CustomTooltip />} />
                                </Sankey>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-500">
                                No allocation shift can be drawn until recommendations exist.
                            </div>
                        )}
                        </div>
                    </div>
                </div>
            </section>

            <section className="mt-16">
                <div className="mb-6 flex items-start gap-3">
                    <Target className="mt-0.5 h-5 w-5 text-indigo-300" />
                    <div>
                        <h2 className="text-sm font-medium uppercase tracking-wider text-slate-400">Service Migration Table</h2>
                        <p className="mt-4 max-w-prose text-sm leading-relaxed text-slate-400">Inline bars compare each candidate against the highest savings move in this scope.</p>
                    </div>
                </div>
                <div className="overflow-hidden rounded-xl bg-slate-900/20">
                    <div className="overflow-x-auto">
                    <table className="w-full min-w-[920px] table-fixed text-sm">
                        <thead className="border-b border-white/5 bg-slate-800/30 text-xs font-medium uppercase text-slate-500">
                            <tr>
                                <th className="w-[20%] px-4 py-3 text-left font-medium">Service</th>
                                <th className="w-[16%] px-4 py-3 text-left font-medium">Move</th>
                                <th className="w-[12%] px-4 py-3 text-left font-medium">Risk</th>
                                <th className="w-[28%] px-4 py-3 text-left font-medium">Monthly Savings</th>
                                <th className="w-[12%] px-4 py-3 text-right font-medium">Annual</th>
                                <th className="w-[12%] px-4 py-3 text-right font-medium">Break-even</th>
                            </tr>
                        </thead>
                        <tbody>
                            {moves.length > 0 ? moves.map((move) => {
                                const width = Math.max(6, (move.monthly_savings / maxMoveSavings) * 100);
                                const rowKey = `${move.category}-${move.from_cloud}-${move.to_cloud}`;
                                const isTop = rowKey === topMoveKey;
                                return (
                                    <tr
                                        key={rowKey}
                                        className={`border-b border-white/5 transition-colors hover:bg-white/[0.02] ${isTop ? "bg-indigo-500/5" : ""}`}
                                    >
                                        <td className="px-4 py-4">
                                            <div className="flex items-center gap-2">
                                                {isTop && (
                                                    <span className="relative flex h-2 w-2 flex-shrink-0">
                                                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                                                        <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
                                                    </span>
                                                )}
                                                <p className="font-medium text-white">{move.category}</p>
                                            </div>
                                            <p className="mt-1 truncate text-xs text-slate-500">{move.from_service} to {move.to_service}</p>
                                        </td>
                                        <td className="px-4 py-4">
                                            <div className="flex items-center gap-2 text-xs text-slate-300">
                                                <span style={{ color: providerColor(move.from_cloud) }}>{move.from_cloud}</span>
                                                <ArrowRight className="h-3.5 w-3.5 text-slate-600" />
                                                <span style={{ color: providerColor(move.to_cloud) }}>{move.to_cloud}</span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-4">
                                            <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${riskClassName(move.migration_risk)}`}>
                                                {move.migration_risk}
                                            </span>
                                        </td>
                                        <td className="px-4 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800/80">
                                                    <div
                                                        className="h-2 rounded-full bg-gradient-to-r from-emerald-500 to-emerald-300 shadow-[0_0_8px_rgba(52,211,153,0.4)] transition-all"
                                                        style={{ width: `${width}%` }}
                                                    />
                                                </div>
                                                <span className="w-24 text-right font-semibold text-emerald-300 tabular-nums">{fmt(move.monthly_savings)}</span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-4 text-right text-white tabular-nums">{fmt(move.annual_savings ?? move.monthly_savings * 12)}</td>
                                        <td className="px-4 py-4 text-right text-slate-300">{move.break_even_months ? `${move.break_even_months} mo` : "TBD"}</td>
                                    </tr>
                                );
                            }) : (
                                <tr>
                                    <td colSpan={6} className="px-4 py-10 text-center text-slate-500">No positive-savings migration candidates in this scope.</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                    </div>
                </div>
            </section>

            <section className="mt-16 rounded-r-lg border-l-2 border-indigo-500/40 bg-indigo-500/5 px-5 py-4">
                <div className="flex gap-3">
                    <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-indigo-300" />
                    <div className="space-y-2 text-xs leading-6 text-slate-500">
                        {report.advisor_notes?.map((note) => <p key={note}>{note}</p>)}
                        <p>{report.disclaimer}</p>
                    </div>
                </div>
            </section>
        </main>
    );
}
