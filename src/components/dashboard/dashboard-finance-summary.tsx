"use client";

import Link from "next/link";
import {
    AlertTriangle,
    ArrowUpRight,
    CalendarClock,
    Landmark,
    Wallet,
} from "lucide-react";

import type { BackendIntegration, FinanceForecastResponse } from "@/lib/api";
import type { FinanceBudgetEvent } from "@/lib/api";
import {
    formatCurrency,
    formatDateLabel,
    formatPercent,
    formatSignedCurrency,
    getBudgetSourceLabel,
    getStatusPresentation,
    hasRenderableForecast,
    type StatusPresentation,
} from "@/components/dashboard/finance-formatters";

export type DashboardFinanceAccountSummary = {
    integration: BackendIntegration;
    forecast: FinanceForecastResponse | null;
};

type DashboardFinanceSummaryProps = {
    portfolioForecast: FinanceForecastResponse | null;
    portfolioBudgetEvent?: FinanceBudgetEvent | null;
    accountForecasts: DashboardFinanceAccountSummary[];
    loadError?: string | null;
};

type ProviderVarianceSummary = {
    provider: string;
    actualMtdSpend: number;
    forecastEomSpend: number;
    varianceAmount: number | null;
    riskCount: number;
};

const cardClassName =
    "rounded-2xl border border-white/10 bg-slate-900/50 p-5 backdrop-blur-xl shadow-2xl shadow-black/20";

const forecastCardClassName = `${cardClassName} border-t-2 border-t-sky-400/60 border-b-2 border-b-sky-400/30`;
const budgetCardClassName = `${cardClassName} border-t-2 border-t-violet-400/60 border-b-2 border-b-violet-400/30`;
const riskCardClassName = `${cardClassName} border-t-2 border-t-amber-400/60 border-b-2 border-b-amber-400/30`;
const providerCardClassName = `${cardClassName} border-t-2 border-t-emerald-400/60 border-b-2 border-b-emerald-400/30`;

const statusMeta: Record<string, StatusPresentation> = {
    on_track: {
        label: "On track",
        className: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    },
    approaching_budget: {
        label: "Approaching budget",
        className: "border-amber-400/30 bg-amber-400/10 text-amber-300",
    },
    forecasted_over_budget: {
        label: "Forecasted over budget",
        className: "border-rose-400/30 bg-rose-400/10 text-rose-300",
    },
    over_budget: {
        label: "Over budget",
        className: "border-rose-400/30 bg-rose-500/15 text-rose-200",
    },
    no_budget_configured: {
        label: "No budget configured",
        className: "border-slate-400/20 bg-slate-400/10 text-slate-300",
    },
    insufficient_history: {
        label: "Awaiting history",
        className: "border-indigo-400/30 bg-indigo-400/10 text-indigo-300",
    },
};

function buildTopProviderVariance(
    accountForecasts: DashboardFinanceAccountSummary[]
): ProviderVarianceSummary | null {
    const grouped = new Map<string, ProviderVarianceSummary>();

    for (const row of accountForecasts) {
        if (!hasRenderableForecast(row.forecast)) {
            continue;
        }

        const provider = (row.integration.provider || "unknown").toUpperCase();
        const current = grouped.get(provider) ?? {
            provider,
            actualMtdSpend: 0,
            forecastEomSpend: 0,
            varianceAmount: 0,
            riskCount: 0,
        };

        current.actualMtdSpend += row.forecast.actual_mtd_spend;
        current.forecastEomSpend += row.forecast.forecast_eom_spend;
        current.varianceAmount =
            (current.varianceAmount ?? 0) + (row.forecast.variance_amount ?? 0);

        if (
            row.forecast.status === "approaching_budget" ||
            row.forecast.status === "forecasted_over_budget" ||
            row.forecast.status === "over_budget"
        ) {
            current.riskCount += 1;
        }

        grouped.set(provider, current);
    }

    if (grouped.size === 0) {
        return null;
    }

    return Array.from(grouped.values()).sort((left, right) => {
        const rightVariance = right.varianceAmount ?? Number.NEGATIVE_INFINITY;
        const leftVariance = left.varianceAmount ?? Number.NEGATIVE_INFINITY;

        if (rightVariance !== leftVariance) {
            return rightVariance - leftVariance;
        }

        return right.forecastEomSpend - left.forecastEomSpend;
    })[0] ?? null;
}

