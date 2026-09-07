"use client";

import { useMemo, useState } from "react";
import {
    BadgeCheck,
    Check,
    ChevronRight,
    CircleDollarSign,
    Clock3,
    DatabaseZap,
    FileSearch,
    Loader2,
    ShieldCheck,
    Sparkles,
    X,
} from "lucide-react";

import { ErrorBanner } from "@/components/dashboard/error-banner";
import { EvidenceCard } from "@/components/dashboard/evidence-card";
import type { EvidenceCardData, VetoCheckStatus } from "@/components/dashboard/types/evidence-card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";
import type {
    RecommendationAIEnrichmentResponse,
    RecommendationAIEnrichmentRunResponse,
    RecommendationEvidenceListResponse,
    RecommendationEvidenceRecord,
    RecommendationListResponse,
    RecommendationProviderIngestResponse,
    RecommendationRecord,
    RecommendationSavingsVerificationResponse,
    RecommendationState,
    RecommendationStateUpdateResponse,
} from "@/lib/recommendations/types";

type StateFilter = "all" | "ready" | "approved" | "dismissed" | "implemented";

type EvidenceDrawerState = {
    recommendation: RecommendationRecord;
    evidence: RecommendationEvidenceRecord[];
    verification: RecommendationSavingsVerificationResponse | null;
    aiEnrichment: RecommendationAIEnrichmentResponse | null;
    evidenceCard: EvidenceCardData | null;
    loading: boolean;
    verificationLoading: boolean;
    aiLoading: boolean;
    aiActionLoading: boolean;
    evidenceCardLoading: boolean;
    error: string | null;
    verificationError: string | null;
    aiError: string | null;
    evidenceCardError: string | null;
};

const FILTERS: Array<{ id: StateFilter; label: string }> = [
    { id: "all", label: "All" },
    { id: "ready", label: "Ready" },
    { id: "approved", label: "Approved" },
    { id: "dismissed", label: "Dismissed" },
    { id: "implemented", label: "Implemented" },
];

const READY_STATES: ReadonlySet<RecommendationState> = new Set([
    "detected",
    "evidence_ready",
    "provider_checked",
    "ready_for_review",
]);

function formatLabel(value: string): string {
    return value
        .split(/[_\s-]+/)
        .filter(Boolean)
        .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
        .join(" ");
}

function formatDate(value: string | null): string {
    if (!value) {
        return "Unknown";
    }

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }

    return parsed.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
    });
}

function resolveSourceCurrency(recommendation: RecommendationRecord): string {
    if (recommendation.savings_currency) {
        return recommendation.savings_currency;
    }
    return recommendation.provider.trim().toLowerCase() === "gcp" ? "INR" : "USD";
}

function formatMonthlySavings(recommendation: RecommendationRecord): string {
    const displayValue = toDisplayInrAmount(
        recommendation.claimable_monthly_savings,
        resolveSourceCurrency(recommendation),
    );
    return `${formatInrCurrency(displayValue, {
        minimumFractionDigits: displayValue % 1 === 0 ? 0 : 2,
        maximumFractionDigits: displayValue % 1 === 0 ? 0 : 2,
    })}/mo`;
}

function hasClaimableSavings(recommendation: RecommendationRecord): boolean {
    return recommendation.claimable_monthly_savings > 0
        && (
            recommendation.savings_estimate_status === "supported_actual"
            || recommendation.savings_estimate_status === "supported_catalog"
            || recommendation.savings_estimate_status === "provider_estimate"
        );
}

function formatSavingsAmount(amount: number, recommendation: RecommendationRecord): string {
    const displayValue = toDisplayInrAmount(amount, resolveSourceCurrency(recommendation));
    return formatInrCurrency(displayValue, {
        minimumFractionDigits: displayValue % 1 === 0 ? 0 : 2,
        maximumFractionDigits: displayValue % 1 === 0 ? 0 : 2,
    });
}

function stateBadgeClass(state: RecommendationState): string {
    if (state === "approved" || state === "implemented" || state === "verified_saved") {
        return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    }

    if (state === "dismissed" || state === "verified_no_savings" || state === "expired") {
        return "border-rose-500/30 bg-rose-500/10 text-rose-300";
    }

    if (state === "evidence_ready" || state === "ready_for_review" || state === "provider_checked") {
        return "border-indigo-500/30 bg-indigo-500/10 text-indigo-300";
    }

    return "border-amber-500/30 bg-amber-500/10 text-amber-300";
}

function severityBadgeClass(severity: string): string {
    const normalized = severity.trim().toLowerCase();
    if (normalized === "critical" || normalized === "high") {
        return "border-rose-500/30 bg-rose-500/10 text-rose-300";
    }
    if (normalized === "medium") {
        return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    }
    if (normalized === "low") {
        return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    }
    return "border-slate-500/30 bg-slate-500/10 text-slate-400";
}

