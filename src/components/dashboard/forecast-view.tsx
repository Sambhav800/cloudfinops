"use client";

import Link from "next/link";
import { Card, Text, Title } from "@tremor/react";
import {
    AlertTriangle,
    ArrowUpRight,
    CalendarClock,
    Cloud,
    Landmark,
    TrendingUp,
    Wallet,
} from "lucide-react";
import {
    Area,
    AreaChart,
    Bar,
    CartesianGrid,
    Cell,
    ComposedChart,
    Legend,
    Line,
    ReferenceLine,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

import type {
    BackendIntegration,
    FinanceBudgetEvent,
    FinanceForecastResponse,
    FinanceSpendHistoryResponse,
} from "@/lib/api";
import {
    formatCompactCurrency,
    formatCurrency,
    formatDateLabel,
    formatPercent,
    formatSignedCurrency,
    getBudgetSourceLabel,
    getStatusPresentation,
    hasRenderableForecast,
    type StatusPresentation,
} from "@/components/dashboard/finance-formatters";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

export type ForecastAccountSummary = {
    integration: BackendIntegration;
    forecast: FinanceForecastResponse | null;
};

export type ForecastViewProps = {
    initialPortfolioForecast: FinanceForecastResponse | null;
    initialSpendHistory: FinanceSpendHistoryResponse | null;
    initialAccountForecasts: ForecastAccountSummary[];
    initialBudgetEvents: FinanceBudgetEvent[];
    loadError?: string | null;
};

type ProviderSummary = {
    provider: string;
    accounts: number;
    actualMtdSpend: number;
    forecastEomSpend: number;
    budgetLimit: number | null;
    riskCount: number;
};

type SpendHistoryPoint = FinanceSpendHistoryResponse["history"][number];

type OutlookChartPoint = {
    label: string;
    actual: number | null;
    projected: number | null;
};

type DailySpendChartPoint = {
    date: string;
    amount: number;
    average: number;
};

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
        label: "Insufficient history",
        className: "border-sky-400/30 bg-sky-400/10 text-sky-300",
    },
    awaiting_history: {
        label: "Awaiting history",
        className: "border-slate-400/20 bg-slate-400/10 text-slate-300",
    },
};

const budgetEventMeta: Record<FinanceBudgetEvent["event_type"], StatusPresentation> = {
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
    recovered: {
        label: "Recovered",
        className: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    },
};

const panelClassName = "rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-xl ring-0 shadow-2xl shadow-black/20";
const insetPanelClassName = "rounded-2xl border border-white/10 bg-slate-900 p-4";
const emptyPanelClassName = "rounded-2xl border border-dashed border-white/10 bg-white/[0.03] px-5 py-8";
const CHART_STYLE = {
    gridColor: "rgba(255,255,255,0.06)",
    tickColor: "#64748b",
    tooltipBg: "#0f172a",
    tooltipBorder: "rgba(255,255,255,0.1)",
    fontSize: 11,
} as const;
const CHART_COLORS = {
    actual: "#38bdf8",
    projected: "#8b5cf6",
    budget: "#10b981",
    daily: "#6366f1",
    dailyAccent: "#7c3aed",
    average: "#10b981",
} as const;

function formatEventDate(value: string) {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }

    return parsed.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}
function hasMeaningfulSpendHistory(history: FinanceSpendHistoryResponse | null | undefined) {
    if (!history) {
        return false;
    }

    return history.history.length >= 5 && history.history.some((point) => point.amount > 0);
}

function sortSpendHistoryPoints(points: SpendHistoryPoint[]) {
    return points
        .slice()
        .sort(
            (left, right) =>
                new Date(left.spend_date).getTime() - new Date(right.spend_date).getTime()
        );
}

function buildOutlookChartData(
    history: SpendHistoryPoint[],
    forecast: FinanceForecastResponse | null
): OutlookChartPoint[] {
    if (!forecast || history.length === 0) {
        return [];
    }

    const actualPoints: OutlookChartPoint[] = [];
    let cumulativeSpend = 0;

    for (let index = 0; index < history.length; index += 1) {
        const point = history[index];
        cumulativeSpend += point.amount;
        actualPoints.push({
            label: formatDateLabel(point.spend_date),
            actual: cumulativeSpend,
            projected: index === history.length - 1 ? cumulativeSpend : null,
        });
    }

    const lastPoint = history[history.length - 1];
    const lastDate = new Date(lastPoint.spend_date);
    if (Number.isNaN(lastDate.getTime())) {
        return actualPoints;
    }

    const endOfMonth = new Date(lastDate.getFullYear(), lastDate.getMonth() + 1, 0);
    const remainingDays = Math.max(endOfMonth.getDate() - lastDate.getDate(), 0);
    if (remainingDays === 0) {
        return actualPoints;
    }

    const futurePoints: OutlookChartPoint[] = [];
    for (let step = 1; step <= remainingDays; step += 1) {
        const nextDate = new Date(lastDate);
        nextDate.setDate(lastDate.getDate() + step);

        futurePoints.push({
            label: nextDate.toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
            }),
            actual: null,
            projected:
                cumulativeSpend +
                ((forecast.forecast_eom_spend - cumulativeSpend) * step) / remainingDays,
        });
    }

    return [...actualPoints, ...futurePoints];
}

