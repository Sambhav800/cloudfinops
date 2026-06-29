"use client";

import {
    CheckCircle,
    CheckCircle2,
    XCircle,
    AlertTriangle,
    IndianRupee,
    Server,
    Trash2,
    ArrowRight,
    Copy,
    Gem,
    Loader2,
    Play,
    Target,
    TrendingUp,
    X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
    ResponsiveContainer,
    LineChart,
    Line,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    Cell,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import type { BackendResourcesResponse } from "@/lib/api";
import type { ActionItem } from "@/lib/dashboard/data";
import {
    formatInrCurrency,
    normalizeResourceRows,
    toDisplayInrAmount,
    type ResourceRow,
} from "@/lib/resources/contract";

const actionTypeIcons: Record<string, typeof Server> = {
    terminate: Trash2,
    rightsize: Server,
    delete: Trash2,
    purchase_ri: IndianRupee,
    optimize: ArrowRight,
};

const PROVIDER_COLORS: Record<string, string> = {
    aws: "#FF9900",
    azure: "#0078D4",
    gcp: "#4285F4",
};

const CHART_STYLE = {
    gridColor: "rgba(255,255,255,0.06)",
    tickColor: "#475569",
    tooltipBg: "#0f172a",
    tooltipBorder: "rgba(255,255,255,0.1)",
    fontSize: 11,
};

const CAT_COLORS = [
    "#10b981",
    "#6366f1",
    "#f59e0b",
    "#06b6d4",
    "#8b5cf6",
    "#84cc16",
];

type StatusFilter = "all" | "pending" | "approved" | "rejected";
type SimulationResult = {
    currentState: string;
    proposedState: string;
    projectedMonthlySavings: number;
    projectedAnnualSavings: number;
    riskLabel: string;
    script: string;
    resource: ResourceRow | null;
};

type SimulationModalState =
    | { status: "loading"; action: ActionItem }
    | { status: "error"; action: ActionItem; message: string }
    | { status: "ready"; action: ActionItem; simulation: SimulationResult }
    | null;

function toMetricNumber(value: unknown): number {
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

function normalizeLookupValue(value: unknown): string {
    return String(value ?? "").trim().toLowerCase();
}

function resolveActionSourceCurrency(action: ActionItem): string {
    const metadata = action.metadata ?? {};
    const explicitCurrency = pickFirstString(
        metadata.currency,
        metadata.billing_currency,
        metadata.cost_currency,
        metadata.savings_currency,
    );
    if (explicitCurrency) {
        return explicitCurrency.toUpperCase();
    }

    const provider = normalizeLookupValue(
        metadata.provider ??
        metadata.cloud_provider ??
        metadata.cloudProvider ??
        action.provider,
    );
    return provider === "gcp" ? "INR" : "USD";
}

function getActionDisplaySavings(action: ActionItem): number {
    return toDisplayInrAmount(action.estimated_savings || 0, resolveActionSourceCurrency(action));
}

function formatExactCurrency(value: number, sourceCurrency = "INR"): string {
    const displayValue = toDisplayInrAmount(value, sourceCurrency);
    const hasFraction = Math.abs(displayValue % 1) > 0.001;
    return formatInrCurrency(displayValue, {
        minimumFractionDigits: hasFraction ? 2 : 0,
        maximumFractionDigits: hasFraction ? 2 : 0,
    });
}

function formatCompactCurrency(value: number): string {
    return formatInrCurrency(value, {
        notation: "compact",
        compactDisplay: "short",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });
}

function formatAnnualCurrency(value: number): string {
    const annualValue = value * 12;
    return `${formatCompactCurrency(annualValue)}/yr`;
}

function formatMonthlyCurrency(value: number): string {
    return `${formatInrCurrency(value, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    })}/mo`;
}

function formatDetailedMonthlyCurrency(value: number | null): string {
    if (value === null) {
        return "Unknown monthly cost";
    }

    return `${formatExactCurrency(value)}/mo`;
}

function formatDetailedAnnualCurrency(value: number): string {
    return `${formatExactCurrency(value)}/yr`;
}

function formatActionDate(createdAt: string): string {
    const parsed = new Date(createdAt);
    if (Number.isNaN(parsed.getTime())) {
        return createdAt;
    }
    return parsed.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
    });
}

function formatActionLabel(value: string): string {
    return value
        .split(/[_\s-]+/)
        .filter(Boolean)
        .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
        .join(" ");
}

function normalizeActionCopy(value: string): string {
    return value
        .replace(/\s+/g, " ")
        .replace(/[.!?]+$/g, "")
        .trim()
        .toLowerCase();
}

function shouldRenderActionDescription(action: ActionItem): boolean {
    const description = normalizeActionCopy(action.description || "");

    if (!description || description === "no description available") {
        return false;
    }

    const title = normalizeActionCopy(action.title || "");
    if (description === title) {
        return false;
    }

    const resourceName = normalizeActionCopy(action.resource_name || "");
    if (resourceName && description === resourceName) {
        return false;
    }

    return true;
}

function getImpactMeta(estimatedSavings: number) {
    if (estimatedSavings >= toDisplayInrAmount(500, "USD")) {
        return {
            label: "High",
            bg: "bg-rose-500/15",
            text: "text-rose-400",
        };
    }

    if (estimatedSavings >= toDisplayInrAmount(100, "USD")) {
        return {
            label: "Medium",
            bg: "bg-amber-500/15",
            text: "text-amber-400",
        };
    }

    return {
        label: "Low",
        bg: "bg-slate-500/15",
        text: "text-slate-400",
    };
}

function getEffortMeta(action: ActionItem) {
    const effortSource = `${action.action_type} ${action.title}`.toLowerCase();

    if (effortSource.includes("migrate") || effortSource.includes("reserved")) {
        return {
            label: "High",
            bg: "bg-rose-500/15",
            text: "text-rose-400",
        };
    }

    if (effortSource.includes("delete") || effortSource.includes("terminate")) {
        return {
            label: "Low",
            bg: "bg-emerald-500/15",
            text: "text-emerald-400",
        };
    }

    if (effortSource.includes("rightsize") || effortSource.includes("resize")) {
        return {
            label: "Medium",
            bg: "bg-amber-500/15",
            text: "text-amber-400",
        };
    }

    return {
        label: "Medium",
        bg: "bg-amber-500/15",
        text: "text-amber-400",
    };
}

