"use client";

import { useState } from "react";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
} from "recharts";
import { Clock } from "lucide-react";

type HistoryPoint = {
    date: string;
    sm_pct: number | null;
    mem_pct: number | null;
    power_w: number | null;
    temp_c: number | null;
    sample_count: number;
};

type Props = {
    data: HistoryPoint[];
    resourceName?: string;
    loading?: boolean;
};

type Range = "7d" | "30d" | "90d";

export function GpuHistoricalTrends({ data, resourceName, loading }: Props) {
    const [range, setRange] = useState<Range>("7d");

    if (loading) {
        return (
            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                <div className="h-6 w-48 animate-pulse rounded bg-slate-700" />
                <div className="mt-4 h-48 animate-pulse rounded bg-slate-800" />
            </div>
        );
    }

    if (!data || data.length === 0) {
        return (
            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                <div className="flex items-center gap-2">
                    <Clock className="h-5 w-5 text-slate-400" />
                    <h3 className="text-lg font-semibold text-white">Historical Trends</h3>
                </div>
                <p className="mt-4 text-sm text-slate-400">
                    No historical data available yet. Metrics will appear after the first collection cycle.
                </p>
            </div>
        );
    }

    const rangeMap: Record<Range, number> = { "7d": 7, "30d": 30, "90d": 90 };
    const filteredData = data.slice(-rangeMap[range]);

    const chartData = filteredData.map((d) => ({
        date: d.date ? new Date(d.date).toLocaleDateString([], { month: "short", day: "numeric" }) : "",
        "SM %": d.sm_pct,
        "Mem %": d.mem_pct,
        "Power (W)": d.power_w,
        "Temp (°C)": d.temp_c,
    }));

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
            <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Clock className="h-5 w-5 text-slate-400" />
                    <h3 className="text-lg font-semibold text-white">
                        Historical Trends
                        {resourceName && <span className="ml-2 text-sm text-slate-400">— {resourceName}</span>}
                    </h3>
                </div>
                <div className="flex gap-1 rounded-lg border border-white/10 p-0.5">
                    {(["7d", "30d", "90d"] as Range[]).map((r) => (
                        <button
                            key={r}
                            onClick={() => setRange(r)}
                            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                                range === r
                                    ? "bg-indigo-600 text-white"
                                    : "text-slate-400 hover:text-white"
                            }`}
                        >
                            {r}
                        </button>
                    ))}
                </div>
            </div>

            <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} />
                    <Tooltip
                        contentStyle={{
                            background: "#1e293b",
                            border: "1px solid rgba(255,255,255,0.1)",
                            borderRadius: "8px",
                        }}
                        labelStyle={{ color: "#e2e8f0" }}
                    />
                    <Legend
                        wrapperStyle={{ fontSize: "11px", color: "#94a3b8" }}
                    />
                    <Line
                        type="monotone"
                        dataKey="SM %"
                        stroke="#818cf8"
                        strokeWidth={2}
                        dot={false}
                        connectNulls
                    />
                    <Line
                        type="monotone"
                        dataKey="Mem %"
                        stroke="#34d399"
                        strokeWidth={2}
                        dot={false}
                        connectNulls
                    />
                    <Line
                        type="monotone"
                        dataKey="Temp (°C)"
                        stroke="#fb923c"
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls
                        strokeDasharray="4 4"
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
