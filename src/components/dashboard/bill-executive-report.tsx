"use client";

import Image from "next/image";
import { useMemo, useState } from "react";
import {
    ArrowRight,
    Check,
    CheckCircle2,
    ChevronDown,
    ChevronUp,
    Copy,
    Printer,
    Sparkles,
} from "lucide-react";

import { cleanServiceName, normalizeBillExecutiveReport } from "@/lib/bill-executive-report";
import type {
    BillAnalysisRecord,
    BillExecutiveCrossCloudComparison,
    BillExecutiveFinding,
    BillExecutiveFindingAction,
    BillExecutiveReport,
} from "@/lib/api";
import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";

type BillExecutiveReportProps = {
    analysis: BillAnalysisRecord;
    report: BillExecutiveReport;
};

const gradeClassName: Record<string, string> = {
    A: "text-emerald-400",
    B: "text-indigo-400",
    C: "text-amber-400",
    D: "text-orange-400",
    F: "text-rose-500",
};

const severityClassName: Record<string, string> = {
    critical: "border border-rose-500/20 bg-rose-500/10 text-rose-400",
    high: "border border-amber-500/20 bg-amber-500/10 text-amber-400",
    medium: "border border-indigo-500/20 bg-indigo-500/10 text-indigo-400",
    low: "border border-slate-500/20 bg-slate-500/10 text-slate-300",
    optimized: "border border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
};

const riskClassName: Record<string, string> = {
    None: "border border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
    Low: "border border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
    Medium: "border border-amber-500/20 bg-amber-500/10 text-amber-400",
    High: "border border-rose-500/20 bg-rose-500/10 text-rose-400",
};

const surfaceClassName = "rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-xl";

