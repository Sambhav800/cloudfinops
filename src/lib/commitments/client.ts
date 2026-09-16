import type { CommitmentRecommendationResponse, CommitmentScenario, FinanceCommitmentsResponse } from "../api";
import { RECOMMENDATION_STATUS_LABELS } from "./presentation";

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isAmount(value: unknown): value is number {
    return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function isPercentage(value: unknown): boolean {
    return value === null || (isAmount(value) && value <= 100);
}

function isTimestamp(value: unknown): value is string {
    return typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value));
}

function isPurchaseScenario(value: unknown): value is CommitmentScenario {
    if (!isRecord(value)) return false;
    return [value.label, value.integration_id, value.recommendation_id].every((field) => typeof field === "string" && field.trim().length > 0)
        && typeof value.account_id === "string" && /^\d{12}$/.test(value.account_id)
        && isAmount(value.hourly_commitment_usd) && value.hourly_commitment_usd > 0
        && isAmount(value.monthly_commitment_usd) && isAmount(value.monthly_saving_usd) && isAmount(value.annual_saving_usd)
        && isPercentage(value.provider_estimated_savings_pct) && isPercentage(value.estimated_utilization_pct)
        && value.commitment_pct === null && value.effective_discount_pct === null && value.over_commitment_risk_pct === null
        && value.risk_level === "Unassessed" && (value.term_years === 1 || value.term_years === 3)
        && value.source === "aws_cost_explorer" && value.payment_option === "NO_UPFRONT"
        && value.savings_plans_type === "COMPUTE_SP" && value.lookback_days === 60 && isTimestamp(value.generated_at);
}

async function readFinanceResponse(path: string, signal: AbortSignal): Promise<unknown> {
    try {
        const response = await fetch(path, { cache: "no-store", signal });
        const payload: unknown = await response.json().catch(() => null);
        if (!response.ok) {
            const detail = isRecord(payload) && typeof payload.detail === "string" ? payload.detail : `Finance service returned ${response.status}`;
            throw new Error(detail);
        }
        if (!isRecord(payload)) throw new Error("Finance service returned an invalid response.");
        return payload;
    } catch (error) {
        if (error instanceof Error && error.name === "TimeoutError") {
            throw new Error("Finance request timed out. Please retry.");
        }
        throw error;
    }
}

export async function loadCommitmentSnapshot(signal: AbortSignal): Promise<FinanceCommitmentsResponse> {
    try {
        const payload = await readFinanceResponse("/api/finance/commitments", signal);
        if (!isRecord(payload) || !Array.isArray(payload.commitments) || !Array.isArray(payload.integrations) || !isRecord(payload.summary)) {
            throw new Error("Commitment snapshot is missing its summary or account sync status.");
        }
        return payload as unknown as FinanceCommitmentsResponse;
    } catch (error) {
        throw error instanceof Error ? error : new Error("Commitment snapshot unavailable.");
    }
}

export async function loadCommitmentRecommendations(signal: AbortSignal): Promise<CommitmentRecommendationResponse> {
    try {
        const payload = await readFinanceResponse("/api/finance/commitment-recommendation", signal);
        if (!isRecord(payload) || typeof payload.status !== "string" || !Object.hasOwn(RECOMMENDATION_STATUS_LABELS, payload.status)
            || payload.source !== "aws_cost_explorer" || payload.currency !== "USD"
            || (payload.message != null && typeof payload.message !== "string")
            || (payload.important_notes !== undefined && (!Array.isArray(payload.important_notes) || !payload.important_notes.every((note) => typeof note === "string")))
            || (payload.fetched_at !== null && !isTimestamp(payload.fetched_at))
            || (payload.generated_at !== null && !isTimestamp(payload.generated_at))
            || (payload.pricing_basis !== null && payload.pricing_basis !== "live_api")
            || (payload.scenarios !== undefined && (!Array.isArray(payload.scenarios) || !payload.scenarios.every(isPurchaseScenario)))) {
            throw new Error("Provider recommendations returned an invalid response.");
        }
        const hasScenarios = Array.isArray(payload.scenarios) && payload.scenarios.length > 0;
        if ((payload.status === "ready") !== hasScenarios
            || (hasScenarios && (payload.pricing_basis !== "live_api" || !isTimestamp(payload.fetched_at) || !isTimestamp(payload.generated_at)))) {
            throw new Error("Provider recommendations returned an invalid response.");
        }
        return payload as unknown as CommitmentRecommendationResponse;
    } catch (error) {
        throw error instanceof Error ? error : new Error("Provider recommendations unavailable.");
    }
}
