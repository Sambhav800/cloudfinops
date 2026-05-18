"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, FileDown, Gauge, PiggyBank, Sparkles, TrendingDown, TriangleAlert } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";

type CommitmentScenario = {
    label: string;
    commitment_pct: number;
    monthly_commitment_usd: number;
    monthly_saving_usd: number;
    annual_saving_usd: number;
    effective_discount_pct: number;
    over_commitment_risk_pct: number;
    risk_level: "Low" | "Medium" | "High";
    term_years: number;
};

type CommitmentRecommendationResponse = {
    status: "ready" | "insufficient_history" | "no_spend_data";
    message?: string | null;
    days_available?: number | null;
    analysis_basis_days?: number | null;
    avg_monthly_spend_usd?: number | null;
    forecast_eom_spend_usd?: number | null;
    forecast_method?: string | null;
    forecast_stable?: boolean | null;
    spend_volatility_pct?: number | null;
    compute_fraction_pct?: number | null;
    safe_baseline_monthly_usd?: number | null;
    scenarios?: CommitmentScenario[];
    recommended_scenario?: CommitmentScenario | null;
    important_notes?: string[];
    aws_console_link?: string | null;
};

const MIN_REQUIRED_DAYS = 14;

function formatCurrency(value: number | null | undefined) {
    return formatInrCurrency(toDisplayInrAmount(Number(value || 0), "USD"));
}

function formatPercent(value: number | null | undefined) {
    return `${Number(value || 0).toFixed(1)}%`;
}

