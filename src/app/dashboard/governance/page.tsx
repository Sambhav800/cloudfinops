
import { getGovernanceAnalysis } from "@/lib/dashboard/data";
import { GovernanceViewClient } from "@/components/dashboard/governance-view-client";

export const dynamic = "force-dynamic";

export default async function GovernancePage() {
    const fallbackAnalysis = {
        score: { value: 0, trend: 'stable', rating: 'Fair' },
        tagging: { missingTags: 0, costImpact: 0, assets: [] },
        budget: { projectedSpend: 0, budgetLimit: 0, burnRate: 0, status: 'Safe', alert: 'No data yet.' },
        officeHours: { savings: 0, enabled: false, recommendation: 'Run a scan to generate insights.' },
        policies: [],
        trends: [],
        frameworkSummary: [],
        agentNotifications: [],
        resources: [],
        policyViolations: [],
    } as Awaited<ReturnType<typeof getGovernanceAnalysis>>;

    let analysis = fallbackAnalysis;
    let loadError: string | null = null;

    try {
        analysis = await getGovernanceAnalysis() || fallbackAnalysis;
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("Governance page load error:", error);
        }
        loadError = error instanceof Error ? error.message : "Failed to load governance data";
    }

    return (
        <div className="min-h-screen bg-slate-950 text-slate-200">
            <div className="px-6 py-4">
                <h1 className="text-2xl font-bold text-white">Governance Rules Engine</h1>
                <p className="text-sm text-slate-400">Prevention Layer: Detect, Predict, and Enforce</p>
            </div>
            <GovernanceViewClient initialAnalysis={analysis} loadError={loadError} />
        </div>
    );
}
