
import { RecommendationLedgerView } from "@/components/dashboard/recommendation-ledger-view";
import { ErrorBanner } from "@/components/dashboard/error-banner";
import { getRecommendationLedger } from "@/lib/recommendations/data";
import type { RecommendationListResponse } from "@/lib/recommendations/types";

export const dynamic = "force-dynamic";

export default async function PendingActionsPage() {
    let recommendations: RecommendationListResponse = { recommendations: [], count: 0 };
    let loadError: string | null = null;

    try {
        recommendations = await getRecommendationLedger();
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("Recommendations page load error:", error);
        }
        loadError = error instanceof Error ? error.message : "Failed to load recommendations";
    }

    const readyCount = recommendations.recommendations.filter((recommendation) =>
        recommendation.state === "detected"
        || recommendation.state === "evidence_ready"
        || recommendation.state === "provider_checked"
        || recommendation.state === "ready_for_review"
    ).length;

    return (
        <div className="min-h-screen">
            <div className="px-6 py-4">
                <h1 className="text-2xl font-bold text-white">Recommendations</h1>
                <p className="text-sm text-slate-400">{`${readyCount} recommendations ready for review from the canonical ledger`}</p>
            </div>
            <div className="space-y-4">
                {loadError && <ErrorBanner message={loadError} />}
                <RecommendationLedgerView initialData={recommendations} />
            </div>
        </div>
    );
}
