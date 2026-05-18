import type { FinanceForecastResponse } from "@/lib/api";
import { DISPLAY_CURRENCY, formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";

export type StatusPresentation = {
    label: string;
    className: string;
};

export function formatCurrency(value: number | null | undefined, currency = DISPLAY_CURRENCY) {
    if (value === null || value === undefined) {
        return "Not set";
    }

    return formatInrCurrency(toDisplayInrAmount(value, currency));
}

export function formatCompactCurrency(value: number | null | undefined, currency = DISPLAY_CURRENCY) {
    if (value === null || value === undefined) {
        return "Not set";
    }

    return formatInrCurrency(toDisplayInrAmount(value, currency), {
        notation: "compact",
        minimumFractionDigits: 0,
        maximumFractionDigits: 1,
    });
}

export function formatSignedCurrency(value: number | null | undefined, currency = DISPLAY_CURRENCY) {
    if (value === null || value === undefined) {
        return "No variance";
    }

    const absolute = formatCurrency(Math.abs(value), currency);
    if (value === 0) {
        return absolute;
    }

    return value > 0 ? `+${absolute}` : `-${absolute}`;
}

export function formatPercent(value: number | null | undefined) {
    if (value === null || value === undefined) {
        return "No variance";
    }

    const rounded = Math.round(value * 10) / 10;
    return `${rounded > 0 ? "+" : ""}${rounded}%`;
}

export function formatDateLabel(value: string) {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }

    return parsed.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
    });
}

export function getStatusPresentation(
    status: string,
    statusMeta: Record<string, StatusPresentation>,
): StatusPresentation {
    return statusMeta[status] ?? {
        label: status.replace(/_/g, " "),
        className: "border-slate-400/20 bg-slate-400/10 text-slate-200",
    };
}

export function getBudgetSourceLabel(
    source: string,
    labels: {
        portfolioSum: string;
        integration: string;
        default: string;
    } = {
        portfolioSum: "Sum of active account budgets",
        integration: "Account budget",
        default: "No budget configured",
    },
) {
    if (source === "portfolio_sum") {
        return labels.portfolioSum;
    }

    if (source === "integration") {
        return labels.integration;
    }

    return labels.default;
}

export function hasRenderableForecast(
    forecast: FinanceForecastResponse | null | undefined,
): forecast is FinanceForecastResponse {
    return Boolean(
        forecast &&
        forecast.history_days_used >= 5 &&
        forecast.status !== "insufficient_history",
    );
}
