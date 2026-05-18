"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
    Bot,
    Check,
    ChevronRight,
    Copy,
    Loader2,
    Play,
    Sparkles,
    X,
} from "lucide-react";

import type { BackendNotificationRecord, BackendNotificationsResponse } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";

type CopilotActionLabel = "Rightsize" | "Stop" | "RI Purchase" | "Optimize";

type RecommendationItem = {
    id: string;
    title: string;
    description: string;
    resourceName: string;
    resourceType: string;
    actionLabel: CopilotActionLabel;
    estimatedSavings: number;
    metadata: Record<string, unknown>;
};

type CopilotModalState =
    | { kind: "simulate"; item: RecommendationItem }
    | { kind: "script"; item: RecommendationItem; script: string }
    | null;

function toNumber(value: unknown): number {
    const parsed = typeof value === "number"
        ? value
        : typeof value === "string"
            ? Number(value)
            : 0;
    return Number.isFinite(parsed) ? parsed : 0;
}

function pickFirstString(...values: unknown[]): string | null {
    for (const value of values) {
        if (typeof value === "string" && value.trim()) {
            return value.trim();
        }
    }
    return null;
}

function normalizeActionLabel(notification: BackendNotificationRecord): CopilotActionLabel {
    const metadata = (notification.metadata as Record<string, unknown> | undefined) ?? {};
    const normalized = [
        String(metadata.action_type || "").trim().toLowerCase(),
        String(notification.action || "").trim().toLowerCase(),
        String(notification.recommendation || "").trim().toLowerCase(),
    ]
        .filter(Boolean)
        .join(" ");

    if (
        normalized.includes("savings plan")
        || normalized.includes("reserved instance")
        || normalized.includes("commitment")
        || normalized.includes("purchase_ri")
    ) {
        return "RI Purchase";
    }
    if (
        normalized.includes("stop")
        || normalized.includes("shutdown")
        || normalized.includes("deallocate")
        || normalized.includes("terminate")
        || normalized.includes("delete")
        || normalized.includes("remove")
    ) {
        return "Stop";
    }
    if (
        normalized.includes("rightsize")
        || normalized.includes("resize")
        || normalized.includes("downsize")
        || normalized.includes("smaller")
    ) {
        return "Rightsize";
    }
    return "Optimize";
}

function mapRecommendation(notification: BackendNotificationRecord): RecommendationItem {
    const metadata = (notification.metadata as Record<string, unknown> | undefined) ?? {};
    return {
        id: notification.id,
        title: pickFirstString(
            notification.recommendation,
            metadata.resource_name,
            `Action: ${notification.type}`,
        ) ?? `Action: ${notification.type}`,
        description: pickFirstString(
            metadata.description,
            metadata.ai_reasoning,
            notification.recommendation,
            "No description available",
        ) ?? "No description available",
        resourceName: pickFirstString(
            metadata.resource_name,
            notification.resource_id,
            notification.recommendation,
            "Unknown resource",
        ) ?? "Unknown resource",
        resourceType: pickFirstString(
            metadata.resource_type,
            notification.type,
            "Cloud Resource",
        ) ?? "Cloud Resource",
        actionLabel: normalizeActionLabel(notification),
        estimatedSavings: toNumber(metadata.estimated_savings ?? metadata.potential_savings),
        metadata,
    };
}

function resolveSavingsCurrency(metadata: Record<string, unknown>): string {
    const provider = String(metadata.provider ?? metadata.cloud_provider ?? metadata.cloudProvider ?? "").trim().toLowerCase();
    const fallbackCurrency = provider === "gcp" ? "INR" : "USD";

    return String(
        metadata.currency ??
        metadata.billing_currency ??
        metadata.cost_currency ??
        metadata.savings_currency ??
        fallbackCurrency
    ).toUpperCase();
}

