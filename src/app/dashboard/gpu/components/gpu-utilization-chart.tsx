"use client";

import { useEffect, useRef, useState } from "react";
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";
import { Activity } from "lucide-react";

type MetricsSample = {
    resource_id: string;
    provider: string;
    latest: {
        ts: string;
        sm_pct?: number;
        mem_pct?: number;
        power_w?: number;
        temp_c?: number;
    };
    daily_avg: {
        sm_pct?: number;
        mem_pct?: number;
    };
};

type Props = {
    wsUrl: string;
    userId: string;
    token: string;
    initialMetrics?: MetricsSample[];
};

type ChartPoint = {
    time: string;
    sm_pct: number;
    mem_pct: number;
};

export function GpuUtilizationChart({ wsUrl, userId, token, initialMetrics }: Props) {
    const [liveData, setLiveData] = useState<ChartPoint[]>([]);
    const [connected, setConnected] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        if (initialMetrics && initialMetrics.length > 0) {
            const points = initialMetrics.map((m) => ({
                time: new Date(m.latest.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                sm_pct: m.latest.sm_pct ?? 0,
                mem_pct: m.latest.mem_pct ?? 0,
            }));
            setLiveData(points);
        }
    }, [initialMetrics]);

    useEffect(() => {
        if (!wsUrl || !userId || !token) return;

        const ws = new WebSocket(`${wsUrl}/ws/${userId}?token=${token}`);
        wsRef.current = ws;

        ws.onopen = () => setConnected(true);
        ws.onclose = () => setConnected(false);
        ws.onerror = () => setConnected(false);

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === "gpu_metrics" && msg.payload) {
                    const payload = msg.payload;
                    const newPoint: ChartPoint = {
                        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                        sm_pct: payload.sm_pct ?? 0,
                        mem_pct: payload.mem_pct ?? 0,
                    };
                    setLiveData((prev) => [...prev.slice(-59), newPoint]);
                }
            } catch {}
        };

        return () => {
            ws.close();
            wsRef.current = null;
        };
    }, [wsUrl, userId, token]);

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
            <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Activity className="h-5 w-5 text-indigo-400" />
                    <h3 className="text-lg font-semibold text-white">Real-Time GPU Utilization</h3>
                </div>
                <div className="flex items-center gap-2">
                    <div className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "bg-rose-400"}`} />
                    <span className="text-xs text-slate-400">{connected ? "Live" : "Disconnected"}</span>
                </div>
            </div>

            {liveData.length === 0 ? (
                <div className="flex h-48 items-center justify-center text-slate-500">
                    <p>Waiting for GPU metrics data...</p>
                </div>
            ) : (
                <ResponsiveContainer width="100%" height={200}>
                    <AreaChart data={liveData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis dataKey="time" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                        <YAxis domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 11 }} unit="%" />
                        <Tooltip
                            contentStyle={{ background: "#1e293b", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px" }}
                            labelStyle={{ color: "#e2e8f0" }}
                        />
                        <Area
                            type="monotone"
                            dataKey="sm_pct"
                            name="SM Occupancy"
                            stroke="#818cf8"
                            fill="#818cf8"
                            fillOpacity={0.2}
                            strokeWidth={2}
                        />
                        <Area
                            type="monotone"
                            dataKey="mem_pct"
                            name="Memory Util"
                            stroke="#34d399"
                            fill="#34d399"
                            fillOpacity={0.1}
                            strokeWidth={2}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            )}

            <div className="mt-3 flex gap-4 text-xs text-slate-400">
                <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-indigo-400" />
                    <span>SM Occupancy</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-emerald-400" />
                    <span>Memory Utilization</span>
                </div>
            </div>
        </div>
    );
}
