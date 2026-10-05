"use client";

import { useState, useEffect } from "react";
import { PiggyBank, AlertTriangle } from "lucide-react";
import type { CommitmentRecommendationResponse, FinanceCommitmentsResponse } from "@/lib/api";
import { commitmentSupportLabel, commitmentSyncLabel, formatCommitmentDate, formatCommitmentMoney } from "@/lib/commitments/presentation";
import { loadCommitmentRecommendations, loadCommitmentSnapshot } from "@/lib/commitments/client";
import { Skeleton } from "@/components/ui/skeleton";
import { CommitmentsKpiStrip } from "@/components/dashboard/commitments/kpi-strip";
import { CoverageDonut } from "@/components/dashboard/commitments/coverage-donut";
import { InvestmentReturn } from "@/components/dashboard/commitments/investment-return";
import { ExpiryTimeline, type ExpiryBucket } from "@/components/dashboard/commitments/expiry-timeline";
import { InventoryTable, type FormattedCommitment } from "@/components/dashboard/commitments/inventory-table";
import { ProviderRecommendationsCard } from "@/components/dashboard/commitments/ai-copilot-card";
import { ScenarioComparison } from "@/components/dashboard/commitments/scenario-comparison";

function buildExpiryBuckets(commitments: FormattedCommitment[]): ExpiryBucket[] {
    const now = new Date();
    const buckets: ExpiryBucket[] = [];
    for (let i = 0; i < 6; i++) {
        const month = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + i, 1));
        buckets.push({
            month: month.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" }),
            count: 0,
            urgency: i === 0 ? "critical" : i <= 2 ? "warning" : "stable",
        });
    }
    for (const c of commitments) {
        if (c.status !== "active" || c.daysRemaining === null || c.daysRemaining <= 0) continue;
        const end = new Date(c.end_date);
        const monthDiff = (end.getUTCFullYear() - now.getUTCFullYear()) * 12 + end.getUTCMonth() - now.getUTCMonth();
        if (monthDiff >= 0 && monthDiff < 6) buckets[monthDiff].count++;
    }
    return buckets;
}

function RequestError({ title, message }: { title: string; message: string }) {
    return (
        <div role="alert" className="rounded-2xl border border-rose-500/20 bg-slate-900/50 p-6">
            <AlertTriangle className="mb-3 h-5 w-5 text-rose-400" />
            <h2 className="font-semibold text-white">{title}</h2>
            <p className="mt-2 text-sm text-slate-400">{message}</p>
            <button onClick={() => window.location.reload()} className="mt-4 rounded-xl bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500">Retry</button>
        </div>
    );
}