function getStatusMeta(status: ActionItem["status"]) {
    if (status === "approved" || status === "completed") {
        return {
            label: status.charAt(0).toUpperCase() + status.slice(1),
            bg: "bg-emerald-500/15",
            text: "text-emerald-400",
            icon: CheckCircle,
        };
    }

    if (status === "rejected") {
        return {
            label: "Rejected",
            bg: "bg-rose-500/15",
            text: "text-rose-400",
            icon: XCircle,
        };
    }

    return {
        label: "Pending",
        bg: "bg-amber-500/15",
        text: "text-amber-400",
        icon: AlertTriangle,
    };
}

function computePriorityScore(action: ActionItem): number {
    const savings = getActionDisplaySavings(action);
    const created = new Date(action.created_at);
    const daysSinceCreation = Number.isNaN(created.getTime())
        ? 1
        : Math.max(1, Math.floor((Date.now() - created.getTime()) / 86_400_000));
    return savings * daysSinceCreation;
}

function getAgeIndicator(createdAt: string): { label: string; color: string } | null {
    const created = new Date(createdAt);
    if (Number.isNaN(created.getTime())) return null;
    const daysPending = Math.floor((Date.now() - created.getTime()) / 86_400_000);
    if (daysPending > 14) return { label: `${daysPending}d`, color: "text-rose-400 bg-rose-500/15" };
    if (daysPending > 7) return { label: `${daysPending}d`, color: "text-amber-400 bg-amber-500/15" };
    return { label: `${daysPending}d`, color: "text-emerald-400 bg-emerald-500/15" };
}

function getRiskBadge(riskLevel: string) {
    if (riskLevel === "high") {
        return "bg-rose-500/15 text-rose-400";
    }
    if (riskLevel === "medium") {
        return "bg-amber-500/15 text-amber-400";
    }
    return "bg-emerald-500/15 text-emerald-400";
}

function getResourceLifecycleLabel(resource: ResourceRow | null): string {
    if (!resource) {
        return "Current";
    }

    if (resource.status === "zombie" || resource.status === "waste") {
        return "Idle";
    }

    return "Running";
}

function getCurrentShape(action: ActionItem, resource: ResourceRow | null): string | null {
    const metadata = resource?.metadata ?? {};
    return pickFirstString(
        action.metadata.current_size,
        metadata.current_size,
        action.metadata.instance_type,
        metadata.instance_type,
        action.metadata.machine_type,
        metadata.machine_type,
        action.metadata.recommended_from,
        metadata.vm_size,
        metadata.sku,
        metadata.node_type,
        metadata.resource_state,
        resource?.service_type,
        action.resource_type,
    );
}

function getProposedShape(action: ActionItem): string | null {
    return pickFirstString(
        action.metadata.recommended_size,
        action.metadata.target_size,
        action.metadata.recommended_instance_type,
        action.metadata.recommended_state,
        action.metadata.target_state,
        action.metadata.commitment_type,
        action.metadata.recommended_commitment,
    );
}

function resolveCurrentMonthlyCost(action: ActionItem, resource: ResourceRow | null): number | null {
    if (resource) {
        return resource.cost;
    }

    const metadataCost = toMetricNumber(
        action.metadata.current_cost
        ?? action.metadata.monthly_cost
        ?? action.metadata.before_cost
        ?? action.metadata.cost,
    );
    return metadataCost > 0 ? toDisplayInrAmount(metadataCost, resolveActionSourceCurrency(action)) : null;
}

function resolveProjectedMonthlyCost(action: ActionItem, currentMonthlyCost: number | null): number | null {
    if (action.action_type === "stop" || action.action_type === "terminate") {
        return 0;
    }

    if (currentMonthlyCost === null) {
        return null;
    }

    return Math.max(currentMonthlyCost - Math.max(getActionDisplaySavings(action), 0), 0);
}

function buildCurrentStateLabel(action: ActionItem, resource: ResourceRow | null): string {
    const lifecycle = getResourceLifecycleLabel(resource);
    const shape = getCurrentShape(action, resource);
    const monthlyCost = resolveCurrentMonthlyCost(action, resource);

    if (shape && monthlyCost !== null) {
        return `${lifecycle} ${shape} @ ${formatDetailedMonthlyCurrency(monthlyCost)}`;
    }
    if (shape) {
        return `${lifecycle} ${shape}`;
    }
    if (monthlyCost !== null) {
        return `${action.resource_name} @ ${formatDetailedMonthlyCurrency(monthlyCost)}`;
    }

    return action.resource_name;
}

function buildProposedStateLabel(action: ActionItem, resource: ResourceRow | null): string {
    const projectedMonthlyCost = resolveProjectedMonthlyCost(action, resolveCurrentMonthlyCost(action, resource));
    const proposedShape = getProposedShape(action);

    if (action.action_type === "rightsize") {
        if (proposedShape && projectedMonthlyCost !== null) {
            return `Rightsize to ${proposedShape} @ ${formatDetailedMonthlyCurrency(projectedMonthlyCost)}`;
        }
        if (proposedShape) {
            return `Rightsize to ${proposedShape}`;
        }
    }

    if (action.action_type === "purchase_ri") {
        if (proposedShape && projectedMonthlyCost !== null) {
            return `Purchase ${proposedShape} @ ${formatDetailedMonthlyCurrency(projectedMonthlyCost)}`;
        }
        return `Purchase commitment coverage @ ${formatDetailedMonthlyCurrency(projectedMonthlyCost)}`;
    }

    if (action.action_type === "stop" || action.action_type === "terminate") {
        const actionLabel = formatActionLabel(action.action_type);
        return `${actionLabel} resource @ ${formatDetailedMonthlyCurrency(0)}`;
    }

    if (proposedShape && projectedMonthlyCost !== null) {
        return `${formatActionLabel(action.action_type)} to ${proposedShape} @ ${formatDetailedMonthlyCurrency(projectedMonthlyCost)}`;
    }
    if (projectedMonthlyCost !== null) {
        return `${formatActionLabel(action.action_type)} @ ${formatDetailedMonthlyCurrency(projectedMonthlyCost)}`;
    }

    return formatActionLabel(action.action_type);
}

