"use client";

import { Calendar } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { CommitmentEmptyState } from "./empty-state";

export interface ExpiryBucket {
    month: string;
    count: number;
    urgency: "critical" | "warning" | "stable";
}

interface ExpiryTimelineProps {
    buckets: ExpiryBucket[];
    criticalCount: number;
    warningCount: number;
    isEmpty: boolean;
}

const urgencyColors: Record<string, string> = {
    critical: "#f87171",
    warning: "#fbbf24",
    stable: "#6366f1",
};

export function ExpiryTimeline({
    buckets,
    criticalCount,
    warningCount,
    isEmpty,
}: ExpiryTimelineProps) {
    if (isEmpty) {
        return (
            <CommitmentEmptyState
                icon={Calendar}
                title="No expiration data"
                subtitle="Active commitments will show their expiration timeline here."
            />
        );
    }

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl">
            <p className="mb-4 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                Expiration Radar
            </p>

            <div className="h-36">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={buckets} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                        <XAxis
                            dataKey="month"
                            tick={{ fill: "#64748b", fontSize: 10 }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <YAxis
                            allowDecimals={false}
                            tick={{ fill: "#64748b", fontSize: 10 }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: "#0f172a",
                                border: "1px solid rgba(255,255,255,0.1)",
                                borderRadius: "8px",
                                fontSize: "12px",
                            }}
                            labelStyle={{ color: "#94a3b8" }}
                            itemStyle={{ color: "#ffffff" }}
                        />
                        <Bar dataKey="count" radius={[4, 4, 0, 0]} name="Commitments">
                            {buckets.map((bucket, index) => (
                                <Cell key={index} fill={urgencyColors[bucket.urgency]} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>

            <div className="mt-3 flex items-center gap-3">
                {criticalCount > 0 && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/20 bg-rose-500/10 px-2.5 py-1 text-[10px] font-medium text-rose-400">
                        {criticalCount} expiring &lt;30d
                    </span>
                )}
                {warningCount > 0 && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-[10px] font-medium text-amber-400">
                        {warningCount} expiring &lt;90d
                    </span>
                )}
                {criticalCount === 0 && warningCount === 0 && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-medium text-emerald-400">
                        No known expirations within 90 days
                    </span>
                )}
            </div>
        </div>
    );
}