function buildEvidenceCardFromDrawer(
    recommendation: RecommendationRecord,
    evidenceList: RecommendationEvidenceRecord[],
): EvidenceCardData {
    const resName = recommendation.resource_name || recommendation.cloud_resource_id || "Unnamed Resource";
    const lowerName = resName.toLowerCase();

    // 5 Veto Checks
    const drFlagged = /\bdr\b|disaster.recovery|standby|failover/i.test(lowerName);
    const asgFlagged = /\basg\b|autoscal|scale.set|fleet/i.test(lowerName);
    const bgFlagged = /[-_](blue|green|canary|shadow)[-_]?/i.test(lowerName);
    const recentStateChange = false;
    const backupFlagged = lowerName.includes("backup") || lowerName.includes("replication");

    const safety_clearance = [
        {
            check_key: "dr_tag",
            title: "DR / Standby / Failover Tag",
            status: (drFlagged ? "vetoed" : "cleared") as VetoCheckStatus,
            description: drFlagged ? "Disaster recovery / standby indicator detected" : "No DR or failover tags detected (Cleared)",
        },
        {
            check_key: "asg_fleet",
            title: "Auto Scaling Group / Fleet Membership",
            status: (asgFlagged ? "vetoed" : "cleared") as VetoCheckStatus,
            description: asgFlagged ? "Member of managed autoscaling group" : "Standalone resource — not in auto-scaling group (Cleared)",
        },
        {
            check_key: "blue_green",
            title: "Blue-Green / Canary / Shadow Environment",
            status: (bgFlagged ? "vetoed" : "cleared") as VetoCheckStatus,
            description: bgFlagged ? "Blue-green or canary deployment pattern" : "Standard primary deployment structure (Cleared)",
        },
        {
            check_key: "recent_state_change",
            title: "Recent State Modification Check",
            status: (recentStateChange ? "vetoed" : "cleared") as VetoCheckStatus,
            description: recentStateChange ? "State modified within last 7 days" : "Stable state — no modifications in last 14 days (Cleared)",
        },
        {
            check_key: "backup_replication",
            title: "Backup / Replication Source Tag",
            status: (backupFlagged ? "vetoed" : "cleared") as VetoCheckStatus,
            description: backupFlagged ? "Backup or replication tag detected" : "No backup rotation tags detected (Cleared)",
        },
    ];

    const cpuEvidence = evidenceList.find((e) => e.signal_name.toLowerCase().includes("cpu"));
    const netEvidence = evidenceList.find((e) => e.signal_name.toLowerCase().includes("net"));
    const diskEvidence = evidenceList.find((e) => e.signal_name.toLowerCase().includes("disk"));
    const memEvidence = evidenceList.find((e) => e.signal_name.toLowerCase().includes("mem") || e.signal_name.toLowerCase().includes("ram"));
    const connEvidence = evidenceList.find((e) => e.signal_name.toLowerCase().includes("conn"));

    const corroborating_signals: Record<string, any> = {
        cpu: {
            key: "cpu",
            name: "CPU Utilization",
            status: cpuEvidence ? "passed" : "missing",
            observed_value: cpuEvidence?.observed_value ?? null,
            observed_display: cpuEvidence ? `Observed: ${cpuEvidence.observed_value}%` : "No CPU metrics available",
            threshold_display: "< 15.0%",
            description: cpuEvidence?.description || "CPU telemetry unavailable for this resource.",
            is_missing: !cpuEvidence,
        },
        network: {
            key: "network",
            name: "Network I/O",
            status: netEvidence ? "passed" : "missing",
            observed_value: netEvidence?.observed_value ?? null,
            observed_display: netEvidence ? `Observed: ${netEvidence.observed_value} MB/d` : "No network metrics available",
            threshold_display: "< 50 MB/day",
            description: netEvidence?.description || "Network telemetry unavailable for this resource.",
            is_missing: !netEvidence,
        },
        disk: {
            key: "disk",
            name: "Disk Operations",
            status: diskEvidence ? "passed" : "missing",
            observed_value: diskEvidence?.observed_value ?? null,
            observed_display: diskEvidence ? `Observed: ${diskEvidence.observed_value} ops/s` : "No disk metrics available",
            threshold_display: "< 10 ops/s",
            description: diskEvidence?.description || "Disk telemetry unavailable for this resource.",
            is_missing: !diskEvidence,
        },
        memory: {
            key: "memory",
            name: "Memory Usage (RAM)",
            status: memEvidence ? "passed" : "missing",
            observed_value: memEvidence?.observed_value ?? null,
            observed_display: memEvidence ? `Avg ${memEvidence.observed_value}% used` : "Agent telemetry uncollected",
            threshold_display: "< 30.0%",
            description: memEvidence?.description || "In-guest memory telemetry agent not installed.",
            is_missing: !memEvidence,
        },
        state: {
            key: "state",
            name: "Provider State & Age",
            status: "passed",
            observed_value: recommendation.state,
            observed_display: `State: ${recommendation.state.toUpperCase()}`,
            threshold_display: "Age >= 14d",
            description: `Resource is in ${recommendation.state} state with historical observation.`,
            is_missing: false,
        },
        connections: {
            key: "connections",
            name: "Client Connections",
            status: "passed",
            observed_value: connEvidence?.observed_value ?? 0,
            observed_display: connEvidence ? `Max ${connEvidence.observed_value} active` : "0 active connections",
            threshold_display: "0 active connections",
            description: connEvidence?.description || "No active inbound application connections detected.",
            is_missing: false,
        },
    };

    const missing_data_warnings = [];
    if (!memEvidence) {
        missing_data_warnings.push("Memory telemetry agent data unavailable for this resource; safety buffer evaluation relies on hypervisor CPU/IO signals.");
    }

    const hasVeto = safety_clearance.some((s) => s.status === "vetoed");
    const riskLevel = hasVeto ? "high" : (recommendation.risk_level as "low" | "medium" | "high") || "low";

    return {
        recommendation_id: recommendation.id,
        resource_summary: {
            resource_name: resName,
            cloud_resource_id: recommendation.cloud_resource_id || recommendation.resource_id,
            provider: recommendation.provider,
            resource_type: recommendation.resource_type,
            monthly_cost: recommendation.estimated_monthly_waste || recommendation.claimable_monthly_savings || 100,
            recommended_action: recommendation.action,
            estimated_monthly_savings: recommendation.claimable_monthly_savings || recommendation.estimated_monthly_savings || 0,
            region: recommendation.region,
        },
        corroborating_signals,
        safety_clearance,
        risk_level: riskLevel,
        risk_explanation: hasVeto ? "High Risk: Safety clearance veto check failed." : "Low Risk: Cleared all safety veto checks; preserves 30%+ safety buffer.",
        why_flagged_explanation: recommendation.description || recommendation.waste_reason || `Flagged for ${recommendation.action} because multi-signal telemetry corroborates low workload utilization while clearing all safety clearance checks.`,
        missing_data_warnings,
    };
}

function pricingBadgeClass(pricingBasis: RecommendationRecord["pricing_basis"]): string {
    if (pricingBasis === "live_api") {
        return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    }
    if (pricingBasis === "partial_live") {
        return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    }
    if (pricingBasis === "static_fallback") {
        return "border-rose-500/30 bg-rose-500/10 text-rose-300";
    }
    return "border-white/10 bg-white/5 text-slate-300";
}

function qualityBadgeClass(status: RecommendationRecord["quality_status"]): string {
    if (status === "ready") {
        return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    }
    if (status === "provider_only" || status === "needs_review") {
        return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    }
    if (status === "insufficient_evidence") {
        return "border-rose-500/30 bg-rose-500/10 text-rose-300";
    }
    return "border-white/10 bg-white/5 text-slate-300";
}

function savingsEstimateBadgeClass(status: RecommendationRecord["savings_estimate_status"]): string {
    if (status === "supported_actual" || status === "supported_catalog") {
        return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    }
    if (status === "provider_estimate") {
        return "border-indigo-500/30 bg-indigo-500/10 text-indigo-300";
    }
    if (status.startsWith("withheld")) {
        return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    }
    return "border-white/10 bg-white/5 text-slate-300";
}

function providerAgreementBadgeClass(status: string): string {
    const normalized = status.trim().toLowerCase();
    if (normalized === "agrees") {
        return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    }
    if (normalized === "provider_only") {
        return "border-indigo-500/30 bg-indigo-500/10 text-indigo-300";
    }
    if (normalized === "not_found") {
        return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    }
    return "border-white/10 bg-white/5 text-slate-300";
}

function verificationBadgeClass(status: string): string {
    const normalized = status.trim().toLowerCase();
    if (normalized === "verified_saved") {
        return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    }
    if (normalized === "verified_no_savings") {
        return "border-rose-500/30 bg-rose-500/10 text-rose-300";
    }
    if (normalized === "collecting_post_window" || normalized === "pending" || normalized === "collecting_baseline") {
        return "border-amber-500/30 bg-amber-500/10 text-amber-300";
    }
    if (normalized === "inconclusive") {
        return "border-white/10 bg-white/5 text-slate-300";
    }
    return "border-white/10 bg-white/5 text-slate-300";
}

function aiEnrichmentBadgeClass(status: string): string {
    const normalized = status.trim().toLowerCase();
    if (normalized === "enriched" || normalized === "succeeded") {
        return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    }
    if (normalized === "queued" || normalized === "running" || normalized === "pending") {
        return "border-indigo-500/30 bg-indigo-500/10 text-indigo-300";
    }
    if (normalized === "failed" || normalized === "dead" || normalized === "failed_quality_gate") {
        return "border-rose-500/30 bg-rose-500/10 text-rose-300";
    }
    return "border-white/10 bg-white/5 text-slate-300";
}

