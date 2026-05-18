"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import {
    ArrowDownRight,
    Calculator,
    Layers,
    Percent,
    PiggyBank,
    RefreshCw,
    Save,
    Sparkles,
    Trash2,
    Upload,
} from "lucide-react";
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";

const fmt = (v: number) => formatInrCurrency(toDisplayInrAmount(v || 0, "USD"), { minimumFractionDigits: 0, maximumFractionDigits: 0 });
const fmtPct = (v: number) => `${v.toFixed(1)}%`;

type ServiceRow = {
    category: string;
    source_service: string;
    aws_service: string;
    gcp_service: string;
    azure_service: string;
    source_monthly: number;
    default_tier1_pct: number;
    tier1_discount_pct: number;
};

type WaterfallItem = {
    label: string;
    value: number;
    type: "start" | "saving" | "increase" | "end";
};

type PricingMetadata = {
    pricing_basis_per_category: Record<string, string>;
    computed_at: string;
    sources_used: string[];
    is_stale: boolean;
};

type InstancePricing = Record<string, Record<string, {
    instance_type: string;
    vcpu?: number;
    memory_gb?: number;
    unit?: string;
    hourly_usd?: number;
    monthly_usd?: number;
    source: string;
}>>;

type CalculationResult = {
    service_breakdown: Array<{
        category: string;
        source_service: string;
        target_service: string;
        source_monthly: number;
        target_base: number;
        tier1_discount_pct: number;
        after_tier1: number;
        final_cost: number;
        total_saving: number;
        annual_saving: number;
    }>;
    source_monthly_total: number;
    target_base_total: number;
    after_tier1_total: number;
    after_tier2_total: number;
    final_cost: number;
    total_monthly_savings: number;
    total_annual_savings: number;
    total_reduction_pct: number;
    three_year_savings: number;
    est_migration_cost: number;
    payback_months: number;
    one_year_net: number;
    three_year_net: number;
    waterfall: WaterfallItem[];
    tier1_blended_pct: number;
    tier2_savings_amount: number;
    tier3_savings_amount: number;
    source_provider: string;
    target_provider: string;
    pricing_metadata?: PricingMetadata;
    instance_pricing?: InstancePricing;
};

type Template = {
    id: string;
    name: string;
    source_provider: string;
    target_provider: string;
    services: ServiceRow[];
    tier2_volume_pct: number;
    tier3_negotiated_pct: number;
    created_at: string;
    updated_at: string;
};

const TABS = ["Calculator", "Discounts", "Summary", "Pricing", "Templates"] as const;
type Tab = (typeof TABS)[number];

const PROVIDERS = ["aws", "gcp", "azure"] as const;
const PROVIDER_LABELS: Record<string, string> = { aws: "AWS", gcp: "GCP", azure: "Azure" };

const SERVICE_CATALOG: { category: string; aws: string; gcp: string; azure: string; tier1: number }[] = [
    { category: "Compute", aws: "EC2", gcp: "Compute Engine", azure: "Azure VMs", tier1: 30 },
    { category: "Database", aws: "RDS", gcp: "Cloud SQL", azure: "Azure SQL", tier1: 28 },
    { category: "Storage", aws: "S3", gcp: "Cloud Storage", azure: "Blob Storage", tier1: 20 },
    { category: "CDN", aws: "CloudFront", gcp: "Cloud CDN", azure: "Azure CDN", tier1: 40 },
    { category: "Networking", aws: "VPC", gcp: "VPC", azure: "VNet", tier1: 15 },
    { category: "Load Balancing", aws: "ALB/NLB", gcp: "Cloud LB", azure: "Azure LB", tier1: 15 },
    { category: "Kubernetes", aws: "EKS", gcp: "GKE", azure: "AKS", tier1: 35 },
    { category: "Serverless", aws: "Lambda", gcp: "Cloud Functions", azure: "Azure Functions", tier1: 10 },
    { category: "Machine Learning", aws: "SageMaker", gcp: "Vertex AI", azure: "Azure ML", tier1: 25 },
    { category: "Data Warehouse", aws: "Redshift", gcp: "BigQuery", azure: "Synapse", tier1: 30 },
    { category: "Security", aws: "GuardDuty", gcp: "SCC", azure: "Defender", tier1: 10 },
    { category: "Monitoring", aws: "CloudWatch", gcp: "Cloud Monitoring", azure: "Monitor", tier1: 12 },
    { category: "Other", aws: "Other", gcp: "Other", azure: "Other", tier1: 10 },
];

const SAMPLE_COSTS: Record<string, number> = {
    Compute: 4200, Database: 1800, Storage: 950, CDN: 620, Networking: 380,
    "Load Balancing": 280, Kubernetes: 1100, Serverless: 450, "Machine Learning": 2300,
    "Data Warehouse": 1500, Security: 150, Monitoring: 200, Other: 170,
};

