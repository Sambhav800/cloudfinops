"use client";

import { useState } from "react";
import {
    Calendar,
    Clock,
    Filter,
    Plus,
    Search,
    ShieldCheck,
    ShieldOff,
    Sparkles,
    Trash2,
    X,
} from "lucide-react";
import { removeShield, acceptSuggestion, dismissSuggestionAction } from "@/app/actions/exclusions";
import { CreateRuleModal } from "@/components/dashboard/create-rule-modal";
import type { ResourceExclusion, ExclusionSuggestion, ExclusionStatsResponse } from "@/lib/api";

type Tab = "active" | "rules" | "suggestions" | "expired";

const REASON_LABELS: Record<string, { label: string; color: string }> = {
    seasonal: { label: "Seasonal", color: "text-blue-400 bg-blue-500/10 border-blue-500/20" },
    disaster_recovery: { label: "DR", color: "text-violet-400 bg-violet-500/10 border-violet-500/20" },
    compliance: { label: "Compliance", color: "text-amber-400 bg-amber-500/10 border-amber-500/20" },
    batch_processing: { label: "Batch", color: "text-teal-400 bg-teal-500/10 border-teal-500/20" },
    other: { label: "Other", color: "text-slate-400 bg-slate-500/10 border-slate-500/20" },
};

const FREQUENCY_LABELS: Record<string, string> = {
    quarterly: "Every 3 months",
    semi_annual: "Every 6 months",
    annual: "Yearly",
    custom: "Custom",
};