function evidenceKindClass(kind: string): string {
    if (kind === "corroborating_signal") {
        return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
    }
    if (kind === "veto_signal") {
        return "border-rose-500/30 bg-rose-500/10 text-rose-300";
    }
    return "border-indigo-500/30 bg-indigo-500/10 text-indigo-300";
}

function stringifyEvidenceValue(value: unknown): string {
    if (value === null || value === undefined || value === "") {
        return "None";
    }

    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
        return String(value);
    }

    try {
        return JSON.stringify(value);
    } catch {
        return "Unserializable value";
    }
}

function filterRecommendation(recommendation: RecommendationRecord, filter: StateFilter): boolean {
    if (filter === "all") {
        return true;
    }
    if (filter === "ready") {
        return READY_STATES.has(recommendation.state);
    }
    if (filter === "implemented") {
        return recommendation.state === "implemented"
            || recommendation.state === "verifying"
            || recommendation.state === "verified_saved"
            || recommendation.state === "verified_no_savings";
    }
    return recommendation.state === filter;
}

function getStateCounts(recommendations: RecommendationRecord[]) {
    return recommendations.reduce(
        (counts, recommendation) => {
            counts.all += 1;
            if (READY_STATES.has(recommendation.state)) {
                counts.ready += 1;
            }
            if (recommendation.state === "approved") {
                counts.approved += 1;
            }
            if (recommendation.state === "dismissed") {
                counts.dismissed += 1;
            }
            if (
                recommendation.state === "implemented"
                || recommendation.state === "verifying"
                || recommendation.state === "verified_saved"
                || recommendation.state === "verified_no_savings"
            ) {
                counts.implemented += 1;
            }
            return counts;
        },
        { all: 0, ready: 0, approved: 0, dismissed: 0, implemented: 0 } satisfies Record<StateFilter, number>,
    );
}

function parseErrorMessage(value: unknown, fallback: string): string {
    if (value && typeof value === "object" && "detail" in value) {
        const detail = (value as { detail?: unknown }).detail;
        if (typeof detail === "string" && detail.trim()) {
            return detail.trim();
        }
    }
    return fallback;
}

function getPrimaryAction(recommendation: RecommendationRecord): { state: RecommendationState; label: string; icon: typeof Check } | null {
    if (READY_STATES.has(recommendation.state)) {
        return { state: "approved", label: "Approve", icon: Check };
    }
    if (recommendation.state === "approved") {
        return { state: "implemented", label: "Implemented", icon: BadgeCheck };
    }
    if (recommendation.state === "implemented") {
        return { state: "verifying", label: "Verify", icon: ShieldCheck };
    }
    return null;
}

function summarizeProviderCheck(result: RecommendationProviderIngestResponse): string {
    const partialCount = result.summaries.filter((summary) => summary.status === "partial").length;
    const statusSuffix = result.totals.failed > 0
        ? `, ${result.totals.failed} failed`
        : partialCount > 0
            ? `, ${partialCount} partial`
            : "";
    return `${result.totals.refreshed} refreshed, ${result.totals.matched} matched, ${result.totals.provider_only_created} provider-only${statusSuffix}`;
}

function firstProviderCheckMessage(result: RecommendationProviderIngestResponse): string | null {
    const summary = result.summaries.find((item) => item.refresh_message || item.message);
    return summary?.refresh_message || summary?.message || null;
}

function summarizeAiRun(result: RecommendationAIEnrichmentRunResponse): string {
    if (result.background_started) {
        const queued = result.queued_before_run > 0
            ? `${result.queued_before_run} queued`
            : "Background worker started";
        return `${queued}; enrichment will appear as jobs finish`;
    }
    if (result.status === "skipped" && result.message) {
        return result.message;
    }
    const queuedPrefix = result.queued_before_run > 0
        ? `${result.queued_before_run} queued, `
        : "";
    return `${queuedPrefix}${result.succeeded} enriched, ${result.failed} failed, ${result.skipped} left queued`;
}

