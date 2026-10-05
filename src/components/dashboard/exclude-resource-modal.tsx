"use client";

import { useState } from "react";
import { ShieldCheck, X } from "lucide-react";
import { shieldResource } from "@/app/actions/exclusions";

type Props = {
    resourceName: string;
    cloudResourceId: string;
    integrationId: string;
    provider: string;
    onClose: () => void;
};

const REASONS = [
    { value: "seasonal", label: "Seasonal", desc: "Used quarterly, semi-annually, or annually" },
    { value: "disaster_recovery", label: "Disaster Recovery", desc: "DR standby infrastructure" },
    { value: "compliance", label: "Compliance", desc: "Required for audits or regulatory checks" },
    { value: "batch_processing", label: "Batch Processing", desc: "Periodic batch jobs or pipelines" },
    { value: "other", label: "Other", desc: "Custom reason" },
] as const;

const FREQUENCIES = [
    { value: "quarterly", label: "Quarterly (every 3 months)" },
    { value: "semi_annual", label: "Semi-Annual (every 6 months)" },
    { value: "annual", label: "Annual (yearly)" },
] as const;

export function ExcludeResourceModal({
    resourceName,
    cloudResourceId,
    integrationId,
    provider,
    onClose,
}: Props) {
    const [reason, setReason] = useState("seasonal");
    const [reasonNote, setReasonNote] = useState("");
    const [frequency, setFrequency] = useState("quarterly");
    const [expiresInDays, setExpiresInDays] = useState(365);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setSubmitting(true);

        const result = await shieldResource({
            cloud_resource_id: cloudResourceId,
            integration_id: integrationId,
            resource_name: resourceName,
            provider,
            reason,
            reason_note: reasonNote.trim() || undefined,
            usage_schedule: { frequency: frequency as "quarterly" | "semi_annual" | "annual" | "custom" },
            expires_in_days: expiresInDays,
        });

        if (!result.success) {
            setError(result.error || "Failed to shield resource");
            setSubmitting(false);
            return;
        }

        onClose();
        window.location.reload();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="w-full max-w-md rounded-2xl border border-white/10 bg-slate-900 p-6 shadow-2xl">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10">
                            <ShieldCheck className="h-5 w-5 text-indigo-400" />
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold text-white">Shield Resource</h2>
                            <p className="text-xs text-slate-400 truncate max-w-[250px]">{resourceName}</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white">
                        <X className="h-5 w-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="mt-5 space-y-4">
                    {/* Reason */}
                    <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1.5">Why is this resource not a zombie?</label>
                        <div className="space-y-1.5">
                            {REASONS.map((r) => (
                                <label
                                    key={r.value}
                                    className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 transition-colors ${
                                        reason === r.value
                                            ? "border-indigo-500 bg-indigo-500/10"
                                            : "border-white/10 bg-slate-800 hover:border-white/20"
                                    }`}
                                >
                                    <input
                                        type="radio"
                                        name="reason"
                                        value={r.value}
                                        checked={reason === r.value}
                                        onChange={(e) => setReason(e.target.value)}
                                        className="sr-only"
                                    />
                                    <div>
                                        <p className="text-sm font-medium text-white">{r.label}</p>
                                        <p className="text-xs text-slate-500">{r.desc}</p>
                                    </div>
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Frequency */}
                    <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1">Expected Usage Frequency</label>
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

                    {/* Note */}
                    <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1">Note (optional)</label>
                        <input
                            type="text"
                            value={reasonNote}
                            onChange={(e) => setReasonNote(e.target.value)}
                            placeholder="e.g. Used during year-end financial close"
                            className="w-full rounded-lg border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
                        />
                    </div>

                    {/* Expiry */}
                    <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1">
                            Shield expires in: {expiresInDays} days ({Math.round(expiresInDays / 30)} months)
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
                        <p className="mt-1 text-xs text-slate-500">
                            After expiry, this resource will be evaluated normally again
                        </p>
                    </div>

                    {error && <p className="text-sm text-rose-400">{error}</p>}

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
                                <ShieldCheck className="h-4 w-4" />
                            )}
                            Shield from Detection
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
