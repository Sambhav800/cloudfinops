"use client";

import { useMemo, type ReactNode } from "react";
import { Activity, ArrowRight, Cloud, MessageSquare, Sparkles } from "lucide-react";
import {
    Area,
    AreaChart,
    CartesianGrid,
    ResponsiveContainer,
    Sankey,
    Tooltip,
    Treemap,
    XAxis,
    YAxis,
} from "recharts";

import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";

const PROVIDER_COLORS = { aws: "#FF9900", azure: "#0078D4", gcp: "#4285F4" };
const CHART_STYLE = {
    gridColor: "rgba(255,255,255,0.06)",
    tickColor: "#475569",
    tooltipBg: "#0f172a",
};

const PROVIDER_ORDER = { AWS: 0, AZURE: 1, GCP: 2 } as const;
const SANKEY_TOP_SERVICES = 10;
const TOPOLOGY_COLORS = ["#818cf8", "#34d399", "#f59e0b", "#fb7185", "#22d3ee"];

type ProviderSummary = {
    provider: string;
    monthly_spend: number;
    potential_savings: number;
    resource_count: number;
    last_scan?: string | null;
    integration_count?: number;
    integration_ids?: string[];
    account_identifiers?: string[];
};

type CategoryRow = {
    category: string;
    by_provider: Record<string, number>;
    total: number;
};

type DailyProviderSpend = {
    spend_date: string;
    aws: number;
    azure: number;
    gcp: number;
    total: number;
};

type HeatmapDay = {
    spend_date: string;
    amount: number;
    intensity: number;
};

type ProviderForecast = {
    provider: string;
    forecast_monthly: number;
    forecast_annual: number;
    history_days: number;
    forecast_source: string;
};

type ServiceHierarchyChild = {
    name: string;
    service: string;
    provider: string;
    value: number;
    resource_count: number;
    cost_sources: string[];
};

type ServiceHierarchyNode = {
    name: string;
    value: number;
    children: ServiceHierarchyChild[];
};

type SpendFlow = {
    provider: string;
    category: string;
    service: string;
    value: number;
    resource_count: number;
    cost_sources: string[];
};

export type TotalBillResponse = {
    total_spend: number;
    total_savings: number;
    total_resources: number;
    provider_count: number;
    providers: ProviderSummary[];
    categories: CategoryRow[];
    daily_provider_spend_30d?: DailyProviderSpend[];
    heatmap_days?: HeatmapDay[];
    provider_forecasts?: ProviderForecast[];
    service_hierarchy?: ServiceHierarchyNode[];
    spend_flows?: SpendFlow[];
    visual_currency?: string;
    visual_data_notes?: string[];
};

type SankeyNode = { name: string };
type SankeyLink = { source: number; target: number; value: number };
type SankeyData = { nodes: SankeyNode[]; links: SankeyLink[] };

type TooltipSeriesPayload = {
    name?: string | number;
    value?: number | string;
    color?: string;
    payload?: Record<string, unknown>;
    dataKey?: string | number;
};

type TopServiceRow = {
    key: string;
    name: string;
    service: string;
    provider: string;
    category: string;
    value: number;
    resourceCount: number;
    costSources: string[];
};

function sourceCurrencyForProvider(provider: string) {
    const normalized = provider.trim().toUpperCase();
    return normalized === "AWS" || normalized === "AZURE" ? "USD" : "INR";
}

function toProviderDisplayAmount(value: number, provider: string) {
    return toDisplayInrAmount(value || 0, sourceCurrencyForProvider(provider));
}