function formatCurrency(value: number, metadata: Record<string, unknown> = {}) {
    return formatInrCurrency(toDisplayInrAmount(value, resolveSavingsCurrency(metadata)), {
        minimumFractionDigits: value % 1 === 0 ? 0 : 2,
        maximumFractionDigits: value % 1 === 0 ? 0 : 2,
    });
}

function buildCurrentState(item: RecommendationItem) {
    return pickFirstString(
        item.metadata.current_size,
        item.metadata.current_state,
        item.metadata.instance_type,
        item.metadata.machine_type,
        item.metadata.resource_state,
        item.resourceType,
    ) ?? item.resourceType;
}

function buildProposedState(item: RecommendationItem) {
    if (item.actionLabel === "Rightsize") {
        return pickFirstString(
            item.metadata.recommended_size,
            item.metadata.target_size,
            item.metadata.recommended_instance_type,
        ) ?? "Smaller recommended configuration";
    }

    if (item.actionLabel === "RI Purchase") {
        return pickFirstString(
            item.metadata.recommended_commitment,
            item.metadata.commitment_type,
            item.metadata.term,
        ) ?? "Commitment coverage added";
    }

    if (item.actionLabel === "Stop") {
        return pickFirstString(
            item.metadata.recommended_state,
            item.metadata.target_state,
        ) ?? "Resource stopped or removed";
    }

    return pickFirstString(
        item.metadata.recommended_state,
        item.metadata.recommended_size,
        item.metadata.target_state,
    ) ?? item.actionLabel;
}