function ReasonBadge({ reason }: { reason: string }) {
    const config = REASON_LABELS[reason] ?? REASON_LABELS.other;
    return (
        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${config.color}`}>
            {config.label}
        </span>
    );
}

function ProviderBadge({ provider }: { provider: string | null }) {
    if (!provider) return null;
    const colors: Record<string, string> = {
        aws: "text-orange-400",
        azure: "text-blue-400",
        gcp: "text-red-400",
    };
    return (
        <span className={`text-xs font-medium uppercase ${colors[provider] ?? "text-slate-400"}`}>
            {provider}
        </span>
    );
}

type ExclusionsViewProps = {
    exclusions: ResourceExclusion[];
    stats: ExclusionStatsResponse | null;
    suggestions: ExclusionSuggestion[];
};

export function ExclusionsView({ exclusions, stats, suggestions }: ExclusionsViewProps) {
    const [activeTab, setActiveTab] = useState<Tab>("active");
    const [search, setSearch] = useState("");
    const [showRuleModal, setShowRuleModal] = useState(false);
    const [removing, setRemoving] = useState<string | null>(null);

    const activeExclusions = exclusions.filter((e) => e.is_active && !e.is_expired);
    const ruleExclusions = exclusions.filter((e) => e.type === "rule" && e.is_active);
    const expiredExclusions = exclusions.filter((e) => e.is_expired || !e.is_active);

    const filteredItems = (() => {
        const source =
            activeTab === "rules" ? ruleExclusions :
            activeTab === "expired" ? expiredExclusions :
            activeExclusions;

        if (!search.trim()) return source;
        const q = search.toLowerCase();
        return source.filter(
            (e) =>
                (e.resource_name || "").toLowerCase().includes(q) ||
                (e.reason_note || "").toLowerCase().includes(q),
        );
    })();

    const handleRemove = async (id: string) => {
        setRemoving(id);
        await removeShield(id);
        setRemoving(null);
        window.location.reload();
    };

    const tabs: { key: Tab; label: string; count: number }[] = [
        { key: "active", label: "Active Shields", count: activeExclusions.length },
        { key: "rules", label: "Rules", count: ruleExclusions.length },
        { key: "suggestions", label: "Suggestions", count: suggestions.length },
        { key: "expired", label: "Expired", count: expiredExclusions.length },
    ];

    return (
        <div className="space-y-6">
            {/* Stats strip */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard
                    icon={<ShieldCheck className="h-5 w-5 text-indigo-400" />}
                    label="Active Shields"
                    value={stats?.total_active ?? activeExclusions.length}
                />
                <StatCard
                    icon={<Filter className="h-5 w-5 text-violet-400" />}
                    label="Rules Active"
                    value={stats?.rules_active ?? ruleExclusions.length}
                />
                <StatCard
                    icon={<Sparkles className="h-5 w-5 text-amber-400" />}
                    label="Suggestions"
                    value={stats?.pending_suggestions ?? suggestions.length}
                />
                <StatCard
                    icon={<Clock className="h-5 w-5 text-rose-400" />}
                    label="Expiring Soon"
                    value={stats?.expiring_soon ?? 0}
                />
            </div>

            {/* Tabs + Search + Create Rule button */}
            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex gap-1">
                        {tabs.map((tab) => (
                            <button
                                key={tab.key}
                                onClick={() => setActiveTab(tab.key)}
                                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                                    activeTab === tab.key
                                        ? "bg-indigo-600 text-white"
                                        : "text-slate-400 hover:bg-slate-800 hover:text-white"
                                }`}
                            >
                                {tab.label}
                                {tab.count > 0 && (
                                    <span className="ml-1.5 rounded-full bg-white/10 px-1.5 py-0.5 text-xs">
                                        {tab.count}
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                            <input
                                type="text"
                                placeholder="Search exclusions..."
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                className="h-9 w-56 rounded-lg border border-white/10 bg-slate-800 pl-9 pr-3 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
                            />
                        </div>
                        <button
                            onClick={() => setShowRuleModal(true)}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
                        >
                            <Plus className="h-4 w-4" />
                            Create Rule
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="mt-6">
                    {activeTab === "suggestions" ? (
                        <SuggestionsList suggestions={suggestions} />
                    ) : filteredItems.length === 0 ? (
                        <EmptyState tab={activeTab} />
                    ) : (
                        <div className="space-y-3">
                            {filteredItems.map((exclusion) => (
                                <ExclusionRow
                                    key={exclusion.id}
                                    exclusion={exclusion}
                                    onRemove={handleRemove}
                                    removing={removing === exclusion.id}
                                />
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {showRuleModal && <CreateRuleModal onClose={() => setShowRuleModal(false)} />}
        </div>
    );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4">
            <div className="flex items-center gap-3">
                {icon}
                <div>
                    <p className="text-2xl font-semibold text-white">{value}</p>
                    <p className="text-xs text-slate-400">{label}</p>
                </div>
            </div>
        </div>
    );
}

function ExclusionRow({
    exclusion,
    onRemove,
    removing,
}: {
    exclusion: ResourceExclusion;
    onRemove: (id: string) => void;
    removing: boolean;
}) {
    const isRule = exclusion.type === "rule";
    const expiresDate = exclusion.expires_at ? new Date(exclusion.expires_at).toLocaleDateString() : "—";

    return (
        <div className="flex items-center justify-between rounded-xl border border-white/5 bg-slate-800/50 px-4 py-3 transition-colors hover:border-white/10">
            <div className="flex items-center gap-4">
                <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${isRule ? "bg-violet-500/10" : "bg-indigo-500/10"}`}>
                    {isRule ? (
                        <Filter className="h-4.5 w-4.5 text-violet-400" />
                    ) : (
                        <ShieldCheck className="h-4.5 w-4.5 text-indigo-400" />
                    )}
                </div>
                <div>
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-white">
                            {isRule
                                ? `Rule: ${exclusion.rule_match?.match_type} ${exclusion.rule_match?.tag_key ? `(${exclusion.rule_match.tag_key}=${exclusion.rule_match.tag_value})` : exclusion.rule_match?.pattern || exclusion.rule_match?.service_type || exclusion.rule_match?.region || ""}`
                                : exclusion.resource_name || exclusion.cloud_resource_id || "Unknown"}
                        </span>
                        <ProviderBadge provider={exclusion.provider} />
                    </div>
                    <div className="mt-0.5 flex items-center gap-3 text-xs text-slate-500">
                        <ReasonBadge reason={exclusion.reason} />
                        {exclusion.usage_schedule && (
                            <span className="flex items-center gap-1">
                                <Calendar className="h-3 w-3" />
                                {FREQUENCY_LABELS[exclusion.usage_schedule.frequency] || exclusion.usage_schedule.frequency}
                            </span>
                        )}
                        <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            Expires {expiresDate}
                        </span>
                        {exclusion.reason_note && (
                            <span className="max-w-[200px] truncate text-slate-500" title={exclusion.reason_note}>
                                {exclusion.reason_note}
                            </span>
                        )}
                    </div>
                </div>
            </div>
            <button
                onClick={() => onRemove(exclusion.id)}
                disabled={removing}
                className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-rose-500/10 hover:text-rose-400 disabled:opacity-50"
                title="Remove shield"
            >
                {removing ? (
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-transparent" />
                ) : (
                    <Trash2 className="h-4 w-4" />
                )}
            </button>
        </div>
    );
}

function SuggestionsList({ suggestions }: { suggestions: ExclusionSuggestion[] }) {
    const [processing, setProcessing] = useState<string | null>(null);

    if (suggestions.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-12 text-center">
                <Sparkles className="h-10 w-10 text-slate-600" />
                <p className="mt-3 text-sm text-slate-400">No suggestions yet</p>
                <p className="mt-1 text-xs text-slate-500">
                    Suggestions appear when resources are flagged zombie in 3+ consecutive scans
                </p>
            </div>
        );
    }

    const handleAccept = async (suggestion: ExclusionSuggestion) => {
        setProcessing(suggestion.id);
        await acceptSuggestion(suggestion.id, {
            cloud_resource_id: suggestion.cloud_resource_id,
            integration_id: suggestion.integration_id,
            resource_name: suggestion.resource_name,
            provider: suggestion.provider,
            reason: suggestion.suggested_reason,
        });
        setProcessing(null);
        window.location.reload();
    };

    const handleDismiss = async (id: string) => {
        setProcessing(id);
        await dismissSuggestionAction(id);
        setProcessing(null);
        window.location.reload();
    };

    return (
        <div className="space-y-3">
            {suggestions.map((suggestion) => (
                <div
                    key={suggestion.id}
                    className="flex items-center justify-between rounded-xl border border-amber-500/10 bg-amber-500/5 px-4 py-3"
                >
                    <div className="flex items-center gap-4">
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500/10">
                            <Sparkles className="h-4.5 w-4.5 text-amber-400" />
                        </div>
                        <div>
                            <span className="text-sm font-medium text-white">
                                {suggestion.resource_name || suggestion.cloud_resource_id}
                            </span>
                            <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">
                                <ProviderBadge provider={suggestion.provider} />
                                <span>
                                    Flagged {suggestion.consecutive_zombie_scans} consecutive scans
                                </span>
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => handleAccept(suggestion)}
                            disabled={processing === suggestion.id}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                        >
                            <ShieldCheck className="h-3.5 w-3.5" />
                            Shield
                        </button>
                        <button
                            onClick={() => handleDismiss(suggestion.id)}
                            disabled={processing === suggestion.id}
                            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-700 hover:text-white disabled:opacity-50"
                            title="Dismiss"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}

function EmptyState({ tab }: { tab: Tab }) {
    const messages: Record<Tab, { title: string; desc: string }> = {
        active: {
            title: "No active shields",
            desc: "Shield resources from the Resources page to prevent false zombie detection",
        },
        rules: {
            title: "No rules created",
            desc: "Create rules to automatically shield resources matching specific tags or patterns",
        },
        suggestions: {
            title: "No suggestions",
            desc: "Suggestions appear when resources are flagged zombie in 3+ consecutive scans",
        },
        expired: {
            title: "No expired shields",
            desc: "Expired shields will appear here for review",
        },
    };

    const msg = messages[tab];

    return (
        <div className="flex flex-col items-center justify-center py-12 text-center">
            <ShieldOff className="h-10 w-10 text-slate-600" />
            <p className="mt-3 text-sm text-slate-400">{msg.title}</p>
            <p className="mt-1 text-xs text-slate-500">{msg.desc}</p>
        </div>
    );
}
