"use client";

import { useEffect, useState } from "react";
import { RefreshCw, TriangleAlert } from "lucide-react";
import type { CommitmentRecommendationResponse } from "@/lib/api";
import { loadCommitmentRecommendations } from "@/lib/commitments/client";
import { Skeleton } from "@/components/ui/skeleton";
import { ProviderRecommendationsCard } from "./ai-copilot-card";
import { ScenarioComparison } from "./scenario-comparison";

interface CommitmentOptimizerCardProps {
    initialData?: CommitmentRecommendationResponse | null;
}

export function CommitmentOptimizerCard({ initialData }: CommitmentOptimizerCardProps) {
    const [data, setData] = useState<CommitmentRecommendationResponse | null>(initialData ?? null);
    const [loading, setLoading] = useState(!initialData);
    const [error, setError] = useState<string | null>(null);
    const [requestVersion, setRequestVersion] = useState(0);

    useEffect(() => {
        if (initialData && requestVersion === 0) return;
        const controller = new AbortController();
        const load = async () => {
            setLoading(true);
            setError(null);
            setData(null);
            try {
                const result = await loadCommitmentRecommendations(
                    AbortSignal.any([controller.signal, AbortSignal.timeout(20_000)]),
                );
                if (!controller.signal.aborted) setData(result);
            } catch (requestError) {
                if (!controller.signal.aborted) {
                    setError(requestError instanceof Error ? requestError.message : "Provider recommendations unavailable.");
                }
            } finally {
                if (!controller.signal.aborted) setLoading(false);
            }
        };
        void load();
        return () => controller.abort();
    }, [initialData, requestVersion]);

    return (
        <section id="commitment-optimizer-card" aria-labelledby="commitment-optimizer-title" className="min-w-0 space-y-4">
            <div className="flex items-center justify-between gap-3">
                <h2 id="commitment-optimizer-title" className="text-lg font-semibold text-white">Commitment Optimizer</h2>
                <button
                    type="button"
                    onClick={() => setRequestVersion((version) => version + 1)}
                    disabled={loading}
                    aria-label={error ? "Retry recommendations" : "Refresh recommendations"}
                    title={error ? "Retry recommendations" : "Refresh recommendations"}
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/10 text-slate-400 hover:bg-indigo-600 hover:text-white disabled:opacity-50"
                >
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                </button>
            </div>
            {loading ? (
                <div aria-label="Loading provider recommendations" aria-busy="true" className="grid min-h-64 gap-4 lg:grid-cols-2">
                    <Skeleton className="h-64 w-full rounded-2xl" />
                    <Skeleton className="h-64 w-full rounded-2xl" />
                </div>
            ) : error ? (
                <div role="alert" className="flex min-h-64 items-start gap-3 border-t border-white/10 py-6 text-sm text-rose-400">
                    <TriangleAlert className="h-5 w-5 shrink-0" aria-hidden="true" />
                    <div className="min-w-0 space-y-1">
                        <p className="font-semibold">Could not load commitment recommendations</p>
                        <p className="break-words">{error}</p>
                    </div>
                </div>
            ) : data ? (
                <>
                    <div className="grid min-w-0 gap-4 lg:grid-cols-5">
                        <ProviderRecommendationsCard data={data} />
                        <ScenarioComparison scenarios={data.status === "ready" ? data.scenarios ?? [] : []} currency={data.currency} />
                    </div>
                    {(data.important_notes ?? []).length > 0 && (
                        <ul className="list-inside list-disc space-y-1 text-xs text-slate-400">
                            {data.important_notes?.map((note) => <li key={note} className="break-words">{note}</li>)}
                        </ul>
                    )}
                </>
            ) : <p role="alert" className="min-h-64 text-sm text-slate-400">No provider response returned.</p>}
        </section>
    );
}