function buildDailySpendChartData(history: SpendHistoryPoint[]) {
    const recentPoints = history.slice(-14);
    return recentPoints.map((point, index, points): DailySpendChartPoint => {
        const rollingWindow = points.slice(Math.max(0, index - 2), index + 1);
        const rollingAverage =
            rollingWindow.reduce((sum, current) => sum + current.amount, 0) /
            rollingWindow.length;

        return {
            date: formatDateLabel(point.spend_date),
            amount: point.amount,
            average: rollingAverage,
        };
    });
}

function buildProviderSummaries(rows: ForecastAccountSummary[]): ProviderSummary[] {
    const grouped = new Map<string, ProviderSummary>();

    for (const row of rows) {
        const forecast = row.forecast;
        if (!hasRenderableForecast(forecast)) {
            continue;
        }

        const provider = (row.integration.provider || "unknown").toUpperCase();
        const current = grouped.get(provider) ?? {
            provider,
            accounts: 0,
            actualMtdSpend: 0,
            forecastEomSpend: 0,
            budgetLimit: null,
            riskCount: 0,
        };

        current.accounts += 1;
        current.actualMtdSpend += forecast.actual_mtd_spend;
        current.forecastEomSpend += forecast.forecast_eom_spend;
        current.budgetLimit = forecast.budget_limit
            ? (current.budgetLimit ?? 0) + forecast.budget_limit
            : current.budgetLimit;

        if (forecast.status === "approaching_budget" || forecast.status === "forecasted_over_budget" || forecast.status === "over_budget") {
            current.riskCount += 1;
        }

        grouped.set(provider, current);
    }

    return Array.from(grouped.values()).sort((left, right) => right.forecastEomSpend - left.forecastEomSpend);
}