function escapeHtml(value: string) {
    return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function getRiskBadgeClass(risk: CommitmentScenario["risk_level"]) {
    if (risk === "Low") {
        return "border border-emerald-500/20 bg-emerald-500/10 text-emerald-400";
    }
    if (risk === "Medium") {
        return "border border-amber-500/20 bg-amber-500/10 text-amber-400";
    }
    return "border border-rose-500/20 bg-rose-500/10 text-rose-400";
}

function OptimizerSkeleton() {
    return (
        <div className="space-y-8">
            <div className="grid gap-4 md:grid-cols-3">
                {[1, 2, 3].map((item) => (
                    <div
                        key={item}
                        className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl"
                    >
                        <Skeleton className="mb-4 h-4 w-28 bg-slate-800" />
                        <Skeleton className="mb-2 h-10 w-40 bg-slate-700" />
                        <Skeleton className="h-4 w-48 bg-slate-800" />
                    </div>
                ))}
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 backdrop-blur-xl">
                <Skeleton className="mb-5 h-5 w-48 bg-slate-800" />
                <div className="space-y-3">
                    {[1, 2, 3, 4].map((row) => (
                        <Skeleton key={row} className="h-14 w-full bg-slate-800" />
                    ))}
                </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
                <Skeleton className="mb-3 h-6 w-56 bg-slate-800" />
                <Skeleton className="mb-2 h-5 w-full bg-slate-800" />
                <Skeleton className="mb-6 h-5 w-4/5 bg-slate-800" />
                <div className="flex gap-3">
                    <Skeleton className="h-11 w-44 rounded-xl bg-slate-800" />
                    <Skeleton className="h-11 w-36 rounded-xl bg-slate-800" />
                </div>
            </div>
        </div>
    );
}

export default function OptimizerPage() {
    const [data, setData] = useState<CommitmentRecommendationResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        const loadRecommendation = async () => {
            setLoading(true);
            setError(null);

            try {
                const response = await fetch("/api/finance/commitment-recommendation", {
                    cache: "no-store",
                });
                const payload = await response.json().catch(() => ({}));

                if (!response.ok) {
                    throw new Error(
                        typeof payload?.detail === "string"
                            ? payload.detail
                            : "Failed to load commitment recommendation.",
                    );
                }

                if (!cancelled) {
                    setData(payload as CommitmentRecommendationResponse);
                }
            } catch (requestError) {
                if (!cancelled) {
                    const message = requestError instanceof Error
                        ? requestError.message
                        : "Failed to load commitment recommendation.";
                    setError(message);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };

        loadRecommendation();

        return () => {
            cancelled = true;
        };
    }, []);

    const subtitleDays = data?.analysis_basis_days ?? data?.days_available;
    const ready = data?.status === "ready";
    const scenarios = data?.scenarios ?? [];
    const recommendedScenario = data?.recommended_scenario ?? null;

    const handleExportPdf = () => {
        if (!ready || !data || !recommendedScenario) {
            return;
        }

        const printWindow = window.open("", "_blank", "noopener,noreferrer,width=1100,height=900");
        if (!printWindow) {
            return;
        }

        const notesMarkup = (data.important_notes ?? [])
            .map((note) => `<li>${escapeHtml(note)}</li>`)
            .join("");
        const rowsMarkup = scenarios
            .map((scenario) => `
                <tr>
                    <td>${escapeHtml(scenario.label)}</td>
                    <td>${formatCurrency(scenario.monthly_commitment_usd)}</td>
                    <td>${formatCurrency(scenario.monthly_saving_usd)}</td>
                    <td>${formatCurrency(scenario.annual_saving_usd)}</td>
                    <td>${escapeHtml(scenario.risk_level)}</td>
                </tr>
            `)
            .join("");

        printWindow.document.write(`
            <!doctype html>
            <html>
                <head>
                    <title>CloudFinOps Savings Plan Recommendation</title>
                    <style>
                        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #0f172a; margin: 40px; }
                        h1, h2, h3 { margin: 0 0 12px; }
                        p { margin: 0 0 12px; line-height: 1.5; }
                        .hero { border: 1px solid #cbd5e1; border-radius: 18px; padding: 24px; margin-bottom: 24px; background: #f8fafc; }
                        .metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 24px 0; }
                        .metric { border: 1px solid #e2e8f0; border-radius: 16px; padding: 16px; background: #ffffff; }
                        .metric small { display: block; color: #475569; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.06em; }
                        .metric strong { font-size: 24px; }
                        table { width: 100%; border-collapse: collapse; margin: 24px 0; }
                        th, td { padding: 12px 14px; border-bottom: 1px solid #e2e8f0; text-align: left; }
                        th { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #475569; background: #f8fafc; }
                        .note-box { margin-top: 24px; padding: 18px; border: 1px solid #e2e8f0; border-radius: 16px; background: #f8fafc; }
                        ul { margin: 12px 0 0 20px; }
                    </style>
                </head>
                <body>
                    <div class="hero">
                        <h1>CloudFinOps Savings Plan Optimizer</h1>
                        <p>AI-powered commitment analysis based on your last ${subtitleDays ?? 0} days of spend.</p>
                        <p><strong>Recommendation:</strong> ${escapeHtml(recommendedScenario.label)}</p>
                        <p>
                            Based on your ${formatCurrency(data.avg_monthly_spend_usd)} average monthly AWS spend with
                            ${formatPercent(data.spend_volatility_pct)} volatility, CloudFinOps recommends committing
                            ${formatCurrency(recommendedScenario.monthly_commitment_usd)}/month for a ${recommendedScenario.term_years}-year term.
                            Estimated savings: ${formatCurrency(recommendedScenario.monthly_saving_usd)}/month
                            (${formatCurrency(recommendedScenario.annual_saving_usd)}/year).
                        </p>
                    </div>

                    <div class="metric-grid">
                        <div class="metric">
                            <small>Avg Monthly Spend</small>
                            <strong>${formatCurrency(data.avg_monthly_spend_usd)}</strong>
                        </div>
                        <div class="metric">
                            <small>Spend Volatility</small>
                            <strong>${formatPercent(data.spend_volatility_pct)}</strong>
                        </div>
                        <div class="metric">
                            <small>Compute Fraction</small>
                            <strong>${formatPercent(data.compute_fraction_pct)}</strong>
                        </div>
                    </div>

                    <h2>Scenario Comparison</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Scenario</th>
                                <th>Monthly Commit</th>
                                <th>Monthly Saving</th>
                                <th>Annual Saving</th>
                                <th>Risk</th>
                            </tr>
                        </thead>
                        <tbody>${rowsMarkup}</tbody>
                    </table>

                    <div class="note-box">
                        <h3>Important Notes</h3>
                        <ul>${notesMarkup}</ul>
                    </div>
                </body>
            </html>
        `);
        printWindow.document.close();
        printWindow.focus();
        window.setTimeout(() => {
            printWindow.print();
        }, 250);
    };

    return (
        <main className="min-h-screen bg-slate-950 p-6 text-slate-200 md:p-10">
            <div className="mx-auto max-w-7xl space-y-8">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-indigo-400">
                            <Sparkles className="h-3.5 w-3.5" />
                            Optimizer
                        </div>
                        <h1 className="text-3xl font-bold text-white md:text-4xl">Savings Plan Optimizer</h1>
                        <p className="mt-2 text-sm text-slate-400 md:text-base">
                            AI-powered commitment analysis based on your last {subtitleDays ?? 0} days of spend
                        </p>
                    </div>
                    {ready && data?.forecast_method ? (
                        <div className="rounded-2xl border border-white/10 bg-slate-900/50 px-4 py-3 text-sm text-slate-300 backdrop-blur-xl">
                            <span className="text-slate-500">Forecast engine</span>
                            <div className="mt-1 font-semibold text-white">
                                {data.forecast_method === "holt_winters"
                                    ? "Holt-Winters"
                                    : data.forecast_method.replaceAll("_", " ")}
                            </div>
                        </div>
                    ) : null}
                </div>

                {loading ? (
                    <OptimizerSkeleton />
                ) : error ? (
                    <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-6 text-rose-100">
                        <div className="flex items-start gap-3">
                            <TriangleAlert className="mt-0.5 h-5 w-5 text-rose-400" />
                            <div>
                                <h2 className="text-lg font-semibold text-white">Optimizer unavailable</h2>
                                <p className="mt-1 text-sm text-rose-100/80">{error}</p>
                            </div>
                        </div>
                    </div>
                ) : data?.status === "insufficient_history" ? (
                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
                        <div className="flex items-start gap-3">
                            <Gauge className="mt-0.5 h-5 w-5 text-indigo-400" />
                            <div className="w-full">
                                <h2 className="text-xl font-semibold text-white">Need more billing history</h2>
                                <p className="mt-2 text-sm text-slate-300">
                                    We need at least 14 days of billing history to generate recommendations. Your
                                    account has {data.days_available ?? 0} days available.
                                </p>
                                <div className="mt-5">
                                    <div className="mb-2 flex items-center justify-between text-xs uppercase tracking-[0.18em] text-slate-500">
                                        <span>History progress</span>
                                        <span>{data.days_available ?? 0}/{MIN_REQUIRED_DAYS} days</span>
                                    </div>
                                    <div className="h-3 overflow-hidden rounded-full bg-slate-800">
                                        <div
                                            className="h-full rounded-full bg-indigo-500 transition-all"
                                            style={{
                                                width: `${Math.min(
                                                    100,
                                                    ((data.days_available ?? 0) / MIN_REQUIRED_DAYS) * 100,
                                                )}%`,
                                            }}
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                ) : data?.status === "no_spend_data" ? (
                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
                        <div className="flex items-start gap-3">
                            <PiggyBank className="mt-0.5 h-5 w-5 text-indigo-400" />
                            <div>
                                <h2 className="text-xl font-semibold text-white">No AWS billing baseline yet</h2>
                                <p className="mt-2 text-sm text-slate-300">
                                    {data.message || "Connect an AWS account and run a scan to see commitment recommendations."}
                                </p>
                            </div>
                        </div>
                    </div>
                ) : ready && data && recommendedScenario ? (
                    <div className="space-y-8">
                        <div className="grid gap-4 md:grid-cols-3">
                            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
                                <div className="mb-3 flex items-center justify-between">
                                    <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Avg Monthly Spend</p>
                                    <PiggyBank className="h-4 w-4 text-indigo-400" />
                                </div>
                                <p className="text-3xl font-bold text-white">
                                    {formatCurrency(data.avg_monthly_spend_usd)}
                                </p>
                                <p className="mt-2 text-sm text-slate-400">
                                    Forecasted month-end spend: {formatCurrency(data.forecast_eom_spend_usd)}
                                </p>
                            </div>

                            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
                                <div className="mb-3 flex items-center justify-between">
                                    <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Spend Volatility</p>
                                    <TrendingDown className="h-4 w-4 text-amber-400" />
                                </div>
                                <p className="text-3xl font-bold text-white">
                                    {formatPercent(data.spend_volatility_pct)}
                                </p>
                                <p className="mt-2 text-sm text-slate-400">
                                    Lower volatility means it is safer to commit more baseline spend.
                                </p>
                            </div>

                            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
                                <div className="mb-3 flex items-center justify-between">
                                    <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Compute Fraction</p>
                                    <Gauge className="h-4 w-4 text-emerald-400" />
                                </div>
                                <p className="text-3xl font-bold text-white">
                                    {formatPercent(data.compute_fraction_pct)}
                                </p>
                                <p className="mt-2 text-sm text-slate-400">
                                    Portion of total resource spend that looks eligible for Compute Savings Plans.
                                </p>
                            </div>
                        </div>

                        <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur-xl">
                            <div className="border-b border-white/10 px-6 py-5">
                                <h2 className="text-xl font-semibold text-white">Scenario Comparison</h2>
                                <p className="mt-1 text-sm text-slate-400">
                                    Compare commitment amount, expected savings, and over-commitment risk.
                                </p>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="min-w-full">
                                    <thead className="bg-white/5 text-left text-xs uppercase tracking-[0.18em] text-slate-400">
                                        <tr>
                                            <th className="px-4 py-3">Scenario</th>
                                            <th className="px-4 py-3">Monthly Commit</th>
                                            <th className="px-4 py-3">Monthly Saving</th>
                                            <th className="px-4 py-3">Annual Saving</th>
                                            <th className="px-4 py-3">Risk</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {scenarios.map((scenario) => {
                                            const isRecommended = (
                                                scenario.label === recommendedScenario.label
                                                && scenario.term_years === recommendedScenario.term_years
                                            );

                                            return (
                                                <tr
                                                    key={`${scenario.label}-${scenario.term_years}`}
                                                    className={`border-b border-white/5 text-sm text-slate-300 transition-colors hover:bg-white/[0.03] ${isRecommended
                                                        ? "bg-indigo-500/10 shadow-[inset_0_0_0_1px_rgba(99,102,241,0.5)]"
                                                        : ""
                                                        }`}
                                                >
                                                    <td className="px-4 py-4">
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-medium text-white">
                                                                {scenario.label}
                                                            </span>
                                                            {isRecommended ? (
                                                                <span className="rounded-full border border-indigo-500/20 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-indigo-300">
                                                                    Recommended
                                                                </span>
                                                            ) : null}
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-4">{formatCurrency(scenario.monthly_commitment_usd)}</td>
                                                    <td className="px-4 py-4">{formatCurrency(scenario.monthly_saving_usd)}</td>
                                                    <td className="px-4 py-4">{formatCurrency(scenario.annual_saving_usd)}</td>
                                                    <td className="px-4 py-4">
                                                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getRiskBadgeClass(scenario.risk_level)}`}>
                                                            {scenario.risk_level}
                                                        </span>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div className="rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-indigo-900/30 via-slate-900/60 to-slate-900/80 p-6 backdrop-blur-xl">
                            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                                <div className="max-w-3xl">
                                    <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-indigo-300">
                                        <Sparkles className="h-3.5 w-3.5" />
                                        Our Recommendation
                                    </div>
                                    <h2 className="text-2xl font-bold text-white">
                                        {recommendedScenario.label}
                                    </h2>
                                    <p className="mt-3 text-base leading-7 text-slate-200">
                                        Based on your {formatCurrency(data.avg_monthly_spend_usd)}/month average AWS spend with{" "}
                                        {formatPercent(data.spend_volatility_pct)} volatility, committing{" "}
                                        {formatCurrency(recommendedScenario.monthly_commitment_usd)}/month to a{" "}
                                        {recommendedScenario.term_years}-year Compute Savings Plan would save you approximately{" "}
                                        {formatCurrency(recommendedScenario.monthly_saving_usd)}/month (
                                        {formatCurrency(recommendedScenario.annual_saving_usd)}/year) with a{" "}
                                        {recommendedScenario.risk_level.toLowerCase()} risk of over-commitment.
                                    </p>
                                </div>

                                <div className="flex flex-wrap gap-3">
                                    <a
                                        href={data.aws_console_link || "https://console.aws.amazon.com/billing/home#/bills"}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 font-medium text-white transition-colors hover:bg-indigo-500"
                                    >
                                        Buy on AWS Console
                                        <ArrowUpRight className="h-4 w-4" />
                                    </a>
                                    <button
                                        type="button"
                                        onClick={handleExportPdf}
                                        className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-slate-800 px-4 py-2 font-medium text-slate-200 transition-colors hover:bg-slate-700"
                                    >
                                        Export as PDF
                                        <FileDown className="h-4 w-4" />
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 backdrop-blur-xl">
                            <h2 className="text-lg font-semibold text-white">Important Notes</h2>
                            <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-300">
                                {(data.important_notes ?? []).map((note) => (
                                    <li key={note} className="flex gap-3">
                                        <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-indigo-400" />
                                        <span>{note}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                ) : null}
            </div>
        </main>
    );
}