function buildRiskLabel(action: ActionItem, resource: ResourceRow | null): string {
    const level = formatActionLabel(action.risk_level || "low");
    const currentShape = getCurrentShape(action, resource);
    const proposedShape = getProposedShape(action);

    if (action.action_type === "purchase_ri") {
        return `${level} — billing-only commitment change`;
    }

    if (action.action_type === "stop") {
        return `${level} — service impact if this resource is still in rotation`;
    }

    if (action.action_type === "terminate") {
        return `${level} — destructive change, confirm backups and dependencies`;
    }

    if (action.action_type === "rightsize" && currentShape && proposedShape) {
        const currentFamily = currentShape.split(".")[0]?.toLowerCase();
        const proposedFamily = proposedShape.split(".")[0]?.toLowerCase();
        if (currentFamily && proposedFamily && currentFamily === proposedFamily) {
            return `${level} — same family, reduced size`;
        }
    }

    if (action.action_type === "rightsize") {
        return `${level} — validate utilization before resizing`;
    }

    return `${level} — review dependency impact before execution`;
}

function buildSimulationResult(
    action: ActionItem,
    resource: ResourceRow | null,
    script: string,
): SimulationResult {
    const projectedMonthlySavings = Math.max(getActionDisplaySavings(action), 0);

    return {
        currentState: buildCurrentStateLabel(action, resource),
        proposedState: buildProposedStateLabel(action, resource),
        projectedMonthlySavings,
        projectedAnnualSavings: projectedMonthlySavings * 12,
        riskLabel: buildRiskLabel(action, resource),
        script,
        resource,
    };
}

function findBestMatchingResource(resources: ResourceRow[], action: ActionItem): ResourceRow | null {
    const actionResourceId = normalizeLookupValue(action.resource_id);
    const actionResourceName = normalizeLookupValue(action.resource_name);
    const actionResourceType = normalizeLookupValue(action.resource_type);
    const actionProvider = normalizeLookupValue(action.provider);

    let bestMatch: ResourceRow | null = null;
    let bestScore = 0;

    for (const resource of resources) {
        let score = 0;
        const resourceId = normalizeLookupValue(resource.id);
        const cloudResourceId = normalizeLookupValue(resource.cloud_resource_id);
        const resourceName = normalizeLookupValue(resource.resource_name);
        const resourceType = normalizeLookupValue(resource.service_type);
        const provider = normalizeLookupValue(resource.provider);

        if (actionResourceId && (actionResourceId === resourceId || actionResourceId === cloudResourceId)) {
            score += 8;
        }

        if (actionResourceName && actionResourceName === resourceName) {
            score += 6;
        } else if (
            actionResourceName
            && resourceName
            && (resourceName.includes(actionResourceName) || actionResourceName.includes(resourceName))
        ) {
            score += 3;
        }

        if (actionProvider && actionProvider === provider) {
            score += 2;
        }

        if (
            actionResourceType
            && resourceType
            && (resourceType.includes(actionResourceType) || actionResourceType.includes(resourceType))
        ) {
            score += 1;
        }

        if (score > bestScore) {
            bestScore = score;
            bestMatch = resource;
        }
    }

    return bestScore > 0 ? bestMatch : null;
}