function buildDefaultServices(): ServiceRow[] {
    return SERVICE_CATALOG.map((s) => ({
        category: s.category,
        source_service: s.aws,
        aws_service: s.aws,
        gcp_service: s.gcp,
        azure_service: s.azure,
        source_monthly: 0,
        default_tier1_pct: s.tier1,
        tier1_discount_pct: s.tier1,
    }));
}

function PricingBadge({ basis }: { basis: string }) {
    const config = basis === "live_api"
        ? { color: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30", label: "Live" }
        : basis === "partial_live"
            ? { color: "bg-amber-500/20 text-amber-400 border-amber-500/30", label: "Partial" }
            : { color: "bg-rose-500/20 text-rose-400 border-rose-500/30", label: "Estimated" };
    return (
        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border ${config.color}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${basis === "live_api" ? "bg-emerald-400" : basis === "partial_live" ? "bg-amber-400" : "bg-rose-400"}`} />
            {config.label}
        </span>
    );
}

function FreshnessBadge({ metadata, onRefresh, refreshing }: { metadata: PricingMetadata | null; onRefresh: () => void; refreshing: boolean }) {
    if (!metadata) return null;
    const computedAt = metadata.computed_at ? new Date(metadata.computed_at) : null;
    const ageHours = computedAt ? Math.round((Date.now() - computedAt.getTime()) / 3600000) : null;

    const isFresh = ageHours !== null && ageHours < 24;
    const label = ageHours !== null
        ? ageHours < 1 ? "Just updated" : `Updated ${ageHours}h ago`
        : "Unknown";

    return (
        <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border ${
                isFresh
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : metadata.is_stale
                        ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                        : "bg-amber-500/10 text-amber-400 border-amber-500/20"
            }`}>
                <span className={`h-1.5 w-1.5 rounded-full animate-pulse ${isFresh ? "bg-emerald-400" : metadata.is_stale ? "bg-rose-400" : "bg-amber-400"}`} />
                {isFresh ? "Live pricing" : metadata.is_stale ? "Stale — refresh needed" : "Cached"} · {label}
            </span>
            <button
                onClick={onRefresh}
                disabled={refreshing}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-40 transition-colors"
                title="Refresh pricing data"
            >
                <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            </button>
        </div>
    );
}

