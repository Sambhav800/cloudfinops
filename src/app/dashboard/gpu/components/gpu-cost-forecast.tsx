"use client";

import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine,
} from "recharts";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

type ForecastData = {
    status: string;
    current_monthly_run_rate: number;
    predicted_monthly_cost: number;
    predicted_90d_cost: number;
    growth_rate_pct: number;
    trend: string;
    confidence: number;
    risk_factors: string[];
    recommendation: string;
    daily_spend_history: Array<{ day_offset: number; cost: number }>;
};

type Props = {
    forecast: ForecastData | null;
    loading?: boolean;
};

export function GpuCostForecast({ forecast, loading }: Props) {
    if (loading) {
        return (
            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                <div className="h-6 w-48 animate-pulse rounded bg-slate-700" />
                <div className="mt-4 h-48 animate-pulse rounded bg-slate-800" />
            </div>
        );
    }

    if (!forecast || forecast.status === "no_data") {
        return (
            <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                <h3 className="text-lg font-semibold text-white">Cost Forecast</h3>
                <p className="mt-4 text-sm text-slate-400">
                    Not enough historical data to generate a forecast. Check back after 7 days of GPU activity.
                </p>
            </div>
        );
    }

    const TrendIcon = forecast.trend === "increasing" ? TrendingUp
        : forecast.trend === "declining" ? TrendingDown
        : Minus;

    const trendColor = forecast.trend === "increasing" ? "text-rose-400"
        : forecast.trend === "declining" ? "text-emerald-400"
        : "text-slate-400";

    const chartData = (forecast.daily_spend_history || []).map((d, i) => ({
        day: `D-${d.day_offset}`,
        cost: d.cost,
    })).reverse();

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
            <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white">GPU Cost Forecast</h3>
                <div className={`flex items-center gap-1 ${trendColor}`}>
                    <TrendIcon className="h-4 w-4" />
                    <span className="text-sm font-medium">
                        {forecast.growth_rate_pct > 0 ? "+" : ""}
                        {forecast.growth_rate_pct.toFixed(1)}%/mo
                    </span>
                </div>
            </div>

            <div className="mb-4 grid grid-cols-3 gap-4">
                <div>
                    <p className="text-xs text-slate-400">Current Run Rate</p>
                    <p className="text-lg font-bold text-white">
                        ${forecast.current_monthly_run_rate.toLocaleString()}/mo
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-400">30-Day Prediction</p>
                    <p className="text-lg font-bold text-indigo-300">
                        ${forecast.predicted_monthly_cost.toLocaleString()}/mo
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-400">90-Day Prediction</p>
                    <p className="text-lg font-bold text-amber-300">
                        ${forecast.predicted_90d_cost.toLocaleString()}/mo
                    </p>
                </div>
            </div>

            {chartData.length > 0 && (
                <ResponsiveContainer width="100%" height={160}>
                    <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis dataKey="day" tick={{ fill: "#94a3b8", fontSize: 10 }} />
                        <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} tickFormatter={(v) => `$${v}`} />
                        <Tooltip
                            contentStyle={{ background: "#1e293b", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px" }}
                            formatter={(value: number) => [`$${value.toFixed(2)}`, "Daily Cost"]}
                        />
                        <ReferenceLine
                            y={forecast.current_monthly_run_rate / 30}
                            stroke="#818cf8"
                            strokeDasharray="4 4"
                            label={{ value: "Avg", fill: "#818cf8", fontSize: 10 }}
                        />
                        <Area
                            type="monotone"
                            dataKey="cost"
                            stroke="#f59e0b"
                            fill="#f59e0b"
                            fillOpacity={0.15}
                            strokeWidth={2}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            )}

            {forecast.recommendation && (
                <div className="mt-4 rounded-lg border border-indigo-500/20 bg-indigo-500/5 px-4 py-3">
                    <p className="text-sm text-indigo-200">{forecast.recommendation}</p>
                </div>
            )}

            {forecast.confidence > 0 && (
                <p className="mt-2 text-xs text-slate-500">
                    Confidence: {(forecast.confidence * 100).toFixed(0)}% · Model: {forecast.status === "fallback" ? "Holt-Winters" : "Gemini"}
                </p>
            )}
        </div>
    );
}