function formatCurrency(amount: number, currency: string) {
    return formatInrCurrency(toDisplayInrAmount(amount || 0, currency || "USD"), {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function formatRange(minimum: number, maximum: number, currency: string, suffix: string) {
    return `${formatCurrency(minimum, currency)} - ${formatCurrency(maximum, currency)}${suffix}`;
}

function formatPercent(value: number) {
    return `${Number(value || 0).toFixed(1)}%`;
}

function formatTimestamp(value: string) {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }

    return new Intl.DateTimeFormat("en-US", {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(parsed);
}

function getActionSavings(action: BillExecutiveFindingAction, currency: string) {
    if ((action.monthly_saving_min || 0) === (action.monthly_saving_max || 0)) {
        return `${formatCurrency(action.monthly_saving_max, currency)}/month`;
    }
    return `${formatCurrency(action.monthly_saving_min, currency)} - ${formatCurrency(action.monthly_saving_max, currency)}/month`;
}

function formatSavingsSource(value?: string | null) {
    if (!value) {
        return "Estimated from bill lines";
    }
    return value
        .replace(/_/g, " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getFindingRenderKey(finding: BillExecutiveFinding, index: number) {
    return `${finding.service}-${finding.rank}-${index}`;
}

function CopyButton({
    copied,
    onClick,
    label,
}: {
    copied: boolean;
    onClick: () => void;
    label: string;
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            className="bill-report-hide-print inline-flex items-center gap-2 rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-300 transition hover:border-indigo-500/30 hover:text-white"
        >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied!" : label}
        </button>
    );
}

function isCheapestAwsOptimised(row: BillExecutiveCrossCloudComparison) {
    if (row.aws_optimised == null) {
        return false;
    }

    const comparableValues = [row.aws_optimised, row.gcp, row.azure].filter(
        (value): value is number => typeof value === "number",
    );
    if (comparableValues.length === 0) {
        return false;
    }

    return row.aws_optimised <= Math.min(...comparableValues);
}

function FindingCard({
    finding,
    currency,
    expanded,
    onToggle,
}: {
    finding: BillExecutiveFinding;
    currency: string;
    expanded: boolean;
    onToggle: () => void;
}) {
    const primaryAction = finding.actions[0];
    const calculation = finding.calculation || primaryAction?.calculation || "";
    const evidenceLines = (finding.evidence_lines?.length ? finding.evidence_lines : primaryAction?.evidence_lines) || [];
    const savingsSource = finding.savings_source || primaryAction?.savings_source || null;
    const validationRequired = Boolean(finding.validation_required || primaryAction?.validation_required);
    const confidenceReason = finding.confidence_reason || primaryAction?.confidence_reason || "";
    return (
        <div className={`${surfaceClassName} bill-report-card overflow-hidden`}>
            <div className="flex flex-col gap-4 p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-3">
                        <div className="flex flex-wrap items-center gap-3">
                            <span className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${severityClassName[finding.severity] || severityClassName.low}`}>
                                {finding.severity}
                            </span>
                            <span className="text-xs uppercase tracking-[0.25em] text-slate-500">
                                #{finding.rank}
                            </span>
                        </div>
                        <div>
                            <h3 className="text-2xl font-semibold text-white">{cleanServiceName(finding.service)}</h3>
                            <p className="mt-2 text-sm text-slate-400">
                                {formatCurrency(finding.monthly_cost, currency)} / month
                                <span className="mx-2 text-slate-600">•</span>
                                {formatPercent(finding.pct_of_bill)} of bill
                            </p>
                        </div>
                    </div>

                    {primaryAction ? (
                        <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-right">
                            <p className="text-xs uppercase tracking-[0.22em] text-emerald-200">Savings Range</p>
                            <p className="mt-2 text-lg font-semibold text-white">
                                {getActionSavings(primaryAction, currency)}
                            </p>
                        </div>
                    ) : null}
                </div>

                <div className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
                    <div className="space-y-4">
                        <div>
                            <p className="text-xs uppercase tracking-[0.22em] text-slate-500">What We Found</p>
                            <p className="mt-2 text-sm leading-7 text-slate-200">{finding.what_we_found}</p>
                        </div>
                        <div>
                            <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                                {finding.severity === "optimized" ? "Status" : "Why It Matters"}
                            </p>
                            {finding.severity === "optimized" ? (
                                <p className="mt-2 inline-flex items-center gap-2 text-sm text-emerald-300">
                                    <CheckCircle2 className="h-4 w-4" />
                                    Already optimised
                                </p>
                            ) : (
                                <p className="mt-2 text-sm leading-7 text-slate-300">{finding.why_inefficient}</p>
                            )}
                        </div>
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Recommended Action</p>
                        {primaryAction ? (
                            <>
                                <p className="mt-3 text-sm font-medium text-white">{primaryAction.name}</p>
                                <div className="mt-3 flex flex-wrap gap-2">
                                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                                        {primaryAction.difficulty}
                                    </span>
                                    <span className={`rounded-full px-3 py-1 text-xs ${riskClassName[primaryAction.risk] || riskClassName.Medium}`}>
                                        {primaryAction.risk}
                                    </span>
                                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                                        {primaryAction.time_required}
                                    </span>
                                </div>
                            </>
                        ) : (
                            <p className="mt-3 text-sm text-slate-400">No remediation action was generated for this finding.</p>
                        )}
                    </div>
                </div>

                {(calculation || evidenceLines.length > 0 || savingsSource || validationRequired || confidenceReason) ? (
                    <div className="grid gap-4 rounded-2xl border border-indigo-500/20 bg-indigo-500/10 p-4 lg:grid-cols-[0.9fr_1.1fr]">
                        <div>
                            <p className="text-xs uppercase tracking-[0.22em] text-indigo-200">Savings Basis</p>
                            <div className="mt-3 flex flex-wrap gap-2">
                                <span className="rounded-full border border-indigo-400/20 bg-indigo-400/10 px-3 py-1 text-xs text-indigo-100">
                                    {formatSavingsSource(savingsSource)}
                                </span>
                                {validationRequired ? (
                                    <span className="rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-xs text-amber-100">
                                        Requires validation
                                    </span>
                                ) : null}
                            </div>
                            {calculation ? (
                                <p className="mt-3 rounded-xl border border-white/10 bg-slate-950/50 px-3 py-2 font-mono text-xs text-slate-100">
                                    {calculation}
                                </p>
                            ) : null}
                            {confidenceReason ? (
                                <p className="mt-3 text-xs leading-6 text-slate-300">{confidenceReason}</p>
                            ) : null}
                        </div>
                        {evidenceLines.length > 0 ? (
                            <div>
                                <p className="text-xs uppercase tracking-[0.22em] text-indigo-200">Bill Evidence</p>
                                <ul className="mt-3 space-y-2 text-xs leading-5 text-slate-300">
                                    {evidenceLines.slice(0, 4).map((line, index) => (
                                        <li key={`${finding.service}-evidence-${index}`} className="rounded-xl border border-white/10 bg-slate-950/50 px-3 py-2">
                                            {line}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ) : null}
                    </div>
                ) : null}
            </div>

            <div className="border-t border-white/10 bg-slate-950/40 px-6 py-4">
                <button
                    type="button"
                    onClick={onToggle}
                    className="bill-report-hide-print inline-flex items-center gap-2 rounded-xl border border-white/10 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-indigo-500/30 hover:text-white"
                >
                    {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    {expanded ? "Hide fix plan" : "Show how to fix"}
                </button>

                <div className={`mt-5 grid gap-6 xl:grid-cols-[1.1fr_0.9fr] ${expanded ? "" : "hidden print:grid"}`}>
                        <div className="rounded-2xl border border-white/10 bg-slate-900/80 p-4">
                            <p className="text-xs uppercase tracking-[0.22em] text-slate-500">How to Fix</p>
                            <ol className="mt-4 space-y-3 text-sm text-slate-200">
                                {finding.how_to_fix.map((step: string, index: number) => (
                                    <li key={`${finding.service}-step-${index}`} className="flex gap-3">
                                        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-indigo-500/20 bg-indigo-500/10 text-xs font-semibold text-indigo-300">
                                            {index + 1}
                                        </span>
                                        <span className="leading-7">{step}</span>
                                    </li>
                                ))}
                            </ol>
                        </div>

                        <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/80">
                            <div className="grid grid-cols-[1.3fr_0.7fr_0.9fr_0.9fr_0.7fr] bg-white/5 px-4 py-3 text-[11px] uppercase tracking-wider text-slate-400">
                                <span>Name</span>
                                <span>Difficulty</span>
                                <span>Time</span>
                                <span>Saving</span>
                                <span>Risk</span>
                            </div>
                            <div className="divide-y divide-white/5">
                                {finding.actions.map((action: BillExecutiveFindingAction, index: number) => (
                                    <div key={`${finding.service}-action-${index}`} className="grid grid-cols-[1.3fr_0.7fr_0.9fr_0.9fr_0.7fr] gap-3 px-4 py-4 text-sm text-slate-200">
                                        <span className="font-medium text-white">{action.name}</span>
                                        <span>{action.difficulty}</span>
                                        <span>{action.time_required}</span>
                                        <span>{getActionSavings(action, currency)}</span>
                                        <span className={`inline-flex h-fit rounded-full px-3 py-1 text-xs ${riskClassName[action.risk] || riskClassName.Medium}`}>
                                            {action.risk}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
            </div>
        </div>
    );
}

export function BillExecutiveReport({ analysis, report }: BillExecutiveReportProps) {
    const normalizedReport = useMemo(() => normalizeBillExecutiveReport(report), [report]);
    const [copyKey, setCopyKey] = useState<string | null>(null);
    const [expandedFindings, setExpandedFindings] = useState<Record<string, boolean>>({});
    const [expandedScripts, setExpandedScripts] = useState<Record<string, boolean>>({
        opening: true,
    });

    if (!normalizedReport) {
        return (
            <div className="rounded-2xl border border-white/10 bg-slate-800/40 p-6 text-sm leading-7 text-slate-300 backdrop-blur-xl">
                This saved analysis contains an older executive-report payload. Refresh the page to reload the normalized report, or re-upload the bill if the problem persists.
            </div>
        );
    }

    const sortedFindings = useMemo(
        () => [...normalizedReport.findings].sort((a, b) => b.monthly_cost - a.monthly_cost),
        [normalizedReport.findings],
    );
    const quickWinsTotal = useMemo(
        () => normalizedReport.quick_wins.reduce((sum, item) => sum + (item.saving || 0), 0),
        [normalizedReport.quick_wins],
    );
    const biggestIssueLabel = cleanServiceName(sortedFindings[0]?.service || "Biggest Issue");
    const gradeColor = gradeClassName[normalizedReport.waste_grade] || gradeClassName.C;
    const reportDate = formatTimestamp(analysis.created_at);
    const isSourceGroundedReport = normalizedReport.verification_status === "source_grounded_unverified_savings";
    const isBillLineEstimateReport = normalizedReport.verification_status === "bill_line_rule_estimate";

    const handleCopy = async (key: string, value: string) => {
        try {
            await navigator.clipboard.writeText(value);
            setCopyKey(key);
            window.setTimeout(() => {
                setCopyKey((current) => (current === key ? null : current));
            }, 2000);
        } catch {
            setCopyKey(null);
        }
    };

    const toggleFinding = (service: string) => {
        setExpandedFindings((current) => ({
            ...current,
            [service]: !current[service],
        }));
    };

    const toggleScript = (key: string) => {
        setExpandedScripts((current) => ({
            ...current,
            [key]: !current[key],
        }));
    };

    return (
        <div className="bill-report-shell space-y-8">
            <style jsx global>{`
                @media print {
                    @page {
                        margin: 18mm 14mm 18mm 14mm;
                    }

                    html,
                    body {
                        background: #ffffff !important;
                        color: #000000 !important;
                    }

                    nav,
                    aside,
                    header,
                    .bill-report-hide-print {
                        display: none !important;
                    }

                    .bill-report-shell {
                        background: #ffffff !important;
                        color: #000000 !important;
                        padding: 0 !important;
                    }

                    .bill-report-shell * {
                        color: #000000 !important;
                        box-shadow: none !important;
                    }

                    .bill-report-shell .bg-slate-900\\/50,
                    .bill-report-shell .bg-slate-900\\/60,
                    .bill-report-shell .bg-slate-900\\/70,
                    .bill-report-shell .bg-slate-900,
                    .bill-report-shell .bg-slate-950\\/40,
                    .bill-report-shell .bg-slate-950\\/60,
                    .bill-report-shell .bg-slate-950\\/70,
                    .bill-report-shell .bg-slate-950 {
                        background: #ffffff !important;
                    }

                    .bill-report-section {
                        break-before: page;
                        page-break-before: always;
                    }

                    .bill-report-section:first-of-type {
                        break-before: auto;
                        page-break-before: auto;
                    }

                    .bill-report-card {
                        break-inside: avoid;
                        page-break-inside: avoid;
                    }

                    .bill-report-print-only {
                        display: flex !important;
                    }

                    .bill-report-screen-only {
                        display: none !important;
                    }

                    .bill-report-print-footer {
                        position: fixed;
                        bottom: 0;
                        left: 0;
                        right: 0;
                        display: flex !important;
                        justify-content: space-between;
                        border-top: 1px solid #cbd5e1;
                        padding-top: 8px;
                        font-size: 10px;
                        color: #334155 !important;
                    }

                    .bill-report-print-footer .page-number::after {
                        content: "Page " counter(page);
                    }
                }
            `}</style>

            <div className="bill-report-print-only hidden items-center justify-between rounded-2xl border border-slate-200 bg-white px-6 py-5">
                <div className="flex items-center gap-4">
                    <Image src="/cfs-logo.png" alt="CloudFinOps" width={160} height={42} className="h-10 w-auto" />
                    <div>
                        <p className="text-xs uppercase tracking-[0.3em] text-slate-500">CloudFinOps Executive Report</p>
                        <p className="mt-1 text-sm text-slate-600">{analysis.filename}</p>
                    </div>
                </div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Confidential</p>
            </div>

            <section className="bill-report-section rounded-2xl border border-white/10 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950/70 p-6 shadow-2xl shadow-indigo-950/20">
                <div className="grid gap-8 xl:grid-cols-[1.15fr_0.85fr]">
                    <div className="space-y-5">
                        <div className="flex items-center gap-4">
                            <Image src="/cfs-logo.png" alt="CloudFinOps" width={160} height={42} className="h-10 w-auto" />
                            <div>
                                <p className="text-xs uppercase tracking-[0.3em] text-indigo-200">
                                    {isSourceGroundedReport
                                        ? "Source-Grounded Bill Evidence"
                                        : isBillLineEstimateReport
                                            ? "Estimated From Bill Lines"
                                            : "Executive Bill Intelligence"}
                                </p>
                                <p className="mt-1 text-sm text-slate-400">
                                    Generated from {analysis.rows_parsed.toLocaleString()} parsed bill line items
                                </p>
                            </div>
                        </div>

                        <div className="flex items-end gap-5">
                            <span className={`text-[96px] font-black leading-none ${isSourceGroundedReport ? "text-indigo-300" : gradeColor}`}>
                                {isSourceGroundedReport ? "SRC" : normalizedReport.waste_grade}
                            </span>
                            <div className="pb-3">
                                <p className="text-sm font-medium uppercase tracking-[0.22em] text-slate-400">
                                    {isSourceGroundedReport ? "Evidence Status" : "Waste Grade"}
                                </p>
                                <p className="mt-2 max-w-xl text-sm leading-7 text-slate-300">
                                    {normalizedReport.waste_grade_explanation}
                                </p>
                            </div>
                        </div>

                        <div>
                            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Headline Finding</p>
                            <h2 className="mt-4 max-w-4xl text-3xl font-bold leading-tight text-white">
                                {normalizedReport.headline}
                            </h2>
                            <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300">
                                {normalizedReport.benchmark_context}
                            </p>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-1">
                            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-5">
                                <p className="text-xs uppercase tracking-[0.25em] text-emerald-200">
                                    {isSourceGroundedReport
                                        ? "Savings Not Claimed"
                                        : isBillLineEstimateReport
                                            ? "Estimated From Bill Lines"
                                            : "Savings Identified"}
                                </p>
                                <p className="mt-3 text-2xl font-bold text-white">
                                    {formatRange(normalizedReport.additional_savings_min, normalizedReport.additional_savings_max, analysis.currency, " / month")}
                                </p>
                            </div>
                            <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/10 p-5">
                                <p className="text-xs uppercase tracking-[0.25em] text-indigo-200">
                                    {isSourceGroundedReport ? "Current Bill" : "Optimised Bill"}
                                </p>
                                <p className="mt-3 text-2xl font-bold text-white">
                                    {isSourceGroundedReport
                                        ? `${formatCurrency(analysis.total_analyzed_spend, analysis.currency)} / month`
                                        : formatRange(normalizedReport.optimised_bill_min, normalizedReport.optimised_bill_max, analysis.currency, " / month")}
                                </p>
                            </div>
                            <div className="rounded-2xl border border-violet-500/20 bg-violet-500/10 p-5">
                                <p className="text-xs uppercase tracking-[0.25em] text-violet-200">
                                    {isSourceGroundedReport
                                        ? "Annual Savings Not Claimed"
                                        : isBillLineEstimateReport
                                            ? "Annual Estimated Savings"
                                            : "Annual Savings"}
                                </p>
                                <p className="mt-3 text-2xl font-bold text-white">
                                    {formatRange(normalizedReport.annual_savings_min, normalizedReport.annual_savings_max, analysis.currency, " / year")}
                                </p>
                            </div>
                        </div>

                        <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
                            <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
                                <span>
                                    {isSourceGroundedReport
                                        ? "Implementation: not generated from bill-only evidence"
                                        : isBillLineEstimateReport
                                            ? `Implementation estimate: ${normalizedReport.implementation_timeline_days} days`
                                        : `Implementation: ${normalizedReport.implementation_timeline_days} days`}
                                </span>
                                {!isSourceGroundedReport ? (
                                    <>
                                        <span className="text-slate-600">|</span>
                                        <span>{isBillLineEstimateReport ? "Validation required before execution" : "Zero downtime approach"}</span>
                                    </>
                                ) : null}
                            </div>
                            <div className="mt-4 flex flex-wrap gap-2">
                                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                                    Confidence: {normalizedReport.confidence}
                                </span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                                    Existing savings: {formatCurrency(normalizedReport.existing_savings_active, analysis.currency)}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <section className="bill-report-section space-y-5">
                <div className="flex items-center justify-between gap-4">
                    <div>
                        <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Section 2</p>
                        <h3 className="mt-2 text-2xl font-semibold text-white">What We Found</h3>
                    </div>
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                        {sortedFindings.length} service findings
                    </span>
                </div>
                <div className="bill-report-findings-grid space-y-5">
                    {sortedFindings.map((finding, index) => {
                        const findingKey = getFindingRenderKey(finding, index);

                        return (
                            <FindingCard
                                key={findingKey}
                                finding={finding}
                                currency={analysis.currency}
                                expanded={Boolean(expandedFindings[findingKey])}
                                onToggle={() => toggleFinding(findingKey)}
                            />
                        );
                    })}
                </div>
            </section>

            <section className="bill-report-section space-y-5">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Section 3</p>
                    <h3 className="mt-2 text-2xl font-semibold text-white">Start Here</h3>
                    <p className="mt-2 text-sm text-slate-400">
                        {isSourceGroundedReport
                            ? "No remediation plan is generated until usage telemetry or billing export mapping is connected."
                            : isBillLineEstimateReport
                                ? "Start with bill-line-backed actions, then validate commitment and workload assumptions before execution."
                            : "Zero downtime, results on your next bill."}
                    </p>
                </div>
                {normalizedReport.quick_wins.length > 0 ? (
                    <>
                        <div className="bill-report-quickwins-grid grid gap-4 md:grid-cols-3">
                            {normalizedReport.quick_wins.map((item, index) => (
                                <div key={`${item.action}-${index}`} className={`${surfaceClassName} bill-report-card p-5`}>
                                    <div className="flex items-center justify-between gap-3">
                                        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                                            {item.time}
                                        </span>
                                        <span className={`rounded-full px-3 py-1 text-xs ${riskClassName[item.risk] || riskClassName.Low}`}>
                                            {item.risk}
                                        </span>
                                    </div>
                                    <h4 className="mt-4 text-lg font-semibold text-white">{item.action}</h4>
                                    <p className="mt-4 text-2xl font-bold text-emerald-400">
                                        {formatCurrency(item.saving, analysis.currency)}/month
                                    </p>
                                </div>
                            ))}
                        </div>
                        <div className={`${surfaceClassName} p-5`}>
                            <p className="text-sm text-slate-300">
                                Total quick wins: <span className="font-semibold text-white">{formatCurrency(quickWinsTotal, analysis.currency)}/month</span> in less than a day of work.
                            </p>
                        </div>
                    </>
                ) : (
                    <div className={`${surfaceClassName} p-5 text-sm leading-7 text-slate-300`}>
                        No verified quick wins are claimed from this bill alone. Connect billing export/resource telemetry before showing savings actions.
                    </div>
                )}
            </section>

            <section className="bill-report-section space-y-5">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Section 4</p>
                    <h3 className="mt-2 text-2xl font-semibold text-white">90-Day Roadmap</h3>
                </div>
                {normalizedReport.roadmap.length > 0 ? (
                <div className="bill-report-roadmap-grid grid gap-4 xl:grid-cols-4">
                    {normalizedReport.roadmap.map((phase, index) => {
                        const phaseKey = `${phase.phase}-${index}`;

                        return (
                        <div key={phaseKey} className={`${surfaceClassName} bill-report-card relative p-5`}>
                            {index < normalizedReport.roadmap.length - 1 ? (
                                <div className="bill-report-screen-only absolute right-[-18px] top-10 hidden h-px w-9 bg-white/10 xl:block" />
                            ) : null}
                            <div className="flex items-center gap-3">
                                <div className="flex h-10 w-10 items-center justify-center rounded-full border border-indigo-500/20 bg-indigo-500/10 text-sm font-semibold text-indigo-300">
                                    {index + 1}
                                </div>
                                <div>
                                    <p className="text-sm font-semibold text-white">{phase.phase}</p>
                                    <p className="text-xs text-slate-400">{phase.timeframe}</p>
                                </div>
                            </div>
                            <ul className="mt-4 space-y-2 text-sm text-slate-300">
                                {phase.actions.map((action, actionIndex) => (
                                    <li key={`${phaseKey}-action-${actionIndex}`} className="flex gap-2">
                                        <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-indigo-400" />
                                        <span>{action}</span>
                                    </li>
                                ))}
                            </ul>
                            <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3">
                                <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Expected Saving</p>
                                <p className="mt-2 text-lg font-semibold text-white">
                                    {formatRange(phase.expected_saving_min, phase.expected_saving_max, analysis.currency, " / month")}
                                </p>
                            </div>
                        </div>
                    )})}
                </div>
                ) : (
                    <div className={`${surfaceClassName} p-5 text-sm leading-7 text-slate-300`}>
                        No roadmap is generated from source-only bill evidence.
                    </div>
                )}
            </section>

            <section className="bill-report-section space-y-5">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Section 5</p>
                    <h3 className="mt-2 text-2xl font-semibold text-white">Cross-Cloud Comparison</h3>
                </div>
                {normalizedReport.cross_cloud_comparison.length > 0 ? (
                <div className={`${surfaceClassName} overflow-hidden`}>
                    <div className="grid grid-cols-[1.4fr_0.8fr_0.8fr_0.8fr_0.8fr] bg-white/5 px-5 py-4 text-[11px] uppercase tracking-wider text-slate-400">
                        <span>Service</span>
                        <span>AWS Now</span>
                        <span>AWS Optimised</span>
                        <span>GCP</span>
                        <span>Azure</span>
                    </div>
                    <div className="divide-y divide-white/5">
                        {normalizedReport.cross_cloud_comparison.map((row, index) => (
                            <div
                                key={`${row.service}-${index}`}
                                className={`grid grid-cols-[1.4fr_0.8fr_0.8fr_0.8fr_0.8fr] gap-3 px-5 py-4 text-sm ${isCheapestAwsOptimised(row) ? "bg-emerald-500/5" : "bg-transparent"}`}
                            >
                                <span className="font-medium text-white">{cleanServiceName(row.service)}</span>
                                <span className="text-slate-300">{row.aws_current == null ? "N/A" : formatCurrency(row.aws_current, analysis.currency)}</span>
                                <span className="text-slate-300">{row.aws_optimised == null ? "N/A" : formatCurrency(row.aws_optimised, analysis.currency)}</span>
                                <span className="text-slate-300">{row.gcp == null ? "N/A" : formatCurrency(row.gcp, analysis.currency)}</span>
                                <span className="text-slate-300">{row.azure == null ? "N/A" : formatCurrency(row.azure, analysis.currency)}</span>
                            </div>
                        ))}
                    </div>
                    <div className="border-t border-white/10 px-5 py-4 text-xs text-slate-400">
                        Your existing Savings Plans are AWS-specific. Migration analysis is an estimate only and should be validated separately.
                    </div>
                </div>
                ) : (
                    <div className={`${surfaceClassName} p-5 text-sm leading-7 text-slate-300`}>
                        Cross-cloud comparison is hidden until savings estimates are explicitly marked as estimates or verified by billing telemetry.
                    </div>
                )}
            </section>

            <section className="bill-report-section space-y-5">
                <div className="flex items-center justify-between gap-4">
                    <div>
                        <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Section 6</p>
                        <h3 className="mt-2 text-2xl font-semibold text-white">Executive Summary</h3>
                    </div>
                    <CopyButton
                        copied={copyKey === "summary"}
                        onClick={() => handleCopy("summary", normalizedReport.executive_summary)}
                        label="Copy Report Summary"
                    />
                </div>
                <div className="print-white-card rounded-3xl bg-white p-8 text-slate-900 shadow-2xl shadow-slate-950/20">
                    <p className="whitespace-pre-line text-base leading-8">
                        {normalizedReport.executive_summary}
                    </p>
                </div>
            </section>

            <section className="bill-report-section space-y-5">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Section 7</p>
                    <h3 className="mt-2 text-2xl font-semibold text-white">Client Scripts</h3>
                </div>
                <div className="space-y-4">
                    {[
                        { key: "opening", label: "Opening the Conversation", value: normalizedReport.client_scripts.opening },
                        {
                            key: "biggest_issue",
                            label: `Explaining ${biggestIssueLabel}`,
                            value: normalizedReport.client_scripts.explain_biggest_issue,
                        },
                        { key: "objection", label: "Handling Objections", value: normalizedReport.client_scripts.handle_objection },
                        { key: "closing", label: "Closing the Deal", value: normalizedReport.client_scripts.closing },
                    ].map((script) => {
                        const expanded = Boolean(expandedScripts[script.key]);
                        return (
                            <div key={script.key} className={`${surfaceClassName} bill-report-card overflow-hidden`}>
                                <div className="flex items-center justify-between gap-4 p-5">
                                    <button
                                        type="button"
                                        onClick={() => toggleScript(script.key)}
                                        className="flex items-center gap-3 text-left"
                                    >
                                        {expanded ? <ChevronUp className="h-4 w-4 text-indigo-400" /> : <ChevronDown className="h-4 w-4 text-indigo-400" />}
                                        <span className="text-lg font-semibold text-white">{script.label}</span>
                                    </button>
                                    <CopyButton
                                        copied={copyKey === script.key}
                                        onClick={() => handleCopy(script.key, script.value)}
                                        label="Copy Script"
                                    />
                                </div>
                                <div className={`border-t border-white/10 px-5 py-5 text-sm leading-7 text-slate-200 ${expanded ? "" : "hidden print:block"}`}>
                                    {script.value}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </section>

            <section className="bill-report-section rounded-2xl border border-white/10 bg-slate-900/50 px-6 py-5">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div className="space-y-1">
                        <p className="flex items-center gap-2 text-sm text-slate-300">
                            <Sparkles className="h-4 w-4 text-indigo-400" />
                            Generated by CloudFinOps AI
                        </p>
                        <p className="text-xs text-slate-500">
                            {reportDate} | Based on {analysis.rows_parsed.toLocaleString()} line items
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => window.print()}
                        className="bill-report-hide-print inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
                    >
                        <Printer className="h-4 w-4" />
                        Download as PDF
                    </button>
                </div>
            </section>

            <div className="bill-report-print-footer hidden">
                <span>CONFIDENTIAL | CloudFinOps</span>
                <span className="page-number" />
            </div>
        </div>
    );
}
