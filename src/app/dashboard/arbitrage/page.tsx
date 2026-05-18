"use client";

import { useEffect, useState } from "react";
import { RefreshCw, AlertCircle } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";

import { buildBackendAuthHeaders } from "@/app/api/_shared/fetch-with-backend-auth-fallback";
import { BillAnalysisView } from "@/components/dashboard/bill-analysis-view";
import type { BillAnalysisRecord } from "@/lib/api";
import {
    LAST_ANALYSIS_STORAGE_KEY,
    getBillAnalysisId,
} from "@/lib/bill-analysis-client-state";
import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";

type AnalysisResult = BillAnalysisRecord;
const HISTORY_LIMIT = 5;

type PreviousAnalysis = {
    analysis_id: string;
    filename: string;
    provider_detected: string;
    total_analyzed_spend: number;
    total_potential_savings: number;
    currency: string;
    created_at: string;
};

type BillAnalysesResponse = {
    analyses?: Array<AnalysisResult & PreviousAnalysis>;
};

function persistSidebarAnalysisId(analysisId: string | null) {
    if (typeof window === "undefined" || !analysisId) {
        return;
    }

    try {
        window.localStorage.setItem(LAST_ANALYSIS_STORAGE_KEY, analysisId);
    } catch {
        // Ignore storage failures in private browsing / restricted environments.
    }
}

function formatAnalysisAmountInInr(amount: number, sourceCurrency: string) {
    return formatInrCurrency(toDisplayInrAmount(amount, sourceCurrency || "USD"));
}

function LoadingState() {
    return (
        <div className="min-h-[40vh] flex items-center justify-center p-4 md:px-8 md:pb-8">
            <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-800/40 px-5 py-4 text-sm text-slate-300 backdrop-blur-xl">
                <RefreshCw className="h-4 w-4 animate-spin text-indigo-400" />
                Loading bill analysis...
            </div>
        </div>
    );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
    return (
        <div className="min-h-[40vh] flex flex-col items-center justify-center text-center gap-4 p-8">
            <div className="rounded-full bg-rose-500/10 p-4">
                <AlertCircle className="h-7 w-7 text-rose-400" />
            </div>
            <h2 className="text-xl text-white font-semibold">Failed to Load Analysis</h2>
            <p className="max-w-md text-slate-400">{message}</p>
            <button
                onClick={onRetry}
                className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
            >
                Retry
            </button>
        </div>
    );
}

const AUTH_RETRY_DELAYS_MS = [400, 800, 1600];

async function fetchWithAuthRetry(
    url: string,
    token: string | null,
    userId: string | null | undefined,
    options?: RequestInit,
): Promise<Response> {
    const requestUrl = typeof window === "undefined"
        ? url
        : new URL(url, window.location.origin).toString();
    const headers = new Headers(
        buildBackendAuthHeaders(requestUrl, {
            token,
            userId: userId ?? null,
        }, options?.headers),
    );

    for (let attempt = 0; attempt <= AUTH_RETRY_DELAYS_MS.length; attempt++) {
        const res = await fetch(url, { cache: "no-store", ...options, headers });
        if (res.status !== 401 || attempt === AUTH_RETRY_DELAYS_MS.length) {
            return res;
        }
        await new Promise((resolve) => setTimeout(resolve, AUTH_RETRY_DELAYS_MS[attempt]));
    }
    // Unreachable, but satisfies TS
    return fetch(url, { cache: "no-store", ...options, headers });
}

