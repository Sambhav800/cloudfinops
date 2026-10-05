import type { CommitmentRecommendationResponse } from "../api";

export const NOT_MEASURED = "Not measured";

export function commitmentSupportLabel(provider: string): string {
    if (provider === "aws") return "AWS inventory and Compute Savings Plan purchase estimates";
    if (provider === "gcp") return "GCP inventory only; purchase estimates unsupported";
    if (provider === "azure") return "Azure commitment inventory and purchase estimates unsupported";
    return "Commitment support unavailable";
}

export function commitmentSyncLabel(status: string): string {
    const labels: Record<string, string> = {
        ready: "Synced", no_commitments: "Synced: no commitments", not_synced: "Not synced",
        error: "Sync failed", unavailable: "Unavailable", unsupported: "Unsupported",
        pending: "Sync pending", syncing: "Sync in progress", demo: "Demo snapshot",
    };
    return labels[status] ?? status.replaceAll("_", " ");
}

export function formatCommitmentMoney(value: number | null | undefined, currency: string | null | undefined): string {
    if (typeof value !== "number" || !Number.isFinite(value) || !currency) return NOT_MEASURED;
    try {
        return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency,
            currencyDisplay: "code",
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(value);
    } catch {
        return NOT_MEASURED;
    }
}

export function formatCommitmentPercent(value: number | null | undefined): string {
    return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(1)}%` : NOT_MEASURED;
}

export function formatCommitmentDate(value: string | null | undefined, includeTime = false): string {
    if (!value) return NOT_MEASURED;
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return NOT_MEASURED;
    return new Intl.DateTimeFormat("en-US", {
        year: "numeric", month: "short", day: "numeric", timeZone: "UTC",
        ...(includeTime ? { hour: "2-digit", minute: "2-digit", timeZoneName: "short" } as const : {}),
    }).format(date);
}

export function formatSavingsPeriod(start: string | null | undefined, end: string | null | undefined): string {
    const from = formatCommitmentDate(start);
    const to = formatCommitmentDate(end);
    return from === NOT_MEASURED || to === NOT_MEASURED ? "Savings period not measured" : `${from} to ${to}`;
}

export const RECOMMENDATION_STATUS_LABELS: Record<CommitmentRecommendationResponse["status"], string> = {
    ready: "Provider alternatives available",
    not_synced: "Not synced",
    stale: "Stale provider data",
    unavailable: "Provider data unavailable",
    no_recommendations: "No provider recommendations",
    unsupported: "Provider recommendations unsupported",
    insufficient_history: "Insufficient billing history",
    no_spend_data: "No billing data",
};
