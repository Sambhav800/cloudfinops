"use client";

import type { ComponentProps } from "react";
import { useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Cloud } from "lucide-react";
import type { getDashboardMetrics } from "@/lib/dashboard/data";
import type { FinanceBudgetEvent, FinanceForecastResponse } from "@/lib/api";
import { DashboardOverview } from "@/components/dashboard/overview";
import { FinOpsInsights } from "@/components/dashboard/finops-insights";
import { CostScoreSection } from "@/components/dashboard/cost-score-section";
import { RescanButton } from "@/components/dashboard/rescan-button";
import type {
    DashboardFinanceAccountSummary,
} from "@/components/dashboard/dashboard-finance-summary";
type DashboardOverviewProps = ComponentProps<typeof DashboardOverview>;
type DashboardStats = Awaited<ReturnType<typeof getDashboardMetrics>>;

const PROVIDER_COLORS = {
    aws: "#FF9900",
    azure: "#0078D4",
    gcp: "#4285F4",
} as const;

export function DashboardSectionsClient({
    stats,
    resources,
    wasteData,
    spendData,
    inventory,
    hasConnectedAccounts,
}: {
    stats: DashboardStats;
    resources: DashboardOverviewProps["resources"];
    wasteData: DashboardOverviewProps["wasteData"];
    spendData: DashboardOverviewProps["spendData"];
    inventory: DashboardOverviewProps["inventory"];
    hasConnectedAccounts: boolean;
    portfolioForecast?: unknown;
    portfolioBudgetEvent?: unknown;
    accountForecasts?: unknown[];
    financeLoadError?: string | null;
}) {
    const [activeProvider, setActiveProvider] = useState<"all" | "aws" | "azure" | "gcp">("all");

    const hasRenderableStats = Boolean(
        stats &&
        (
            stats.totalSpend > 0 ||
            stats.potentialSavings > 0 ||
            stats.totalResources > 0 ||
            stats.costOfInaction > 0 ||
            stats.providerCosts.length > 0
        )
    );
    const availableProviderCosts =
        stats?.providerCosts?.filter((providerCost) =>
            providerCost.spend > 0 ||
            providerCost.resources > 0 ||
            providerCost.savings > 0
        ) ?? [];
    const providerCount = Math.max(
        new Set(
            resources
                .map((resource) => String(resource.provider || "").trim().toLowerCase())
                .filter(Boolean)
        ).size,
        availableProviderCosts.length
    );
    const activeScopeLabel = activeProvider === "all" ? "All providers" : `${activeProvider.toUpperCase()} only`;
    const costTrackedResources = stats?.totalResources ?? resources.length;

    if (!hasConnectedAccounts) {
        return (
            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-8 shadow-2xl shadow-black/20">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div className="flex items-start gap-4">
                        <div className="rounded-2xl bg-indigo-400/10 p-3 text-indigo-300">
                            <Cloud className="h-6 w-6" />
                        </div>
                        <div>
                            <h2 className="text-2xl font-semibold text-white">Connect an account to start</h2>
                            <p className="mt-2 max-w-2xl text-sm text-slate-400">
                                Run your first authenticated cloud scan to populate monthly spend, savings, inventory,
                                waste distribution, and budget risk metrics from Mongo-backed scan results.
                            </p>
                        </div>
                    </div>

                    <Link
                        href="/dashboard/settings"
                        className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
                    >
                        Connect Cloud Account
                        <ArrowUpRight className="h-4 w-4" />
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <>
            <div className="mb-8 rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl shadow-2xl shadow-black/20">
                <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
                    <div className="space-y-4">
                        <div className="flex flex-wrap items-center gap-2">
                            <span className="inline-flex items-center rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-indigo-200">
                                Executive Overview
                            </span>
                            <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
                                {costTrackedResources.toLocaleString()} cost-tracked resources
                            </span>
                            <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-400">
                                {resources.length.toLocaleString()} inventory assets scanned
                            </span>
                            <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
                                {providerCount} provider{providerCount === 1 ? "" : "s"} connected
                            </span>
                        </div>

                        <div>
                            <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
                                Portfolio operating posture
                            </h2>
                            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                                Review spend, budget drift, savings opportunities, and resource health from one structured command surface built for weekly operating reviews.
                            </p>
                        </div>
                    </div>

                    <div className="flex flex-col gap-3 xl:items-end">
                        <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-3">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                                Provider Lens
                            </p>
                            <div className="mt-3 flex flex-wrap gap-2">
                                <button
                                    onClick={() => setActiveProvider("all")}
                                    className={`rounded-xl border px-4 py-2 text-sm font-medium transition-all ${
                                        activeProvider === "all"
                                            ? "border-indigo-500 bg-indigo-600 text-white shadow-lg shadow-indigo-500/20"
                                            : "border-white/10 bg-slate-900/50 text-slate-400 hover:border-white/20 hover:text-white"
                                    }`}
                                >
                                    All Providers
                                </button>

                                {availableProviderCosts.map((providerCost) => {
                                    const providerKey = providerCost.provider.toLowerCase();
                                    if (!(providerKey in PROVIDER_COLORS)) {
                                        return null;
                                    }

                                    const key = providerKey as keyof typeof PROVIDER_COLORS;
                                    const color = PROVIDER_COLORS[key];
                                    const isActive = activeProvider === key;

                                    return (
                                        <button
                                            key={key}
                                            onClick={() => setActiveProvider(key)}
                                            className={`flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition-all ${
                                                isActive
                                                    ? "bg-slate-800 text-white shadow-lg border-white/20"
                                                    : "border-white/10 bg-slate-900/50 text-slate-400 hover:border-white/20 hover:text-white"
                                            }`}
                                            style={
                                                isActive
                                                    ? {
                                                        borderColor: `${color}60`,
                                                        boxShadow: `0 4px 20px ${color}20`,
                                                    }
                                                    : undefined
                                            }
                                        >
                                            <span
                                                className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
                                                style={{ backgroundColor: color }}
                                            />
                                            {providerCost.provider.toUpperCase()}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                            <span className="text-xs text-slate-500">Viewing {activeScopeLabel}</span>
                            <RescanButton />
                        </div>
                    </div>
                </div>
            </div>

            {stats === null ? (
                <>
                    <CostScoreSection
                        totalSpend={0}
                        potentialSavings={0}
                        annualSavings={0}
                        aiConfidence={0}
                        totalResources={0}
                        costOfInaction={0}
                        providerCosts={[]}
                        isLoading
                        activeProvider={activeProvider}
                    />
                    <FinOpsInsights stats={null} activeProvider={activeProvider} />
                </>
            ) : hasRenderableStats ? (
                <>
                    <CostScoreSection
                        totalSpend={stats.totalSpend}
                        potentialSavings={stats.potentialSavings}
                        annualSavings={stats.annualSavings}
                        aiConfidence={stats.confidence?.score || 0}
                        totalResources={stats.totalResources}
                        costOfInaction={stats.costOfInaction}
                        providerCosts={stats.providerCosts || []}
                        activeProvider={activeProvider}
                    />
                    <FinOpsInsights stats={stats} activeProvider={activeProvider} />
                </>
            ) : (
                <div className="mb-8 rounded-2xl border border-white/10 bg-slate-900/50 p-5 text-sm text-slate-400 shadow-2xl shadow-black/20">
                    Run a scan to populate cost, confidence, and sustainability metrics for this dashboard.
                </div>
            )}

            <DashboardOverview
                stats={stats}
                resources={resources}
                wasteData={wasteData}
                spendData={spendData}
                inventory={inventory}
                activeProvider={activeProvider}
            />
        </>
    );
}
