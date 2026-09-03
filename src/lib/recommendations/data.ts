import "server-only";

import { auth } from "@clerk/nextjs/server";

import { BACKEND_URL } from "@/lib/config";
import type {
    RecommendationAIEnrichmentStatus,
    RecommendationEvidenceListResponse,
    RecommendationEvidenceRecord,
    RecommendationListResponse,
    RecommendationPricingBasis,
    RecommendationQualityStatus,
    RecommendationRecord,
    RecommendationSavingsEstimateStatus,
    RecommendationState,
} from "./types";

const RECOMMENDATION_STATES: ReadonlySet<RecommendationState> = new Set([
    "detected",
    "evidence_ready",
    "provider_checked",
    "ready_for_review",
    "approved",
    "dismissed",
    "implemented",
    "verifying",
    "verified_saved",
    "verified_no_savings",
    "expired",
    "superseded",
]);

const PRICING_BASES: ReadonlySet<RecommendationPricingBasis> = new Set([
    "live_api",
    "partial_live",
    "static_fallback",
    "unknown",
]);

const QUALITY_STATUSES: ReadonlySet<RecommendationQualityStatus> = new Set([
    "ready",
    "needs_review",
    "insufficient_evidence",
    "provider_only",
    "legacy_unassessed",
]);

const SAVINGS_ESTIMATE_STATUSES: ReadonlySet<RecommendationSavingsEstimateStatus> = new Set([
    "supported_actual",
    "supported_catalog",
    "provider_estimate",
    "unavailable",
    "withheld_evidence",
    "withheld_calculation",
    "withheld_partial_pricing",
    "withheld_static_pricing",
    "withheld_missing_pricing",
    "withheld_unassessed",
]);

const AI_ENRICHMENT_STATUSES: ReadonlySet<RecommendationAIEnrichmentStatus> = new Set([
    "pending",
    "queued",
    "running",
    "enriched",
    "failed",
    "failed_quality_gate",
    "dead",
    "not_required",
    "not_requested",
]);

function asRecord(value: unknown): Record<string, unknown> {
    return value && typeof value === "object" && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : {};
}

function asString(value: unknown, fallback = ""): string {
    if (typeof value === "string") {
        return value.trim() || fallback;
    }
    if (value === null || value === undefined) {
        return fallback;
    }
    return String(value).trim() || fallback;
}

function asNullableString(value: unknown): string | null {
    const normalized = asString(value);
    return normalized ? normalized : null;
}

function asNumber(value: unknown): number {
    const parsed = typeof value === "number"
        ? value
        : typeof value === "string"
            ? Number(value)
            : 0;

    return Number.isFinite(parsed) ? parsed : 0;
}

function asStringArray(value: unknown): string[] {
    if (!Array.isArray(value)) {
        return [];
    }

    return value
        .map((item) => asString(item))
        .filter(Boolean);
}

function asRecommendationState(value: unknown): RecommendationState {
    const normalized = asString(value, "detected").toLowerCase();
    return RECOMMENDATION_STATES.has(normalized as RecommendationState)
        ? (normalized as RecommendationState)
        : "detected";
}

function asPricingBasis(value: unknown): RecommendationPricingBasis {
    const normalized = asString(value, "unknown").toLowerCase();
    return PRICING_BASES.has(normalized as RecommendationPricingBasis)
        ? (normalized as RecommendationPricingBasis)
        : "unknown";
}

function asQualityStatus(value: unknown): RecommendationQualityStatus {
    const normalized = asString(value, "legacy_unassessed").toLowerCase();
    return QUALITY_STATUSES.has(normalized as RecommendationQualityStatus)
        ? (normalized as RecommendationQualityStatus)
        : "legacy_unassessed";
}

function asSavingsEstimateStatus(value: unknown): RecommendationSavingsEstimateStatus {
    const normalized = asString(value, "withheld_unassessed").toLowerCase();
    return SAVINGS_ESTIMATE_STATUSES.has(normalized as RecommendationSavingsEstimateStatus)
        ? (normalized as RecommendationSavingsEstimateStatus)
        : "withheld_unassessed";
}

function asAIEnrichmentStatus(value: unknown): RecommendationAIEnrichmentStatus {
    const normalized = asString(value, "not_requested").toLowerCase();
    return AI_ENRICHMENT_STATUSES.has(normalized as RecommendationAIEnrichmentStatus)
        ? (normalized as RecommendationAIEnrichmentStatus)
        : "not_requested";
}