export function SavingsCopilotCard() {
    const router = useRouter();
    const [items, setItems] = useState<RecommendationItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [pendingId, setPendingId] = useState<string | null>(null);
    const [modal, setModal] = useState<CopilotModalState>(null);
    const [copied, setCopied] = useState(false);

    const loadRecommendations = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch("/api/notifications?status=pending", {
                cache: "no-store",
            });

            if (!response.ok) {
                throw new Error(`Failed to load recommendations (${response.status})`);
            }

            const payload = (await response.json()) as BackendNotificationsResponse;
            const recommendations = (payload.notifications ?? [])
                .filter((notification) => notification.status === "pending")
                .filter((notification) => String(notification.type || "").trim().toLowerCase() === "cost_optimization")
                .map(mapRecommendation)
                .filter((recommendation) => recommendation.estimatedSavings > 0)
                .sort((left, right) => right.estimatedSavings - left.estimatedSavings);

            setItems(recommendations);
        } catch (loadError) {
            setError(loadError instanceof Error ? loadError.message : "Failed to load recommendations");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadRecommendations();
    }, [loadRecommendations]);

    const topRecommendations = useMemo(() => items.slice(0, 3), [items]);
    const recommendationCount = items.length;

    const postAction = useCallback(async (path: string, payload: Record<string, unknown>) => {
        const response = await fetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(typeof data?.detail === "string" ? data.detail : "Action failed");
        }
        return data as { success?: boolean; script?: string };
    }, []);

    const handleDismiss = useCallback(async (item: RecommendationItem) => {
        setPendingId(item.id);
        setError(null);

        try {
            const result = await postAction("/api/pending-actions/reject", {
                notification_id: item.id,
                reason: "Dismissed from Savings Copilot",
            });
            if (!result.success) {
                throw new Error("Dismiss failed");
            }
            setItems((current) => current.filter((entry) => entry.id !== item.id));
            router.refresh();
        } catch (dismissError) {
            setError(dismissError instanceof Error ? dismissError.message : "Dismiss failed");
        } finally {
            setPendingId(null);
        }
    }, [postAction, router]);

    const handleApprove = useCallback(async (item: RecommendationItem) => {
        setPendingId(item.id);
        setError(null);

        try {
            const generated = await postAction("/api/pending-actions/generate-fix", {
                notification_id: item.id,
            });
            if (!generated.success || !generated.script) {
                throw new Error("Could not generate CLI script");
            }

            const approved = await postAction("/api/pending-actions/execute", {
                notification_id: item.id,
            });
            if (!approved.success) {
                throw new Error("Could not approve recommendation");
            }

            setItems((current) => current.filter((entry) => entry.id !== item.id));
            setModal({ kind: "script", item, script: generated.script });
            router.refresh();
        } catch (approveError) {
            setError(approveError instanceof Error ? approveError.message : "Approval failed");
        } finally {
            setPendingId(null);
        }
    }, [postAction, router]);

    const handleCopy = useCallback(async () => {
        if (modal?.kind !== "script") {
            return;
        }

        await navigator.clipboard.writeText(modal.script);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }, [modal]);

    return (
        <>
            <div className="rounded-2xl border border-white/10 border-t-2 border-t-indigo-500/60 bg-slate-900/60 p-4 backdrop-blur-xl">
                <div className="mb-3 flex items-start justify-between gap-3">
                    <div>
                        <div className="flex items-center gap-2">
                            <Bot className="h-4 w-4 text-indigo-400" />
                            <span className="text-xs uppercase tracking-wider text-slate-400">
                                Savings Copilot
                            </span>
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                            AI-identified optimizations ready for review
                        </p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-right">
                        {loading ? (
                            <>
                                <Skeleton className="h-7 w-10 bg-slate-700" />
                                <Skeleton className="mt-2 h-3 w-16 bg-slate-800" />
                            </>
                        ) : (
                            <>
                                <p className="text-2xl font-bold text-white">{recommendationCount}</p>
                                <p className="text-[10px] text-slate-500">ready now</p>
                            </>
                        )}
                    </div>
                </div>

                {loading ? (
                    <div className="space-y-3">
                        {[1, 2, 3].map((row) => (
                            <div key={row} className="rounded-xl border border-white/10 bg-black/20 p-3">
                                <Skeleton className="h-4 w-36 bg-slate-700" />
                                <Skeleton className="mt-2 h-3 w-28 bg-slate-800" />
                                <div className="mt-3 flex gap-2">
                                    <Skeleton className="h-8 flex-1 bg-slate-800" />
                                    <Skeleton className="h-8 flex-1 bg-slate-800" />
                                    <Skeleton className="h-8 flex-1 bg-slate-800" />
                                </div>
                            </div>
                        ))}
                    </div>
                ) : error ? (
                    <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-300">
                        <p>{error}</p>
                        <button
                            type="button"
                            onClick={() => void loadRecommendations()}
                            className="mt-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-white transition hover:bg-white/10"
                        >
                            Retry
                        </button>
                    </div>
                ) : topRecommendations.length === 0 ? (
                    <div className="rounded-xl border border-white/10 bg-black/20 p-4">
                        <p className="text-sm font-medium text-white">No pending cost optimizations</p>
                        <p className="mt-1 text-xs text-slate-500">
                            New savings recommendations will appear here after the next scan.
                        </p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {topRecommendations.map((item) => {
                            const isPending = pendingId === item.id;
                            return (
                                <div
                                    key={item.id}
                                    className="rounded-xl border border-white/10 bg-black/20 p-3"
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0">
                                            <p className="truncate text-sm font-medium text-white">{item.resourceName}</p>
                                            <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                                                <span className="rounded-full border border-indigo-500/20 bg-indigo-500/10 px-2 py-0.5 text-indigo-300">
                                                    {item.actionLabel}
                                                </span>
                                                <span>{formatCurrency(item.estimatedSavings, item.metadata)}/mo</span>
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-sm font-semibold text-emerald-400">
                                                {formatCurrency(item.estimatedSavings, item.metadata)}
                                            </p>
                                            <p className="text-[10px] text-slate-500">monthly</p>
                                        </div>
                                    </div>
                                    <div className="mt-3 grid grid-cols-3 gap-2">
                                        <button
                                            type="button"
                                            onClick={() => setModal({ kind: "simulate", item })}
                                            disabled={isPending}
                                            className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-slate-300 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                            <span className="flex items-center justify-center gap-1.5">
                                                <Play className="h-3.5 w-3.5" />
                                                Simulate
                                            </span>
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => void handleApprove(item)}
                                            disabled={isPending}
                                            className="rounded-xl bg-indigo-600 px-3 py-2 text-xs font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                            <span className="flex items-center justify-center gap-1.5">
                                                {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                                                Approve
                                            </span>
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => void handleDismiss(item)}
                                            disabled={isPending}
                                            className="rounded-xl border border-white/10 bg-transparent px-3 py-2 text-xs font-medium text-slate-400 transition hover:border-white/20 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                            <span className="flex items-center justify-center gap-1.5">
                                                <X className="h-3.5 w-3.5" />
                                                Dismiss
                                            </span>
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {modal ? (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm">
                    <div className="w-full max-w-2xl rounded-2xl border border-white/10 bg-slate-950 p-6 shadow-2xl">
                        <div className="flex items-start justify-between gap-4">
                            <div>
                                <p className="text-xs uppercase tracking-[0.2em] text-indigo-400">
                                    {modal.kind === "simulate" ? "Simulation" : "CLI Script"}
                                </p>
                                <h3 className="mt-2 text-xl font-semibold text-white">
                                    {modal.item.resourceName}
                                </h3>
                                <p className="mt-1 text-sm text-slate-400">
                                    {modal.kind === "simulate"
                                        ? "Before/after view of the recommended change."
                                        : "Generated CLI script ready after approval."}
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={() => setModal(null)}
                                className="rounded-xl border border-white/10 p-2 text-slate-400 transition hover:border-white/20 hover:text-white"
                            >
                                <X className="h-4 w-4" />
                            </button>
                        </div>

                        {modal.kind === "simulate" ? (
                            <div className="mt-6 grid gap-4 md:grid-cols-2">
                                <div className="rounded-2xl border border-white/10 border-t-2 border-t-rose-500/60 bg-slate-900/50 p-4">
                                    <p className="text-xs uppercase tracking-wider text-slate-500">Before</p>
                                    <p className="mt-3 text-lg font-semibold text-white">{buildCurrentState(modal.item)}</p>
                                    <p className="mt-2 text-sm text-slate-400">{modal.item.description}</p>
                                </div>
                                <div className="rounded-2xl border border-white/10 border-t-2 border-t-emerald-500/60 bg-slate-900/50 p-4">
                                    <p className="text-xs uppercase tracking-wider text-slate-500">After</p>
                                    <p className="mt-3 text-lg font-semibold text-white">{buildProposedState(modal.item)}</p>
                                    <p className="mt-2 text-sm text-slate-400">
                                        Estimated savings: <span className="font-medium text-emerald-400">{formatCurrency(modal.item.estimatedSavings, modal.item.metadata)}/mo</span>
                                    </p>
                                </div>
                            </div>
                        ) : (
                            <div className="mt-6">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                    <div className="flex items-center gap-2 text-sm text-slate-400">
                                        <Sparkles className="h-4 w-4 text-indigo-400" />
                                        Existing `/generate-fix` output for this approved recommendation
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => void handleCopy()}
                                        className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-slate-300 transition hover:bg-white/10"
                                    >
                                        <span className="flex items-center gap-1.5">
                                            <Copy className="h-3.5 w-3.5" />
                                            {copied ? "Copied" : "Copy script"}
                                        </span>
                                    </button>
                                </div>
                                <pre className="max-h-[360px] overflow-auto rounded-2xl border border-white/10 bg-black/30 p-4 text-xs leading-6 text-slate-200">
                                    {modal.script}
                                </pre>
                            </div>
                        )}

                        <div className="mt-6 flex justify-end">
                            <button
                                type="button"
                                onClick={() => setModal(null)}
                                className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
                            >
                                <span className="flex items-center gap-1.5">
                                    Close
                                    <ChevronRight className="h-4 w-4" />
                                </span>
                            </button>
                        </div>
                    </div>
                </div>
            ) : null}
        </>
    );
}