export default function ArbitragePage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { userId, getToken } = useAuth();
    const requestedTab = searchParams.get("tab") === "arbitrage" ? "arbitrage" : "executive";
    const [data, setData] = useState<AnalysisResult | null>(null);
    const [loading, setLoading] = useState(true);
    const [noData, setNoData] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [previousAnalyses, setPreviousAnalyses] = useState<PreviousAnalysis[]>([]);

    useEffect(() => {
        let isCancelled = false;

        const loadData = async () => {
            setNoData(false);
            setError(null);
            setLoading(true);

            const requestedAnalysisId = searchParams.get("id");

            let availableAnalyses: Array<AnalysisResult & PreviousAnalysis> = [];
            let token: string | null = null;

            try {
                token = await getToken();
                if (!token) {
                    try {
                        token = await getToken({ template: "default" });
                    } catch {
                        token = null;
                    }
                }
                const userParam = userId ? `&userId=${encodeURIComponent(userId)}` : "";
                const listRes = await fetchWithAuthRetry(`/api/bill-analyses?limit=${HISTORY_LIMIT}${userParam}`, token, userId);
                if (listRes.ok) {
                    const { analyses } = (await listRes.json()) as BillAnalysesResponse;
                    availableAnalyses = analyses || [];
                    if (!isCancelled) {
                        setPreviousAnalyses(
                            availableAnalyses.map((analysis) => ({
                                analysis_id: analysis.analysis_id || analysis.id,
                                filename: analysis.filename,
                                provider_detected: analysis.provider_detected,
                                total_analyzed_spend: analysis.total_analyzed_spend,
                                total_potential_savings: analysis.total_potential_savings,
                                currency: analysis.currency,
                                created_at: analysis.created_at,
                            })),
                        );
                    }
                } else {
                    const errBody = await listRes.json().catch(() => ({}));
                    if (process.env.NODE_ENV === "development") {
                        console.error("Bill analyses list failed:", listRes.status, errBody);
                    }
                }
            } catch (fetchError) {
                if (process.env.NODE_ENV === "development") {
                    console.error("Failed to load recent analyses:", fetchError);
                }
            }

            // Determine target ID: explicit param > latest from list > null
            const targetId = requestedAnalysisId
                || (availableAnalyses[0]
                    ? (availableAnalyses[0].analysis_id || availableAnalyses[0].id)
                    : null);

            if (targetId) {
                const detailUserParam = userId ? `?userId=${encodeURIComponent(userId)}` : "";
                try {
                    const detailRes = await fetchWithAuthRetry(
                        `/api/bill-analyses/${encodeURIComponent(targetId)}${detailUserParam}`,
                        token,
                        userId
                    );
                    if (detailRes.ok) {
                        const saved = await detailRes.json();
                        if (!isCancelled) {
                            setData(saved as AnalysisResult);
                            setLoading(false);
                            setNoData(false);
                            setError(null);
                        }
                        persistSidebarAnalysisId(targetId);
                        return;
                    }
                    // If the specific ID wasn't found but we have a list, try the latest
                    if (!isCancelled && detailRes.status === 404 && availableAnalyses[0] && requestedAnalysisId) {
                        const fallbackId = availableAnalyses[0].analysis_id || availableAnalyses[0].id;
                        if (fallbackId !== requestedAnalysisId) {
                            try {
                                const fallbackRes = await fetchWithAuthRetry(
                                    `/api/bill-analyses/${encodeURIComponent(fallbackId)}${detailUserParam}`,
                                    token,
                                    userId
                                );
                                if (fallbackRes.ok) {
                                    const fallbackData = await fallbackRes.json();
                                    if (!isCancelled) {
                                        setData(fallbackData as AnalysisResult);
                                        setLoading(false);
                                        setNoData(false);
                                        setError(null);
                                    }
                                    persistSidebarAnalysisId(fallbackId);
                                    return;
                                }
                            } catch {
                                // Fall through to error state
                            }
                        }
                    }
                    const errBody = await detailRes.json().catch(() => ({}));
                    if (!isCancelled) {
                        setError(errBody?.detail || `Analysis not found (${detailRes.status})`);
                        setLoading(false);
                    }
                    return;
                } catch (fetchError) {
                    if (!isCancelled) {
                        setError(fetchError instanceof Error ? fetchError.message : "Failed to load analysis");
                        setLoading(false);
                    }
                    return;
                }
            }

            // No analysis found.
            if (!isCancelled) {
                setData(null);
                setNoData(true);
                setLoading(false);
            }
        };

        void loadData();

        return () => {
            isCancelled = true;
        };
    }, [searchParams, userId, getToken]);

    const selectedAnalysisId =
        searchParams.get("id")
        || getBillAnalysisId(data)
        || previousAnalyses[0]?.analysis_id
        || "";

    return (
        <>
            {previousAnalyses.length > 0 && (
                <div className="bill-report-hide-print p-4 md:px-8 md:pt-8 md:pb-0">
                    <div className="mb-6 flex flex-col gap-4 rounded-2xl border border-white/10 bg-slate-800/40 p-4 backdrop-blur-xl md:flex-row md:items-center md:justify-between">
                        <div>
                            <p className="text-xs uppercase tracking-wider text-slate-400">History</p>
                            <p className="mt-1 text-sm text-slate-300">
                                Switch between your last {previousAnalyses.length} bill analyses.
                            </p>
                        </div>
                        <div className="min-w-[260px]">
                            <label htmlFor="bill-analysis-history" className="sr-only">
                                Bill analysis history
                            </label>
                            <select
                                id="bill-analysis-history"
                                value={selectedAnalysisId}
                                onChange={(event) => {
                                    const nextAnalysisId = event.target.value;
                                    router.push(`/dashboard/arbitrage?id=${encodeURIComponent(nextAnalysisId)}&tab=${requestedTab}`);
                                }}
                                className="w-full rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-sm text-white outline-none transition focus:border-indigo-500"
                            >
                                {previousAnalyses.map((analysis) => (
                                    <option key={analysis.analysis_id} value={analysis.analysis_id}>
                                        {analysis.filename} · {analysis.provider_detected} · {" "}
                                        {formatAnalysisAmountInInr(analysis.total_analyzed_spend, analysis.currency)}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                </div>
            )}

            {loading ? (
                <LoadingState />
            ) : error ? (
                <ErrorState message={error} onRetry={() => router.refresh()} />
            ) : (
                <BillAnalysisView
                    analysis={noData ? null : data}
                    preferredTab={requestedTab}
                />
            )}
        </>
    );
}