export function PendingActionsList({ initialActions }: { initialActions: ActionItem[] }) {
    const router = useRouter();
    const [actions, setActions] = useState(initialActions);
    const [filter, setFilter] = useState<StatusFilter>("all");
    const [pendingMutationId, setPendingMutationId] = useState<string | null>(null);
    const [requestError, setRequestError] = useState<string | null>(null);
    const [simulationModal, setSimulationModal] = useState<SimulationModalState>(null);
    const [copiedScript, setCopiedScript] = useState(false);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [batchProcessing, setBatchProcessing] = useState(false);

    useEffect(() => {
        setActions(initialActions);
    }, [initialActions]);

    const mutatePendingAction = async (
        id: string,
        path: string,
        payload: Record<string, unknown>
    ) => {
        setPendingMutationId(id);
        setRequestError(null);

        try {
            const response = await fetch(path, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(payload),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(
                    typeof data?.detail === "string"
                        ? data.detail
                        : "Pending action update failed."
                );
            }

            return data as { success?: boolean; script?: string };
        } catch (error) {
            setRequestError(
                error instanceof Error ? error.message : "Pending action update failed."
            );
            return null;
        } finally {
            setPendingMutationId(null);
        }
    };

    const fetchJsonWithTimeout = async <T,>(
        input: string,
        init: RequestInit,
        timeoutMs = 15000,
    ): Promise<T> => {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        try {
            const response = await fetch(input, {
                ...init,
                signal: controller.signal,
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(
                    typeof data?.detail === "string"
                        ? data.detail
                        : `Request failed (${response.status})`
                );
            }
            return data as T;
        } catch (error) {
            if (error instanceof Error && error.name === "AbortError") {
                throw new Error("Request timed out. Please try again.");
            }
            throw error;
        } finally {
            clearTimeout(timeoutId);
        }
    };

    const handleApprove = async (id: string) => {
        const result = await mutatePendingAction(id, "/api/pending-actions/execute", {
            notification_id: id,
        });
        if (!result?.success) {
            return;
        }

        setActions((current) =>
            current.map((action) =>
                action.id === id ? { ...action, status: "approved" } : action
            )
        );
        setSimulationModal((current) => {
            if (!current || current.action.id !== id) {
                return current;
            }
            return null;
        });
        router.refresh();
    };

    const handleReject = async (id: string) => {
        const reasonInput = window.prompt(
            "Why are you rejecting this action?",
            "Rejected from dashboard"
        );
        if (reasonInput === null) {
            return;
        }

        const result = await mutatePendingAction(id, "/api/pending-actions/reject", {
            notification_id: id,
            reason: reasonInput.trim() || "Rejected from dashboard",
        });
        if (!result?.success) {
            return;
        }

        setActions((current) =>
            current.map((action) =>
                action.id === id ? { ...action, status: "rejected" } : action
            )
        );
        router.refresh();
    };

    const handleGenerateScript = async (id: string) => {
        const result = await mutatePendingAction(id, "/api/pending-actions/generate-fix", {
            notification_id: id,
        });
        if (!result?.success || !result.script) {
            return;
        }

        window.prompt("Generated fix script", result.script);
    };

    const handleSimulate = async (action: ActionItem) => {
        setSimulationModal({ status: "loading", action });
        setCopiedScript(false);
        setRequestError(null);

        try {
            const [resourcesPayload, scriptPayload] = await Promise.all([
                fetchJsonWithTimeout<BackendResourcesResponse>("/api/resources", {
                    method: "GET",
                    cache: "no-store",
                }),
                fetchJsonWithTimeout<{ success?: boolean; script?: string }>(
                    "/api/pending-actions/generate-fix",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({ notification_id: action.id }),
                    },
                ),
            ]);

            if (!scriptPayload.success || !scriptPayload.script) {
                throw new Error("Could not generate the CLI preview for this action.");
            }

            const resources = normalizeResourceRows(resourcesPayload.resources ?? []);
            const matchedResource = findBestMatchingResource(resources, action);

            setSimulationModal({
                status: "ready",
                action,
                simulation: buildSimulationResult(action, matchedResource, scriptPayload.script),
            });
        } catch (error) {
            const message = error instanceof Error ? error.message : "Could not simulate this action.";
            setSimulationModal({
                status: "error",
                action,
                message,
            });
        }
    };

    const handleCopyCommand = async () => {
        if (!simulationModal || simulationModal.status !== "ready") {
            return;
        }

        try {
            await navigator.clipboard.writeText(simulationModal.simulation.script);
            setCopiedScript(true);
            setTimeout(() => setCopiedScript(false), 2000);
        } catch (error) {
            setRequestError(
                error instanceof Error ? error.message : "Could not copy the generated command."
            );
        }
    };

    const filteredActions = (() => {
        const base = filter === "all" ? actions : actions.filter((action) => action.status === filter);
        return [...base].sort((a, b) => computePriorityScore(b) - computePriorityScore(a));
    })();

    const pendingFilteredIds = filteredActions
        .filter((a) => a.status === "pending")
        .map((a) => a.id);

    const allPendingSelected = pendingFilteredIds.length > 0
        && pendingFilteredIds.every((id) => selectedIds.has(id));

    const toggleSelectAll = () => {
        if (allPendingSelected) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(pendingFilteredIds));
        }
    };

    const toggleSelect = (id: string) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    };

    const handleBatchApprove = async () => {
        setBatchProcessing(true);
        for (const id of selectedIds) {
            const result = await mutatePendingAction(id, "/api/pending-actions/execute", {
                notification_id: id,
            });
            if (!result?.success) break;
            setActions((current) =>
                current.map((action) =>
                    action.id === id ? { ...action, status: "approved" } : action
                )
            );
        }
        setSelectedIds(new Set());
        setBatchProcessing(false);
        router.refresh();
    };

    const handleBatchReject = async () => {
        setBatchProcessing(true);
        for (const id of selectedIds) {
            const result = await mutatePendingAction(id, "/api/pending-actions/reject", {
                notification_id: id,
                reason: "Batch rejected from dashboard",
            });
            if (!result?.success) break;
            setActions((current) =>
                current.map((action) =>
                    action.id === id ? { ...action, status: "rejected" } : action
                )
            );
        }
        setSelectedIds(new Set());
        setBatchProcessing(false);
        router.refresh();
    };

    const totalIdentified = actions.reduce(
        (sum, action) => sum + getActionDisplaySavings(action),
        0
    );

    const totalRealized = actions
        .filter((action) => action.status === "approved" || action.status === "completed")
        .reduce((sum, action) => sum + getActionDisplaySavings(action), 0);

    const totalPotential = actions
        .filter((action) => action.status !== "approved" && action.status !== "completed")
        .reduce((sum, action) => sum + getActionDisplaySavings(action), 0);

    const realizationRate =
        totalIdentified > 0 ? Math.round((totalRealized / totalIdentified) * 100) : 0;

    const monthlyData = (() => {
        const months: Record<string, { identified: number; realized: number }> = {};

        actions.forEach((action: ActionItem) => {
            const date = new Date(action.created_at || Date.now());
            const key = date.toLocaleDateString("en-US", {
                month: "short",
                year: "2-digit",
            });

            if (!months[key]) {
                months[key] = { identified: 0, realized: 0 };
            }

            months[key].identified += getActionDisplaySavings(action);

            if (action.status === "approved" || action.status === "completed") {
                months[key].realized += getActionDisplaySavings(action);
            }
        });

        if (Object.keys(months).length === 0) {
            const currentMonth = new Date().toLocaleDateString("en-US", {
                month: "short",
                year: "2-digit",
            });
            months[currentMonth] = {
                identified: totalIdentified,
                realized: totalRealized,
            };
        }

        return Object.entries(months).map(([month, values]) => ({
            month,
            ...values,
        }));
    })();

    const categoryData = (() => {
        const categories: Record<string, number> = {};

        actions.forEach((action: ActionItem) => {
            const raw = action.action_type || action.resource_type || "other";
            const label = formatActionLabel(raw);
            categories[label] = (categories[label] || 0) + getActionDisplaySavings(action);
        });

        return Object.entries(categories)
            .map(([name, savings]) => ({ name, savings }))
            .sort((left, right) => right.savings - left.savings)
            .slice(0, 6);
    })();

    return (
        <div className="space-y-6 p-6">
            {requestError && (
                <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-200">
                    {requestError}
                </div>
            )}

            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 mb-6">
                <div className="bg-slate-900/50 border border-white/10 border-t-2 border-t-indigo-500/60 rounded-2xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <div className="w-8 h-8 rounded-xl bg-indigo-500/15 flex items-center justify-center">
                            <Gem className="w-4 h-4 text-indigo-400" />
                        </div>
                        <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">
                            Identified
                        </p>
                    </div>
                    <p className="text-2xl font-bold text-white">
                        {formatCompactCurrency(totalIdentified)}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                        {formatAnnualCurrency(totalIdentified)} potential
                    </p>
                </div>

                <div className="bg-slate-900/50 border border-white/10 border-t-2 border-t-emerald-500/60 rounded-2xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <div className="w-8 h-8 rounded-xl bg-emerald-500/15 flex items-center justify-center">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        </div>
                        <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">
                            Realized
                        </p>
                    </div>
                    <p className="text-2xl font-bold text-emerald-400">
                        {formatCompactCurrency(totalRealized)}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">from approved actions</p>
                </div>

                <div className="bg-slate-900/50 border border-white/10 border-t-2 border-t-amber-500/60 rounded-2xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <div className="w-8 h-8 rounded-xl bg-amber-500/15 flex items-center justify-center">
                            <Target className="w-4 h-4 text-amber-400" />
                        </div>
                        <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">
                            Potential
                        </p>
                    </div>
                    <p className="text-2xl font-bold text-white">
                        {formatCompactCurrency(totalPotential)}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">still uncaptured</p>
                </div>

                <div className="bg-slate-900/50 border border-white/10 border-t-2 border-t-cyan-500/60 rounded-2xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <div className="w-8 h-8 rounded-xl bg-cyan-500/15 flex items-center justify-center">
                            <TrendingUp className="w-4 h-4 text-cyan-400" />
                        </div>
                        <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">
                            Rate
                        </p>
                    </div>
                    <p className="text-2xl font-bold text-white">{realizationRate}%</p>
                    <p className="text-xs text-slate-500 mt-1">realization rate</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <div className="bg-slate-900/50 border border-white/10 rounded-2xl p-5">
                    <h3 className="text-white font-semibold mb-0.5">Savings Trend</h3>
                    <p className="text-slate-500 text-xs mb-4">
                        Identified vs realized over time
                    </p>
                    {actions.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-48 rounded-xl bg-white/[0.02] border border-white/5 border-dashed gap-2">
                            <TrendingUp className="w-8 h-8 text-slate-700" />
                            <p className="text-slate-500 text-sm">No pending actions yet</p>
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height={200}>
                            <LineChart
                                data={monthlyData}
                                margin={{ top: 4, right: 8, left: 8, bottom: 0 }}
                            >
                                <CartesianGrid
                                    strokeDasharray="3 3"
                                    stroke={CHART_STYLE.gridColor}
                                    vertical={false}
                                />
                                <XAxis
                                    dataKey="month"
                                    tick={{
                                        fill: CHART_STYLE.tickColor,
                                        fontSize: CHART_STYLE.fontSize,
                                    }}
                                    axisLine={false}
                                    tickLine={false}
                                />
                                <YAxis
                                    tick={{
                                        fill: CHART_STYLE.tickColor,
                                        fontSize: CHART_STYLE.fontSize,
                                    }}
                                    axisLine={false}
                                    tickLine={false}
                                    width={52}
                                    tickFormatter={(value: number) => formatCompactCurrency(value)}
                                />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: CHART_STYLE.tooltipBg,
                                        border: `1px solid ${CHART_STYLE.tooltipBorder}`,
                                        borderRadius: "10px",
                                        fontSize: "12px",
                                    }}
                                    formatter={(value: number) => [
                                        formatExactCurrency(Number(value)),
                                        "",
                                    ]}
                                />
                                <Legend
                                    wrapperStyle={{ fontSize: "11px", color: "#64748b" }}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="identified"
                                    stroke="#6366f1"
                                    strokeWidth={2.5}
                                    dot={{ fill: "#6366f1", r: 3 }}
                                    activeDot={{ r: 5 }}
                                    name="Identified"
                                />
                                <Line
                                    type="monotone"
                                    dataKey="realized"
                                    stroke="#10b981"
                                    strokeWidth={2.5}
                                    dot={{ fill: "#10b981", r: 3 }}
                                    activeDot={{ r: 5 }}
                                    name="Realized"
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    )}
                </div>

                <div className="bg-slate-900/50 border border-white/10 rounded-2xl p-5">
                    <h3 className="text-white font-semibold mb-0.5">Savings by Category</h3>
                    <p className="text-slate-500 text-xs mb-4">
                        Total savings potential per action type
                    </p>
                    {categoryData.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-48 rounded-xl bg-white/[0.02] border border-white/5 border-dashed gap-2">
                            <TrendingUp className="w-8 h-8 text-slate-700" />
                            <p className="text-slate-500 text-sm">No actions yet</p>
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height={200}>
                            <BarChart
                                data={categoryData}
                                margin={{ top: 4, right: 8, left: 8, bottom: 4 }}
                            >
                                <CartesianGrid
                                    strokeDasharray="3 3"
                                    stroke={CHART_STYLE.gridColor}
                                    vertical={false}
                                />
                                <XAxis
                                    dataKey="name"
                                    tick={{ fill: CHART_STYLE.tickColor, fontSize: 10 }}
                                    axisLine={false}
                                    tickLine={false}
                                />
                                <YAxis
                                    tick={{
                                        fill: CHART_STYLE.tickColor,
                                        fontSize: CHART_STYLE.fontSize,
                                    }}
                                    axisLine={false}
                                    tickLine={false}
                                    width={52}
                                    tickFormatter={(value: number) => formatCompactCurrency(value)}
                                />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: CHART_STYLE.tooltipBg,
                                        border: `1px solid ${CHART_STYLE.tooltipBorder}`,
                                        borderRadius: "10px",
                                        fontSize: "12px",
                                    }}
                                    formatter={(value: number) => [
                                        formatExactCurrency(Number(value)),
                                        "Savings",
                                    ]}
                                    cursor={{ fill: "rgba(255,255,255,0.04)" }}
                                />
                                <Bar dataKey="savings" radius={[4, 4, 0, 0]}>
                                    {categoryData.map((_, index: number) => (
                                        <Cell
                                            key={index}
                                            fill={CAT_COLORS[index % CAT_COLORS.length]}
                                        />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
                {(["all", "pending", "approved", "rejected"] as const).map((tab) => {
                    const isActive = filter === tab;

                    return (
                        <button
                            key={tab}
                            onClick={() => setFilter(tab)}
                            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all border ${
                                isActive
                                    ? "bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-500/20"
                                    : "bg-slate-900/50 border-white/10 text-slate-400 hover:text-white hover:border-white/20"
                            }`}
                        >
                            {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                    );
                })}
            </div>

            {selectedIds.size > 0 && (
                <div className="flex items-center gap-3 rounded-2xl border border-indigo-500/30 bg-indigo-500/10 px-4 py-3">
                    <span className="text-sm font-medium text-indigo-200">
                        {selectedIds.size} selected
                    </span>
                    <div className="h-4 w-px bg-white/10" />
                    <button
                        onClick={() => void handleBatchApprove()}
                        disabled={batchProcessing}
                        className="flex items-center gap-1.5 rounded-lg bg-emerald-500/15 px-3 py-1.5 text-xs font-medium text-emerald-400 transition hover:bg-emerald-500/25 disabled:opacity-60"
                    >
                        <CheckCircle className="h-3.5 w-3.5" />
                        {batchProcessing ? "Processing..." : "Approve All"}
                    </button>
                    <button
                        onClick={() => void handleBatchReject()}
                        disabled={batchProcessing}
                        className="flex items-center gap-1.5 rounded-lg bg-rose-500/15 px-3 py-1.5 text-xs font-medium text-rose-400 transition hover:bg-rose-500/25 disabled:opacity-60"
                    >
                        <XCircle className="h-3.5 w-3.5" />
                        {batchProcessing ? "Processing..." : "Reject All"}
                    </button>
                    <button
                        onClick={() => setSelectedIds(new Set())}
                        disabled={batchProcessing}
                        className="ml-auto text-xs text-slate-400 transition hover:text-white"
                    >
                        Clear
                    </button>
                </div>
            )}

            <div className="bg-slate-900/50 border border-white/10 rounded-2xl overflow-hidden">
                {filteredActions.length === 0 ? (
                    <div className="p-8">
                        <div className="flex flex-col items-center justify-center h-48 rounded-xl bg-white/[0.02] border border-white/5 border-dashed gap-2">
                            <AlertTriangle className="w-8 h-8 text-slate-700" />
                            <p className="text-slate-500 text-sm">
                                No actions available for this filter
                            </p>
                        </div>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="min-w-[1320px] w-full">
                            <thead className="bg-white/[0.02] border-b border-white/10">
                                <tr>
                                    <th className="w-10 px-3 py-3">
                                        <input
                                            type="checkbox"
                                            checked={allPendingSelected && pendingFilteredIds.length > 0}
                                            onChange={toggleSelectAll}
                                            className="h-3.5 w-3.5 rounded border-white/20 bg-transparent text-indigo-600 focus:ring-indigo-500/30"
                                        />
                                    </th>
                                    {[
                                        "Action",
                                        "Provider",
                                        "Resource",
                                        "Monthly Savings",
                                        "Annual Savings",
                                        "Impact",
                                        "Effort",
                                        "Status",
                                        "Opened",
                                        "Actions",
                                    ].map((header) => (
                                        <th
                                            key={header}
                                            className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500"
                                        >
                                            {header}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {filteredActions.map((action) => {
                                    const Icon = actionTypeIcons[action.action_type] || Server;
                                    const monthlySavings = getActionDisplaySavings(action);
                                    const annualSavings = monthlySavings * 12;
                                    const impactMeta = getImpactMeta(monthlySavings);
                                    const effortMeta = getEffortMeta(action);
                                    const statusMeta = getStatusMeta(action.status);
                                    const StatusIcon = statusMeta.icon;
                                    const providerKey = (action.provider || "").toLowerCase();
                                    const providerColor =
                                        PROVIDER_COLORS[providerKey] ?? "#94a3b8";
                                    const showDescription = shouldRenderActionDescription(action);
                                    const isSimulating =
                                        simulationModal?.status === "loading"
                                        && simulationModal.action.id === action.id;
                                    const isBusy = pendingMutationId === action.id || isSimulating;

                                    return (
                                        <tr
                                            key={action.id}
                                            className="hover:bg-white/[0.02] transition-colors"
                                        >
                                            <td className="w-10 px-3 py-4 align-top">
                                                {action.status === "pending" ? (
                                                    <input
                                                        type="checkbox"
                                                        checked={selectedIds.has(action.id)}
                                                        onChange={() => toggleSelect(action.id)}
                                                        className="h-3.5 w-3.5 rounded border-white/20 bg-transparent text-indigo-600 focus:ring-indigo-500/30"
                                                    />
                                                ) : (
                                                    <span className="block h-3.5 w-3.5" />
                                                )}
                                            </td>
                                            <td className="px-4 py-4 align-top">
                                                <div className="flex items-start gap-3 min-w-[280px]">
                                                    <div
                                                        className={`p-2.5 rounded-xl ${
                                                            action.risk_level === "high"
                                                                ? "bg-rose-500/10"
                                                                : action.risk_level === "medium"
                                                                  ? "bg-amber-500/10"
                                                                  : "bg-emerald-500/10"
                                                        }`}
                                                    >
                                                        <Icon
                                                            className={`h-4 w-4 ${
                                                                action.risk_level === "high"
                                                                    ? "text-rose-400"
                                                                    : action.risk_level === "medium"
                                                                      ? "text-amber-400"
                                                                      : "text-emerald-400"
                                                            }`}
                                                        />
                                                    </div>
                                                    <div className="min-w-0">
                                                        <div className="flex items-center gap-2 flex-wrap">
                                                            <p className="text-sm font-semibold text-white">
                                                                {action.title}
                                                            </p>
                                                            <span
                                                                className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${getRiskBadge(action.risk_level)}`}
                                                            >
                                                                {action.risk_level || "low"} risk
                                                            </span>
                                                        </div>
                                                        {showDescription ? (
                                                            <p className="mt-1 max-w-md text-xs text-slate-400">
                                                                {action.description}
                                                            </p>
                                                        ) : null}
                                                        <div className="mt-2">
                                                            <span className="inline-flex rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide text-slate-400">
                                                                {formatActionLabel(action.action_type)}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="px-4 py-4 align-top">
                                                {action.provider ? (
                                                    <span
                                                        className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded"
                                                        style={{
                                                            backgroundColor: `${providerColor}25`,
                                                            color: providerColor,
                                                        }}
                                                    >
                                                        {action.provider.toUpperCase()}
                                                    </span>
                                                ) : (
                                                    <span className="text-sm text-slate-600">-</span>
                                                )}
                                            </td>
                                            <td className="px-4 py-4 align-top">
                                                <div className="min-w-[180px]">
                                                    <p className="text-sm text-slate-200">
                                                        {action.resource_name}
                                                    </p>
                                                    <p className="text-xs text-slate-500 mt-1">
                                                        {action.resource_type}
                                                    </p>
                                                </div>
                                            </td>
                                            <td className="px-4 py-4 align-top">
                                                <span className="text-emerald-400 font-mono text-sm">
                                                    {formatMonthlyCurrency(monthlySavings)}
                                                </span>
                                            </td>
                                            <td className="px-4 py-4 align-top">
                                                <span className="text-emerald-400 font-mono text-sm">
                                                    {formatDetailedAnnualCurrency(annualSavings)}
                                                </span>
                                            </td>
                                            <td className="px-4 py-4 align-top">
                                                <span
                                                    className={`text-xs font-medium px-2 py-0.5 rounded-full ${impactMeta.bg} ${impactMeta.text}`}
                                                >
                                                    {impactMeta.label}
                                                </span>
                                            </td>
                                            <td className="px-4 py-4 align-top">
                                                <span
                                                    className={`text-xs font-medium px-2 py-0.5 rounded-full ${effortMeta.bg} ${effortMeta.text}`}
                                                >
                                                    {effortMeta.label}
                                                </span>
                                            </td>
                                            <td className="px-4 py-4 align-top">
                                                <span
                                                    className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full ${statusMeta.bg} ${statusMeta.text}`}
                                                >
                                                    <StatusIcon className="h-3.5 w-3.5" />
                                                    {statusMeta.label}
                                                </span>
                                            </td>
                                            <td className="px-4 py-4 align-top">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-slate-400">
                                                        {formatActionDate(action.created_at)}
                                                    </span>
                                                    {action.status === "pending" && (() => {
                                                        const age = getAgeIndicator(action.created_at);
                                                        return age ? (
                                                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${age.color}`}>
                                                                {age.label}
                                                            </span>
                                                        ) : null;
                                                    })()}
                                                </div>
                                            </td>
                                            <td className="px-4 py-4 align-top">
                                                {action.status === "pending" ? (
                                                    <div className="flex flex-wrap justify-end gap-2 min-w-[380px]">
                                                        <button
                                                            onClick={() =>
                                                                void handleSimulate(action)
                                                            }
                                                            disabled={isBusy}
                                                            className="flex items-center gap-2 px-3 py-2 bg-white/5 text-slate-200 rounded-lg hover:bg-white/10 transition-colors disabled:opacity-60"
                                                        >
                                                            {isSimulating ? (
                                                                <Loader2 className="h-4 w-4 animate-spin" />
                                                            ) : (
                                                                <Play className="h-4 w-4" />
                                                            )}
                                                            {isSimulating ? "Loading..." : "Simulate"}
                                                        </button>
                                                        <button
                                                            onClick={() =>
                                                                void handleGenerateScript(action.id)
                                                            }
                                                            disabled={isBusy}
                                                            className="flex items-center gap-2 px-3 py-2 bg-indigo-500/10 text-indigo-300 rounded-lg hover:bg-indigo-500/20 transition-colors disabled:opacity-60"
                                                        >
                                                            <ArrowRight className="h-4 w-4" />
                                                            {pendingMutationId === action.id
                                                                ? "Generating..."
                                                                : "Generate Script"}
                                                        </button>
                                                        <button
                                                            onClick={() =>
                                                                void handleApprove(action.id)
                                                            }
                                                            disabled={isBusy}
                                                            className="flex items-center gap-2 px-3 py-2 bg-emerald-500/10 text-emerald-400 rounded-lg hover:bg-emerald-500/20 transition-colors disabled:opacity-60"
                                                        >
                                                            <CheckCircle className="h-4 w-4" />
                                                            {pendingMutationId === action.id
                                                                ? "Saving..."
                                                                : "Approve"}
                                                        </button>
                                                        <button
                                                            onClick={() =>
                                                                void handleReject(action.id)
                                                            }
                                                            disabled={isBusy}
                                                            className="flex items-center gap-2 px-3 py-2 bg-rose-500/10 text-rose-400 rounded-lg hover:bg-rose-500/20 transition-colors disabled:opacity-60"
                                                        >
                                                            <XCircle className="h-4 w-4" />
                                                            {pendingMutationId === action.id
                                                                ? "Saving..."
                                                                : "Reject"}
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <span className="text-sm text-slate-500">
                                                        No actions
                                                    </span>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {simulationModal ? (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm">
                    <div className="w-full max-w-3xl rounded-2xl border border-white/10 bg-slate-950 p-6 shadow-2xl">
                        <div className="flex items-start justify-between gap-4">
                            <div>
                                <p className="text-xs uppercase tracking-[0.2em] text-indigo-400">
                                    Simulation Preview
                                </p>
                                <h3 className="mt-2 text-xl font-semibold text-white">
                                    {simulationModal.action.resource_name}
                                </h3>
                                <p className="mt-1 text-sm text-slate-400">
                                    Review the live resource state and generated fix before marking this action done.
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={() => setSimulationModal(null)}
                                className="rounded-xl border border-white/10 p-2 text-slate-400 transition hover:border-white/20 hover:text-white"
                            >
                                <X className="h-4 w-4" />
                            </button>
                        </div>

                        {simulationModal.status === "loading" ? (
                            <div className="mt-6 space-y-4">
                                <div className="grid gap-4 md:grid-cols-2">
                                    {[0, 1].map((column) => (
                                        <div
                                            key={column}
                                            className="rounded-2xl border border-white/10 bg-slate-900/50 p-4"
                                        >
                                            <Skeleton className="h-3 w-24 bg-slate-700" />
                                            <Skeleton className="mt-3 h-6 w-48 bg-slate-800" />
                                            <Skeleton className="mt-3 h-4 w-full bg-slate-800" />
                                        </div>
                                    ))}
                                </div>
                                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                                    <Skeleton className="h-3 w-28 bg-slate-700" />
                                    <Skeleton className="mt-3 h-20 w-full bg-slate-800" />
                                </div>
                            </div>
                        ) : simulationModal.status === "error" ? (
                            <div className="mt-6 rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-200">
                                <p>{simulationModal.message}</p>
                                <div className="mt-4 flex gap-2">
                                    <button
                                        type="button"
                                        onClick={() => void handleSimulate(simulationModal.action)}
                                        className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
                                    >
                                        Retry
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setSimulationModal(null)}
                                        className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
                                    >
                                        Execute Later
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <>
                                <div className="mt-6 grid gap-4 md:grid-cols-2">
                                    <div className="rounded-2xl border border-white/10 border-t-2 border-t-rose-500/60 bg-slate-900/50 p-4">
                                        <p className="text-xs uppercase tracking-wider text-slate-500">
                                            Current state
                                        </p>
                                        <p className="mt-3 text-lg font-semibold text-white">
                                            {simulationModal.simulation.currentState}
                                        </p>
                                        <p className="mt-2 text-sm text-slate-400">
                                            Latest inventory match:{" "}
                                            <span className="text-slate-300">
                                                {simulationModal.simulation.resource?.resource_name ?? "Using notification metadata"}
                                            </span>
                                        </p>
                                    </div>
                                    <div className="rounded-2xl border border-white/10 border-t-2 border-t-emerald-500/60 bg-slate-900/50 p-4">
                                        <p className="text-xs uppercase tracking-wider text-slate-500">
                                            Proposed state
                                        </p>
                                        <p className="mt-3 text-lg font-semibold text-white">
                                            {simulationModal.simulation.proposedState}
                                        </p>
                                        <p className="mt-2 text-sm text-slate-400">
                                            Action type:{" "}
                                            <span className="text-slate-300">
                                                {formatActionLabel(simulationModal.action.action_type)}
                                            </span>
                                        </p>
                                    </div>
                                </div>

                                <div className="mt-4 grid gap-4 md:grid-cols-2">
                                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                                        <p className="text-xs uppercase tracking-wider text-slate-500">
                                            Projected savings
                                        </p>
                                        <p className="mt-3 text-lg font-semibold text-emerald-400">
                                            {formatDetailedMonthlyCurrency(simulationModal.simulation.projectedMonthlySavings)}
                                        </p>
                                        <p className="mt-2 text-sm text-slate-400">
                                            {formatDetailedMonthlyCurrency(simulationModal.simulation.projectedMonthlySavings)} (
                                            {formatDetailedAnnualCurrency(simulationModal.simulation.projectedAnnualSavings)})
                                        </p>
                                    </div>
                                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                                        <p className="text-xs uppercase tracking-wider text-slate-500">
                                            Risk label
                                        </p>
                                        <p className="mt-3 text-lg font-semibold text-white">
                                            {simulationModal.simulation.riskLabel}
                                        </p>
                                        <p className="mt-2 text-sm text-slate-400">
                                            Derived from the recommendation severity and the current resource shape.
                                        </p>
                                    </div>
                                </div>

                                <div className="mt-4 rounded-2xl border border-white/10 bg-slate-900/50 p-4">
                                    <div>
                                        <div>
                                            <p className="text-xs uppercase tracking-wider text-slate-500">
                                                CLI preview
                                            </p>
                                            <p className="mt-1 text-sm text-slate-400">
                                                Exact command generated by the existing fix generator.
                                            </p>
                                        </div>
                                    </div>
                                    <pre className="mt-4 max-h-[320px] overflow-auto rounded-2xl border border-white/10 bg-black/30 p-4 text-xs leading-6 text-slate-200">
                                        {simulationModal.simulation.script}
                                    </pre>
                                </div>

                                <div className="mt-6 flex flex-wrap justify-end gap-2">
                                    <button
                                        type="button"
                                        onClick={() => setSimulationModal(null)}
                                        className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
                                    >
                                        Execute Later
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => void handleCopyCommand()}
                                        className="rounded-xl border border-white/10 bg-transparent px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-white/20 hover:text-white"
                                    >
                                        Copy Command
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => void handleApprove(simulationModal.action.id)}
                                        disabled={pendingMutationId === simulationModal.action.id}
                                        className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                        <span className="flex items-center gap-1.5">
                                            {pendingMutationId === simulationModal.action.id ? (
                                                <Loader2 className="h-4 w-4 animate-spin" />
                                            ) : (
                                                <CheckCircle className="h-4 w-4" />
                                            )}
                                            Mark Done
                                        </span>
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            ) : null}
        </div>
    );
}
