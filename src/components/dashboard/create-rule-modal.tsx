"use client";

import { useState } from "react";
import { Filter, X } from "lucide-react";
import { createShieldRule } from "@/app/actions/exclusions";
import type { RuleMatch } from "@/lib/api";

type Props = {
    onClose: () => void;
};

const MATCH_TYPES = [
    { value: "tag", label: "Tag Match", desc: "Match resources by tag key/value" },
    { value: "name_pattern", label: "Name Pattern", desc: "Match resource names by regex" },
    { value: "service_type", label: "Service Type", desc: "Match all resources of a type" },
    { value: "region", label: "Region", desc: "Match all resources in a region" },
] as const;

const REASONS = [
    { value: "seasonal", label: "Seasonal" },
    { value: "disaster_recovery", label: "Disaster Recovery" },
    { value: "compliance", label: "Compliance" },
    { value: "batch_processing", label: "Batch Processing" },
    { value: "other", label: "Other" },
] as const;

const FREQUENCIES = [
    { value: "quarterly", label: "Quarterly" },
    { value: "semi_annual", label: "Semi-Annual" },
    { value: "annual", label: "Annual" },
    { value: "custom", label: "Custom" },
] as const;

export function CreateRuleModal({ onClose }: Props) {
    const [matchType, setMatchType] = useState<string>("tag");
    const [tagKey, setTagKey] = useState("");
    const [tagValue, setTagValue] = useState("");
    const [pattern, setPattern] = useState("");
    const [serviceType, setServiceType] = useState("");
    const [region, setRegion] = useState("");
    const [reason, setReason] = useState("seasonal");
    const [reasonNote, setReasonNote] = useState("");
    const [frequency, setFrequency] = useState("quarterly");
    const [expiresInDays, setExpiresInDays] = useState(365);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        const ruleMatch: RuleMatch = { match_type: matchType as RuleMatch["match_type"] };
        if (matchType === "tag") {
            if (!tagKey.trim()) { setError("Tag key is required"); return; }
            ruleMatch.tag_key = tagKey.trim();
            ruleMatch.tag_value = tagValue.trim() || null;
        } else if (matchType === "name_pattern") {
            if (!pattern.trim()) { setError("Pattern is required"); return; }
            ruleMatch.pattern = pattern.trim();
        } else if (matchType === "service_type") {
            if (!serviceType.trim()) { setError("Service type is required"); return; }
            ruleMatch.service_type = serviceType.trim();
        } else if (matchType === "region") {
            if (!region.trim()) { setError("Region is required"); return; }
            ruleMatch.region = region.trim();
        }

        setSubmitting(true);
        const result = await createShieldRule({
            rule_match: ruleMatch,
            reason,
            reason_note: reasonNote.trim() || undefined,
            usage_schedule: { frequency: frequency as "quarterly" | "semi_annual" | "annual" | "custom" },
            expires_in_days: expiresInDays,
        });

        if (!result.success) {
            setError(result.error || "Failed to create rule");
            setSubmitting(false);
            return;
        }

        onClose();
        window.location.reload();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-slate-900 p-6 shadow-2xl">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-500/10">
                            <Filter className="h-5 w-5 text-violet-400" />
                        </div>
                        <h2 className="text-lg font-semibold text-white">Create Shield Rule</h2>
                    </div>
                    <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white">
                        <X className="h-5 w-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                    {/* Match Type */}
                    <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1.5">Match Type</label>
                        <div className="grid grid-cols-2 gap-2">
                            {MATCH_TYPES.map((mt) => (
                                <button
                                    key={mt.value}
                                    type="button"
                                    onClick={() => setMatchType(mt.value)}
                                    className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                                        matchType === mt.value
                                            ? "border-indigo-500 bg-indigo-500/10 text-white"
                                            : "border-white/10 bg-slate-800 text-slate-400 hover:border-white/20"
                                    }`}
                                >
                                    <p className="font-medium">{mt.label}</p>
                                    <p className="mt-0.5 text-xs opacity-60">{mt.desc}</p>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Match Fields */}
                    <div className="space-y-3">
                        {matchType === "tag" && (
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-medium text-slate-400 mb-1">Tag Key</label>
                                    <input
                                        type="text"
                                        value={tagKey}
                                        onChange={(e) => setTagKey(e.target.value)}
                                        placeholder="e.g. Environment"
                                        className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium text-slate-400 mb-1">Tag Value (optional)</label>
                                    <input
                                        type="text"
                                        value={tagValue}
                                        onChange={(e) => setTagValue(e.target.value)}
                                        placeholder="e.g. DR"
                                        className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
                                    />
                                </div>
                            </div>
                        )}
                        {matchType === "name_pattern" && (
                            <div>
                                <label className="block text-xs font-medium text-slate-400 mb-1">Name Pattern (regex)</label>
                                <input
                                    type="text"
                                    value={pattern}
                                    onChange={(e) => setPattern(e.target.value)}
                                    placeholder="e.g. dr-.*|backup-.*"
                                    className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
                                />
                            </div>
                        )}
                        {matchType === "service_type" && (
                            <div>
                                <label className="block text-xs font-medium text-slate-400 mb-1">Service Type</label>
                                <input
                                    type="text"
                                    value={serviceType}
                                    onChange={(e) => setServiceType(e.target.value)}
                                    placeholder="e.g. Virtual Machine"
                                    className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
                                />
                            </div>
                        )}
                        {matchType === "region" && (
                            <div>
                                <label className="block text-xs font-medium text-slate-400 mb-1">Region</label>
                                <input
                                    type="text"
                                    value={region}
                                    onChange={(e) => setRegion(e.target.value)}
                                    placeholder="e.g. us-east-1"
                                    className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
                                />
                            </div>
                        )}
                    </div>

                    {/* Reason + Frequency */}
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1">Reason</label>
                            <select
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                            >
                                {REASONS.map((r) => (
                                    <option key={r.value} value={r.value}>{r.label}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1">Usage Frequency</label>
                            <select
                                value={frequency}
                                onChange={(e) => setFrequency(e.target.value)}
                                className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                            >
                                {FREQUENCIES.map((f) => (
                                    <option key={f.value} value={f.value}>{f.label}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {/* Note + Expiry */}
                    <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1">Note (optional)</label>
                        <input
                            type="text"
                            value={reasonNote}
                            onChange={(e) => setReasonNote(e.target.value)}
                            placeholder="e.g. Tax season batch jobs, active every January"
                            className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1">
                            Expires in: {expiresInDays} days ({Math.round(expiresInDays / 30)} months)
                        </label>
                        <input
                            type="range"
                            min={30}
                            max={1095}
                            step={30}
                            value={expiresInDays}
                            onChange={(e) => setExpiresInDays(Number(e.target.value))}
                            className="w-full accent-indigo-500"
                        />
                    </div>

                    {error && (
                        <p className="text-sm text-rose-400">{error}</p>
                    )}

                    <div className="flex justify-end gap-3 pt-2">
                        <button
                            type="button"
                            onClick={onClose}
                            className="rounded-lg border border-white/10 px-4 py-2 text-sm text-slate-400 hover:bg-slate-800 hover:text-white"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={submitting}
                            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                        >
                            {submitting ? (
                                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                            ) : (
                                <Filter className="h-4 w-4" />
                            )}
                            Create Rule
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
