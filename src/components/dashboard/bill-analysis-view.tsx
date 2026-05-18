"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowDownRight, RefreshCw, Shield, Sparkles } from "lucide-react";

import { BillExecutiveReport as BillExecutiveReportPanel } from "@/components/dashboard/bill-executive-report";
import { cleanServiceName, normalizeBillExecutiveReport } from "@/lib/bill-executive-report";
import type {
    BillAnalysisOpportunity,
    BillAnalysisRecord,
    BillExecutiveFinding,
} from "@/lib/api";
import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";

type BillAnalysisViewProps = {
    analysis: BillAnalysisRecord | null;
    recentAnalyses?: BillAnalysisRecord[];
    preferredTab?: "arbitrage" | "executive";
};

type RawBillFileMetadata = {
    status?: string;
    content_type?: string;
    original_filename?: string;
};

const riskClassName: Record<string, string> = {
    Low: "border border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
    Medium: "border border-amber-500/20 bg-amber-500/10 text-amber-400",
    High: "border border-rose-500/20 bg-rose-500/10 text-rose-400",
};

const providerBadgeClassName: Record<string, string> = {
    AWS: "border border-orange-500/20 bg-orange-500/10 text-orange-400",
    AZURE: "border border-blue-500/20 bg-blue-500/10 text-blue-400",
    GCP: "border border-green-500/20 bg-green-500/10 text-green-400",
};

const surfaceClassName = "rounded-2xl border border-white/10 bg-slate-800/40 backdrop-blur-xl";
const insetSurfaceClassName = "rounded-xl border border-white/10 bg-slate-900 px-3 py-3";

function getProviderBadgeClassName(provider: string) {
    return providerBadgeClassName[provider.trim().toUpperCase()] ?? "border border-indigo-500/20 bg-indigo-500/10 text-indigo-400";
}