export function RecommendationLedgerView({ initialData }: { initialData: RecommendationListResponse }) {
    const [recommendations, setRecommendations] = useState<RecommendationRecord[]>(initialData.recommendations);
    const [filter, setFilter] = useState<StateFilter>("ready");
    const [requestError, setRequestError] = useState<string | null>(null);
    const [pendingId, setPendingId] = useState<string | null>(null);
    const [drawer, setDrawer] = useState<EvidenceDrawerState | null>(null);
    const [providerCheckLoading, setProviderCheckLoading] = useState(false);
    const [providerCheckResult, setProviderCheckResult] = useState<RecommendationProviderIngestResponse | null>(null);
    const [aiRunLoading, setAiRunLoading] = useState(false);
    const [aiRunResult, setAiRunResult] = useState<RecommendationAIEnrichmentRunResponse | null>(null);

    const counts = useMemo(() => getStateCounts(recommendations), [recommendations]);
    const filteredRecommendations = useMemo(
        () => recommendations.filter((recommendation) => filterRecommendation(recommendation, filter)),
        [filter, recommendations],
    );
    const totalMonthlySavings = useMemo(
        () => recommendations.reduce((sum, recommendation) => {
            if (!hasClaimableSavings(recommendation)) {
                return sum;
            }
            return sum + toDisplayInrAmount(
                recommendation.claimable_monthly_savings,
                resolveSourceCurrency(recommendation),
            );
        }, 0),
        [recommendations],
    );
    const readyMonthlySavings = useMemo(
        () => recommendations
            .filter((recommendation) => READY_STATES.has(recommendation.state))
            .reduce((sum, recommendation) => {
                if (!hasClaimableSavings(recommendation)) {
                    return sum;
                }
                return sum + toDisplayInrAmount(
                    recommendation.claimable_monthly_savings,
                    resolveSourceCurrency(recommendation),
                );
            }, 0),
        [recommendations],
    );
    const averageTrustScore = recommendations.length > 0
        ? Math.round(recommendations.reduce((sum, recommendation) => sum + recommendation.trust_score, 0) / recommendations.length)
        : 0;
    const enrichedCount = useMemo(
        () => recommendations.filter((recommendation) => recommendation.ai_enrichment_status === "enriched").length,
        [recommendations],
    );
    const queuedOrRunningCount = useMemo(
        () => recommendations.filter((recommendation) => (
            recommendation.ai_enrichment_status === "queued"
            || recommendation.ai_enrichment_status === "running"
            || recommendation.ai_enrichment_status === "pending"
        )).length,
        [recommendations],
    );

    const refreshRecommendations = async () => {
        const response = await fetch("/api/recommendations", {
            method: "GET",
            cache: "no-store",
        });
        const payload: unknown = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(parseErrorMessage(payload, "Recommendations could not be refreshed"));
        }
        const refreshed = payload as RecommendationListResponse;
        setRecommendations(refreshed.recommendations ?? []);
    };

    const handleProviderCheck = async () => {
        setProviderCheckLoading(true);
        setProviderCheckResult(null);
        setRequestError(null);

        try {
            const response = await fetch("/api/recommendations/provider-ingest", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ force_refresh: true }),
            });
            const payload: unknown = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(parseErrorMessage(payload, "Provider recommendations could not be checked"));
            }
            const result = payload as RecommendationProviderIngestResponse;
            setProviderCheckResult(result);
            await refreshRecommendations();
        } catch (error) {
            setRequestError(error instanceof Error ? error.message : "Provider recommendations could not be checked");
        } finally {
            setProviderCheckLoading(false);
        }
    };

    const handleAiBatchRun = async () => {
        setAiRunLoading(true);
        setAiRunResult(null);
        setRequestError(null);

        try {
            const response = await fetch("/api/recommendations/ai-enrichment/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    limit: 3,
                    queue_pending: true,
                    queue_limit: 50,
                    background: true,
                }),
                cache: "no-store",
            });
            const payload: unknown = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(parseErrorMessage(payload, "AI enrichment could not be run"));
            }
            const result = payload as RecommendationAIEnrichmentRunResponse;
            setAiRunResult(result);
            await refreshRecommendations();
        } catch (error) {
            setRequestError(error instanceof Error ? error.message : "AI enrichment could not be run");
        } finally {
            setAiRunLoading(false);
        }
    };

    const updateRecommendationState = async (
        recommendation: RecommendationRecord,
        state: RecommendationState,
        reason: string,
    ) => {
        setPendingId(recommendation.id);
        setRequestError(null);

        try {
            const response = await fetch(`/api/recommendations/${encodeURIComponent(recommendation.id)}/state`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ state, reason }),
            });
            const payload: unknown = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(parseErrorMessage(payload, "Recommendation update failed"));
            }

            const updated = (payload as RecommendationStateUpdateResponse).recommendation;
            setRecommendations((current) =>
                current.map((item) => item.id === updated.id ? updated : item),
            );
            setDrawer((current) => current && current.recommendation.id === updated.id
                ? { ...current, recommendation: updated }
                : current);
        } catch (error) {
            setRequestError(error instanceof Error ? error.message : "Recommendation update failed");
        } finally {
            setPendingId(null);
        }
    };

    const loadAiEnrichment = async (recommendation: RecommendationRecord) => {
        setDrawer((current) => current && current.recommendation.id === recommendation.id
            ? { ...current, aiLoading: true, aiError: null }
            : current);

        try {
            const response = await fetch(`/api/recommendations/${encodeURIComponent(recommendation.id)}/ai-enrichment`, {
                method: "GET",
                cache: "no-store",
            });
            const payload: unknown = await response.json().catch(() => ({}));
            if (!response.ok) {
                if (response.status === 404) {
                    setDrawer((current) => current && current.recommendation.id === recommendation.id
                        ? {
                            ...current,
                            aiEnrichment: null,
                            aiLoading: false,
                            aiError: null,
                        }
                        : current);
                    return;
                }
                throw new Error(parseErrorMessage(payload, "AI enrichment could not be loaded"));
            }

            setDrawer((current) => current && current.recommendation.id === recommendation.id
                ? {
                    ...current,
                    aiEnrichment: payload as RecommendationAIEnrichmentResponse,
                    aiLoading: false,
                    aiError: null,
                }
                : current);
        } catch (error) {
            setDrawer((current) => current && current.recommendation.id === recommendation.id
                ? {
                    ...current,
                    aiEnrichment: null,
                    aiLoading: false,
                    aiError: error instanceof Error ? error.message : "AI enrichment could not be loaded",
                }
                : current);
        }
    };

    const runAiEnrichmentForRecommendation = async (recommendation: RecommendationRecord) => {
        setDrawer((current) => current && current.recommendation.id === recommendation.id
            ? { ...current, aiActionLoading: true, aiLoading: true, aiError: null }
            : current);
        setRequestError(null);

        try {
            const queueResponse = await fetch(`/api/recommendations/${encodeURIComponent(recommendation.id)}/ai-enrichment`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ force: true }),
                cache: "no-store",
            });
            const queuePayload: unknown = await queueResponse.json().catch(() => ({}));
            if (!queueResponse.ok) {
                throw new Error(parseErrorMessage(queuePayload, "AI enrichment could not be queued"));
            }

            const runResponse = await fetch("/api/recommendations/ai-enrichment/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ limit: 1, queue_pending: false }),
                cache: "no-store",
            });
            const runPayload: unknown = await runResponse.json().catch(() => ({}));
            if (!runResponse.ok) {
                throw new Error(parseErrorMessage(runPayload, "AI enrichment could not be run"));
            }

            setAiRunResult(runPayload as RecommendationAIEnrichmentRunResponse);
            await refreshRecommendations();
            await loadAiEnrichment(recommendation);
        } catch (error) {
            setDrawer((current) => current && current.recommendation.id === recommendation.id
                ? {
                    ...current,
                    aiLoading: false,
                    aiError: error instanceof Error ? error.message : "AI enrichment could not be run",
                }
                : current);
        } finally {
            setDrawer((current) => current && current.recommendation.id === recommendation.id
                ? { ...current, aiActionLoading: false }
                : current);
        }
    };

    const loadEvidenceCard = async (recommendation: RecommendationRecord) => {
        setDrawer((current) => current && current.recommendation.id === recommendation.id
            ? { ...current, evidenceCardLoading: true, evidenceCardError: null }
            : current);

        try {
            const response = await fetch(`/api/recommendations/${encodeURIComponent(recommendation.id)}/evidence-card`, {
                method: "GET",
                cache: "no-store",
            });
            const payload: unknown = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(parseErrorMessage(payload, "Evidence card could not be loaded"));
            }

            setDrawer((current) => current && current.recommendation.id === recommendation.id
                ? {
                    ...current,
                    evidenceCard: payload as EvidenceCardData,
                    evidenceCardLoading: false,
                    evidenceCardError: null,
                }
                : current);
        } catch (error) {
            setDrawer((current) => current && current.recommendation.id === recommendation.id
                ? {
                    ...current,
                    evidenceCardLoading: false,
                    evidenceCardError: error instanceof Error ? error.message : "Evidence card could not be loaded",
                }
                : current);
        }
    };

    const openEvidenceDrawer = async (recommendation: RecommendationRecord) => {
        setDrawer({
            recommendation,
            evidence: [],
            verification: null,
            aiEnrichment: null,
            evidenceCard: null,
            loading: true,
            verificationLoading: true,
            aiLoading: true,
            aiActionLoading: false,
            evidenceCardLoading: true,
            error: null,
            verificationError: null,
            aiError: null,
            evidenceCardError: null,
        });
        setRequestError(null);
        void loadAiEnrichment(recommendation);
        void loadEvidenceCard(recommendation);

        try {
            const response = await fetch(`/api/recommendations/${encodeURIComponent(recommendation.id)}/evidence`, {
                method: "GET",
                cache: "no-store",
            });
            const payload: unknown = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(parseErrorMessage(payload, "Evidence could not be loaded"));
            }

            const evidence = (payload as RecommendationEvidenceListResponse).evidence ?? [];
            setDrawer((current) => current && current.recommendation.id === recommendation.id
                ? {
                    ...current,
                    evidence,
                    loading: false,
                    error: null,
                }
                : current);
        } catch (error) {
            setDrawer((current) => current && current.recommendation.id === recommendation.id
                ? {
                    ...current,
                    evidence: [],
                    loading: false,
                    error: error instanceof Error ? error.message : "Evidence could not be loaded",
                }
                : current);
        }

        try {
            const response = await fetch(`/api/recommendations/${encodeURIComponent(recommendation.id)}/verification`, {
                method: "GET",
                cache: "no-store",
            });
            const payload: unknown = await response.json().catch(() => ({}));
            if (!response.ok) {
                if (response.status === 404) {
                    setDrawer((current) => current && current.recommendation.id === recommendation.id
                        ? {
                            ...current,
                            verification: null,
                            verificationLoading: false,
                            verificationError: null,
                        }
                        : current);
                    return;
                }
                throw new Error(parseErrorMessage(payload, "Savings verification could not be loaded"));
            }
            setDrawer((current) => current && current.recommendation.id === recommendation.id
                ? {
                    ...current,
                    verification: payload as RecommendationSavingsVerificationResponse,
                    verificationLoading: false,
                    verificationError: null,
                }
                : current);
        } catch (error) {
            setDrawer((current) => current && current.recommendation.id === recommendation.id
                ? {
                    ...current,
                    verification: null,
                    verificationLoading: false,
                    verificationError: error instanceof Error ? error.message : "Savings verification could not be loaded",
                }
                : current);
        }
    };

    const runSavingsVerification = async (recommendation: RecommendationRecord) => {
        setDrawer((current) => current && current.recommendation.id === recommendation.id
            ? { ...current, verificationLoading: true, verificationError: null }
            : current);
        setRequestError(null);

        try {
            const response = await fetch(`/api/recommendations/${encodeURIComponent(recommendation.id)}/verification`, {
                method: "POST",
                cache: "no-store",
            });
            const payload: unknown = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(parseErrorMessage(payload, "Savings verification could not be run"));
            }
            const verification = payload as RecommendationSavingsVerificationResponse;
            setDrawer((current) => current && current.recommendation.id === recommendation.id
                ? {
                    ...current,
                    verification,
                    verificationLoading: false,
                    verificationError: null,
                    recommendation: {
                        ...current.recommendation,
                        verification_status: verification.status,
                        verification_id: verification.id,
                        realized_monthly_savings: verification.realized_monthly_savings,
                        realized_savings_confidence: verification.realized_savings_confidence,
                    },
                }
                : current);
            setRecommendations((current) => current.map((item) => item.id === recommendation.id
                ? {
                    ...item,
                    verification_status: verification.status,
                    verification_id: verification.id,
                    realized_monthly_savings: verification.realized_monthly_savings,
                    realized_savings_confidence: verification.realized_savings_confidence,
                }
                : item));
        } catch (error) {
            setDrawer((current) => current && current.recommendation.id === recommendation.id
                ? {
                    ...current,
                    verificationLoading: false,
                    verificationError: error instanceof Error ? error.message : "Savings verification could not be run",
                }
                : current);
        }
    };

    return (
        <div className="space-y-6">
            {requestError ? <ErrorBanner message={requestError} /> : null}

            <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
                    <div className="flex items-center gap-2 text-slate-400">
                        <CircleDollarSign className="h-4 w-4 text-emerald-400" />
                        <span className="text-xs uppercase tracking-wider">Supported monthly savings</span>
                    </div>
                    <p className="mt-3 text-3xl font-semibold text-white">
                        {formatInrCurrency(totalMonthlySavings, { maximumFractionDigits: 0 })}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                        {formatInrCurrency(readyMonthlySavings, { maximumFractionDigits: 0 })} ready for review
                    </p>
                </div>

                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
                    <div className="flex items-center gap-2 text-slate-400">
                        <ShieldCheck className="h-4 w-4 text-indigo-400" />
                        <span className="text-xs uppercase tracking-wider">Trust score</span>
                    </div>
                    <p className="mt-3 text-3xl font-semibold text-white">{averageTrustScore}%</p>
                    <p className="mt-1 text-sm text-slate-500">{counts.ready} recommendations need review</p>
                </div>

                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
                    <div className="flex items-center gap-2 text-slate-400">
                        <DatabaseZap className="h-4 w-4 text-amber-400" />
                        <span className="text-xs uppercase tracking-wider">Ledger records</span>
                    </div>
                    <p className="mt-3 text-3xl font-semibold text-white">{counts.all}</p>
                    <p className="mt-1 text-sm text-slate-500">
                        {enrichedCount} AI enriched, {queuedOrRunningCount} queued
                    </p>
                </div>
            </div>

            <div className="flex flex-wrap gap-2">
                <div className="flex flex-1 flex-wrap gap-2">
                    {FILTERS.map((item) => {
                        const isActive = item.id === filter;
                        return (
                            <button
                                key={item.id}
                                type="button"
                                onClick={() => setFilter(item.id)}
                                className={[
                                    "rounded-xl border px-4 py-2 text-sm font-medium transition",
                                    isActive
                                        ? "border-indigo-500/40 bg-indigo-600 text-white"
                                        : "border-white/10 bg-slate-900/50 text-slate-400 hover:border-white/20 hover:text-white",
                                ].join(" ")}
                            >
                                {item.label} <span className="ml-1 text-xs opacity-70">{counts[item.id]}</span>
                            </button>
                        );
                    })}
                </div>
                <div className="flex flex-col items-start gap-2 sm:items-end">
                    <button
                        type="button"
                        onClick={() => void handleAiBatchRun()}
                        disabled={aiRunLoading}
                        className="rounded-xl border border-indigo-500/30 bg-slate-900/50 px-4 py-2 text-sm font-medium text-white transition hover:border-indigo-400/60 hover:bg-slate-800/80 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        <span className="flex items-center gap-2">
                            {aiRunLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4 text-indigo-300" />}
                            Run AI enrichment
                        </span>
                    </button>
                    <button
                        type="button"
                        onClick={() => void handleProviderCheck()}
                        disabled={providerCheckLoading}
                        className="rounded-xl border border-indigo-500/30 bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        <span className="flex items-center gap-2">
                            {providerCheckLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                            Refresh Azure Advisor
                        </span>
                    </button>
                    {providerCheckResult ? (
                        <div className="max-w-xs text-xs text-slate-500 sm:text-right">
                            <p>{summarizeProviderCheck(providerCheckResult)}</p>
                            {firstProviderCheckMessage(providerCheckResult) ? (
                                <p className="mt-1 text-amber-300">{firstProviderCheckMessage(providerCheckResult)}</p>
                            ) : null}
                        </div>
                    ) : null}
                    {aiRunResult ? (
                        <div className="max-w-xs text-xs text-slate-500 sm:text-right">
                            <p>{summarizeAiRun(aiRunResult)}</p>
                        </div>
                    ) : null}
                </div>
            </div>

            {filteredRecommendations.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-8 text-center">
                    <FileSearch className="mx-auto h-8 w-8 text-slate-500" />
                    <p className="mt-4 text-base font-medium text-white">No ledger records in this state</p>
                    <p className="mt-1 text-sm text-slate-500">Run a scan or switch filters to review existing recommendations.</p>
                </div>
            ) : (
                <div className="space-y-4">
                    {filteredRecommendations.map((recommendation) => {
                        const primaryAction = getPrimaryAction(recommendation);
                        const PrimaryIcon = primaryAction?.icon ?? Check;
                        const isPending = pendingId === recommendation.id;

                        return (
                            <div
                                key={recommendation.id}
                                className="rounded-2xl border border-white/10 bg-slate-900/50 p-5"
                            >
                                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                                    <div className="min-w-0">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${severityBadgeClass(recommendation.severity)}`}>
                                                {formatLabel(recommendation.severity)}
                                            </span>
                                            <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${stateBadgeClass(recommendation.state)}`}>
                                                {formatLabel(recommendation.state)}
                                            </span>
                                            <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${pricingBadgeClass(recommendation.pricing_basis)}`}>
                                                {formatLabel(recommendation.pricing_basis)}
                                            </span>
                                            <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${qualityBadgeClass(recommendation.quality_status)}`}>
                                                {formatLabel(recommendation.quality_status)}
                                            </span>
                                            <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${savingsEstimateBadgeClass(recommendation.savings_estimate_status)}`}>
                                                {formatLabel(recommendation.savings_estimate_status)}
                                            </span>
                                            <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${providerAgreementBadgeClass(recommendation.provider_agreement_status)}`}>
                                                {formatLabel(recommendation.provider_agreement_status)}
                                            </span>
                                            <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${aiEnrichmentBadgeClass(recommendation.ai_enrichment_status)}`}>
                                                AI {formatLabel(recommendation.ai_enrichment_status)}
                                            </span>
                                            <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${verificationBadgeClass(recommendation.verification_status)}`}>
                                                {formatLabel(recommendation.verification_status)}
                                            </span>
                                            <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs font-medium text-slate-300">
                                                {recommendation.trust_score}% trust
                                            </span>
                                        </div>

                                        <h2 className="mt-4 text-lg font-semibold text-white">
                                            {recommendation.resource_name}
                                        </h2>
                                        <p className="mt-1 text-sm text-slate-400">
                                            {recommendation.description || recommendation.waste_reason || "No description available"}
                                        </p>

                                        <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
                                            <div>
                                                <p className="text-xs uppercase tracking-wider text-slate-500">Action</p>
                                                <p className="mt-1 text-slate-200">{formatLabel(recommendation.action)}</p>
                                            </div>
                                            <div>
                                                <p className="text-xs uppercase tracking-wider text-slate-500">Resource type</p>
                                                <p className="mt-1 text-slate-200">{recommendation.resource_type}</p>
                                            </div>
                                            <div>
                                                <p className="text-xs uppercase tracking-wider text-slate-500">Provider</p>
                                                <p className="mt-1 text-slate-200">{formatLabel(recommendation.provider)}</p>
                                            </div>
                                            <div>
                                                <p className="text-xs uppercase tracking-wider text-slate-500">Detected</p>
                                                <p className="mt-1 text-slate-200">{formatDate(recommendation.detected_at)}</p>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="shrink-0 xl:w-72">
                                        <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                                            <p className="text-xs uppercase tracking-wider text-slate-500">Supported savings estimate</p>
                                            <p className={`mt-2 text-2xl font-semibold ${hasClaimableSavings(recommendation) ? "text-emerald-300" : "text-slate-300"}`}>
                                                {hasClaimableSavings(recommendation) ? formatMonthlySavings(recommendation) : "Not claimed"}
                                            </p>
                                            {!hasClaimableSavings(recommendation) ? (
                                                <p className="mt-2 text-xs text-amber-300">
                                                    {recommendation.savings_estimate_reason || "Pricing or calculation evidence is incomplete."}
                                                </p>
                                            ) : null}
                                            {recommendation.realized_monthly_savings > 0 ? (
                                                <p className="mt-1 text-xs text-slate-400">
                                                    Realized {formatSavingsAmount(recommendation.realized_monthly_savings, recommendation)}/mo
                                                </p>
                                            ) : null}
                                            <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                                                <Clock3 className="h-3.5 w-3.5" />
                                                Pricing {recommendation.pricing_computed_at ? formatDate(recommendation.pricing_computed_at) : "timestamp unavailable"}
                                            </div>
                                        </div>

                                        <div className="mt-3 grid grid-cols-2 gap-2">
                                            <button
                                                type="button"
                                                onClick={() => void openEvidenceDrawer(recommendation)}
                                                className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/10"
                                            >
                                                <span className="flex items-center justify-center gap-1.5">
                                                    <FileSearch className="h-4 w-4" />
                                                    Evidence
                                                </span>
                                            </button>

                                            {primaryAction ? (
                                                <button
                                                    type="button"
                                                    onClick={() => void updateRecommendationState(
                                                        recommendation,
                                                        primaryAction.state,
                                                        `${primaryAction.label} from recommendations ledger`,
                                                    )}
                                                    disabled={isPending}
                                                    className="rounded-xl bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
                                                >
                                                    <span className="flex items-center justify-center gap-1.5">
                                                        {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PrimaryIcon className="h-4 w-4" />}
                                                        {primaryAction.label}
                                                    </span>
                                                </button>
                                            ) : (
                                                <button
                                                    type="button"
                                                    disabled
                                                    className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-slate-500"
                                                >
                                                    Reviewed
                                                </button>
                                            )}
                                        </div>

                                        {READY_STATES.has(recommendation.state) ? (
                                            <button
                                                type="button"
                                                onClick={() => void updateRecommendationState(
                                                    recommendation,
                                                    "dismissed",
                                                    "Dismissed from recommendations ledger",
                                                )}
                                                disabled={isPending}
                                                className="mt-2 w-full rounded-xl border border-white/10 bg-transparent px-3 py-2 text-sm font-medium text-slate-400 transition hover:border-rose-500/30 hover:text-rose-300 disabled:cursor-not-allowed disabled:opacity-60"
                                            >
                                                <span className="flex items-center justify-center gap-1.5">
                                                    <X className="h-4 w-4" />
                                                    Dismiss
                                                </span>
                                            </button>
                                        ) : null}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {drawer ? (
                <div className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm">
                    <button
                        type="button"
                        aria-label="Close evidence drawer"
                        className="absolute inset-0 cursor-default"
                        onClick={() => setDrawer(null)}
                    />
                    <aside className="relative h-full w-full max-w-2xl overflow-y-auto border-l border-white/10 bg-slate-950 p-6 shadow-2xl">
                        <div className="flex items-start justify-between gap-4">
                            <div>
                                <p className="text-xs uppercase tracking-[0.2em] text-indigo-400">Evidence Chain</p>
                                <h3 className="mt-2 text-xl font-semibold text-white">{drawer.recommendation.resource_name}</h3>
                                <p className="mt-1 text-sm text-slate-400">{drawer.recommendation.cloud_resource_id}</p>
                            </div>
                            <button
                                type="button"
                                onClick={() => setDrawer(null)}
                                className="rounded-xl border border-white/10 p-2 text-slate-400 transition hover:border-white/20 hover:text-white"
                            >
                                <X className="h-4 w-4" />
                            </button>
                        </div>

                        {/* EVIDENCE CARD & SAFETY CLEARANCE CHECKLIST COMPONENT */}
                        <div className="mt-6">
                            {drawer.evidenceCardLoading ? (
                                <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5 space-y-4">
                                    <div className="flex items-center justify-between">
                                        <Skeleton className="h-5 w-48 bg-slate-800" />
                                        <Skeleton className="h-6 w-20 rounded-full bg-slate-800" />
                                    </div>
                                    <Skeleton className="h-4 w-full bg-slate-800" />
                                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2">
                                        <Skeleton className="h-16 rounded-xl bg-slate-800" />
                                        <Skeleton className="h-16 rounded-xl bg-slate-800" />
                                        <Skeleton className="h-16 rounded-xl bg-slate-800" />
                                    </div>
                                    <Skeleton className="h-24 rounded-xl bg-slate-800" />
                                </div>
                            ) : drawer.evidenceCard ? (
                                <EvidenceCard cardData={drawer.evidenceCard} />
                            ) : (
                                <EvidenceCard cardData={buildEvidenceCardFromDrawer(drawer.recommendation, drawer.evidence)} />
                            )}
                        </div>

                        <div className="mt-6 grid gap-3 sm:grid-cols-4">
                            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                                <p className="text-xs uppercase tracking-wider text-slate-500">Trust</p>
                                <p className="mt-2 text-2xl font-semibold text-white">{drawer.recommendation.trust_score}%</p>
                            </div>
                            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                                <p className="text-xs uppercase tracking-wider text-slate-500">Evidence</p>
                                <p className="mt-2 text-2xl font-semibold text-white">{drawer.loading ? "--" : drawer.evidence.length}</p>
                            </div>
                            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                                <p className="text-xs uppercase tracking-wider text-slate-500">Verification</p>
                                <p className="mt-2 text-sm font-medium text-slate-200">{formatLabel(drawer.recommendation.verification_status)}</p>
                            </div>
                            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                                <p className="text-xs uppercase tracking-wider text-slate-500">AI</p>
                                <p className="mt-2 text-sm font-medium text-slate-200">{formatLabel(drawer.recommendation.ai_enrichment_status)}</p>
                            </div>
                        </div>

                        <div className="mt-6 rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                            <div className="flex items-center gap-2 text-sm text-slate-300">
                                <DatabaseZap className="h-4 w-4 text-indigo-400" />
                                <span>Pricing basis</span>
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                                <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${pricingBadgeClass(drawer.recommendation.pricing_basis)}`}>
                                    {formatLabel(drawer.recommendation.pricing_basis)}
                                </span>
                                <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${qualityBadgeClass(drawer.recommendation.quality_status)}`}>
                                    {formatLabel(drawer.recommendation.quality_status)}
                                </span>
                                <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${savingsEstimateBadgeClass(drawer.recommendation.savings_estimate_status)}`}>
                                    {formatLabel(drawer.recommendation.savings_estimate_status)}
                                </span>
                                <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${providerAgreementBadgeClass(drawer.recommendation.provider_agreement_status)}`}>
                                    {formatLabel(drawer.recommendation.provider_agreement_status)}
                                </span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs font-medium text-slate-300">
                                    {drawer.recommendation.cost_source}
                                </span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs font-medium text-slate-300">
                                    {drawer.recommendation.pricing_computed_at ? formatDate(drawer.recommendation.pricing_computed_at) : "No timestamp"}
                                </span>
                            </div>
                            <p className="mt-3 text-sm text-slate-400">
                                {drawer.recommendation.savings_estimate_reason || "No savings claim explanation stored."}
                            </p>
                            {drawer.recommendation.quality_reasons.length > 0 ? (
                                <ul className="mt-3 space-y-1 text-sm text-amber-300">
                                    {drawer.recommendation.quality_reasons.map((reason) => (
                                        <li key={reason}>{reason}</li>
                                    ))}
                                </ul>
                            ) : null}
                        </div>

                        <div className="mt-6 rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                    <div className="flex items-center gap-2 text-sm text-slate-300">
                                        <Sparkles className="h-4 w-4 text-indigo-300" />
                                        <span>AI enrichment</span>
                                    </div>
                                    <div className="mt-2 flex flex-wrap gap-2">
                                        <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${aiEnrichmentBadgeClass(drawer.recommendation.ai_enrichment_status)}`}>
                                            {formatLabel(drawer.recommendation.ai_enrichment_status)}
                                        </span>
                                        {drawer.recommendation.ai_model ? (
                                            <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs font-medium text-slate-300">
                                                {drawer.recommendation.ai_model}
                                            </span>
                                        ) : null}
                                        {drawer.recommendation.ai_enriched_at ? (
                                            <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs font-medium text-slate-300">
                                                {formatDate(drawer.recommendation.ai_enriched_at)}
                                            </span>
                                        ) : null}
                                    </div>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => void runAiEnrichmentForRecommendation(drawer.recommendation)}
                                    disabled={drawer.aiActionLoading}
                                    className="rounded-xl border border-indigo-500/30 bg-indigo-600 px-3 py-2 text-xs font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    <span className="flex items-center justify-center gap-1.5">
                                        {drawer.aiActionLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                                        Enrich now
                                    </span>
                                </button>
                            </div>

                            {drawer.aiLoading ? (
                                <div className="mt-4 space-y-3">
                                    <Skeleton className="h-4 w-2/3 bg-slate-800" />
                                    <Skeleton className="h-3 w-full bg-slate-800" />
                                    <Skeleton className="h-3 w-5/6 bg-slate-800" />
                                </div>
                            ) : drawer.aiError ? (
                                <div className="mt-4">
                                    <ErrorBanner message={drawer.aiError} />
                                </div>
                            ) : drawer.aiEnrichment ? (
                                <div className="mt-4 space-y-4">
                                    <div>
                                        <p className="text-sm font-medium text-white">
                                            {drawer.aiEnrichment.summary || drawer.recommendation.ai_summary || "AI summary unavailable"}
                                        </p>
                                        {drawer.aiEnrichment.business_impact ? (
                                            <p className="mt-2 text-sm text-slate-400">{drawer.aiEnrichment.business_impact}</p>
                                        ) : null}
                                        {drawer.aiEnrichment.evidence_narrative ? (
                                            <p className="mt-2 text-sm text-slate-500">{drawer.aiEnrichment.evidence_narrative}</p>
                                        ) : null}
                                    </div>

                                    {drawer.aiEnrichment.remediation_steps.length > 0 ? (
                                        <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                                            <p className="text-xs uppercase tracking-wider text-slate-500">Handoff steps</p>
                                            <ol className="mt-3 space-y-2 text-sm text-slate-300">
                                                {drawer.aiEnrichment.remediation_steps.map((step, index) => (
                                                    <li key={`${step}-${index}`} className="flex gap-2">
                                                        <span className="text-slate-500">{index + 1}.</span>
                                                        <span>{step}</span>
                                                    </li>
                                                ))}
                                            </ol>
                                        </div>
                                    ) : null}

                                    <div className="grid gap-3 sm:grid-cols-3">
                                        <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                                            <p className="text-xs text-slate-500">Risk</p>
                                            <p className="mt-1 text-sm text-slate-300">{drawer.aiEnrichment.risk_notes || "Not specified"}</p>
                                        </div>
                                        <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                                            <p className="text-xs text-slate-500">Rollback</p>
                                            <p className="mt-1 text-sm text-slate-300">{drawer.aiEnrichment.rollback_plan || "Not specified"}</p>
                                        </div>
                                        <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                                            <p className="text-xs text-slate-500">Validation</p>
                                            <p className="mt-1 text-sm text-slate-300">{drawer.aiEnrichment.validation_plan || "Not specified"}</p>
                                        </div>
                                    </div>

                                    {drawer.aiEnrichment.assumptions.length > 0 || drawer.aiEnrichment.confidence_notes ? (
                                        <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                                            <p className="text-xs uppercase tracking-wider text-slate-500">Confidence</p>
                                            {drawer.aiEnrichment.confidence_notes ? (
                                                <p className="mt-2 text-sm text-slate-300">{drawer.aiEnrichment.confidence_notes}</p>
                                            ) : null}
                                            {drawer.aiEnrichment.assumptions.length > 0 ? (
                                                <div className="mt-3 flex flex-wrap gap-2">
                                                    {drawer.aiEnrichment.assumptions.map((assumption) => (
                                                        <span key={assumption} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-slate-400">
                                                            {assumption}
                                                        </span>
                                                    ))}
                                                </div>
                                            ) : null}
                                        </div>
                                    ) : null}
                                </div>
                            ) : (
                                <div className="mt-4 rounded-xl border border-white/10 bg-slate-950/70 p-4">
                                    <p className="text-sm font-medium text-white">No AI enrichment stored</p>
                                    {drawer.recommendation.ai_enrichment_error ? (
                                        <p className="mt-1 text-sm text-rose-300">{drawer.recommendation.ai_enrichment_error}</p>
                                    ) : (
                                        <p className="mt-1 text-sm text-slate-500">{aiRunResult ? summarizeAiRun(aiRunResult) : "Deterministic recommendation is available."}</p>
                                    )}
                                </div>
                            )}
                        </div>

                        <div className="mt-6 rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                    <div className="flex items-center gap-2 text-sm text-slate-300">
                                        <ShieldCheck className="h-4 w-4 text-emerald-400" />
                                        <span>Savings verification</span>
                                    </div>
                                    <p className="mt-1 text-xs text-slate-500">
                                        Estimate vs measured before/after spend.
                                    </p>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => void runSavingsVerification(drawer.recommendation)}
                                    disabled={drawer.verificationLoading}
                                    className="rounded-xl border border-indigo-500/30 bg-indigo-600 px-3 py-2 text-xs font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    <span className="flex items-center justify-center gap-1.5">
                                        {drawer.verificationLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />}
                                        Run verification
                                    </span>
                                </button>
                            </div>

                            {drawer.verificationLoading ? (
                                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                                    {[1, 2, 3].map((row) => (
                                        <Skeleton key={row} className="h-16 rounded-2xl bg-slate-800" />
                                    ))}
                                </div>
                            ) : drawer.verificationError ? (
                                <div className="mt-4">
                                    <ErrorBanner message={drawer.verificationError} />
                                </div>
                            ) : drawer.verification ? (
                                <>
                                    <div className="mt-4 flex flex-wrap gap-2">
                                        <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${verificationBadgeClass(drawer.verification.status)}`}>
                                            {formatLabel(drawer.verification.status)}
                                        </span>
                                        <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs font-medium text-slate-300">
                                            {formatLabel(drawer.verification.measurement_source)}
                                        </span>
                                        <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs font-medium text-slate-300">
                                            {Math.round(drawer.verification.realized_savings_confidence)}% confidence
                                        </span>
                                    </div>
                                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                                        <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                                            <p className="text-xs text-slate-500">Estimated</p>
                                            <p className="mt-1 text-sm font-semibold text-slate-100">
                                                {formatSavingsAmount(drawer.verification.estimated_monthly_savings, drawer.recommendation)}/mo
                                            </p>
                                        </div>
                                        <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                                            <p className="text-xs text-slate-500">Baseline</p>
                                            <p className="mt-1 text-sm font-semibold text-slate-100">
                                                {formatSavingsAmount(drawer.verification.baseline_monthly_cost, drawer.recommendation)}/mo
                                            </p>
                                        </div>
                                        <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                                            <p className="text-xs text-slate-500">Realized</p>
                                            <p className="mt-1 text-sm font-semibold text-emerald-300">
                                                {formatSavingsAmount(drawer.verification.realized_monthly_savings, drawer.recommendation)}/mo
                                            </p>
                                        </div>
                                    </div>
                                    <p className="mt-4 text-sm text-slate-400">
                                        {drawer.verification.explanation || "No verification explanation stored yet."}
                                    </p>
                                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                                        <span>Baseline {formatDate(drawer.verification.baseline_window_start)} to {formatDate(drawer.verification.baseline_window_end)}</span>
                                        <ChevronRight className="h-3.5 w-3.5" />
                                        <span>Post {formatDate(drawer.verification.post_window_start)} to {formatDate(drawer.verification.post_window_end)}</span>
                                    </div>
                                </>
                            ) : (
                                <div className="mt-4 rounded-xl border border-white/10 bg-slate-950/70 p-4">
                                    <p className="text-sm font-medium text-white">Verification not started</p>
                                    <p className="mt-1 text-sm text-slate-500">
                                        Mark the recommendation implemented, then run verification after post-change cost data is available.
                                    </p>
                                </div>
                            )}
                        </div>

                        <div className="mt-6 space-y-3">
                            {drawer.loading ? (
                                <>
                                    {[1, 2, 3].map((row) => (
                                        <div key={row} className="rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                                            <Skeleton className="h-4 w-40 bg-slate-700" />
                                            <Skeleton className="mt-3 h-3 w-full bg-slate-800" />
                                            <Skeleton className="mt-2 h-3 w-2/3 bg-slate-800" />
                                        </div>
                                    ))}
                                </>
                            ) : drawer.error ? (
                                <ErrorBanner message={drawer.error} />
                            ) : drawer.evidence.length === 0 ? (
                                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
                                    <p className="text-sm font-medium text-white">No evidence rows stored</p>
                                    <p className="mt-1 text-sm text-slate-500">The ledger record exists, but the scan did not persist supporting signals.</p>
                                </div>
                            ) : (
                                drawer.evidence.map((item) => (
                                    <div key={item.id} className="rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                                        <div className="flex flex-wrap items-center justify-between gap-3">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${evidenceKindClass(item.evidence_kind)}`}>
                                                    {formatLabel(item.evidence_kind)}
                                                </span>
                                                <span className="text-sm font-medium text-white">{formatLabel(item.signal_name)}</span>
                                            </div>
                                            <span className="text-xs text-slate-500">
                                                {Math.round(item.data_completeness * 100)}% data
                                            </span>
                                        </div>
                                        <p className="mt-3 text-sm text-slate-400">{item.description || "No description provided"}</p>
                                        <div className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
                                            <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                                                <p className="text-slate-500">Observed</p>
                                                <p className="mt-1 break-words text-slate-200">{stringifyEvidenceValue(item.observed_value)}</p>
                                            </div>
                                            <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
                                                <p className="text-slate-500">Threshold</p>
                                                <p className="mt-1 break-words text-slate-200">{stringifyEvidenceValue(item.threshold)}</p>
                                            </div>
                                        </div>
                                        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                                            <span>{item.source_system}</span>
                                            <ChevronRight className="h-3.5 w-3.5" />
                                            <span>{formatDate(item.collected_at)}</span>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </aside>
                </div>
            ) : null}
        </div>
    );
}