export function ForecastView({
    initialPortfolioForecast,
    initialSpendHistory,
    initialAccountForecasts,
    initialBudgetEvents,
    loadError,
}: ForecastViewProps) {
    const portfolioForecast = initialPortfolioForecast;
    const chartCurrency = portfolioForecast?.currency || initialSpendHistory?.currency || "USD";
    const historyPoints = sortSpendHistoryPoints(initialSpendHistory?.history ?? []);
    const hasMeaningfulPortfolioHistory = hasMeaningfulSpendHistory(initialSpendHistory);
    const shouldShowPortfolioData = Boolean(portfolioForecast) && hasRenderableForecast(portfolioForecast) && hasMeaningfulPortfolioHistory;
    const portfolioData = shouldShowPortfolioData ? portfolioForecast : null;
    const outlookChartData = buildOutlookChartData(historyPoints, portfolioData);
    const dailySpendChartData = buildDailySpendChartData(historyPoints);
    const sortedAccountForecasts = initialAccountForecasts
        .slice()
        .sort((left, right) => {
            const leftVariance = left.forecast?.variance_amount ?? Number.NEGATIVE_INFINITY;
            const rightVariance = right.forecast?.variance_amount ?? Number.NEGATIVE_INFINITY;
            return rightVariance - leftVariance;
        });
    const providerSummaries = buildProviderSummaries(sortedAccountForecasts);
    const portfolioStatus = getStatusPresentation(portfolioForecast?.status ?? "no_budget_configured", statusMeta);
    const portfolioProgress = portfolioForecast?.budget_limit
        ? Math.max(0, Math.round((portfolioForecast.forecast_eom_spend / portfolioForecast.budget_limit) * 100))
        : null;
    const projectedRunway = portfolioData
        ? Math.max(portfolioData.forecast_eom_spend - portfolioData.actual_mtd_spend, 0)
        : 0;
    const budgetGap = portfolioData?.budget_limit
        ? portfolioData.budget_limit - portfolioData.forecast_eom_spend
        : null;
    const averageDailySpend = dailySpendChartData.length > 0
        ? dailySpendChartData.reduce((sum, point) => sum + point.amount, 0) / dailySpendChartData.length
        : 0;
    const peakDailySpend = dailySpendChartData.length > 0
        ? dailySpendChartData.reduce(
            (peak, point) => (point.amount > peak.amount ? point : peak),
            dailySpendChartData[0]
        )
        : null;
    const readyAccountCount = sortedAccountForecasts.filter(({ forecast }) => hasRenderableForecast(forecast)).length;
    const awaitingHistoryCount = Math.max(sortedAccountForecasts.length - readyAccountCount, 0);
    const portfolioEmptyMessage = portfolioForecast?.message
        || "CloudFinOps needs at least five normalized daily spend records before Budget Copilot can project month-end risk confidently.";

    return (
        <div className="p-6 space-y-6">
            {loadError && (
                <div className="rounded-2xl border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">
                    Forecast data could not be loaded cleanly. The view is showing the data that was available.
                </div>
            )}

            {!portfolioData ? (
                <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.25fr_0.75fr]">
                    <Card className={panelClassName}>
                        <div className="flex h-full flex-col gap-6 lg:justify-between">
                            <div className="space-y-4">
                                <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-400/10 text-sky-300">
                                    <TrendingUp className="h-5 w-5" />
                                </div>
                                <div className="space-y-2">
                                    <Title className="text-white">Budget Copilot is waiting for spend history</Title>
                                    <Text className="max-w-2xl text-slate-400">
                                        {portfolioEmptyMessage}
                                    </Text>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                                <div className={insetPanelClassName}>
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Active accounts</p>
                                    <p className="mt-2 text-2xl font-semibold text-white">{sortedAccountForecasts.length}</p>
                                    <p className="mt-2 text-sm text-slate-400">Connected accounts included in the portfolio.</p>
                                </div>
                                <div className={insetPanelClassName}>
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Ready for forecast</p>
                                    <p className="mt-2 text-2xl font-semibold text-white">{readyAccountCount}</p>
                                    <p className="mt-2 text-sm text-slate-400">Accounts with enough normalized billing history.</p>
                                </div>
                                <div className={insetPanelClassName}>
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">History collected</p>
                                    <p className="mt-2 text-2xl font-semibold text-white">{portfolioForecast?.history_days_used ?? historyPoints.length}</p>
                                    <p className="mt-2 text-sm text-slate-400">Normalized daily spend points currently available.</p>
                                </div>
                            </div>
                        </div>
                    </Card>

                    <Card className={panelClassName}>
                        <div className="space-y-5">
                            <div>
                                <Title className="text-white">What happens next</Title>
                                <Text className="text-slate-400">
                                    This route unlocks once CloudFinOps has enough stable billing coverage to avoid misleading month-end projections.
                                </Text>
                            </div>

                            <div className="space-y-3">
                                <div className={insetPanelClassName}>
                                    <p className="text-sm font-medium text-white">Minimum forecast threshold</p>
                                    <p className="mt-2 text-sm text-slate-400">
                                        Five normalized daily billing records with non-zero spend across the connected portfolio.
                                    </p>
                                </div>
                                <div className={insetPanelClassName}>
                                    <p className="text-sm font-medium text-white">Accounts still waiting</p>
                                    <p className="mt-2 text-sm text-slate-400">
                                        {awaitingHistoryCount > 0
                                            ? `${awaitingHistoryCount} account${awaitingHistoryCount === 1 ? "" : "s"} still need more history before per-account forecasting is trustworthy.`
                                            : "All connected accounts are ready once the portfolio history threshold is met."}
                                    </p>
                                </div>
                            </div>

                            <Link
                                href="/dashboard/settings"
                                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-slate-800 px-4 py-2 text-sm font-medium text-slate-300 transition hover:bg-slate-700 hover:text-white"
                            >
                                Review account setup
                                <ArrowUpRight className="h-4 w-4" />
                            </Link>
                        </div>
                    </Card>
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <Card className={panelClassName}>
                            <div className="flex items-start justify-between">
                                <div>
                                    <Text className="text-slate-400">Actual MTD spend</Text>
                                    <p className="mt-3 text-3xl font-semibold text-white">
                                        {formatCurrency(portfolioData.actual_mtd_spend, chartCurrency)}
                                    </p>
                                </div>
                                <span className="rounded-xl bg-sky-400/10 p-3 text-sky-300">
                                    <Wallet className="h-5 w-5" />
                                </span>
                            </div>
                            <p className="mt-4 text-xs text-slate-500">
                                {portfolioData.history_days_used} daily records used for this projection.
                            </p>
                        </Card>

                        <Card className={panelClassName}>
                            <div className="flex items-start justify-between">
                                <div>
                                    <Text className="text-slate-400">Forecasted month end</Text>
                                    <p className="mt-3 text-3xl font-semibold text-white">
                                        {formatCurrency(portfolioData.forecast_eom_spend, chartCurrency)}
                                    </p>
                                </div>
                                <span className="rounded-xl bg-violet-400/10 p-3 text-violet-300">
                                    <CalendarClock className="h-5 w-5" />
                                </span>
                            </div>
                            <p className="mt-4 text-xs text-slate-500">
                                Method: {portfolioData.forecast_method.replace(/_/g, " ")}
                                {portfolioData.forecast_stable ? " · stable" : " · provisional"}
                            </p>
                        </Card>

                        <Card className={panelClassName}>
                            <div className="flex items-start justify-between">
                                <div>
                                    <Text className="text-slate-400">Budget ceiling</Text>
                                    <p className="mt-3 text-3xl font-semibold text-white">
                                        {formatCurrency(portfolioData.budget_limit, chartCurrency)}
                                    </p>
                                </div>
                                <span className="rounded-xl bg-emerald-400/10 p-3 text-emerald-300">
                                    <Landmark className="h-5 w-5" />
                                </span>
                            </div>
                            <p className="mt-4 text-xs text-slate-500">
                                Source: {getBudgetSourceLabel(portfolioData.budget_source)}
                            </p>
                        </Card>

                        <Card className={panelClassName}>
                            <div className="flex items-start justify-between">
                                <div>
                                    <Text className="text-slate-400">Forecast variance</Text>
                                    <p className="mt-3 text-3xl font-semibold text-white">
                                        {formatSignedCurrency(portfolioData.variance_amount, chartCurrency)}
                                    </p>
                                </div>
                                <span className="rounded-xl bg-amber-400/10 p-3 text-amber-300">
                                    <AlertTriangle className="h-5 w-5" />
                                </span>
                            </div>
                            <p className="mt-4 text-xs text-slate-500">
                                {formatPercent(portfolioData.variance_pct)} versus the configured budget.
                            </p>
                        </Card>
                    </div>

                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.35fr_0.9fr]">
                        <Card className={panelClassName}>
                            <div className="mb-5 flex items-start justify-between gap-4">
                                <div>
                                    <Title className="text-white">Budget Copilot outlook</Title>
                                    <Text className="text-slate-400">
                                        Actual month-to-date spend against forecasted month-end exposure.
                                    </Text>
                                </div>
                                <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium ${portfolioStatus.className}`}>
                                    {portfolioStatus.label}
                                </span>
                            </div>

                            <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
                                <div className={insetPanelClassName}>
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Recorded MTD</p>
                                    <p className="mt-2 text-lg font-semibold text-white">
                                        {formatCurrency(portfolioData.actual_mtd_spend, chartCurrency)}
                                    </p>
                                </div>
                                <div className={insetPanelClassName}>
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Projected runway</p>
                                    <p className="mt-2 text-lg font-semibold text-indigo-300">
                                        {formatCurrency(projectedRunway, chartCurrency)}
                                    </p>
                                </div>
                                <div className={insetPanelClassName}>
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                                        {budgetGap !== null && budgetGap < 0 ? "Projected overrun" : "Budget headroom"}
                                    </p>
                                    <p className={`mt-2 text-lg font-semibold ${budgetGap !== null && budgetGap < 0 ? "text-rose-300" : "text-emerald-300"}`}>
                                        {budgetGap !== null
                                            ? formatCurrency(Math.abs(budgetGap), chartCurrency)
                                            : "Not set"}
                                    </p>
                                </div>
                            </div>

                            {outlookChartData.length > 0 ? (
                                <>
                                    <ResponsiveContainer width="100%" height={320}>
                                        <AreaChart
                                            data={outlookChartData}
                                            margin={{ top: 8, right: 12, left: 0, bottom: 4 }}
                                        >
                                            <defs>
                                                <linearGradient
                                                    id="forecastActualGradient"
                                                    x1="0"
                                                    y1="0"
                                                    x2="0"
                                                    y2="1"
                                                >
                                                    <stop
                                                        offset="5%"
                                                        stopColor={CHART_COLORS.actual}
                                                        stopOpacity={0.35}
                                                    />
                                                    <stop
                                                        offset="95%"
                                                        stopColor={CHART_COLORS.actual}
                                                        stopOpacity={0.04}
                                                    />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid
                                                strokeDasharray="3 3"
                                                stroke={CHART_STYLE.gridColor}
                                                vertical={false}
                                            />
                                            <XAxis
                                                dataKey="label"
                                                tick={{
                                                    fill: CHART_STYLE.tickColor,
                                                    fontSize: CHART_STYLE.fontSize,
                                                }}
                                                axisLine={false}
                                                tickLine={false}
                                                interval="preserveStartEnd"
                                            />
                                            <YAxis
                                                tick={{
                                                    fill: CHART_STYLE.tickColor,
                                                    fontSize: CHART_STYLE.fontSize,
                                                }}
                                                axisLine={false}
                                                tickLine={false}
                                                width={68}
                                                tickFormatter={(value: number) => formatCompactCurrency(value, chartCurrency)}
                                            />
                                            <Tooltip
                                                contentStyle={{
                                                    backgroundColor: CHART_STYLE.tooltipBg,
                                                    border: `1px solid ${CHART_STYLE.tooltipBorder}`,
                                                    borderRadius: "12px",
                                                    fontSize: "12px",
                                                }}
                                                labelStyle={{ color: "#94a3b8" }}
                                                itemStyle={{ color: "#fff" }}
                                                formatter={(value: number, name: string) => [
                                                    formatCurrency(Number(value), chartCurrency),
                                                    name,
                                                ]}
                                            />
                                            <Legend
                                                wrapperStyle={{
                                                    color: "#94a3b8",
                                                    fontSize: "11px",
                                                    paddingTop: "12px",
                                                }}
                                            />
                                            {portfolioData.budget_limit ? (
                                                <ReferenceLine
                                                    y={portfolioData.budget_limit}
                                                    stroke={CHART_COLORS.budget}
                                                    strokeDasharray="5 5"
                                                    ifOverflow="extendDomain"
                                                />
                                            ) : null}
                                            <Area
                                                type="monotone"
                                                dataKey="actual"
                                                name="Actual MTD"
                                                stroke={CHART_COLORS.actual}
                                                strokeWidth={2.5}
                                                fill="url(#forecastActualGradient)"
                                                connectNulls={false}
                                                activeDot={{ r: 4, fill: CHART_COLORS.actual }}
                                            />
                                            <Line
                                                type="monotone"
                                                dataKey="projected"
                                                name="Projected EOM"
                                                stroke={CHART_COLORS.projected}
                                                strokeWidth={2.5}
                                                strokeDasharray="6 4"
                                                dot={false}
                                                connectNulls
                                                activeDot={{ r: 4, fill: CHART_COLORS.projected }}
                                            />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </>
                            ) : (
                                <div className={`${emptyPanelClassName} text-sm text-slate-400`}>
                                    Budget Copilot will render an outlook chart once current-period spend history is available.
                                </div>
                            )}
                        </Card>

                        <Card className={panelClassName}>
                            <div className="space-y-5">
                                <div>
                                    <Title className="text-white">Portfolio budget status</Title>
                                    <Text className="text-slate-400">
                                        As of {formatDateLabel(portfolioData.as_of)}
                                    </Text>
                                </div>

                                <div className={insetPanelClassName}>
                                    <div className="flex items-center justify-between gap-3">
                                        <p className="text-sm font-medium text-white">Month-end budget utilization</p>
                                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${portfolioStatus.className}`}>
                                            {portfolioStatus.label}
                                        </span>
                                    </div>
                                    <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-800">
                                        <div
                                            className={`h-full rounded-full ${portfolioData.status === "forecasted_over_budget" || portfolioData.status === "over_budget"
                                                ? "bg-rose-400"
                                                : portfolioData.status === "approaching_budget"
                                                    ? "bg-amber-400"
                                                    : "bg-emerald-400"
                                                }`}
                                            style={{ width: `${Math.min(portfolioProgress ?? 0, 100)}%` }}
                                        />
                                    </div>
                                    <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                                        <span>Forecast utilization</span>
                                        <span>{portfolioProgress !== null ? `${portfolioProgress}%` : "No budget set"}</span>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                    <div className={insetPanelClassName}>
                                        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Trend</p>
                                        <p className="mt-2 text-lg font-semibold text-white capitalize">
                                            {portfolioData.trend.replace(/_/g, " ")}
                                        </p>
                                    </div>
                                    <div className={insetPanelClassName}>
                                        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Budget source</p>
                                        <p className="mt-2 text-lg font-semibold text-white">
                                            {getBudgetSourceLabel(portfolioData.budget_source)}
                                        </p>
                                    </div>
                                </div>

                                <div className={`${insetPanelClassName} text-sm text-slate-300`}>
                                    {portfolioData.message}
                                </div>
                            </div>
                        </Card>
                    </div>

                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.15fr_1fr]">
                        <Card className={panelClassName}>
                            <div className="mb-5">
                                <Title className="text-white">Recent daily spend</Title>
                                <Text className="text-slate-400">
                                    Last {dailySpendChartData.length || 0} normalized days from the portfolio spend history.
                                </Text>
                            </div>

                            {dailySpendChartData.length > 0 ? (
                                <>
                                    <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
                                        <div className={insetPanelClassName}>
                                            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">14-day average</p>
                                            <p className="mt-2 text-lg font-semibold text-white">
                                                {formatCurrency(averageDailySpend, chartCurrency)}
                                            </p>
                                        </div>
                                        <div className={insetPanelClassName}>
                                            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Peak recorded day</p>
                                            <p className="mt-2 text-lg font-semibold text-white">
                                                {peakDailySpend ? formatCurrency(peakDailySpend.amount, chartCurrency) : "Not available"}
                                            </p>
                                        </div>
                                        <div className={insetPanelClassName}>
                                            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Trend line</p>
                                            <p className="mt-2 text-lg font-semibold text-emerald-300">3-day average</p>
                                        </div>
                                    </div>

                                    <ResponsiveContainer width="100%" height={300}>
                                        <ComposedChart
                                            data={dailySpendChartData}
                                            margin={{ top: 8, right: 12, left: 0, bottom: 4 }}
                                        >
                                            <CartesianGrid
                                                strokeDasharray="3 3"
                                                stroke={CHART_STYLE.gridColor}
                                                vertical={false}
                                            />
                                            <XAxis
                                                dataKey="date"
                                                tick={{
                                                    fill: CHART_STYLE.tickColor,
                                                    fontSize: CHART_STYLE.fontSize,
                                                }}
                                                axisLine={false}
                                                tickLine={false}
                                                interval="preserveStartEnd"
                                            />
                                            <YAxis
                                                tick={{
                                                    fill: CHART_STYLE.tickColor,
                                                    fontSize: CHART_STYLE.fontSize,
                                                }}
                                                axisLine={false}
                                                tickLine={false}
                                                width={68}
                                                tickFormatter={(value: number) => formatCompactCurrency(value, chartCurrency)}
                                            />
                                            <Tooltip
                                                contentStyle={{
                                                    backgroundColor: CHART_STYLE.tooltipBg,
                                                    border: `1px solid ${CHART_STYLE.tooltipBorder}`,
                                                    borderRadius: "12px",
                                                    fontSize: "12px",
                                                }}
                                                labelStyle={{ color: "#94a3b8" }}
                                                itemStyle={{ color: "#fff" }}
                                                formatter={(value: number, name: string) => [
                                                    formatCurrency(Number(value), chartCurrency),
                                                    name,
                                                ]}
                                                cursor={{ fill: "rgba(255,255,255,0.04)" }}
                                            />
                                            <Legend
                                                wrapperStyle={{
                                                    color: "#94a3b8",
                                                    fontSize: "11px",
                                                    paddingTop: "12px",
                                                }}
                                            />
                                            <Bar
                                                dataKey="amount"
                                                name="Daily spend"
                                                radius={[6, 6, 0, 0]}
                                            >
                                                {dailySpendChartData.map(
                                                    (_point: DailySpendChartPoint, index: number) => (
                                                        <Cell
                                                            key={`daily-spend-bar-${index}`}
                                                            fill={
                                                                index === dailySpendChartData.length - 1
                                                                    ? CHART_COLORS.dailyAccent
                                                                    : CHART_COLORS.daily
                                                            }
                                                        />
                                                    )
                                                )}
                                            </Bar>
                                            <Line
                                                type="monotone"
                                                dataKey="average"
                                                name="3-day average"
                                                stroke={CHART_COLORS.average}
                                                strokeWidth={2.5}
                                                dot={false}
                                                activeDot={{ r: 4, fill: CHART_COLORS.average }}
                                            />
                                        </ComposedChart>
                                    </ResponsiveContainer>
                                </>
                            ) : (
                                <div className={`${emptyPanelClassName} text-sm text-slate-400`}>
                                    Spend history will appear here once the connected accounts have daily billing coverage.
                                </div>
                            )}
                        </Card>

                        <Card className={panelClassName}>
                            <div className="mb-5 flex items-start justify-between gap-3">
                                <div>
                                    <Title className="text-white">Provider outlook</Title>
                                    <Text className="text-slate-400">
                                        Forecasted month-end exposure by provider.
                                    </Text>
                                </div>
                                <span className="rounded-full border border-white/10 bg-slate-800 px-3 py-1 text-xs text-slate-300">
                                    {providerSummaries.length} providers
                                </span>
                            </div>

                            <div className="space-y-3">
                                {providerSummaries.length === 0 ? (
                                    <div className={`${emptyPanelClassName} text-sm text-slate-400`}>
                                        Provider rollups will appear once active integrations return finance data.
                                    </div>
                                ) : (
                                    providerSummaries.map((summary) => (
                                        <div key={summary.provider} className={insetPanelClassName}>
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="flex items-center gap-3">
                                                    <span className="rounded-xl bg-indigo-500/10 p-2 text-indigo-400">
                                                        <Cloud className="h-4 w-4" />
                                                    </span>
                                                    <div>
                                                        <p className="font-medium text-white">{summary.provider}</p>
                                                        <p className="text-xs text-slate-500">{summary.accounts} active accounts</p>
                                                    </div>
                                                </div>
                                                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${summary.riskCount > 0 ? "bg-amber-400/10 text-amber-300" : "bg-emerald-400/10 text-emerald-300"}`}>
                                                    {summary.riskCount > 0 ? `${summary.riskCount} at risk` : "Healthy"}
                                                </span>
                                            </div>

                                            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                                                <div>
                                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Actual MTD</p>
                                                    <p className="mt-1 text-sm font-semibold text-white">
                                                        {formatCurrency(summary.actualMtdSpend, chartCurrency)}
                                                    </p>
                                                </div>
                                                <div>
                                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Forecast EOM</p>
                                                    <p className="mt-1 text-sm font-semibold text-white">
                                                        {formatCurrency(summary.forecastEomSpend, chartCurrency)}
                                                    </p>
                                                </div>
                                                <div>
                                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Budget</p>
                                                    <p className="mt-1 text-sm font-semibold text-white">
                                                        {formatCurrency(summary.budgetLimit, chartCurrency)}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </Card>
                    </div>

                    <Card className={panelClassName}>
                        <div className="mb-5 flex items-start justify-between gap-3">
                            <div>
                                <Title className="text-white">Account budget table</Title>
                                <Text className="text-slate-400">
                                    Per-account forecast status for connected integrations.
                                </Text>
                            </div>
                            <Link
                                href="/dashboard/settings"
                                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-slate-800 px-3 py-2 text-xs font-medium text-slate-300 transition hover:bg-slate-700 hover:text-white"
                            >
                                Manage budgets
                                <ArrowUpRight className="h-3.5 w-3.5" />
                            </Link>
                        </div>

                        {sortedAccountForecasts.length === 0 ? (
                            <div className={`${emptyPanelClassName} text-sm text-slate-400`}>
                                No active integrations are available for per-account budget tracking yet.
                            </div>
                        ) : (
                            <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/40">
                            <Table>
                                <TableHeader>
                                    <TableRow className="border-b border-white/5 bg-white/5 hover:bg-transparent">
                                        <TableHead className="text-slate-400">Account</TableHead>
                                        <TableHead className="text-slate-400">Provider</TableHead>
                                        <TableHead className="text-slate-400">Actual MTD</TableHead>
                                        <TableHead className="text-slate-400">Forecast EOM</TableHead>
                                        <TableHead className="text-slate-400">Budget</TableHead>
                                        <TableHead className="text-slate-400">Variance</TableHead>
                                        <TableHead className="text-slate-400">Status</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {sortedAccountForecasts.map(({ integration, forecast }) => {
                                        const hasAccountForecast = hasRenderableForecast(forecast);
                                        const forecastStatus = getStatusPresentation(
                                            forecast
                                                ? hasAccountForecast
                                                    ? forecast.status
                                                    : "awaiting_history"
                                                : "awaiting_history",
                                            statusMeta,
                                        );

                                        return (
                                            <TableRow key={integration.id} className="border-b border-white/5 hover:bg-white/[0.03]">
                                                <TableCell>
                                                    <div>
                                                        <p className="font-medium text-white">{integration.name}</p>
                                                        <p className="text-xs text-slate-500">
                                                            {integration.account_identifier || "Connected account"}
                                                        </p>
                                                    </div>
                                                </TableCell>
                                                <TableCell className="font-medium uppercase text-slate-300">
                                                    {integration.provider}
                                                </TableCell>
                                                <TableCell className="text-slate-200">
                                                    {forecast && hasAccountForecast
                                                        ? formatCurrency(forecast.actual_mtd_spend, forecast.currency)
                                                        : "Awaiting history"}
                                                </TableCell>
                                                <TableCell className="text-slate-200">
                                                    {forecast && hasAccountForecast
                                                        ? formatCurrency(forecast.forecast_eom_spend, forecast.currency)
                                                        : "Awaiting history"}
                                                </TableCell>
                                                <TableCell className="text-slate-200">
                                                    {forecast ? formatCurrency(forecast.budget_limit, forecast.currency) : "Unavailable"}
                                                </TableCell>
                                                <TableCell className={forecast && hasAccountForecast && (forecast.variance_amount ?? 0) > 0 ? "text-rose-300" : "text-slate-200"}>
                                                    {forecast && hasAccountForecast
                                                        ? formatSignedCurrency(forecast.variance_amount, forecast.currency)
                                                        : "Awaiting history"}
                                                </TableCell>
                                                <TableCell>
                                                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${forecastStatus.className}`}>
                                                        {forecastStatus.label}
                                                    </span>
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                            </div>
                        )}
                    </Card>

                    <Card className={panelClassName}>
                        <div className="mb-5">
                            <Title className="text-white">Top month-end drivers</Title>
                            <Text className="text-slate-400">
                                Largest backend-derived account contributors to the remaining month-end spend projection.
                            </Text>
                        </div>

                        {portfolioData.drivers.length === 0 ? (
                            <div className={`${emptyPanelClassName} text-sm text-slate-400`}>
                                Driver breakdown is not available yet for this portfolio. The forecast remains deterministic, and provider/account rollups above still show where the projected spend is concentrated.
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                                {portfolioData.drivers.map((driver) => (
                                    <div key={`${driver.dimension}-${driver.key}`} className={insetPanelClassName}>
                                        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{driver.dimension}</p>
                                        <p className="mt-2 font-medium text-white">{driver.key}</p>
                                        <p className="mt-3 flex items-center gap-2 text-sm text-rose-300">
                                            <ArrowUpRight className="h-4 w-4" />
                                            {formatCurrency(driver.delta_amount, chartCurrency)}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        )}
                    </Card>

                    <Card className={panelClassName}>
                        <div className="mb-5 flex items-start justify-between gap-4">
                            <div>
                                <Title className="text-white">Recent budget activity</Title>
                                <Text className="text-slate-400">
                                    Durable budget events created when portfolio or account budget status changes.
                                </Text>
                            </div>
                            <div className="rounded-full border border-white/10 bg-slate-800 px-3 py-1 text-xs font-medium text-slate-300">
                                {initialBudgetEvents.length} recent event{initialBudgetEvents.length === 1 ? "" : "s"}
                            </div>
                        </div>

                        {initialBudgetEvents.length === 0 ? (
                            <div className={`${emptyPanelClassName} text-sm text-slate-400`}>
                                No budget status changes have been recorded yet. As soon as CloudFinOps sees a portfolio or account move toward risk, over budget, or recover back on track, it will appear here.
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {initialBudgetEvents.map((event) => {
                                    const meta = budgetEventMeta[event.event_type];
                                    return (
                                        <div
                                            key={event.id}
                                            className="rounded-2xl border border-white/10 bg-slate-900 p-4"
                                        >
                                            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                                <div className="space-y-2">
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${meta.className}`}>
                                                            {meta.label}
                                                        </span>
                                                        <span className="rounded-full border border-white/10 bg-slate-800 px-2.5 py-1 text-xs text-slate-300">
                                                            {event.scope === "portfolio" ? "Portfolio" : "Account"}
                                                        </span>
                                                    </div>
                                                    <p className="font-medium text-white">{event.title}</p>
                                                    <p className="text-sm text-slate-400">{event.message}</p>
                                                </div>
                                                <div className="shrink-0 text-left text-xs text-slate-500 md:text-right">
                                                    <p>{formatEventDate(event.created_at)}</p>
                                                    <p className="mt-2 text-slate-300">
                                                        Forecast {formatCurrency(event.forecast_eom_spend, event.currency)}
                                                    </p>
                                                    <p>
                                                        Budget {formatCurrency(event.budget_limit, event.currency)}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </Card>
                </>
            )}
        </div>
    );
}