export default function CommitmentsPage() {
    const [snapshot, setSnapshot] = useState<FinanceCommitmentsResponse | null>(null);
    const [recommendation, setRecommendation] = useState<CommitmentRecommendationResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [recommendationLoading, setRecommendationLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [recommendationError, setRecommendationError] = useState<string | null>(null);

    useEffect(() => {
        const controller = new AbortController();
        const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(20_000)]);
        const loadInventory = async () => {
            try {
                const data = await loadCommitmentSnapshot(signal);
                if (!controller.signal.aborted) setSnapshot(data);
            } catch (requestError) {
                if (!controller.signal.aborted) setError(requestError instanceof Error ? requestError.message : "Failed to load commitments.");
            } finally {
                if (!controller.signal.aborted) setLoading(false);
            }
        };
        const loadRecommendations = async () => {
            try {
                const data = await loadCommitmentRecommendations(signal);
                if (!controller.signal.aborted) setRecommendation(data);
            } catch (requestError) {
                if (!controller.signal.aborted) setRecommendationError(requestError instanceof Error ? requestError.message : "Failed to load provider recommendations.");
            } finally {
                if (!controller.signal.aborted) setRecommendationLoading(false);
            }
        };
        void loadInventory();
        void loadRecommendations();
        return () => controller.abort();
    }, []);

    const formattedCommitments: FormattedCommitment[] = (snapshot?.commitments ?? []).map((item) => {
        const end = new Date(item.end_date).getTime();
        return {
            ...item,
            daysRemaining: Number.isFinite(end) ? Math.ceil((end - new Date().getTime()) / 86_400_000) : null,
            endDateStr: formatCommitmentDate(item.end_date),
            formattedAmount: formatCommitmentMoney(item.commitment_amount, item.currency),
            formattedSavings: formatCommitmentMoney(item.savings_amount, item.currency),
        };
    });
    const active = formattedCommitments.filter((c) => c.status === "active" && c.daysRemaining !== null && c.daysRemaining > 0);
    const criticalCount = active.filter((c) => c.daysRemaining !== null && c.daysRemaining < 30).length;
    const warningCount = active.filter((c) => c.daysRemaining !== null && c.daysRemaining >= 30 && c.daysRemaining < 90).length;

    return (
        <main className="min-h-screen w-full space-y-8 bg-slate-950 p-6 text-slate-200 md:p-10">
            <header>
                <div className="mb-2 flex items-center gap-3">
                    <PiggyBank className="h-6 w-6 shrink-0 text-emerald-400" />
                    <h1 className="text-3xl font-bold text-white">Commitment Command Center</h1>
                </div>
                <p className="text-slate-400">Reserved Instances, Savings Plans, and committed use discounts.</p>
            </header>

            {loading ? (
                <div aria-label="Loading commitment snapshot" className="space-y-6">
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        {[1, 2, 3, 4].map((key) => <Skeleton key={key} className="h-32 rounded-2xl bg-slate-800" />)}
                    </div>
                    <Skeleton className="h-60 rounded-2xl bg-slate-800" />
                </div>
            ) : error ? <RequestError title="Commitment snapshot unavailable" message={error} /> : snapshot ? (
                <section className="space-y-8">
                    <div>
                        <h2 className="mb-3 text-lg font-semibold text-white">Account sync status</h2>
                        {snapshot.integrations.length === 0 ? <p className="text-sm text-slate-400">No account sync status available.</p> : (
                            <ul className="divide-y divide-white/10">
                                {snapshot.integrations.map((integration) => (
                                    <li key={integration.integration_id} className="space-y-2 py-3 text-sm">
                                        <div className="flex flex-wrap items-center gap-3">
                                            <span className="font-medium uppercase text-white">{integration.provider}</span>
                                            <span className="break-all text-slate-400">{integration.integration_id}</span>
                                            <span className="rounded-full border border-white/10 px-2 py-1 text-xs text-amber-300">{commitmentSyncLabel(integration.status)}</span>
                                            {integration.stale && <span className="text-xs text-amber-300">Stale snapshot</span>}
                                            <span className="text-slate-400">{integration.commitment_count} commitments</span>
                                        </div>
                                        <p className="text-xs text-slate-400">{commitmentSupportLabel(integration.provider)}</p>
                                        <p className="text-xs text-slate-400">Last success: {formatCommitmentDate(integration.last_success_at, true)} | Last attempt: {formatCommitmentDate(integration.last_attempt_at, true)}</p>
                                        {integration.error && <p className="text-slate-400">{integration.error}</p>}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                    <CommitmentsKpiStrip summary={snapshot.summary} />
                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                        <CoverageDonut />
                        <InvestmentReturn summary={snapshot.summary} />
                        <ExpiryTimeline buckets={buildExpiryBuckets(formattedCommitments)} criticalCount={criticalCount} warningCount={warningCount} isEmpty={active.length === 0} />
                    </div>
                    <InventoryTable commitments={formattedCommitments} isLoading={false} />
                </section>
            ) : <RequestError title="Commitment snapshot unavailable" message="No snapshot returned." />}

            {recommendationLoading ? <Skeleton aria-label="Loading provider recommendations" className="h-60 rounded-2xl bg-slate-800" /> :
                recommendationError ? <RequestError title="Provider recommendations unavailable" message={recommendationError} /> :
                recommendation ? (
                    <section className="grid grid-cols-1 gap-6 lg:grid-cols-5">
                        <ProviderRecommendationsCard data={recommendation} />
                        <ScenarioComparison scenarios={recommendation.scenarios ?? []} currency={recommendation.currency} />
                    </section>
                ) : <RequestError title="Provider recommendations unavailable" message="No provider response returned." />}
        </main>
    );
}
