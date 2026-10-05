export type RecommendationState =
    | "detected"
    | "evidence_ready"
    | "provider_checked"
    | "ready_for_review"
    | "approved"
    | "dismissed"
    | "implemented"
    | "verifying"
    | "verified_saved"
    | "verified_no_savings"
    | "expired"
    | "superseded";

export type RecommendationPricingBasis =
    | "live_api"
    | "partial_live"
    | "static_fallback"
    | "unknown";

export type RecommendationQualityStatus =
    | "ready"
    | "needs_review"
    | "insufficient_evidence"
    | "provider_only"
    | "legacy_unassessed";

export type RecommendationSavingsEstimateStatus =
    | "supported_actual"
    | "supported_catalog"
    | "provider_estimate"
    | "unavailable"
    | "withheld_evidence"
    | "withheld_calculation"
    | "withheld_partial_pricing"
    | "withheld_static_pricing"
    | "withheld_missing_pricing"
    | "withheld_unassessed";

export type RecommendationAIEnrichmentStatus =
    | "pending"
    | "queued"
    | "running"
    | "enriched"
    | "failed"
    | "failed_quality_gate"
    | "dead"
    | "not_required"
    | "not_requested";

export type RecommendationRecord = {
    id: string;
    integration_id: string;
    provider: string;
    resource_id: string;
    cloud_resource_id: string;
    resource_name: string;
    resource_type: string;
    region: string;
    recommendation_type: string;
    action: string;
    state: RecommendationState;
    severity: string;
    confidence: number;
    trust_score: number;
    quality_status: RecommendationQualityStatus;
    quality_reasons: string[];
    risk_level: string;
    effort: string;
    description: string;
    waste_reason: string;
    estimated_monthly_savings: number;
    claimable_monthly_savings: number;
    savings_estimate_status: RecommendationSavingsEstimateStatus;
    savings_calculation_method: string;
    savings_estimate_reason: string;
    estimated_monthly_waste: number;
    savings_currency: string | null;
    cost_source: string;
    pricing_basis: RecommendationPricingBasis;
    pricing_computed_at: string | null;
    evidence_status: string;
    provider_agreement_status: string;
    ai_enrichment_status: RecommendationAIEnrichmentStatus;
    ai_enrichment_id: string | null;
    ai_enrichment_job_id: string | null;
    ai_enriched_at: string | null;
    ai_model: string | null;
    ai_summary: string | null;
    ai_enrichment_error: string | null;
    source_systems: string[];
    pipeline_version: string;
    detected_at: string;
    implemented_at: string | null;
    verification_status: string;
    verification_id: string | null;
    realized_monthly_savings: number;
    realized_savings_confidence: number;
    created_at: string | null;
    updated_at: string | null;
};

export type RecommendationListResponse = {
    recommendations: RecommendationRecord[];
    count: number;
};

export type RecommendationEvidenceRecord = {
    id: string;
    recommendation_id: string;
    resource_id: string;
    evidence_kind: string;
    signal_name: string;
    observed_value: unknown;
    threshold: unknown;
    description: string;
    metric_window_start: string | null;
    metric_window_end: string | null;
    data_completeness: number;
    source_system: string;
    collected_at: string;
};

export type RecommendationEvidenceListResponse = {
    evidence: RecommendationEvidenceRecord[];
    count: number;
};

export type RecommendationStateUpdateResponse = {
    recommendation: RecommendationRecord;
    event: {
        id: string;
        recommendation_id: string;
        from_state: string | null;
        to_state: RecommendationState;
        actor_type: string;
        actor_id: string;
        reason: string | null;
        created_at: string;
    };
};

export type RecommendationSavingsVerificationResponse = {
    id: string;
    recommendation_id: string;
    integration_id: string;
    provider: string;
    resource_id: string;
    cloud_resource_id: string;
    action: string;
    status: string;
    estimated_monthly_savings: number;
    baseline_window_start: string | null;
    baseline_window_end: string | null;
    post_window_start: string | null;
    post_window_end: string | null;
    baseline_monthly_cost: number;
    post_monthly_cost: number;
    realized_monthly_savings: number;
    realized_savings_confidence: number;
    measurement_source: string;
    explanation: string;
    created_at: string | null;
    updated_at: string | null;
};

export type RecommendationAIEnrichmentResponse = {
    id: string;
    recommendation_id: string;
    job_id: string | null;
    status: string;
    summary: string;
    business_impact: string;
    evidence_narrative: string;
    remediation_steps: string[];
    risk_notes: string;
    rollback_plan: string;
    validation_plan: string;
    assumptions: string[];
    confidence_notes: string;
    evidence_ids_used: string[];
    model: string | null;
    prompt_version: string | null;
    generated_at: string | null;
    created_at: string | null;
    updated_at: string | null;
};

export type RecommendationAIEnrichmentRunResponse = {
    status: string;
    message: string | null;
    processed: number;
    succeeded: number;
    failed: number;
    skipped: number;
    queued_before_run: number;
    background_started: boolean;
    results: Array<{
        job_id: string;
        recommendation_id: string;
        status: string;
        enrichment_id: string | null;
        error: string | null;
    }>;
};

export type RecommendationProviderIngestResponse = {
    summaries: Array<{
        integration_id: string;
        provider: string;
        status: string;
        fetched: number;
        stored: number;
        matched: number;
        provider_only_created: number;
        not_found_marked: number;
        message: string | null;
        refresh_status: string;
        refreshed: boolean;
        refresh_message: string | null;
    }>;
    totals: {
        integrations_checked: number;
        fetched: number;
        stored: number;
        matched: number;
        provider_only_created: number;
        not_found_marked: number;
        failed: number;
        refreshed: number;
        refresh_failed: number;
    };
};
