
import { getAllResources, getDashboardMetrics } from "@/lib/dashboard/data";
import { ResourcesViewClient } from "@/components/dashboard/resources-view-client";
import { formatInrCurrency } from "@/lib/resources/contract";

export const dynamic = "force-dynamic";

const ACTIONABLE_STATUSES = new Set(["zombie", "waste", "non_compliant"]);

function hasActionableStatus(status: string) {
    return ACTIONABLE_STATUSES.has((status || "unknown").toLowerCase());
}

export default async function ResourcesPage() {
    let resources = [] as Awaited<ReturnType<typeof getAllResources>>;
    let stats = null as Awaited<ReturnType<typeof getDashboardMetrics>>;
    let loadError: string | null = null;

    try {
        resources = await getAllResources();
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("Resources page load error:", error);
        }
        loadError = error instanceof Error ? error.message : "Failed to load resources";
    }

    try {
        stats = await getDashboardMetrics();
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("Resources stats load error:", error);
        }
    }

    const actionableResources = resources.filter((resource) => hasActionableStatus(resource.status));
    const costTrackedResources = stats?.totalResources ?? resources.filter((resource) =>
        resource.monthly_cost_available ||
        resource.cost_status === "catalog_estimate" ||
        resource.cost_status === "unavailable"
    ).length;

    // Calculations
    const rowLevelMtdCost = resources.reduce(
        (sum, resource) => sum + (resource.monthly_cost_available ? resource.monthly_cost : 0),
        0,
    );
    const knownMtdCost = (stats?.totalSpend ?? 0) > 0 ? stats?.totalSpend ?? 0 : rowLevelMtdCost;
    const mtdCostLabel = knownMtdCost > 0
        ? formatInrCurrency(knownMtdCost)
        : costTrackedResources > 0
            ? "No MTD actual yet"
            : "No direct charges";
    const providerOrder = ["aws", "azure", "gcp"] as const;
    const providerLabels: Record<(typeof providerOrder)[number], string> = {
        aws: "AWS",
        azure: "Azure",
        gcp: "GCP",
    };
    const providerSummary = providerOrder
        .map((provider) => {
            const count = resources.filter((resource) => resource.provider === provider).length;
            return count > 0 ? `${count} ${providerLabels[provider]}` : null;
        })
        .filter((value): value is string => value !== null)
        .join(" + ");

    return (
        <div className="min-h-screen bg-slate-950 text-slate-200">
            <div className="px-6 py-4">
                <h1 className="text-2xl font-bold text-white">Resources</h1>
                <p className="text-sm text-slate-400">
                    {resources.length > 0
                        ? `${resources.length} inventory assets across ${providerSummary}; ${costTrackedResources.toLocaleString()} cost-tracked resources`
                        : "No resources scanned yet"}
                </p>
            </div>

            <div className="p-6 space-y-6">
                {/* Stats */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="rounded-2xl border border-white/10 border-t-2 border-t-indigo-500/60 bg-slate-900/50 p-5 backdrop-blur-xl">
                        <p className="text-sm text-slate-400">Inventory Assets</p>
                        <p className="text-2xl font-bold text-white">{resources.length}</p>
                    </div>
                    <div className="rounded-2xl border border-white/10 border-t-2 border-t-rose-500/60 bg-slate-900/50 p-5 backdrop-blur-xl">
                        <p className="text-sm text-slate-400">Cost-tracked Resources</p>
                        <p className="text-2xl font-bold text-white">
                            {costTrackedResources.toLocaleString()}
                        </p>
                    </div>
                    <div className="rounded-2xl border border-white/10 border-t-2 border-t-amber-500/60 bg-slate-900/50 p-5 backdrop-blur-xl">
                        <p className="text-sm text-slate-400">Actionable Resources</p>
                        <p className="text-2xl font-bold text-rose-400">
                            {actionableResources.length}
                        </p>
                    </div>
                    <div className="rounded-2xl border border-white/10 border-t-2 border-t-emerald-500/60 bg-slate-900/50 p-5 backdrop-blur-xl">
                        <p className="text-sm text-slate-400">Known MTD Spend</p>
                        <p className="text-2xl font-bold text-emerald-400">{mtdCostLabel}</p>
                    </div>
                </div>

                {/* Health Status Banner */}
                {actionableResources.length === 0 && resources.length > 0 && (
                        <div className="flex items-center gap-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
                            <div className="p-3 bg-emerald-500/20 rounded-full">
                                <svg className="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            </div>
                            <div>
                                <p className="font-semibold text-emerald-300">Infrastructure health is stable</p>
                                <p className="text-sm text-slate-300">No actionable resources are currently flagged. Use the inventory below as the authoritative view of the current estate.</p>
                            </div>
                        </div>
                    )}

                {/* Interactive Resources View with Tabs for CFO */}
                <ResourcesViewClient initialResources={resources} loadError={loadError} />
            </div>
        </div>
    );
}