export default function DiscountManagerPage() {
    const { getToken } = useAuth();
    const [activeTab, setActiveTab] = useState<Tab>("Calculator");
    const [sourceProvider, setSourceProvider] = useState("aws");
    const [targetProvider, setTargetProvider] = useState("gcp");
    const [services, setServices] = useState<ServiceRow[]>(buildDefaultServices);
    const [tier2Pct, setTier2Pct] = useState(0);
    const [tier3Pct, setTier3Pct] = useState(0);
    const [result, setResult] = useState<CalculationResult | null>(null);
    const [pricingMeta, setPricingMeta] = useState<PricingMetadata | null>(null);
    const [instancePricing, setInstancePricing] = useState<InstancePricing | null>(null);
    const [templates, setTemplates] = useState<Template[]>([]);
    const [templateName, setTemplateName] = useState("");
    const [loading, setLoading] = useState(false);
    const [calculating, setCalculating] = useState(false);
    const [refreshing, setRefreshing] = useState(false);

    const authHeaders = useCallback(async (): Promise<Record<string, string>> => {
        const token = await getToken();
        if (token) return { Authorization: `Bearer ${token}` };
        return {};
    }, [getToken]);

    const loadPrefill = useCallback(async () => {
        try {
            const headers = await authHeaders();
            const res = await fetch("/api/discount-manager/prefill", { headers });
            if (!res.ok) {
                setServices(buildDefaultServices());
                return;
            }
            const data = await res.json();
            setSourceProvider(data.source_provider || "aws");
            if (data.services && data.services.length > 0) {
                setServices(
                    data.services.map((s: any) => ({
                        ...s,
                        tier1_discount_pct: s.tier1_discount_pct ?? s.default_tier1_pct ?? 10,
                    }))
                );
            } else {
                setServices(buildDefaultServices());
            }
        } catch {
            setServices(buildDefaultServices());
        }
    }, [authHeaders]);

    const loadSample = useCallback(() => {
        setServices((prev) =>
            prev.map((s) => ({
                ...s,
                source_monthly: SAMPLE_COSTS[s.category] || 0,
            }))
        );
    }, []);

    const calculate = useCallback(async () => {
        const activeServices = services.filter((s) => s.source_monthly > 0);
        if (activeServices.length === 0) { setResult(null); return; }

        setCalculating(true);
        try {
            const headers = await authHeaders();
            const res = await fetch("/api/discount-manager/calculate", {
                method: "POST",
                headers: { ...headers, "Content-Type": "application/json" },
                body: JSON.stringify({
                    services: activeServices.map((s) => ({
                        category: s.category,
                        source_monthly: s.source_monthly,
                        tier1_discount_pct: s.tier1_discount_pct,
                    })),
                    source_provider: sourceProvider,
                    target_provider: targetProvider,
                    tier2_volume_pct: tier2Pct,
                    tier3_negotiated_pct: tier3Pct,
                }),
            });
            if (!res.ok) throw new Error("Calculation failed");
            const data: CalculationResult = await res.json();
            setResult(data);
            if (data.pricing_metadata) setPricingMeta(data.pricing_metadata);
            if (data.instance_pricing) setInstancePricing(data.instance_pricing);
        } catch {
            // Keep previous result on error
        } finally {
            setCalculating(false);
        }
    }, [services, sourceProvider, targetProvider, tier2Pct, tier3Pct, authHeaders]);

    const refreshPricing = useCallback(async () => {
        setRefreshing(true);
        try {
            const headers = await authHeaders();
            const res = await fetch("/api/discount-manager/refresh-pricing", {
                method: "POST",
                headers,
            });
            if (res.ok) {
                // Re-calculate with fresh data
                await calculate();
            }
        } catch {
            // Refresh failed silently
        } finally {
            setRefreshing(false);
        }
    }, [authHeaders, calculate]);

    const checkPricingFreshness = useCallback(async () => {
        try {
            const headers = await authHeaders();
            const res = await fetch("/api/discount-manager/pricing-status", { headers });
            if (res.ok) {
                const data = await res.json();
                setPricingMeta({
                    pricing_basis_per_category: data.pricing_basis_per_category,
                    computed_at: data.computed_at,
                    sources_used: data.sources_used,
                    is_stale: data.is_stale,
                });
                if (data.instance_pricing) setInstancePricing(data.instance_pricing);
                // Auto-refresh if stale
                if (data.is_stale) {
                    refreshPricing();
                }
            }
        } catch {
            // Non-critical
        }
    }, [authHeaders, refreshPricing]);

    const loadTemplates = useCallback(async () => {
        try {
            const headers = await authHeaders();
            const res = await fetch("/api/discount-manager/templates", { headers });
            if (res.ok) {
                const data = await res.json();
                setTemplates(data.templates || []);
            }
        } catch {
            // Template loading failed
        }
    }, [authHeaders]);

    const saveTemplate = useCallback(async () => {
        if (!templateName.trim()) return;
        try {
            const headers = await authHeaders();
            await fetch("/api/discount-manager/templates", {
                method: "POST",
                headers: { ...headers, "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: templateName.trim(),
                    source_provider: sourceProvider,
                    target_provider: targetProvider,
                    services,
                    tier2_volume_pct: tier2Pct,
                    tier3_negotiated_pct: tier3Pct,
                }),
            });
            setTemplateName("");
            await loadTemplates();
        } catch {
            // Save failed
        }
    }, [templateName, sourceProvider, targetProvider, services, tier2Pct, tier3Pct, authHeaders, loadTemplates]);

    const deleteTemplate = useCallback(async (id: string) => {
        try {
            const headers = await authHeaders();
            await fetch(`/api/discount-manager/templates/${id}`, { method: "DELETE", headers });
            await loadTemplates();
        } catch {
            // Delete failed
        }
    }, [authHeaders, loadTemplates]);

    const loadTemplate = useCallback((t: Template) => {
        setSourceProvider(t.source_provider);
        setTargetProvider(t.target_provider);
        setServices(t.services.map((s) => ({ ...s, tier1_discount_pct: s.tier1_discount_pct ?? 10 })));
        setTier2Pct(t.tier2_volume_pct);
        setTier3Pct(t.tier3_negotiated_pct);
        setActiveTab("Calculator");
    }, []);

    useEffect(() => { loadPrefill(); }, [loadPrefill]);
    useEffect(() => { loadTemplates(); }, [loadTemplates]);
    useEffect(() => { checkPricingFreshness(); }, [checkPricingFreshness]);

    useEffect(() => {
        setServices((prev) =>
            prev.map((s) => {
                const catalog = SERVICE_CATALOG.find((c) => c.category === s.category);
                if (!catalog) return s;
                const srcKey = sourceProvider as "aws" | "gcp" | "azure";
                return { ...s, source_service: catalog[srcKey] };
            })
        );
    }, [sourceProvider]);

    useEffect(() => {
        const timeout = setTimeout(() => { calculate(); }, 500);
        return () => clearTimeout(timeout);
    }, [calculate]);

    const clearAll = () => {
        setServices(services.map((s) => ({ ...s, source_monthly: 0 })));
        setTier2Pct(0);
        setTier3Pct(0);
        setResult(null);
    };

    const updateService = (index: number, field: keyof ServiceRow, value: number) => {
        setServices((prev) => prev.map((s, i) => (i === index ? { ...s, [field]: value } : s)));
    };

    if (loading) {
        return (
            <main className="p-6 md:p-10 w-full bg-slate-950 min-h-screen text-slate-200">
                <div className="animate-pulse space-y-6">
                    <div className="h-9 w-72 bg-slate-800 rounded" />
                    <div className="h-96 bg-slate-800 rounded-2xl" />
                </div>
            </main>
        );
    }

    return (
        <main className="p-6 md:p-10 w-full bg-slate-950 min-h-screen text-slate-200">
            {/* Header */}
            <div className="mb-8">
                <div className="flex items-center gap-3 mb-2">
                    <div className="p-2 bg-indigo-500/20 rounded-xl text-indigo-400">
                        <Percent className="w-6 h-6" />
                    </div>
                    <h1 className="text-white text-3xl font-bold">Discount Manager</h1>
                    <FreshnessBadge metadata={pricingMeta} onRefresh={refreshPricing} refreshing={refreshing} />
                </div>
                <p className="text-slate-400 text-lg">
                    Real-time multi-tier discount modeling with live cloud pricing data.
                </p>
            </div>

            {/* Summary Bar */}
            {result && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
                    <MetricCard label={`${PROVIDER_LABELS[sourceProvider]} Monthly`} value={fmt(result.source_monthly_total)} />
                    <MetricCard label="After Product Discounts" value={fmt(result.after_tier1_total)} />
                    <MetricCard label="After Volume/CUD" value={fmt(result.after_tier2_total)} />
                    <MetricCard label={`Final ${PROVIDER_LABELS[targetProvider]} Cost`} value={fmt(result.final_cost)} accent />
                    <MetricCard label="Total Saved" value={fmtPct(result.total_reduction_pct)} accent />
                </div>
            )}

            {/* Provider Selectors */}
            <div className="flex flex-wrap items-center gap-4 mb-6">
                <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-400">From:</span>
                    <select
                        value={sourceProvider}
                        onChange={(e) => {
                            setSourceProvider(e.target.value);
                            if (e.target.value === targetProvider) {
                                setTargetProvider(PROVIDERS.find((p) => p !== e.target.value) || "gcp");
                            }
                        }}
                        className="bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
                    >
                        {PROVIDERS.map((p) => <option key={p} value={p}>{PROVIDER_LABELS[p]}</option>)}
                    </select>
                </div>
                <ArrowDownRight className="w-4 h-4 text-slate-500 rotate-[-45deg]" />
                <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-400">To:</span>
                    <select
                        value={targetProvider}
                        onChange={(e) => setTargetProvider(e.target.value)}
                        className="bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
                    >
                        {PROVIDERS.filter((p) => p !== sourceProvider).map((p) => (
                            <option key={p} value={p}>{PROVIDER_LABELS[p]}</option>
                        ))}
                    </select>
                </div>
                <div className="flex-1" />
                {calculating && (
                    <span className="text-xs text-slate-500 flex items-center gap-1.5">
                        <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse" />
                        Calculating with live prices...
                    </span>
                )}
                <button onClick={loadSample} className="px-3 py-2 text-sm bg-slate-800 hover:bg-slate-700 border border-white/10 rounded-lg text-slate-300 flex items-center gap-2">
                    <Sparkles className="w-4 h-4" /> Load Sample
                </button>
                <button onClick={loadPrefill} className="px-3 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white flex items-center gap-2">
                    <Upload className="w-4 h-4" /> Load from Scan
                </button>
                <button onClick={clearAll} className="px-3 py-2 text-sm bg-slate-800 hover:bg-slate-700 border border-white/10 rounded-lg text-slate-300">
                    Clear All
                </button>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 mb-6 border-b border-white/10 pb-px">
                {TABS.map((tab) => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors ${
                            activeTab === tab
                                ? "bg-slate-800 text-white border-b-2 border-indigo-500"
                                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                        }`}
                    >
                        {tab}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            {activeTab === "Calculator" && (
                <CalculatorTab services={services} sourceProvider={sourceProvider} targetProvider={targetProvider} onUpdate={updateService} pricingBasis={pricingMeta?.pricing_basis_per_category} />
            )}
            {activeTab === "Discounts" && (
                <DiscountsTab
                    tier2Pct={tier2Pct}
                    tier3Pct={tier3Pct}
                    onTier2Change={setTier2Pct}
                    onTier3Change={setTier3Pct}
                    result={result}
                />
            )}
            {activeTab === "Summary" && result && (
                <SummaryTab result={result} />
            )}
            {activeTab === "Summary" && !result && (
                <div className="text-center text-slate-500 py-16">Enter service costs to see the summary.</div>
            )}
            {activeTab === "Pricing" && (
                <PricingTab instancePricing={instancePricing} pricingMeta={pricingMeta} />
            )}
            {activeTab === "Templates" && (
                <TemplatesTab
                    templates={templates}
                    templateName={templateName}
                    onNameChange={setTemplateName}
                    onSave={saveTemplate}
                    onLoad={loadTemplate}
                    onDelete={deleteTemplate}
                />
            )}
        </main>
    );
}

function MetricCard({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
    return (
        <div className={`rounded-2xl border p-4 ${accent ? "border-indigo-500/30 bg-indigo-500/10" : "border-white/10 bg-slate-900/50"}`}>
            <div className="text-xs text-slate-400 mb-1">{label}</div>
            <div className={`text-lg font-bold ${accent ? "text-indigo-300" : "text-white"}`}>{value}</div>
        </div>
    );
}

function CalculatorTab({
    services,
    sourceProvider,
    targetProvider,
    onUpdate,
    pricingBasis,
}: {
    services: ServiceRow[];
    sourceProvider: string;
    targetProvider: string;
    onUpdate: (index: number, field: keyof ServiceRow, value: number) => void;
    pricingBasis?: Record<string, string>;
}) {
    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 overflow-hidden">
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-white/10 bg-white/5">
                            <th className="text-left px-4 py-3 text-slate-400 font-medium">Category</th>
                            <th className="text-left px-4 py-3 text-slate-400 font-medium">{PROVIDER_LABELS[sourceProvider]} Service</th>
                            <th className="text-left px-4 py-3 text-slate-400 font-medium">{PROVIDER_LABELS[targetProvider]} Service</th>
                            <th className="text-right px-4 py-3 text-slate-400 font-medium">{PROVIDER_LABELS[sourceProvider]} $/Mo</th>
                            <th className="text-right px-4 py-3 text-slate-400 font-medium">Disc %</th>
                            <th className="text-center px-4 py-3 text-slate-400 font-medium">Price</th>
                        </tr>
                    </thead>
                    <tbody>
                        {services.map((svc, i) => (
                            <tr key={svc.category} className="border-b border-white/5 hover:bg-white/5">
                                <td className="px-4 py-3 text-white font-medium">{svc.category}</td>
                                <td className="px-4 py-3 text-slate-300">
                                    {svc[`${sourceProvider}_service` as keyof ServiceRow] as string || svc.source_service}
                                </td>
                                <td className="px-4 py-3 text-slate-300">
                                    {svc[`${targetProvider}_service` as keyof ServiceRow] as string || svc.category}
                                </td>
                                <td className="px-4 py-3 text-right">
                                    <input
                                        type="number"
                                        min={0}
                                        step={10}
                                        value={svc.source_monthly || ""}
                                        onChange={(e) => onUpdate(i, "source_monthly", parseFloat(e.target.value) || 0)}
                                        className="w-28 bg-slate-800 border border-white/10 rounded px-2 py-1 text-right text-white"
                                        placeholder="0"
                                    />
                                </td>
                                <td className="px-4 py-3 text-right">
                                    <input
                                        type="number"
                                        min={0}
                                        max={100}
                                        step={1}
                                        value={svc.tier1_discount_pct}
                                        onChange={(e) => onUpdate(i, "tier1_discount_pct", parseFloat(e.target.value) || 0)}
                                        className="w-16 bg-slate-800 border border-white/10 rounded px-2 py-1 text-right text-white"
                                    />
                                </td>
                                <td className="px-4 py-3 text-center">
                                    {pricingBasis && <PricingBadge basis={pricingBasis[svc.category] || "static_fallback"} />}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                    <tfoot>
                        <tr className="bg-white/5">
                            <td colSpan={3} className="px-4 py-3 text-white font-bold">Total</td>
                            <td className="px-4 py-3 text-right text-white font-bold">
                                {fmt(services.reduce((s, r) => s + (r.source_monthly || 0), 0))}
                            </td>
                            <td colSpan={2} />
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>
    );
}

function DiscountsTab({
    tier2Pct,
    tier3Pct,
    onTier2Change,
    onTier3Change,
    result,
}: {
    tier2Pct: number;
    tier3Pct: number;
    onTier2Change: (v: number) => void;
    onTier3Change: (v: number) => void;
    result: CalculationResult | null;
}) {
    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <div className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">1</div>
                        <h3 className="text-white font-semibold">Product Discounts</h3>
                    </div>
                    <p className="text-slate-400 text-sm mb-4">Per-service rates configured in the Calculator tab.</p>
                    <div className="text-2xl font-bold text-emerald-400">
                        {result ? fmtPct(result.tier1_blended_pct) : "—"}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">Blended discount</div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <div className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">2</div>
                        <h3 className="text-white font-semibold">Volume / CUD</h3>
                    </div>
                    <p className="text-slate-400 text-sm mb-4">Applied to post-Tier-1 total. CUDs offer 30-57% on 1-3yr commits.</p>
                    <input
                        type="range"
                        min={0}
                        max={60}
                        step={1}
                        value={tier2Pct}
                        onChange={(e) => onTier2Change(Number(e.target.value))}
                        className="w-full accent-blue-500 mb-2"
                    />
                    <div className="flex justify-between text-sm">
                        <span className="text-slate-400">Discount:</span>
                        <span className="text-blue-400 font-bold">{tier2Pct}%</span>
                    </div>
                    {result && (
                        <div className="mt-3 pt-3 border-t border-white/10 text-xs text-slate-500">
                            Saves {fmt(result.tier2_savings_amount)}/mo
                        </div>
                    )}
                </div>

                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <div className="w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-xs font-bold">3</div>
                        <h3 className="text-white font-semibold">Negotiated</h3>
                    </div>
                    <p className="text-slate-400 text-sm mb-4">Migration incentive from provider account team.</p>
                    <input
                        type="range"
                        min={0}
                        max={40}
                        step={1}
                        value={tier3Pct}
                        onChange={(e) => onTier3Change(Number(e.target.value))}
                        className="w-full accent-purple-500 mb-2"
                    />
                    <div className="flex justify-between text-sm">
                        <span className="text-slate-400">Discount:</span>
                        <span className="text-purple-400 font-bold">{tier3Pct}%</span>
                    </div>
                    {result && (
                        <div className="mt-3 pt-3 border-t border-white/10 text-xs text-slate-500">
                            Saves {fmt(result.tier3_savings_amount)}/mo
                        </div>
                    )}
                </div>
            </div>

            {result && result.waterfall.length > 0 && (
                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                    <h3 className="text-white font-semibold mb-1">Discount Waterfall</h3>
                    <p className="text-slate-400 text-sm mb-6">How savings compound through each tier</p>
                    <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={result.waterfall} margin={{ top: 20, right: 20, left: 20, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                            <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                            <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                            <Tooltip
                                contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "0.75rem" }}
                                labelStyle={{ color: "#fff" }}
                                formatter={(value: number) => [fmt(value), "Amount"]}
                            />
                            <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                                {result.waterfall.map((entry, idx) => (
                                    <Cell
                                        key={idx}
                                        fill={
                                            entry.type === "start" ? "#f97316"
                                                : entry.type === "end" ? "#6366f1"
                                                    : entry.type === "saving" ? "#10b981"
                                                        : "#ef4444"
                                        }
                                    />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            )}
        </div>
    );
}

function SummaryTab({ result }: { result: CalculationResult }) {
    return (
        <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-5">
                    <PiggyBank className="w-5 h-5 text-emerald-400 mb-2" />
                    <div className="text-xs text-slate-400">Monthly Savings</div>
                    <div className="text-xl font-bold text-emerald-300">{fmt(result.total_monthly_savings)}</div>
                </div>
                <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-5">
                    <Layers className="w-5 h-5 text-emerald-400 mb-2" />
                    <div className="text-xs text-slate-400">Annual Savings</div>
                    <div className="text-xl font-bold text-emerald-300">{fmt(result.total_annual_savings)}</div>
                </div>
                <div className="rounded-2xl border border-indigo-500/30 bg-indigo-500/10 p-5">
                    <Calculator className="w-5 h-5 text-indigo-400 mb-2" />
                    <div className="text-xs text-slate-400">3-Year Savings</div>
                    <div className="text-xl font-bold text-indigo-300">{fmt(result.three_year_savings)}</div>
                </div>
                <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5">
                    <Percent className="w-5 h-5 text-amber-400 mb-2" />
                    <div className="text-xs text-slate-400">Total Reduction</div>
                    <div className="text-xl font-bold text-amber-300">{fmtPct(result.total_reduction_pct)}</div>
                </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-900/50 overflow-hidden">
                <div className="px-5 py-4 border-b border-white/10">
                    <h3 className="text-white font-semibold">Service Breakdown</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-white/10 bg-white/5">
                                <th className="text-left px-4 py-3 text-slate-400 font-medium">Service</th>
                                <th className="text-right px-4 py-3 text-slate-400 font-medium">{PROVIDER_LABELS[result.source_provider]} /Mo</th>
                                <th className="text-right px-4 py-3 text-slate-400 font-medium">{PROVIDER_LABELS[result.target_provider]} Base</th>
                                <th className="text-right px-4 py-3 text-slate-400 font-medium">Prod Disc</th>
                                <th className="text-right px-4 py-3 text-slate-400 font-medium">Final Cost</th>
                                <th className="text-right px-4 py-3 text-slate-400 font-medium">Mo Save</th>
                                <th className="text-right px-4 py-3 text-slate-400 font-medium">Yr Save</th>
                            </tr>
                        </thead>
                        <tbody>
                            {result.service_breakdown.map((row) => (
                                <tr key={row.category} className="border-b border-white/5 hover:bg-white/5">
                                    <td className="px-4 py-3 text-white">{row.target_service}</td>
                                    <td className="px-4 py-3 text-right text-slate-300">{fmt(row.source_monthly)}</td>
                                    <td className="px-4 py-3 text-right text-slate-300">{fmt(row.target_base)}</td>
                                    <td className="px-4 py-3 text-right text-slate-300">{fmtPct(row.tier1_discount_pct)}</td>
                                    <td className="px-4 py-3 text-right text-white font-medium">{fmt(row.final_cost)}</td>
                                    <td className="px-4 py-3 text-right text-emerald-400">{fmt(row.total_saving)}</td>
                                    <td className="px-4 py-3 text-right text-emerald-400">{fmt(row.annual_saving)}</td>
                                </tr>
                            ))}
                        </tbody>
                        <tfoot>
                            <tr className="bg-white/5 font-bold">
                                <td className="px-4 py-3 text-white">TOTAL</td>
                                <td className="px-4 py-3 text-right text-white">{fmt(result.source_monthly_total)}</td>
                                <td className="px-4 py-3 text-right text-white">{fmt(result.target_base_total)}</td>
                                <td className="px-4 py-3 text-right text-white">{fmtPct(result.tier1_blended_pct)}</td>
                                <td className="px-4 py-3 text-right text-white">{fmt(result.final_cost)}</td>
                                <td className="px-4 py-3 text-right text-emerald-400">{fmt(result.total_monthly_savings)}</td>
                                <td className="px-4 py-3 text-right text-emerald-400">{fmt(result.total_annual_savings)}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                <h3 className="text-white font-semibold mb-4">Migration ROI</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                    <div>
                        <div className="text-xs text-slate-400 mb-1">Est. Migration Cost</div>
                        <div className="text-lg font-bold text-white">{fmt(result.est_migration_cost)}</div>
                        <div className="text-xs text-slate-500">~4x monthly saving</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-400 mb-1">Payback Period</div>
                        <div className="text-lg font-bold text-white">{result.payback_months} months</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-400 mb-1">1-Year Net Return</div>
                        <div className={`text-lg font-bold ${result.one_year_net >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                            {fmt(result.one_year_net)}
                        </div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-400 mb-1">3-Year Net Return</div>
                        <div className={`text-lg font-bold ${result.three_year_net >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                            {fmt(result.three_year_net)}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function PricingTab({ instancePricing, pricingMeta }: { instancePricing: InstancePricing | null; pricingMeta: PricingMetadata | null }) {
    if (!instancePricing || Object.keys(instancePricing).length === 0) {
        return (
            <div className="text-center py-16 text-slate-500">
                Pricing data loading... Enter costs and calculate to see live instance pricing.
            </div>
        );
    }

    const categories = Object.keys(instancePricing).filter((k) => !k.endsWith("_tier_b"));

    return (
        <div className="space-y-6">
            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                <h3 className="text-white font-semibold mb-1">Live Instance Price Comparison</h3>
                <p className="text-slate-400 text-sm mb-6">
                    Real prices fetched from Infracost API + Azure Retail Prices API. Updated {pricingMeta?.computed_at ? new Date(pricingMeta.computed_at).toLocaleString() : "—"}.
                </p>

                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-white/10 bg-white/5">
                                <th className="text-left px-4 py-3 text-slate-400 font-medium">Category</th>
                                <th className="text-left px-4 py-3 text-slate-400 font-medium">AWS Instance</th>
                                <th className="text-right px-4 py-3 text-slate-400 font-medium">$/hr</th>
                                <th className="text-left px-4 py-3 text-slate-400 font-medium">GCP Instance</th>
                                <th className="text-right px-4 py-3 text-slate-400 font-medium">$/hr</th>
                                <th className="text-left px-4 py-3 text-slate-400 font-medium">Azure Instance</th>
                                <th className="text-right px-4 py-3 text-slate-400 font-medium">$/hr</th>
                                <th className="text-center px-4 py-3 text-slate-400 font-medium">Source</th>
                            </tr>
                        </thead>
                        <tbody>
                            {categories.map((category) => {
                                const data = instancePricing[category];
                                if (!data) return null;
                                const basis = pricingMeta?.pricing_basis_per_category?.[category];
                                return (
                                    <tr key={category} className="border-b border-white/5 hover:bg-white/5">
                                        <td className="px-4 py-3 text-white font-medium">{category}</td>
                                        <td className="px-4 py-3 text-slate-300 text-xs">{data.aws?.instance_type || "—"}</td>
                                        <td className="px-4 py-3 text-right text-orange-300 font-mono text-xs">
                                            {data.aws?.hourly_usd ? `$${data.aws.hourly_usd.toFixed(4)}` : "—"}
                                        </td>
                                        <td className="px-4 py-3 text-slate-300 text-xs">{data.gcp?.instance_type || "—"}</td>
                                        <td className="px-4 py-3 text-right text-blue-300 font-mono text-xs">
                                            {data.gcp?.hourly_usd ? `$${data.gcp.hourly_usd.toFixed(4)}` : "—"}
                                        </td>
                                        <td className="px-4 py-3 text-slate-300 text-xs">{data.azure?.instance_type || "—"}</td>
                                        <td className="px-4 py-3 text-right text-cyan-300 font-mono text-xs">
                                            {data.azure?.hourly_usd ? `$${data.azure.hourly_usd.toFixed(4)}` : "—"}
                                        </td>
                                        <td className="px-4 py-3 text-center">
                                            {basis && <PricingBadge basis={basis} />}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Tier B comparison */}
            {Object.keys(instancePricing).some((k) => k.endsWith("_tier_b")) && (
                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                    <h3 className="text-white font-semibold mb-1">8 vCPU / 32 GB Tier</h3>
                    <p className="text-slate-400 text-sm mb-6">Larger instance comparison for enterprise workloads.</p>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-white/10 bg-white/5">
                                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Category</th>
                                    <th className="text-left px-4 py-3 text-slate-400 font-medium">AWS</th>
                                    <th className="text-right px-4 py-3 text-slate-400 font-medium">$/hr</th>
                                    <th className="text-left px-4 py-3 text-slate-400 font-medium">GCP</th>
                                    <th className="text-right px-4 py-3 text-slate-400 font-medium">$/hr</th>
                                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Azure</th>
                                    <th className="text-right px-4 py-3 text-slate-400 font-medium">$/hr</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Object.keys(instancePricing).filter((k) => k.endsWith("_tier_b")).map((key) => {
                                    const category = key.replace("_tier_b", "");
                                    const data = instancePricing[key];
                                    if (!data) return null;
                                    return (
                                        <tr key={key} className="border-b border-white/5 hover:bg-white/5">
                                            <td className="px-4 py-3 text-white font-medium">{category}</td>
                                            <td className="px-4 py-3 text-slate-300 text-xs">{data.aws?.instance_type || "—"}</td>
                                            <td className="px-4 py-3 text-right text-orange-300 font-mono text-xs">
                                                {data.aws?.hourly_usd ? `$${data.aws.hourly_usd.toFixed(4)}` : "—"}
                                            </td>
                                            <td className="px-4 py-3 text-slate-300 text-xs">{data.gcp?.instance_type || "—"}</td>
                                            <td className="px-4 py-3 text-right text-blue-300 font-mono text-xs">
                                                {data.gcp?.hourly_usd ? `$${data.gcp.hourly_usd.toFixed(4)}` : "—"}
                                            </td>
                                            <td className="px-4 py-3 text-slate-300 text-xs">{data.azure?.instance_type || "—"}</td>
                                            <td className="px-4 py-3 text-right text-cyan-300 font-mono text-xs">
                                                {data.azure?.hourly_usd ? `$${data.azure.hourly_usd.toFixed(4)}` : "—"}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}

function TemplatesTab({
    templates,
    templateName,
    onNameChange,
    onSave,
    onLoad,
    onDelete,
}: {
    templates: Template[];
    templateName: string;
    onNameChange: (v: string) => void;
    onSave: () => void;
    onLoad: (t: Template) => void;
    onDelete: (id: string) => void;
}) {
    return (
        <div className="space-y-6">
            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
                <h3 className="text-white font-semibold mb-3">Save Current Configuration</h3>
                <div className="flex gap-3">
                    <input
                        type="text"
                        value={templateName}
                        onChange={(e) => onNameChange(e.target.value)}
                        placeholder="Template name (e.g. Q3 Migration Plan)"
                        className="flex-1 bg-slate-800 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-slate-500"
                        maxLength={100}
                    />
                    <button
                        onClick={onSave}
                        disabled={!templateName.trim()}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-white flex items-center gap-2 text-sm font-medium"
                    >
                        <Save className="w-4 h-4" /> Save
                    </button>
                </div>
            </div>

            {templates.length === 0 ? (
                <div className="text-center py-16 text-slate-500">
                    No saved templates yet. Configure your discounts and save above.
                </div>
            ) : (
                <div className="space-y-3">
                    {templates.map((t) => (
                        <div key={t.id} className="rounded-xl border border-white/10 bg-slate-900/50 p-4 flex items-center gap-4">
                            <div className="flex-1">
                                <div className="text-white font-medium">{t.name}</div>
                                <div className="text-xs text-slate-400 mt-1">
                                    {PROVIDER_LABELS[t.source_provider]} → {PROVIDER_LABELS[t.target_provider]}
                                    {" · "}Tier 2: {t.tier2_volume_pct}% · Tier 3: {t.tier3_negotiated_pct}%
                                    {" · "}Saved {new Date(t.created_at).toLocaleDateString()}
                                </div>
                            </div>
                            <button
                                onClick={() => onLoad(t)}
                                className="px-3 py-1.5 text-sm bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 rounded-lg"
                            >
                                Load
                            </button>
                            <button
                                onClick={() => onDelete(t.id)}
                                className="p-1.5 text-rose-400 hover:bg-rose-500/10 rounded-lg"
                            >
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
