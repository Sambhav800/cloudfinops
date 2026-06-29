"use client";

import { Cpu, Zap, Palette, Moon, Activity, HelpCircle } from "lucide-react";

type WorkloadClassification = {
    resource_id: string;
    workload_type: string;
    confidence: number;
    reason: string;
    name?: string;
    instance_type?: string;
    provider?: string;
    monthly_cost?: number;
};

type Props = {
    workloads: WorkloadClassification[];
    loading?: boolean;
};

const WORKLOAD_CONFIG: Record<string, { icon: typeof Cpu; color: string; bg: string; label: string }> = {
    training: { icon: Cpu, color: "text-violet-400", bg: "bg-violet-400/10 border-violet-400/20", label: "Training" },
    inference: { icon: Zap, color: "text-cyan-400", bg: "bg-cyan-400/10 border-cyan-400/20", label: "Inference" },
    rendering: { icon: Palette, color: "text-pink-400", bg: "bg-pink-400/10 border-pink-400/20", label: "Rendering" },
    idle: { icon: Moon, color: "text-rose-400", bg: "bg-rose-400/10 border-rose-400/20", label: "Idle" },
    burst: { icon: Activity, color: "text-amber-400", bg: "bg-amber-400/10 border-amber-400/20", label: "Burst" },
    mixed: { icon: HelpCircle, color: "text-slate-400", bg: "bg-slate-400/10 border-slate-400/20", label: "Mixed" },
    unknown: { icon: HelpCircle, color: "text-slate-500", bg: "bg-slate-500/10 border-slate-500/20", label: "Unknown" },
};

export function GpuWorkloadBadges({ workloads, loading }: Props) {
    if (loading) {
        return (
            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                <div className="h-6 w-48 animate-pulse rounded bg-slate-700" />
                <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
                    {[1, 2, 3].map((i) => (
                        <div key={i} className="h-20 animate-pulse rounded-xl bg-slate-800" />
                    ))}
                </div>
            </div>
        );
    }

    if (!workloads || workloads.length === 0) {
        return null;
    }

    // Group by workload type for summary
    const grouped = workloads.reduce<Record<string, WorkloadClassification[]>>((acc, w) => {
        const type = w.workload_type || "unknown";
        if (!acc[type]) acc[type] = [];
        acc[type].push(w);
        return acc;
    }, {});

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
            <h3 className="mb-4 text-lg font-semibold text-white">Workload Classification</h3>

            {/* Summary badges */}
            <div className="mb-4 flex flex-wrap gap-2">
                {Object.entries(grouped).map(([type, items]) => {
                    const config = WORKLOAD_CONFIG[type] || WORKLOAD_CONFIG.unknown;
                    const Icon = config.icon;
                    return (
                        <div
                            key={type}
                            className={`flex items-center gap-2 rounded-full border px-3 py-1.5 ${config.bg}`}
                        >
                            <Icon className={`h-3.5 w-3.5 ${config.color}`} />
                            <span className={`text-sm font-medium ${config.color}`}>
                                {config.label}
                            </span>
                            <span className="text-xs text-slate-400">({items.length})</span>
                        </div>
                    );
                })}
            </div>

            {/* Per-instance list */}
            <div className="space-y-2">
                {workloads.slice(0, 10).map((w) => {
                    const config = WORKLOAD_CONFIG[w.workload_type] || WORKLOAD_CONFIG.unknown;
                    const Icon = config.icon;
                    return (
                        <div
                            key={w.resource_id}
                            className="flex items-center justify-between rounded-lg border border-white/5 bg-slate-800/50 px-4 py-2.5"
                        >
                            <div className="flex items-center gap-3">
                                <Icon className={`h-4 w-4 ${config.color}`} />
                                <div>
                                    <p className="text-sm font-medium text-white">{w.name || w.resource_id}</p>
                                    <p className="text-xs text-slate-400">
                                        {w.instance_type} · {w.provider?.toUpperCase()}
                                    </p>
                                </div>
                            </div>
                            <div className="text-right">
                                <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${config.bg} ${config.color}`}>
                                    {config.label}
                                </span>
                                <p className="mt-0.5 text-xs text-slate-500">
                                    {(w.confidence * 100).toFixed(0)}% conf
                                </p>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