export function DashboardFinanceSummary({
    portfolioForecast,
    portfolioBudgetEvent,
    accountForecasts,
    loadError,
}: DashboardFinanceSummaryProps) {
    const portfolioReady = hasRenderableForecast(portfolioForecast);
    const readyAccountCount = accountForecasts.filter(({ forecast }) =>
        hasRenderableForecast(forecast)
    ).length;
    const topProvider = buildTopProviderVariance(accountForecasts);
    const portfolioStatusKey =
        portfolioBudgetEvent?.current_status ||
        (portfolioReady ? portfolioForecast.status : "insufficient_history");
    const portfolioStatus = getStatusPresentation(portfolioStatusKey, statusMeta);
    const portfolioWaitingMessage =
        portfolioForecast?.message ||
        "Collecting enough current-period history to classify budget risk.";
    const portfolioBudgetMessage = portfolioBudgetEvent?.message || portfolioWaitingMessage;
    const portfolioBudgetSource = portfolioBudgetEvent
        ? getBudgetSourceLabel(portfolioBudgetEvent.budget_source, {
            portfolioSum: "Summed from active account budgets",
            integration: "Backed by account budgets",
            default: "No budget configured",
        })
        : portfolioReady
            ? getBudgetSourceLabel(portfolioForecast.budget_source, {
                portfolioSum: "Summed from active account budgets",
                integration: "Backed by account budgets",
                default: "No budget configured",
            })
            : portfolioWaitingMessage;

    return (
        <section className="mb-8 space-y-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                <div>
                    <p className="text-xs font-medium uppercase tracking-[0.24em] text-indigo-300/80">
                        Budget Copilot Summary
                    </p>
                    <h3 className="mt-2 text-xl font-semibold text-white">
                        Month-end spend risk at a glance
                    </h3>
                    <p className="mt-1 text-sm text-slate-400">
                        Deterministic finance signals pulled from the new Release 1 forecast contract.
                    </p>
                </div>

                <Link
                    href="/dashboard/forecast"
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
                >
                    Open Budget Copilot
                    <ArrowUpRight className="h-4 w-4" />
                </Link>
            </div>

            {loadError && (
                <div className="rounded-2xl border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">
                    Budget Copilot summary could not be loaded cleanly. The rest of the dashboard is still available.
                </div>
            )}

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className={forecastCardClassName}>
                    <div className="flex items-start justify-between">
                        <div>
                            <p className="text-sm text-slate-400">Forecasted month end</p>
                            <p className="mt-3 text-3xl font-semibold text-white">
                                {portfolioReady
                                    ? formatCurrency(portfolioForecast.forecast_eom_spend, portfolioForecast.currency)
                                    : "Awaiting history"}
                            </p>
                        </div>
                        <span className="rounded-xl bg-sky-400/15 p-3 text-sky-300">
                            <Wallet className="h-5 w-5" />
                        </span>
                    </div>
                    <p className="mt-4 text-xs text-slate-500">
                        {portfolioReady
                            ? `As of ${formatDateLabel(portfolioForecast.as_of)} · ${portfolioForecast.history_days_used} days used`
                            : "Need five normalized billing days before a trustworthy month-end projection appears here."}
                    </p>
                </div>

                <div className={budgetCardClassName}>
                    <div className="flex items-start justify-between">
                        <div>
                            <p className="text-sm text-slate-400">Budget status</p>
                            <p className="mt-3 text-2xl font-semibold text-white">
                                {portfolioStatus.label}
                            </p>
                        </div>
                        <span className="rounded-xl bg-violet-400/15 p-3 text-violet-300">
                            <CalendarClock className="h-5 w-5" />
                        </span>
                    </div>
                    <div className="mt-4 flex items-center gap-2">
                        <span
                            className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${portfolioStatus.className}`}
                        >
                            {portfolioStatus.label}
                        </span>
                    </div>
                    <p className="mt-4 text-xs text-slate-500">
                        {portfolioReady || portfolioBudgetEvent
                            ? portfolioBudgetSource
                            : portfolioBudgetMessage}
                    </p>
                </div>

                <div className={riskCardClassName}>
                    <div className="flex items-start justify-between">
                        <div>
                            <p className="text-sm text-slate-400">Overrun risk</p>
                            <p className="mt-3 text-3xl font-semibold text-white">
                                {portfolioReady
                                    ? formatSignedCurrency(
                                          portfolioForecast.variance_amount,
                                          portfolioForecast.currency
                                      )
                                    : `${readyAccountCount}/${accountForecasts.length}`}
                            </p>
                        </div>
                        <span className="rounded-xl bg-amber-400/15 p-3 text-amber-300">
                            <AlertTriangle className="h-5 w-5" />
                        </span>
                    </div>
                    <p className="mt-4 text-xs text-slate-500">
                        {portfolioReady
                            ? `${formatPercent(portfolioForecast.variance_pct)} versus the active budget ceiling.`
                            : `Forecast-ready accounts across the connected portfolio.`}
                    </p>
                </div>

                <div className={providerCardClassName}>
                    <div className="flex items-start justify-between">
                        <div>
                            <p className="text-sm text-slate-400">Top provider variance</p>
                            <p className="mt-3 text-2xl font-semibold text-white">
                                {topProvider ? topProvider.provider : "No provider signal yet"}
                            </p>
                        </div>
                        <span className="rounded-xl bg-emerald-400/15 p-3 text-emerald-300">
                            <Landmark className="h-5 w-5" />
                        </span>
                    </div>
                    <p className="mt-4 text-sm text-slate-300">
                        {topProvider
                            ? topProvider.varianceAmount && topProvider.varianceAmount > 0
                                ? `${formatSignedCurrency(topProvider.varianceAmount, portfolioForecast?.currency)} variance · ${topProvider.riskCount} account${topProvider.riskCount === 1 ? "" : "s"} at risk`
                                : `${formatCurrency(topProvider.forecastEomSpend, portfolioForecast?.currency)} forecasted EOM exposure`
                            : "Provider-level variance will appear once at least one account has enough usable history."}
                    </p>
                    <p className="mt-3 text-xs text-slate-500">
                        {topProvider
                            ? `${formatCurrency(topProvider.actualMtdSpend, portfolioForecast?.currency)} actual MTD across ${topProvider.provider}`
                            : "Use the Forecast page for per-account readiness and provider rollups."}
                    </p>
                </div>
            </div>
        </section>
    );
}