function formatCurrency(value: number) {
    return formatInrCurrency(value || 0, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function formatPercent(value: number) {
    return `${value.toFixed(1)}%`;
}

function providerLabel(provider: string) {
    const normalized = provider.trim().toUpperCase();
    if (normalized === "AZURE") return "Azure";
    if (normalized === "AWS" || normalized === "GCP") return normalized;
    return provider || "Unknown";
}

function providerColor(provider: string) {
    const normalized = provider.trim().toLowerCase();
    if (normalized === "aws" || normalized === "azure" || normalized === "gcp") {
        return PROVIDER_COLORS[normalized];
    }
    return "#818cf8";
}

function formatRelativeScan(lastScan?: string | null) {
    if (!lastScan) return "Never scanned";
    const parsed = new Date(lastScan);
    if (Number.isNaN(parsed.getTime())) return "Scan time unavailable";
    const deltaMs = Date.now() - parsed.getTime();
    const hours = Math.max(Math.floor(deltaMs / (1000 * 60 * 60)), 0);
    if (hours < 1) return "Last scan less than an hour ago";
    if (hours < 24) return `Last scan ${hours} hour${hours === 1 ? "" : "s"} ago`;
    const days = Math.floor(hours / 24);
    return `Last scan ${days} day${days === 1 ? "" : "s"} ago`;
}

function toDisplayTotalBillData(data: TotalBillResponse): TotalBillResponse {
    const providers = data.providers.map((provider) => ({
        ...provider,
        monthly_spend: toProviderDisplayAmount(provider.monthly_spend, provider.provider),
        potential_savings: toProviderDisplayAmount(provider.potential_savings, provider.provider),
    }));
    const categories = data.categories.map((category) => {
        const byProvider = Object.fromEntries(
            Object.entries(category.by_provider).map(([provider, amount]) => [
                provider,
                toProviderDisplayAmount(amount, provider),
            ])
        ) as Record<string, number>;
        const total = Object.values(byProvider).reduce((sum, amount) => sum + amount, 0);
        return {
            ...category,
            by_provider: byProvider,
            total: Math.round(total * 100) / 100,
        };
    });
    const totalSpend = providers.reduce((sum, provider) => sum + provider.monthly_spend, 0);
    const totalSavings = providers.reduce((sum, provider) => sum + provider.potential_savings, 0);

    return {
        ...data,
        total_spend: Math.round(totalSpend * 100) / 100,
        total_savings: Math.round(totalSavings * 100) / 100,
        providers,
        categories,
    };
}

function convertHierarchy(nodes: ServiceHierarchyNode[] | undefined): ServiceHierarchyNode[] {
    return (nodes || [])
        .map((node) => {
            const children = node.children.map((child) => ({
                ...child,
                value: Math.round(toProviderDisplayAmount(child.value, child.provider) * 100) / 100,
            }));
            return {
                ...node,
                children,
                value: Math.round(children.reduce((sum, child) => sum + child.value, 0) * 100) / 100,
            };
        })
        .filter((node) => node.value > 0);
}

function shortenServiceName(rawName: string): string {
    if (!rawName) return rawName;
    const cleaned = rawName.trim();
    const lower = cleaned.toLowerCase();
    const prefixes = ["aws ", "azure ", "gcp ", "google ", "google cloud "];
    for (const prefix of prefixes) {
        if (lower.startsWith(prefix)) {
            return cleaned.slice(prefix.length).trim();
        }
    }
    return cleaned;
}

function topologyColor(seed: string) {
    let hash = 0;
    for (let index = 0; index < seed.length; index += 1) {
        hash = (hash + seed.charCodeAt(index) * (index + 1)) % TOPOLOGY_COLORS.length;
    }
    return TOPOLOGY_COLORS[hash];
}

function buildSankeyData(flows: SpendFlow[] | undefined): SankeyData {
    if (!flows || flows.length === 0) return { nodes: [], links: [] };

    type AggregatedFlow = { provider: string; category: string; service: string; value: number };
    const aggregated: AggregatedFlow[] = [];
    const serviceTotals = new Map<string, number>();

    for (const flow of flows) {
        const converted = toProviderDisplayAmount(flow.value, flow.provider);
        if (converted <= 0) continue;
        const provider = providerLabel(flow.provider);
        const service = shortenServiceName(flow.service);
        aggregated.push({ provider, category: flow.category, service, value: converted });
        serviceTotals.set(service, (serviceTotals.get(service) || 0) + converted);
    }

    const rankedServices = Array.from(serviceTotals.entries()).sort((left, right) => right[1] - left[1]);
    const keepSet = new Set(rankedServices.slice(0, SANKEY_TOP_SERVICES).map(([name]) => name));

    const nodeIndex = new Map<string, number>();
    const links = new Map<string, SankeyLink>();
    const nodes: SankeyNode[] = [];

    const ensureNode = (name: string) => {
        const existing = nodeIndex.get(name);
        if (existing !== undefined) return existing;
        const next = nodes.length;
        nodes.push({ name });
        nodeIndex.set(name, next);
        return next;
    };

    const addLink = (sourceName: string, targetName: string, value: number) => {
        if (value <= 0) return;
        const source = ensureNode(sourceName);
        const target = ensureNode(targetName);
        const key = `${source}:${target}`;
        const existing = links.get(key);
        if (existing) {
            existing.value = Math.round((existing.value + value) * 100) / 100;
            return;
        }
        links.set(key, { source, target, value: Math.round(value * 100) / 100 });
    };

    for (const flow of aggregated) {
        const leaf = keepSet.has(flow.service) ? flow.service : "Other services";
        addLink(flow.provider, flow.category, flow.value);
        addLink(flow.category, leaf, flow.value);
    }

    return { nodes, links: Array.from(links.values()) };
}

function buildTopServiceRows(hierarchy: ServiceHierarchyNode[]): TopServiceRow[] {
    return hierarchy
        .flatMap((node) =>
            node.children.map((child) => ({
                key: `${node.name}-${child.provider}-${child.service}-${child.name}`,
                name: child.name,
                service: child.service,
                provider: providerLabel(child.provider),
                category: node.name,
                value: child.value,
                resourceCount: child.resource_count,
                costSources: child.cost_sources,
            }))
        )
        .sort((left, right) => right.value - left.value)
        .slice(0, 10);
}

function CustomTooltip({
    active,
    payload,
    label,
}: {
    active?: boolean;
    payload?: TooltipSeriesPayload[];
    label?: string | number;
}) {
    if (!active || !payload || payload.length === 0) return null;

    const titleSource = label ?? payload[0]?.payload?.name ?? payload[0]?.name ?? "";
    const title = typeof titleSource === "string" || typeof titleSource === "number" ? String(titleSource) : "";

    return (
        <div
            className="rounded-lg border border-white/10 p-3 shadow-xl backdrop-blur-md"
            style={{ backgroundColor: CHART_STYLE.tooltipBg }}
        >
            {title && <p className="mb-2 text-xs font-medium uppercase tracking-wider text-white">{title}</p>}
            <div className="space-y-1.5">
                {payload.map((entry, index) => {
                    const seriesName = typeof entry.name === "string" ? entry.name : String(entry.dataKey ?? "Value");
                    const numeric = typeof entry.value === "number" ? entry.value : Number(entry.value ?? 0);
                    const color = entry.color || "#818cf8";
                    return (
                        <div key={`${seriesName}-${index}`} className="flex items-center justify-between gap-4 text-xs">
                            <span className="flex items-center gap-2 text-slate-300">
                                <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                                {seriesName}
                            </span>
                            <span className="font-medium tabular-nums text-white">{formatCurrency(numeric)}</span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function ProviderLegend() {
    const items: Array<{ key: keyof typeof PROVIDER_COLORS; label: string }> = [
        { key: "aws", label: "AWS" },
        { key: "azure", label: "Azure" },
        { key: "gcp", label: "GCP" },
    ];
    return (
        <div className="flex items-center gap-5 text-xs text-slate-500">
            {items.map((item) => (
                <span key={item.key} className="flex items-center gap-2">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: PROVIDER_COLORS[item.key] }} />
                    {item.label}
                </span>
            ))}
        </div>
    );
}

type TreemapNodeProps = {
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    name?: string;
    value?: number;
    payload?: { provider?: string; name?: string; value?: number };
    provider?: string;
    depth?: number;
};

function CustomTreemapNode(props: TreemapNodeProps) {
    const { x = 0, y = 0, width = 0, height = 0, name = "", value = 0, payload, depth } = props;
    if (depth === 0) return null;

    const color = topologyColor(`${payload?.provider || props.provider || ""}-${name}`);
    const gap = Math.min(5, width / 6, height / 6);
    const innerX = x + gap;
    const innerY = y + gap;
    const innerWidth = Math.max(width - gap * 2, 0);
    const innerHeight = Math.max(height - gap * 2, 0);
    const showLabel = innerWidth > 74 && innerHeight > 46;
    const showValue = innerHeight > 72;
    if (innerWidth <= 0 || innerHeight <= 0) return null;

    return (
        <g>
            <rect
                x={innerX}
                y={innerY}
                width={innerWidth}
                height={innerHeight}
                rx={10}
                ry={10}
                fill={color}
                fillOpacity={0.6}
                className="transition-opacity hover:opacity-95"
            />
            {showLabel && (
                <foreignObject
                    x={innerX + 10}
                    y={innerY + 8}
                    width={Math.max(innerWidth - 20, 20)}
                    height={Math.max(innerHeight - 16, 20)}
                    style={{ pointerEvents: "none" }}
                >
                    <div className="flex h-full w-full flex-col justify-between overflow-hidden">
                        <span className="line-clamp-2 text-[11px] font-medium leading-4 text-white">{name}</span>
                        {showValue && (
                            <span className="mt-2 text-[11px] font-semibold tabular-nums leading-none text-white">
                                {formatCurrency(Number(value) || 0)}
                            </span>
                        )}
                    </div>
                </foreignObject>
            )}
        </g>
    );
}

type SankeyNodeProps = {
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    payload?: { name?: string; value?: number };
    containerWidth?: number;
};

function CustomSankeyNode(props: SankeyNodeProps) {
    const { x = 0, y = 0, width = 0, height = 0, payload, containerWidth = 0 } = props;
    const name = payload?.name || "";
    const fill = providerColor(name);
    const isLeftSide = x + width / 2 < containerWidth / 2;
    const labelX = isLeftSide ? x - 8 : x + width + 8;
    const textAnchor = isLeftSide ? "end" : "start";
    const value = payload?.value || 0;

    return (
        <g>
            <rect x={x} y={y} width={width} height={Math.max(height, 2)} rx={4} ry={4} fill={fill} fillOpacity={0.86} />
            <text
                x={labelX}
                y={y + height / 2}
                textAnchor={textAnchor}
                dominantBaseline="middle"
                fill="#e2e8f0"
                fontSize={11}
                fontWeight={500}
                style={{ pointerEvents: "none" }}
            >
                {name}
            </text>
            {height > 20 && (
                <text
                    x={labelX}
                    y={y + height / 2 + 14}
                    textAnchor={textAnchor}
                    dominantBaseline="middle"
                    fill="#64748b"
                    fontSize={10}
                    style={{ pointerEvents: "none" }}
                >
                    {formatCurrency(Number(value) || 0)}
                </text>
            )}
        </g>
    );
}

function NoDataPanel({ label }: { label: string }) {
    return (
        <div className="flex h-full min-h-[220px] items-center justify-center rounded-xl bg-slate-900/20 px-6 text-center text-sm text-slate-500">
            {label}
        </div>
    );
}

function SectionTitle({ children, detail }: { children: ReactNode; detail?: string }) {
    return (
        <div>
            <h2 className="text-sm font-medium uppercase tracking-wider text-slate-400">{children}</h2>
            {detail && <p className="mt-2 max-w-prose text-sm leading-relaxed text-slate-500">{detail}</p>}
        </div>
    );
}

function MiniMetric({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
    return (
        <div className="min-w-[130px]">
            <div className="flex items-center gap-2 text-indigo-400">{icon}</div>
            <p className="mt-2 text-xs text-slate-500">{label}</p>
            <div className="mt-2 h-px w-full bg-white/5" />
            <p className="mt-2 text-lg font-medium tabular-nums text-white">{value}</p>
        </div>
    );
}

function SpendOrbitHero({ data }: { data: TotalBillResponse }) {
    return (
        <section className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
            <div>
                <h1 className="text-2xl font-semibold tracking-tight text-white">Total Bill</h1>
                <p className="mt-1 max-w-prose text-sm leading-relaxed text-slate-400">Unified multi-cloud spend overview</p>
                <p className="mt-2 text-4xl font-semibold tracking-tight text-white tabular-nums">
                    {formatCurrency(data.total_spend)}
                </p>
                <p className="mt-2 text-xs text-slate-500">{formatCurrency(data.total_spend * 12)} annualized current run rate</p>
            </div>

            <div className="grid gap-6 sm:grid-cols-3 lg:min-w-[500px]">
                <MiniMetric
                    icon={<Activity className="h-4 w-4" />}
                    label="Savings identified"
                    value={formatCurrency(data.total_savings)}
                />
                <MiniMetric
                    icon={<Cloud className="h-4 w-4" />}
                    label="Connected clouds"
                    value={data.provider_count.toLocaleString()}
                />
                <MiniMetric
                    icon={<Sparkles className="h-4 w-4" />}
                    label="Resources tracked"
                    value={data.total_resources.toLocaleString()}
                />
            </div>
        </section>
    );
}

function ProviderAllocationStrip({ providers, totalSpend }: { providers: ProviderSummary[]; totalSpend: number }) {
    if (providers.length === 0) {
        return <NoDataPanel label="Connect a cloud provider to see provider allocation." />;
    }

    let offset = 0;
    return (
        <section className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-4">
                <SectionTitle detail="Provider mix based on the same monthly spend total used by the hero.">Provider Allocation</SectionTitle>
                <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-500">
                    {providers.map((provider) => {
                        const share = totalSpend > 0 ? (provider.monthly_spend / totalSpend) * 100 : 0;
                        return (
                            <span key={provider.provider} className="flex items-center gap-2">
                                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: providerColor(provider.provider) }} />
                                {providerLabel(provider.provider)} {formatPercent(share)}
                            </span>
                        );
                    })}
                </div>
            </div>

            <div className="relative h-2 overflow-hidden rounded-full bg-slate-800">
                {providers.map((provider) => {
                    const share = totalSpend > 0 ? (provider.monthly_spend / totalSpend) * 100 : 0;
                    const left = offset;
                    offset += share;
                    return (
                        <div
                            key={provider.provider}
                            className="absolute inset-y-0"
                            style={{
                                left: `${left}%`,
                                width: `${Math.max(share, 0.35)}%`,
                                backgroundColor: providerColor(provider.provider),
                            }}
                        />
                    );
                })}
            </div>
        </section>
    );
}

function TrendForecastChart({
    dailySpend,
    forecastByProvider,
}: {
    dailySpend: DailyProviderSpend[];
    forecastByProvider: Map<string, ProviderForecast>;
}) {
    const forecastTotal = Array.from(forecastByProvider.values()).reduce((sum, forecast) => {
        return sum + Math.max(forecast.forecast_monthly || 0, 0);
    }, 0);
    const forecastDaily = forecastTotal > 0 ? forecastTotal / 30 : 0;
    const trendData = dailySpend.map((day) => ({
        ...day,
        forecast_daily: forecastDaily,
    }));

    return (
        <section className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-4">
                <SectionTitle detail="Stacked daily actuals with forecast run-rate overlay from provider forecasts.">Spend Trend</SectionTitle>
                <ProviderLegend />
            </div>
            <div className="h-[320px] rounded-xl bg-slate-900/20 p-4">
                {trendData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={trendData} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
                            <defs>
                                <linearGradient id="dailyAwsFill" x1="0" x2="0" y1="0" y2="1">
                                    <stop offset="0%" stopColor={PROVIDER_COLORS.aws} stopOpacity={0.28} />
                                    <stop offset="100%" stopColor={PROVIDER_COLORS.aws} stopOpacity={0} />
                                </linearGradient>
                                <linearGradient id="dailyAzureFill" x1="0" x2="0" y1="0" y2="1">
                                    <stop offset="0%" stopColor={PROVIDER_COLORS.azure} stopOpacity={0.24} />
                                    <stop offset="100%" stopColor={PROVIDER_COLORS.azure} stopOpacity={0} />
                                </linearGradient>
                                <linearGradient id="dailyGcpFill" x1="0" x2="0" y1="0" y2="1">
                                    <stop offset="0%" stopColor={PROVIDER_COLORS.gcp} stopOpacity={0.22} />
                                    <stop offset="100%" stopColor={PROVIDER_COLORS.gcp} stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid stroke={CHART_STYLE.gridColor} vertical={false} />
                            <XAxis dataKey="spend_date" tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={28} />
                            <YAxis tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(value) => formatCurrency(Number(value))} width={88} />
                            <Tooltip content={<CustomTooltip />} cursor={{ stroke: "rgba(255,255,255,0.14)" }} />
                            <Area dataKey="aws" stackId="spend" type="monotone" stroke={PROVIDER_COLORS.aws} strokeWidth={2} fill="url(#dailyAwsFill)" name="AWS" />
                            <Area dataKey="azure" stackId="spend" type="monotone" stroke={PROVIDER_COLORS.azure} strokeWidth={2} fill="url(#dailyAzureFill)" name="Azure" />
                            <Area dataKey="gcp" stackId="spend" type="monotone" stroke={PROVIDER_COLORS.gcp} strokeWidth={2} fill="url(#dailyGcpFill)" name="GCP" />
                            {forecastDaily > 0 && (
                                <Area
                                    dataKey="forecast_daily"
                                    type="monotone"
                                    stroke="#c4b5fd"
                                    strokeWidth={2}
                                    strokeDasharray="6 6"
                                    fill="transparent"
                                    name="Forecast daily"
                                />
                            )}
                        </AreaChart>
                    </ResponsiveContainer>
                ) : (
                    <NoDataPanel label="Run a scan with billing history to populate spend trend." />
                )}
            </div>
        </section>
    );
}

function CostTopologyTheater({ hierarchy, sankeyData }: { hierarchy: ServiceHierarchyNode[]; sankeyData: SankeyData }) {
    return (
        <section className="space-y-4">
            <SectionTitle detail={`Service hierarchy and provider to category to top ${SANKEY_TOP_SERVICES} service flow share the same analytical section.`}>
                Cost Topology Theater
            </SectionTitle>
            <div className="grid gap-6 xl:grid-cols-2">
                <div className="space-y-3">
                    <h3 className="text-xs font-medium uppercase tracking-wider text-slate-500">Service Spend Hierarchy</h3>
                    <div className="h-[340px] rounded-xl bg-slate-900/20 p-4">
                        {hierarchy.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <Treemap
                                    data={hierarchy}
                                    dataKey="value"
                                    nameKey="name"
                                    stroke="transparent"
                                    fill="#818cf8"
                                    content={<CustomTreemapNode />}
                                >
                                    <Tooltip content={<CustomTooltip />} />
                                </Treemap>
                            </ResponsiveContainer>
                        ) : (
                            <NoDataPanel label="No service-level cost signals are available yet." />
                        )}
                    </div>
                </div>

                <div className="space-y-3">
                    <h3 className="text-xs font-medium uppercase tracking-wider text-slate-500">Spend Flow</h3>
                    <div className="h-[340px] rounded-xl bg-slate-900/20 p-4">
                        {sankeyData.nodes.length > 0 && sankeyData.links.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <Sankey
                                    data={sankeyData}
                                    nodePadding={24}
                                    nodeWidth={12}
                                    node={<CustomSankeyNode />}
                                    link={{ stroke: "rgba(255,255,255,0.10)", strokeOpacity: 1 }}
                                    margin={{ top: 12, right: 150, bottom: 12, left: 74 }}
                                >
                                    <Tooltip content={<CustomTooltip />} />
                                </Sankey>
                            </ResponsiveContainer>
                        ) : (
                            <NoDataPanel label="No provider-service flow can be drawn until costed resources are present." />
                        )}
                    </div>
                </div>
            </div>
        </section>
    );
}

function DailySpendHeatmap({ days }: { days: DailyProviderSpend[] }) {
    const maxSpend = Math.max(...days.map((day) => day.total), 0);
    const cells = days.slice(-35);

    return (
        <section className="space-y-4">
            <SectionTitle detail="30-day daily spend intensity. Hover a day to inspect exact spend.">Spend Heatmap</SectionTitle>
            {cells.length > 0 ? (
                <div className="grid w-max grid-cols-7 gap-2">
                    {cells.map((day) => {
                        const intensity = maxSpend > 0 ? Math.max(day.total / maxSpend, 0.12) : 0;
                        return (
                            <div
                                key={day.spend_date}
                                title={`${day.spend_date}: ${formatCurrency(day.total)}`}
                                className="grid h-8 w-8 place-items-center rounded-md text-[10px] text-white/70 transition-transform hover:scale-105"
                                style={{
                                    backgroundColor: day.total > 0
                                        ? `rgba(99, 102, 241, ${Math.min(intensity, 1)})`
                                        : "rgb(30, 41, 59)",
                                }}
                            >
                                {Number(day.spend_date.slice(-2))}
                            </div>
                        );
                    })}
                </div>
            ) : (
                <NoDataPanel label="No daily spend history is available yet." />
            )}
        </section>
    );
}

function ProviderDetailCards({
    providers,
    totalSpend,
    forecastByProvider,
}: {
    providers: ProviderSummary[];
    totalSpend: number;
    forecastByProvider: Map<string, ProviderForecast>;
}) {
    return (
        <section className="space-y-4">
            <SectionTitle detail="Provider-level monthly, annual, savings, and forecast context.">Provider Details</SectionTitle>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {providers.map((provider) => {
                    const forecast = forecastByProvider.get(provider.provider);
                    const forecastMonthly = forecast?.forecast_monthly && forecast.forecast_monthly > 0
                        ? forecast.forecast_monthly
                        : provider.monthly_spend;
                    const share = totalSpend > 0 ? (provider.monthly_spend / totalSpend) * 100 : 0;
                    const color = providerColor(provider.provider);

                    return (
                        <article key={provider.provider} className="rounded-xl bg-slate-900/20 p-5 transition-colors hover:bg-slate-900/40">
                            <div className="flex items-center justify-between gap-3">
                                <div className="flex items-center gap-3">
                                    <span className="h-6 w-6 rounded-full" style={{ backgroundColor: color }} />
                                    <p className="text-sm font-medium text-white">{providerLabel(provider.provider)}</p>
                                </div>
                                <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
                                    Active
                                </span>
                            </div>

                            <p className="mt-3 text-2xl font-semibold tracking-tight text-white tabular-nums">{formatCurrency(provider.monthly_spend)}</p>
                            <p className="mt-1 text-xs text-slate-500">{formatRelativeScan(provider.last_scan)}</p>

                            <div className="mt-5 grid grid-cols-3 gap-4">
                                <div>
                                    <p className="text-xs text-slate-500">Share</p>
                                    <p className="mt-1 text-sm text-slate-300 tabular-nums">{formatPercent(share)}</p>
                                </div>
                                <div>
                                    <p className="text-xs text-slate-500">Annual</p>
                                    <p className="mt-1 text-sm text-slate-300 tabular-nums">{formatCurrency(provider.monthly_spend * 12)}</p>
                                </div>
                                <div>
                                    <p className="text-xs text-slate-500">Forecast</p>
                                    <p className="mt-1 text-sm text-slate-300 tabular-nums">{formatCurrency(forecastMonthly)}</p>
                                </div>
                            </div>

                            <div className="mt-4 grid grid-cols-3 gap-4">
                                <div>
                                    <p className="text-xs text-slate-500">Savings</p>
                                    <p className="mt-1 text-sm text-emerald-300 tabular-nums">{formatCurrency(provider.potential_savings)}</p>
                                </div>
                                <div>
                                    <p className="text-xs text-slate-500">Resources</p>
                                    <p className="mt-1 text-sm text-slate-300 tabular-nums">{provider.resource_count.toLocaleString()}</p>
                                </div>
                                <div>
                                    <p className="text-xs text-slate-500">Accounts</p>
                                    <p className="mt-1 text-sm text-slate-300 tabular-nums">{provider.integration_count ?? 1}</p>
                                </div>
                            </div>
                        </article>
                    );
                })}
            </div>
        </section>
    );
}

function TopServicesTable({ rows }: { rows: TopServiceRow[] }) {
    return (
        <section className="space-y-4">
            <SectionTitle detail="Largest costed services from the backend service hierarchy payload.">Top Services</SectionTitle>
            <div className="overflow-hidden rounded-xl bg-slate-900/20">
                <div className="grid grid-cols-[1.5fr_0.8fr_0.8fr_0.8fr_0.8fr] gap-4 border-b border-white/5 bg-slate-900/30 px-4 py-3 text-xs font-medium uppercase tracking-wider text-slate-400">
                    <span>Service</span>
                    <span>Provider</span>
                    <span>Category</span>
                    <span className="text-right">Spend</span>
                    <span className="text-right">Resources</span>
                </div>
                {rows.length > 0 ? (
                    rows.map((row) => (
                        <div
                            key={row.key}
                            className="grid grid-cols-[1.5fr_0.8fr_0.8fr_0.8fr_0.8fr] gap-4 border-b border-white/5 px-4 py-3 transition-colors last:border-b-0 hover:bg-white/[0.02]"
                        >
                            <div className="min-w-0">
                                <p className="truncate text-sm text-white">{shortenServiceName(row.name)}</p>
                                <p className="mt-0.5 truncate text-xs text-slate-500">{row.costSources.join(", ") || "cost source unavailable"}</p>
                            </div>
                            <span className="text-sm text-slate-300">{row.provider}</span>
                            <span className="truncate text-sm text-slate-300">{row.category}</span>
                            <span className="text-right text-sm text-slate-300 tabular-nums">{formatCurrency(row.value)}</span>
                            <span className="text-right text-sm text-slate-300 tabular-nums">{row.resourceCount.toLocaleString()}</span>
                        </div>
                    ))
                ) : (
                    <div className="px-4 py-8 text-center text-sm text-slate-500">No service-level rows are available yet.</div>
                )}
            </div>
        </section>
    );
}

type InsightTone = "info" | "warn" | "good";

type Insight = {
    id: string;
    tone: InsightTone;
    title: string;
    body: string;
};

const ASSISTANT_OPEN_EVENT = "cloudfinops:open-assistant";

function buildSpendInsights(
    data: TotalBillResponse,
    heatmapDays: HeatmapDay[],
    forecastByProvider: Map<string, ProviderForecast>,
): Insight[] {
    const insights: Insight[] = [];
    const total = data.total_spend || 0;
    const sortedProviders = [...data.providers].sort((a, b) => b.monthly_spend - a.monthly_spend);

    if (sortedProviders.length > 0 && total > 0) {
        const top = sortedProviders[0];
        const share = (top.monthly_spend / total) * 100;
        insights.push({
            id: "concentration",
            tone: share > 70 ? "warn" : "info",
            title: `${providerLabel(top.provider)} is ${share.toFixed(1)}% of the bill`,
            body: share > 70
                ? `Concentration risk. A ${providerLabel(top.provider)} pricing or outage event would hit ${formatCurrency(top.monthly_spend)} of monthly spend.`
                : `Primary provider in your portfolio at ${formatCurrency(top.monthly_spend)} monthly run rate.`,
        });
    }

    if (sortedProviders.length > 1 && total > 0) {
        const tail = sortedProviders[sortedProviders.length - 1];
        const tailShare = (tail.monthly_spend / total) * 100;
        if (tailShare < 5) {
            insights.push({
                id: "underused",
                tone: "info",
                title: `${providerLabel(tail.provider)} is only ${tailShare.toFixed(1)}% of total`,
                body: `${formatCurrency(tail.monthly_spend)} on ${providerLabel(tail.provider)}. Check whether it justifies the operational overhead.`,
            });
        }
    }

    let forecastFlag: { provider: string; deltaPct: number; forecast: number; actual: number } | null = null;
    for (const provider of data.providers) {
        const forecast = forecastByProvider.get(provider.provider);
        if (!forecast || forecast.forecast_monthly <= 0 || provider.monthly_spend <= 0) continue;
        const deltaPct = ((forecast.forecast_monthly - provider.monthly_spend) / provider.monthly_spend) * 100;
        if (Math.abs(deltaPct) < 3) continue;
        if (!forecastFlag || Math.abs(deltaPct) > Math.abs(forecastFlag.deltaPct)) {
            forecastFlag = {
                provider: provider.provider,
                deltaPct,
                forecast: forecast.forecast_monthly,
                actual: provider.monthly_spend,
            };
        }
    }

    if (forecastFlag) {
        const direction = forecastFlag.deltaPct > 0 ? "up" : "down";
        insights.push({
            id: "forecast",
            tone: forecastFlag.deltaPct > 10 ? "warn" : "info",
            title: `${providerLabel(forecastFlag.provider)} forecast trending ${direction} ${Math.abs(forecastFlag.deltaPct).toFixed(1)}%`,
            body: `Projected ${formatCurrency(forecastFlag.forecast)} next cycle vs ${formatCurrency(forecastFlag.actual)} current.`,
        });
    }

    if (heatmapDays.length > 0) {
        const peak = heatmapDays.reduce((best, day) => (day.amount > best.amount ? day : best), heatmapDays[0]);
        if (peak.amount > 0) {
            const parsed = new Date(`${peak.spend_date}T00:00:00`);
            const dateLabel = Number.isNaN(parsed.getTime())
                ? peak.spend_date
                : parsed.toLocaleDateString(undefined, { month: "short", day: "numeric" });
            insights.push({
                id: "peak-day",
                tone: "info",
                title: `Peak day: ${dateLabel}`,
                body: `${formatCurrency(peak.amount)} burned in a single day. Correlate this with deploys or batch jobs.`,
            });
        }
    }

    if (data.total_savings > 0) {
        insights.push({
            id: "savings",
            tone: "good",
            title: `${formatCurrency(data.total_savings)} in identified savings`,
            body: `Annualized opportunity of ${formatCurrency(data.total_savings * 12)} from backend savings signals.`,
        });
    }

    return insights.slice(0, 5);
}

function dispatchAssistantOpen(prompt: string) {
    if (typeof window === "undefined") return;
    window.dispatchEvent(new CustomEvent(ASSISTANT_OPEN_EVENT, { detail: { prompt } }));
}

function buildAssistantSeedPrompt(insights: Insight[], data: TotalBillResponse): string {
    const headlines = insights.slice(0, 3).map((insight) => `- ${insight.title}`).join("\n");
    return [
        "Help me act on my Total Bill insights.",
        "",
        `Current monthly spend: ${formatCurrency(data.total_spend)} across ${data.provider_count} clouds.`,
        "",
        headlines,
        "",
        "What should I prioritise this week?",
    ].join("\n");
}

const INSIGHT_DOT: Record<InsightTone, string> = {
    info: "bg-indigo-400",
    warn: "bg-amber-400",
    good: "bg-emerald-400",
};

function AISpendInsights({
    data,
    heatmapDays,
    forecastByProvider,
}: {
    data: TotalBillResponse;
    heatmapDays: HeatmapDay[];
    forecastByProvider: Map<string, ProviderForecast>;
}) {
    const insights = useMemo(
        () => buildSpendInsights(data, heatmapDays, forecastByProvider),
        [data, heatmapDays, forecastByProvider],
    );

    const handleAsk = () => {
        dispatchAssistantOpen(buildAssistantSeedPrompt(insights, data));
    };

    return (
        <section className="space-y-4 border-l-2 border-indigo-500/50 bg-indigo-500/5 px-5 py-4">
            <div className="flex items-center gap-3">
                <Sparkles className="h-4 w-4 text-indigo-400" />
                <div>
                    <h2 className="text-sm font-medium uppercase tracking-wider text-slate-400">AI Spend Insights</h2>
                    <p className="mt-1 text-sm text-slate-500">Deterministic insight copy from the unified bill payload.</p>
                </div>
            </div>

            {insights.length > 0 ? (
                <ul className="space-y-3">
                    {insights.map((insight) => (
                        <li key={insight.id} className="flex gap-3">
                            <span className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${INSIGHT_DOT[insight.tone]}`} />
                            <div>
                                <p className="text-sm font-medium text-white">{insight.title}</p>
                                <p className="mt-1 text-sm leading-relaxed text-slate-400">{insight.body}</p>
                            </div>
                        </li>
                    ))}
                </ul>
            ) : (
                <p className="text-sm text-slate-500">Insights will appear once at least one provider has costed resources.</p>
            )}

            <button
                type="button"
                onClick={handleAsk}
                className="group inline-flex items-center gap-3 rounded-lg bg-slate-900/30 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-slate-900/40"
            >
                <MessageSquare className="h-4 w-4 text-indigo-300" />
                Ask CloudFinOps Copilot
                <ArrowRight className="h-4 w-4 text-slate-400 transition-transform group-hover:translate-x-1" />
            </button>
        </section>
    );
}

export function TotalBillExperience({ data }: { data: TotalBillResponse }) {
    const displayData = useMemo(() => toDisplayTotalBillData(data), [data]);
    const providers = useMemo(
        () => [...displayData.providers].sort(
            (left, right) =>
                (PROVIDER_ORDER[left.provider as keyof typeof PROVIDER_ORDER] ?? 99)
                - (PROVIDER_ORDER[right.provider as keyof typeof PROVIDER_ORDER] ?? 99)
        ),
        [displayData.providers]
    );
    const dailySpend = data.daily_provider_spend_30d || [];
    const heatmapDays = data.heatmap_days || [];
    const hierarchy = useMemo(() => convertHierarchy(data.service_hierarchy), [data.service_hierarchy]);
    const sankeyData = useMemo(() => buildSankeyData(data.spend_flows), [data.spend_flows]);
    const topServiceRows = useMemo(() => buildTopServiceRows(hierarchy), [hierarchy]);
    const forecastByProvider = useMemo(() => {
        const entries = (data.provider_forecasts || []).map((forecast) => [forecast.provider, forecast] as const);
        return new Map(entries);
    }, [data.provider_forecasts]);

    return (
        <main className="min-h-screen bg-slate-950 px-4 py-8 text-slate-200 md:px-8 lg:px-12">
            <div className="mx-auto max-w-[1500px] space-y-12">
                <SpendOrbitHero data={displayData} />
                <ProviderAllocationStrip providers={providers} totalSpend={displayData.total_spend} />
                <TrendForecastChart dailySpend={dailySpend} forecastByProvider={forecastByProvider} />
                <CostTopologyTheater hierarchy={hierarchy} sankeyData={sankeyData} />
                <DailySpendHeatmap days={dailySpend} />
                <ProviderDetailCards providers={providers} totalSpend={displayData.total_spend} forecastByProvider={forecastByProvider} />
                <TopServicesTable rows={topServiceRows} />
                <AISpendInsights data={displayData} heatmapDays={heatmapDays} forecastByProvider={forecastByProvider} />

                {data.visual_data_notes && data.visual_data_notes.length > 0 && (
                    <section className="border-l-2 border-indigo-500/50 bg-indigo-500/5 px-4 py-3 text-xs leading-6 text-slate-500">
                        {data.visual_data_notes.join(" ")}
                    </section>
                )}
            </div>
        </main>
    );
}