function ProviderBadge({ provider }: { provider: string }) {
    return (
        <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${getProviderBadgeClassName(provider)}`}>
            {provider}
        </span>
    );
}

function formatCurrency(amount: number, currency: string) {
    return formatInrCurrency(toDisplayInrAmount(amount || 0, currency || "USD"), {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function formatPercent(value: number) {
    return `${Number(value || 0).toFixed(1)}%`;
}

function formatCurrencyRange(minimum: number, maximum: number, currency: string) {
    if (Math.abs((minimum || 0) - (maximum || 0)) < 0.01) {
        return formatCurrency(maximum, currency);
    }
    return `${formatCurrency(minimum, currency)} - ${formatCurrency(maximum, currency)}`;
}

function formatTimestamp(value: string) {
    if (!value) {
        return "Unknown";
    }

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }

    return new Intl.DateTimeFormat("en-US", {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(parsed);
}

function sourceLabel(record: BillAnalysisRecord) {
    if (record.source_type === "manual_upload") {
        return "Manual Upload";
    }
    if (record.source_type === "automated_sync") {
        return "Automated Sync";
    }
    return record.source_type.replace(/_/g, " ");
}

function parserLabel(value: string) {
    return value.replace(/_/g, " ").trim() || "Unknown parser";
}

function MetadataRow({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex items-center justify-between gap-4 text-sm">
            <span className="text-slate-400">{label}</span>
            <span className="text-white text-right">{value}</span>
        </div>
    );
}

function getRawBillFileMetadata(sourceMetadata: Record<string, unknown>): RawBillFileMetadata | null {
    const candidate = sourceMetadata.raw_bill_file;
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
        return null;
    }
    return candidate as RawBillFileMetadata;
}

function categoryKeywordMap(category: string): string[] {
    const normalized = category.trim().toLowerCase();
    if (normalized === "database") {
        return ["database", "rds", "sql", "elasticache", "dynamodb", "redis"];
    }
    if (normalized === "networking") {
        return ["network", "vpc", "nat", "data transfer", "public ipv4", "cloudfront", "gateway"];
    }
    if (normalized === "compute") {
        return ["compute", "ec2", "eks", "ecs", "lambda", "container"];
    }
    if (normalized === "storage") {
        return ["storage", "s3", "bucket", "ebs", "snapshot"];
    }
    if (normalized === "load balancing") {
        return ["load balanc", "alb", "elb", "balancer"];
    }
    return [normalized];
}

function findSupportingFinding(
    report: ReturnType<typeof normalizeBillExecutiveReport>,
    opportunity: BillAnalysisOpportunity,
): BillExecutiveFinding | null {
    if (!report) {
        return null;
    }

    const keywords = categoryKeywordMap(opportunity.category);
    return (
        report.findings.find((finding) => {
            const haystack = `${cleanServiceName(finding.service)} ${finding.title} ${finding.what_we_found}`.toLowerCase();
            return keywords.some((keyword) => haystack.includes(keyword));
        }) || null
    );
}

function OpportunityCard({
    opportunity,
    currency,
    supportingFinding,
}: {
    opportunity: BillAnalysisOpportunity;
    currency: string;
    supportingFinding?: BillExecutiveFinding | null;
}) {
    const leftBorderClassName = opportunity.migration_risk === "High"
        ? "border-l-rose-500"
        : opportunity.migration_risk === "Medium"
            ? "border-l-amber-500"
            : "border-l-emerald-500";

    return (
        <div className={`rounded-2xl border border-white/10 border-l-4 ${leftBorderClassName} bg-slate-800/40 p-5 backdrop-blur-xl`}>
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h3 className="text-white font-semibold">{opportunity.category}</h3>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-400">
                        <ProviderBadge provider={opportunity.current_cloud} />
                        <span className="text-slate-500">to</span>
                        <ProviderBadge provider={opportunity.recommended_cloud} />
                    </div>
                </div>
                <div className="text-right">
                    <p className="text-emerald-400 font-semibold flex items-center gap-1 justify-end">
                        <ArrowDownRight className="h-4 w-4" />
                        {formatCurrency(opportunity.savings, currency)} / month
                    </p>
                    <p className="text-xs text-slate-400">{formatPercent(opportunity.savings_pct)} savings</p>
                </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                <div className={insetSurfaceClassName}>
                    <p className="text-xs text-slate-400">Current Cost</p>
                    <p className="text-white">{formatCurrency(opportunity.current_cost, currency)}</p>
                </div>
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-3">
                    <p className="text-xs text-slate-200">Recommended Cost</p>
                    <p className="text-emerald-400">{formatCurrency(opportunity.recommended_cost, currency)}</p>
                </div>
            </div>
            {opportunity.reasoning && <p className="mt-3 text-sm text-slate-300">{opportunity.reasoning}</p>}
            {opportunity.migration_note && (
                <p className="mt-2 text-xs leading-6 text-slate-400">
                    {opportunity.migration_note}
                </p>
            )}
            {opportunity.migration_risk && (
                <span
                    className={`inline-block mt-3 rounded-full px-3 py-1 text-xs ${riskClassName[opportunity.migration_risk] || "border border-white/20 bg-slate-900 text-slate-300"
                        }`}
                >
                    Risk: {opportunity.migration_risk}
                </span>
            )}
            {supportingFinding ? (
                <div className="mt-4 rounded-xl border border-indigo-500/20 bg-indigo-500/10 p-4">
                    <p className="text-xs uppercase tracking-widest text-indigo-300">How To Execute</p>
                    <p className="mt-2 text-sm leading-6 text-slate-100">{supportingFinding.what_we_found}</p>
                    <ol className="mt-3 space-y-2 text-sm text-slate-200">
                        {supportingFinding.how_to_fix.slice(0, 3).map((step, index) => (
                            <li key={`${supportingFinding.service}-step-${index}`} className="flex gap-2">
                                <span className="text-indigo-300">{index + 1}.</span>
                                <span>{step}</span>
                            </li>
                        ))}
                    </ol>
                </div>
            ) : null}
        </div>
    );
}

export function BillAnalysisView({ analysis, recentAnalyses = [], preferredTab }: BillAnalysisViewProps) {
    const executiveReport = normalizeBillExecutiveReport(analysis?.executive_report);
    const defaultTab = preferredTab || (executiveReport ? "executive" : "arbitrage");
    const [activeTab, setActiveTab] = useState<"arbitrage" | "executive">(defaultTab);

    useEffect(() => {
        setActiveTab(preferredTab || (executiveReport ? "executive" : "arbitrage"));
    }, [analysis?.id, executiveReport, preferredTab]);

    if (!analysis) {
        return (
            <div className="min-h-[60vh] flex flex-col items-center justify-center text-center gap-3 p-8">
                <div className="rounded-full bg-slate-900/50 p-4">
                    <RefreshCw className="h-7 w-7 text-slate-400" />
                </div>
                <h2 className="text-xl text-white font-semibold">No Bill Analysis Found</h2>
                <p className="max-w-md text-slate-400">
                    Upload a billing file from Settings to analyze PDF, CSV, or Excel exports in the bill dashboard.
                </p>
                <Link href="/dashboard/settings" className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500">
                    Go to Settings
                </Link>
            </div>
        );
    }

    const positiveOpportunities = (analysis.arbitrage_opportunities || []).filter((item) => (item.savings || 0) > 0);
    const currentAnalysisId = analysis.analysis_id || analysis.id;
    const metadata = analysis.source_metadata || {};
    const rawBillMetadata = getRawBillFileMetadata(metadata);
    const rawBillStatus = String(rawBillMetadata?.status || "").trim().toLowerCase();
    const rawBillAvailable = rawBillStatus === "stored";
    const lineItemsDetected = Number(metadata.line_items_detected || 0);
    const extractorList = Array.isArray(metadata.extractors_used)
        ? metadata.extractors_used.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
        : [];
    const showRecentAnalyses = recentAnalyses.length > 0;
    const recentWithoutSelected = recentAnalyses.filter((item) => {
        const itemId = item.analysis_id || item.id;
        return itemId !== currentAnalysisId;
    });
    const isSourceGroundedReport = executiveReport?.verification_status === "source_grounded_unverified_savings";
    const optimizationRange = executiveReport
        ? formatCurrencyRange(
            executiveReport.additional_savings_min,
            executiveReport.additional_savings_max,
            analysis.currency,
        )
        : formatCurrency(analysis.total_potential_savings, analysis.currency);
    const crossCloudSavings = formatCurrency(analysis.total_potential_savings, analysis.currency);
    const reportConfidence = executiveReport?.confidence
        ? executiveReport.confidence[0].toUpperCase() + executiveReport.confidence.slice(1)
        : null;

    return (
        <div className="space-y-6 p-4 md:p-8">
            <div className="bill-report-hide-print flex items-start justify-between gap-4 flex-wrap">
                <div>
                    <h1 className="text-2xl font-bold text-white">Bill Analysis Dashboard</h1>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-400">
                        <span>{analysis.filename}</span>
                        <span className="text-slate-500">•</span>
                        <ProviderBadge provider={analysis.provider_detected} />
                        <span className="text-slate-500">•</span>
                        <span>{analysis.rows_parsed.toLocaleString()} parsed rows</span>
                    </div>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                    <span className="inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-xs text-indigo-400">
                        <Shield className="h-3.5 w-3.5" />
                        Real uploaded bill analysis
                    </span>
                </div>
            </div>

            {executiveReport ? (
                <div className="bill-report-hide-print rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950/60 p-6 shadow-2xl shadow-indigo-950/20">
                    <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
                        <div className="max-w-4xl">
                            <p className="flex items-center gap-2 text-xs uppercase tracking-[0.28em] text-indigo-300">
                                <Sparkles className="h-4 w-4" />
                                {isSourceGroundedReport ? "Bill Evidence" : "Executive Intelligence"}
                            </p>
                            <h2 className="mt-4 text-2xl font-bold leading-tight text-white">
                                {executiveReport.headline}
                            </h2>
                            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
                                {executiveReport.waste_grade_explanation}
                            </p>
                        </div>
                        <div className="grid gap-4 md:grid-cols-3 xl:min-w-[440px] xl:grid-cols-1">
                            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
                                <p className="text-xs uppercase tracking-[0.22em] text-emerald-200">
                                    {isSourceGroundedReport ? "Verified Savings" : "Optimization Range"}
                                </p>
                                <p className="mt-2 text-xl font-bold text-white">{optimizationRange} / month</p>
                            </div>
                            <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/10 p-4">
                                <p className="text-xs uppercase tracking-[0.22em] text-indigo-200">
                                    {isSourceGroundedReport ? "Current Bill" : "Optimised Bill"}
                                </p>
                                <p className="mt-2 text-xl font-bold text-white">
                                    {isSourceGroundedReport
                                        ? `${formatCurrency(analysis.total_analyzed_spend, analysis.currency)} / month`
                                        : `${formatCurrencyRange(
                                            executiveReport.optimised_bill_min,
                                            executiveReport.optimised_bill_max,
                                            analysis.currency,
                                        )} / month`}
                                </p>
                            </div>
                            <div className="rounded-2xl border border-violet-500/20 bg-violet-500/10 p-4">
                                <p className="text-xs uppercase tracking-[0.22em] text-violet-200">
                                    {isSourceGroundedReport ? "Verification" : "Implementation"}
                                </p>
                                <p className="mt-2 text-xl font-bold text-white">
                                    {isSourceGroundedReport ? "Billing setup needed" : `${executiveReport.implementation_timeline_days} days`}
                                </p>
                                {reportConfidence ? (
                                    <p className="mt-1 text-xs text-violet-100">Confidence: {reportConfidence}</p>
                                ) : null}
                            </div>
                        </div>
                    </div>
                </div>
            ) : null}

            <div className="bill-report-hide-print flex flex-wrap items-center gap-3">
                <button
                    type="button"
                    onClick={() => setActiveTab("arbitrage")}
                    className={`rounded-xl px-4 py-2 text-sm font-medium transition ${activeTab === "arbitrage"
                        ? "border border-indigo-500/30 bg-indigo-600/20 text-indigo-300"
                        : "border border-white/10 bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800/50"
                        }`}
                >
                    Arbitrage Opportunities
                </button>
                <button
                    type="button"
                    onClick={() => setActiveTab("executive")}
                    className={`rounded-xl px-4 py-2 text-sm font-medium transition ${activeTab === "executive"
                        ? "border border-indigo-500/30 bg-indigo-600/20 text-indigo-300"
                        : "border border-white/10 bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800/50"
                        }`}
                >
                    Executive Report
                </button>
            </div>

            {activeTab === "executive" && executiveReport ? (
                <BillExecutiveReportPanel analysis={analysis} report={executiveReport} />
            ) : null}

            {activeTab === "executive" && !executiveReport ? (
                <div className={`${surfaceClassName} p-6 text-sm text-slate-300`}>
                    Executive report generation is not available for this saved analysis yet. Re-upload the bill to generate the consulting summary.
                </div>
            ) : null}

            {activeTab === "arbitrage" && (
                <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-6">
                    <div className="space-y-6">
                        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                            <div className={`${surfaceClassName} p-5`}>
                                <p className="text-sm text-slate-400">Total Bill Analyzed</p>
                                <p className="text-2xl text-white font-bold mt-1">
                                    {formatCurrency(analysis.total_analyzed_spend, analysis.currency)}
                                </p>
                                <p className="text-xs text-slate-500 mt-1">{analysis.currency}/month</p>
                            </div>
                            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-5 backdrop-blur-xl">
                                <p className="text-sm text-emerald-300">
                                    {executiveReport
                                        ? isSourceGroundedReport
                                            ? "Verified Savings"
                                            : "Optimization Savings Range"
                                        : "Potential Monthly Savings"}
                                </p>
                                <p className="text-2xl text-white font-bold mt-1">
                                    {executiveReport ? optimizationRange : formatCurrency(analysis.total_potential_savings, analysis.currency)}
                                </p>
                                <p className="text-xs text-slate-200 mt-1">
                                    {executiveReport && isSourceGroundedReport
                                        ? "Bill-only analysis: no verified savings claimed"
                                        : executiveReport
                                        ? `Cross-cloud repricing alone: ${crossCloudSavings}/month`
                                        : `${positiveOpportunities.length} opportunities`}
                                </p>
                            </div>
                            <div className={`${surfaceClassName} p-5`}>
                                <p className="text-sm text-slate-400">
                                    {executiveReport ? (isSourceGroundedReport ? "Evidence Status" : "Waste Grade") : "Source"}
                                </p>
                                <p className="text-xl text-white font-semibold mt-1">
                                    {executiveReport
                                        ? isSourceGroundedReport
                                            ? "Source-grounded"
                                            : executiveReport.waste_grade
                                        : sourceLabel(analysis)}
                                </p>
                                <p className="text-xs text-slate-500 mt-1">
                                    {executiveReport
                                        ? executiveReport.waste_grade_explanation
                                        : `${analysis.source_format.toUpperCase()} via ${parserLabel(analysis.source_parser)}`}
                                </p>
                            </div>
                            <div className={`${surfaceClassName} p-5`}>
                                <p className="text-sm text-slate-400">
                                    {executiveReport ? "Cross-Cloud Repricing" : "Detected Line Items"}
                                </p>
                                <p className="text-2xl text-white font-bold mt-1">
                                    {executiveReport
                                        ? crossCloudSavings
                                        : (lineItemsDetected || analysis.rows_parsed).toLocaleString()}
                                </p>
                                <p className="text-xs text-slate-500 mt-1">
                                    {executiveReport
                                        ? `${positiveOpportunities.length} repricing estimate${positiveOpportunities.length === 1 ? "" : "s"}`
                                        : "Captured from the uploaded bill"}
                                </p>
                            </div>
                        </div>

                        {executiveReport ? (
                            <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/10 p-5 backdrop-blur-xl">
                                <p className="text-xs uppercase tracking-widest text-indigo-300">Read This Correctly</p>
                                <p className="mt-2 text-sm leading-7 text-slate-200">
                                    {isSourceGroundedReport
                                        ? "This report is limited to exact charges extracted from the uploaded bill. Savings, remediation plans, and resource-level allocations require CUR, Cost Explorer, or usage telemetry."
                                        : "The executive report is your main optimization view. The arbitrage cards below are only cross-cloud repricing estimates. The larger savings range above combines bill intelligence, deterministic service analysis, and the executive-report plan."}
                                </p>
                            </div>
                        ) : null}

                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                            <div className={`${surfaceClassName} p-5`}>
                                <h2 className="mb-3 text-sm uppercase tracking-widest text-slate-400">Spend by Category</h2>
                                <div className="grid grid-cols-2 gap-3">
                                    {Object.entries(analysis.spend_by_category || {})
                                        .sort((a, b) => b[1] - a[1])
                                        .map(([category, cost]) => (
                                            <div key={category} className="rounded-xl border border-white/10 bg-slate-900 px-3 py-3">
                                                <p className="text-xs text-slate-400">{category}</p>
                                                <p className="text-lg text-white font-semibold">
                                                    {formatCurrency(cost, analysis.currency)}
                                                </p>
                                            </div>
                                        ))}
                                </div>
                            </div>

                            <div className={`${surfaceClassName} p-5`}>
                                <h2 className="mb-3 text-sm uppercase tracking-widest text-slate-400">Top Services</h2>
                                <div className="space-y-3">
                                    {(analysis.top_services || []).slice(0, 8).map((service) => (
                                        <div key={`${service.service}-${service.cost}`} className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-slate-900 px-3 py-2">
                                            <div className="min-w-0">
                                                <p className="text-sm text-white truncate">{cleanServiceName(service.service)}</p>
                                            </div>
                                            <span className="text-sm text-slate-300 shrink-0">
                                                {formatCurrency(service.cost, analysis.currency)}
                                            </span>
                                        </div>
                                    ))}
                                    {(!analysis.top_services || analysis.top_services.length === 0) && (
                                        <div className="rounded-xl border border-white/10 bg-slate-900 px-4 py-4 text-sm text-slate-400">
                                            No service-level charges were detected.
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {analysis.gpu_insights && analysis.gpu_insights.gpu_instances_found.length > 0 && (
                            <div className="space-y-4">
                                {/* GPU hero bar */}
                                <div className="rounded-2xl border border-violet-500/20 bg-violet-500/10 p-5 backdrop-blur-xl">
                                    <div className="flex items-center justify-between flex-wrap gap-3">
                                        <div>
                                            <h2 className="text-white font-semibold flex items-center gap-2">
                                                <span>⚡ GPU Intelligence</span>
                                                <span className="text-xs rounded-full bg-violet-500/20 text-violet-300 px-2 py-0.5 border border-violet-500/30">
                                                    {analysis.gpu_insights.gpu_instances_found.length} GPU instance{analysis.gpu_insights.gpu_instances_found.length !== 1 ? "s" : ""} found
                                                </span>
                                            </h2>
                                            <p className="text-sm text-slate-300 mt-1">
                                                Total GPU spend: <span className="text-white font-bold">{formatCurrency(analysis.gpu_insights.total_gpu_spend, analysis.currency)}</span>
                                                {" · "}Potential savings:{" "}
                                                <span className="text-emerald-400 font-bold">{formatCurrency(analysis.gpu_insights.total_potential_savings, analysis.currency)}/mo</span>
                                            </p>
                                        </div>
                                        <a href="/dashboard/gpu" className="text-xs text-violet-400 hover:text-violet-300 underline">
                                            Open full GPU Intelligence →
                                        </a>
                                    </div>
                                </div>

                                {/* Ghost GPU alerts */}
                                {analysis.gpu_insights.ghost_gpus.length > 0 && (
                                    <div className="space-y-2">
                                        <h3 className="text-sm font-semibold text-rose-300 flex items-center gap-2">
                                            👻 Ghost GPUs Detected
                                            <span className="rounded-full bg-rose-500/20 text-rose-300 px-2 py-0.5 text-xs">{analysis.gpu_insights.ghost_gpus.length}</span>
                                        </h3>
                                        {analysis.gpu_insights.ghost_gpus.map((g: { sku: string; cost: number; message: string }, i: number) => (
                                            <div key={i} className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4">
                                                <div className="flex items-start justify-between gap-2 flex-wrap">
                                                    <div>
                                                        <p className="text-white font-medium text-sm">{g.sku.toUpperCase()}</p>
                                                        <p className="text-xs text-rose-300 mt-0.5">{g.message}</p>
                                                    </div>
                                                    <p className="text-rose-300 font-bold text-sm">{formatCurrency(g.cost, analysis.currency)}/mo · {formatCurrency(g.cost * 12, analysis.currency)}/yr</p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* GPU Arbitrage table */}
                                {analysis.gpu_insights.arbitrage_opportunities.length > 0 && (
                                    <div className="space-y-2">
                                        <h3 className="text-sm font-semibold text-slate-200">Specialized Cloud Alternatives</h3>
                                        <div className="rounded-xl border border-white/10 overflow-x-auto">
                                            <table className="w-full text-xs">
                                                <thead>
                                                    <tr className="border-b border-white/10 bg-white/5">
                                                        <th className="text-left px-4 py-2 text-slate-400">SKU / GPU</th>
                                                        <th className="text-right px-4 py-2 text-orange-300">AWS</th>
                                                        <th className="text-right px-4 py-2 text-blue-300">Best Alt.</th>
                                                        <th className="text-right px-4 py-2 text-emerald-300">Save/mo</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {analysis.gpu_insights.arbitrage_opportunities.map((a: { gpu_type: string; savings: number; alternative_cloud: string; current_cost?: number; alternative_cost?: number }, i: number) => (
                                                        <tr key={i} className="border-b border-white/5">
                                                            <td className="px-4 py-2 text-white">{a.gpu_type}</td>
                                                            <td className="px-4 py-2 text-right text-slate-300">
                                                                {a.current_cost !== undefined ? formatCurrency(a.current_cost, analysis.currency) : "—"}
                                                            </td>
                                                            <td className="px-4 py-2 text-right text-blue-300">
                                                                {a.alternative_cloud}{a.alternative_cost !== undefined ? ` · ${formatCurrency(a.alternative_cost, analysis.currency)}` : ""}
                                                            </td>
                                                            <td className="px-4 py-2 text-right text-emerald-300 font-bold">{formatCurrency(a.savings, analysis.currency)}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {analysis.cloudfront_insights?.summary && (
                            <div className="space-y-1 rounded-2xl border border-indigo-500/20 bg-indigo-500/10 p-5 backdrop-blur-xl">
                                <h2 className="text-white font-semibold">CloudFront Deep Insights</h2>
                                <p className="text-sm text-slate-300">
                                    Potential monthly savings:{" "}
                                    {formatCurrency(
                                        Number(analysis.cloudfront_insights.summary.total_monthly_savings_available || 0),
                                        analysis.currency,
                                    )}
                                </p>
                                <p className="text-xs text-slate-400">
                                    {analysis.cloudfront_insights.summary.opportunities_count || 0} CloudFront optimization opportunities.
                                </p>
                            </div>
                        )}

                        <div className="space-y-3">
                            <h2 className="text-white font-semibold">Cross-Cloud Repricing Estimates</h2>
                            {positiveOpportunities.length === 0 && (
                                <div className={`${surfaceClassName} p-4 text-sm text-slate-400`}>
                                    No positive arbitrage opportunities were found for this bill.
                                </div>
                            )}

                            {positiveOpportunities.map((opportunity, index) => (
                                <OpportunityCard
                                    key={`${opportunity.category}-${index}`}
                                    opportunity={opportunity}
                                    currency={analysis.currency}
                                    supportingFinding={findSupportingFinding(executiveReport, opportunity)}
                                />
                            ))}
                        </div>
                    </div>

                    <aside className="space-y-6">
                        <div className={`${surfaceClassName} p-5 space-y-3`}>
                            <h2 className="text-white font-semibold">Analysis Context</h2>
                            <MetadataRow label="Generated" value={formatTimestamp(analysis.created_at)} />
                            <MetadataRow label="Provider" value={analysis.provider_detected} />
                            <MetadataRow label="Source" value={sourceLabel(analysis)} />
                            <MetadataRow label="Format" value={analysis.source_format.toUpperCase()} />
                            <MetadataRow label="Parser" value={parserLabel(analysis.source_parser)} />
                            {extractorList.length > 0 && (
                                <MetadataRow label="Extractors" value={extractorList.join(", ")} />
                            )}
                            {typeof metadata.text_lines_detected === "number" && (
                                <MetadataRow label="Text Lines" value={Number(metadata.text_lines_detected).toLocaleString()} />
                            )}
                            {typeof metadata.table_rows_detected === "number" && (
                                <MetadataRow label="Table Rows" value={Number(metadata.table_rows_detected).toLocaleString()} />
                            )}
                            <MetadataRow
                                label="Raw Bill"
                                value={rawBillAvailable ? "Retained privately" : "Not archived"}
                            />
                        </div>

                        <div className={`${surfaceClassName} p-5 space-y-3`}>
                            <h2 className="text-white font-semibold">Discounts Applied</h2>
                            <div className="flex flex-wrap gap-2 text-xs">
                                {Object.entries(analysis.discounts_applied || {}).map(([cloud, discount]) => (
                                    <span key={cloud} className={`rounded-full px-3 py-1 ${getProviderBadgeClassName(cloud)}`}>
                                        {cloud}: {discount}
                                    </span>
                                ))}
                            </div>
                            <p className="text-xs text-slate-400">
                                {rawBillAvailable
                                    ? "The original uploaded file is retained privately for internal analysis, audit, and reprocessing."
                                    : "This analysis does not have a retrievable raw source file yet. Legacy uploads and unconfigured storage fall back to normalized analysis data only."}
                            </p>
                        </div>

                        {showRecentAnalyses && (
                            <div className={`${surfaceClassName} p-5 space-y-3`}>
                                <h2 className="text-white font-semibold">Recent Analyses</h2>
                                {recentWithoutSelected.length === 0 && (
                                    <div className="rounded-xl border border-white/10 bg-slate-900 px-3 py-3 text-sm text-slate-400">
                                        No older bill analyses are available yet.
                                    </div>
                                )}
                                {recentWithoutSelected.slice(0, 5).map((item) => (
                                    <div
                                        key={item.id}
                                        className="rounded-xl border border-white/10 bg-slate-900 px-3 py-3 text-sm text-slate-400"
                                    >
                                        <p className="text-white truncate">{item.filename}</p>
                                        <p className="mt-2 text-xs">{formatTimestamp(item.created_at)}</p>
                                    </div>
                                ))}
                            </div>
                        )}
                    </aside>
                </div>
            )}
        </div>
    );
}