function normalizeRecommendationRecord(value: unknown): RecommendationRecord {
    const row = asRecord(value);
    return {
        id: asString(row.id),
        integration_id: asString(row.integration_id),
        provider: asString(row.provider, "unknown"),
        resource_id: asString(row.resource_id),
        cloud_resource_id: asString(row.cloud_resource_id),
        resource_name: asString(row.resource_name, "Unknown resource"),
        resource_type: asString(row.resource_type, "Cloud Resource"),
        region: asString(row.region),
        recommendation_type: asString(row.recommendation_type),
        action: asString(row.action, "investigate"),
        state: asRecommendationState(row.state),
        severity: asString(row.severity, "none"),
        confidence: asNumber(row.confidence),
        trust_score: Math.round(asNumber(row.trust_score)),
        quality_status: asQualityStatus(row.quality_status),
        quality_reasons: asStringArray(row.quality_reasons),
        risk_level: asString(row.risk_level, "unknown"),
        effort: asString(row.effort, "unknown"),
        description: asString(row.description),
        waste_reason: asString(row.waste_reason),
        estimated_monthly_savings: asNumber(row.estimated_monthly_savings),
        claimable_monthly_savings: asNumber(row.claimable_monthly_savings),
        savings_estimate_status: asSavingsEstimateStatus(row.savings_estimate_status),
        savings_calculation_method: asString(row.savings_calculation_method, "unknown"),
        savings_estimate_reason: asString(row.savings_estimate_reason),
        estimated_monthly_waste: asNumber(row.estimated_monthly_waste),
        savings_currency: asNullableString(row.savings_currency),
        cost_source: asString(row.cost_source, "unknown"),
        pricing_basis: asPricingBasis(row.pricing_basis),
        pricing_computed_at: asNullableString(row.pricing_computed_at),
        evidence_status: asString(row.evidence_status, "missing"),
        provider_agreement_status: asString(row.provider_agreement_status, "unknown"),
        ai_enrichment_status: asAIEnrichmentStatus(row.ai_enrichment_status),
        ai_enrichment_id: asNullableString(row.ai_enrichment_id),
        ai_enrichment_job_id: asNullableString(row.ai_enrichment_job_id),
        ai_enriched_at: asNullableString(row.ai_enriched_at),
        ai_model: asNullableString(row.ai_model),
        ai_summary: asNullableString(row.ai_summary),
        ai_enrichment_error: asNullableString(row.ai_enrichment_error),
        source_systems: asStringArray(row.source_systems),
        pipeline_version: asString(row.pipeline_version, "unknown"),
        detected_at: asString(row.detected_at),
        implemented_at: asNullableString(row.implemented_at),
        verification_status: asString(row.verification_status, "not_started"),
        verification_id: asNullableString(row.verification_id),
        realized_monthly_savings: asNumber(row.realized_monthly_savings),
        realized_savings_confidence: asNumber(row.realized_savings_confidence),
        created_at: asNullableString(row.created_at),
        updated_at: asNullableString(row.updated_at),
    };
}

function normalizeEvidenceRecord(value: unknown): RecommendationEvidenceRecord {
    const row = asRecord(value);
    return {
        id: asString(row.id),
        recommendation_id: asString(row.recommendation_id),
        resource_id: asString(row.resource_id),
        evidence_kind: asString(row.evidence_kind),
        signal_name: asString(row.signal_name),
        observed_value: row.observed_value,
        threshold: row.threshold,
        description: asString(row.description),
        metric_window_start: asNullableString(row.metric_window_start),
        metric_window_end: asNullableString(row.metric_window_end),
        data_completeness: asNumber(row.data_completeness),
        source_system: asString(row.source_system),
        collected_at: asString(row.collected_at),
    };
}

function normalizeRecommendationListResponse(value: unknown): RecommendationListResponse {
    const payload = asRecord(value);
    const rows = Array.isArray(payload.recommendations) ? payload.recommendations : [];
    const recommendations = rows.map(normalizeRecommendationRecord).filter((row) => row.id);
    return {
        recommendations,
        count: Math.max(asNumber(payload.count), recommendations.length),
    };
}

export function normalizeRecommendationEvidenceResponse(value: unknown): RecommendationEvidenceListResponse {
    const payload = asRecord(value);
    const rows = Array.isArray(payload.evidence) ? payload.evidence : [];
    const evidence = rows.map(normalizeEvidenceRecord).filter((row) => row.id);
    return {
        evidence,
        count: Math.max(asNumber(payload.count), evidence.length),
    };
}

export async function getRecommendationLedger(): Promise<RecommendationListResponse> {
    try {
        const { userId, getToken } = await auth();
        if (!userId) {
            throw new Error("Unauthorized");
        }

        let token: string | null = null;
        try {
            token = await getToken();
        } catch {
            token = null;
        }

        if (!token) {
            try {
                token = await getToken({ template: "default" });
            } catch {
                token = null;
            }
        }

        if (!token) {
            throw new Error("Unauthorized");
        }

        const response = await fetch(`${BACKEND_URL}/api/recommendations`, {
            method: "GET",
            headers: {
                Authorization: `Bearer ${token}`,
            },
            cache: "no-store",
        });

        const payload: unknown = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = asString(asRecord(payload).detail, "Failed to load recommendations");
            throw new Error(detail);
        }

        return normalizeRecommendationListResponse(payload);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to load recommendations";
        throw new Error(message);
    }
}
