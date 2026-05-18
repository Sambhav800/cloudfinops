"use client";

import type { SecurityFinding, SecurityPosture, SecuritySeverity } from "@/lib/dashboard/data";
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Cell,
} from "recharts";
import {
    Activity,
    AlertTriangle,
    Eye,
    LockKeyhole,
    Server,
    ShieldAlert,
    ShieldCheck,
    ShieldX,
} from "lucide-react";

const PROVIDER_COLORS = { aws: "#FF9900", azure: "#0078D4", gcp: "#4285F4" };
const CHART_STYLE = {
    gridColor: "rgba(255,255,255,0.06)",
    tickColor: "#475569",
    tooltipBg: "#0f172a",
};

const TOOLTIP_BORDER = "rgba(255,255,255,0.1)";
const SEVERITY_COLORS: Record<SecuritySeverity, string> = {
    critical: "#ef4444",
    high: "#f97316",
    medium: "#f59e0b",
    low: "#22c55e",
    info: "#6366f1",
};

const CATEGORY_COLORS = ["#f43f5e", "#f97316", "#f59e0b", "#6366f1", "#06b6d4", "#14b8a6"];

type SecurityViewProps = {
    initialPosture: SecurityPosture;
};

function formatLabel(value: string): string {
    if (!value) {
        return "Other";
    }

    return value
        .replace(/[_-]+/g, " ")
        .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDetectedDate(value: string | null): string {
    if (!value) {
        return "No findings";
    }

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }

    return parsed.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
    });
}

function getProviderColor(provider: string): string {
    const key = provider.toLowerCase() as keyof typeof PROVIDER_COLORS;
    return PROVIDER_COLORS[key] ?? "#94a3b8";
}

function getScoreTone(score: number) {
    if (score >= 90) {
        return {
            text: "text-emerald-400",
            border: "border-t-emerald-500/60",
            icon: "text-emerald-400",
            surface: "bg-emerald-500/15",
        };
    }
    if (score >= 70) {
        return {
            text: "text-amber-400",
            border: "border-t-amber-500/60",
            icon: "text-amber-400",
            surface: "bg-amber-500/15",
        };
    }
    return {
        text: "text-rose-400",
        border: "border-t-rose-500/60",
        icon: "text-rose-400",
        surface: "bg-rose-500/15",
    };
}

function statusTone(status: string): string {
    const normalized = status.toLowerCase();
    if (normalized === "open" || normalized === "active" || normalized === "pending") {
        return "bg-rose-500/15 text-rose-400";
    }
    if (normalized === "in_review") {
        return "bg-amber-500/15 text-amber-400";
    }
    return "bg-emerald-500/15 text-emerald-400";
}

function sourceLabel(finding: SecurityFinding): string {
    return finding.source === "agent_notification" ? "Alert" : "Policy";
}

export function SecurityView({ initialPosture }: SecurityViewProps) {
    const posture = initialPosture;
    const { summary } = posture;
    const scoreTone = getScoreTone(summary.score);
    const severityData = posture.findingsBySeverity;
    const categoryData = posture.findingsByCategory;
    const hasCoverage = summary.monitoredResources > 0;

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h1 className="flex items-center gap-3 text-2xl font-bold text-white">
                        <ShieldCheck className="h-7 w-7 text-emerald-400" />
                        Security
                    </h1>
                    <p className="mt-1 text-sm text-slate-400">
                        Live posture from security policies, permission alerts, and scanned resources.
                    </p>
                </div>
                <span className="flex items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-xs text-emerald-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    Live security data
                </span>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
                <div className={`rounded-2xl border border-white/10 border-t-2 ${scoreTone.border} bg-slate-900/50 p-5`}>
                    <div className="mb-3 flex items-center gap-2">
                        <div className={`flex h-8 w-8 items-center justify-center rounded-xl ${scoreTone.surface}`}>
                            <ShieldCheck className={`h-4 w-4 ${scoreTone.icon}`} />
                        </div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Security Score</p>
                    </div>
                    <p className={`text-2xl font-bold ${scoreTone.text}`}>{summary.score}/100</p>
                    <p className="mt-1 text-xs text-slate-500">{summary.rating}</p>
                </div>

                <div className="rounded-2xl border border-white/10 border-t-2 border-t-rose-500/60 bg-slate-900/50 p-5">
                    <div className="mb-3 flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-rose-500/15">
                            <ShieldX className="h-4 w-4 text-rose-400" />
                        </div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Critical</p>
                    </div>
                    <p className="text-2xl font-bold text-rose-400">{summary.critical}</p>
                    <p className="mt-1 text-xs text-slate-500">critical active findings</p>
                </div>

                <div className="rounded-2xl border border-white/10 border-t-2 border-t-orange-500/60 bg-slate-900/50 p-5">
                    <div className="mb-3 flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-orange-500/15">
                            <AlertTriangle className="h-4 w-4 text-orange-400" />
                        </div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">High</p>
                    </div>
                    <p className="text-2xl font-bold text-orange-400">{summary.high}</p>
                    <p className="mt-1 text-xs text-slate-500">high severity findings</p>
                </div>

                <div className="rounded-2xl border border-white/10 border-t-2 border-t-amber-500/60 bg-slate-900/50 p-5">
                    <div className="mb-3 flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500/15">
                            <Eye className="h-4 w-4 text-amber-400" />
                        </div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Open Issues</p>
                    </div>
                    <p className="text-2xl font-bold text-white">{summary.open}</p>
                    <p className="mt-1 text-xs text-slate-500">awaiting remediation</p>
                </div>

                <div className="rounded-2xl border border-white/10 border-t-2 border-t-indigo-500/60 bg-slate-900/50 p-5">
                    <div className="mb-3 flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-500/15">
                            <Activity className="h-4 w-4 text-indigo-400" />
                        </div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Coverage</p>
                    </div>
                    <p className="text-2xl font-bold text-white">{summary.monitoredResources}</p>
                    <p className="mt-1 text-xs text-slate-500">{summary.exposedResources} exposed resources</p>
                </div>
            </div>

            {!hasCoverage && (
                <div className="rounded-2xl border border-white/10 border-t-2 border-t-slate-500/60 bg-slate-900/50 p-5">
                    <div className="flex items-start gap-3">
                        <LockKeyhole className="mt-0.5 h-5 w-5 text-slate-500" />
                        <div>
                            <h2 className="font-semibold text-white">No security coverage yet</h2>
                            <p className="mt-1 text-sm text-slate-400">
                                Connect a cloud account and run a scan to populate security posture metrics.
                            </p>
                        </div>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <div className="rounded-2xl border border-white/10 border-t-2 border-t-rose-500/60 bg-slate-900/50 p-5">
                    <h3 className="font-semibold text-white">Findings by Severity</h3>
                    <p className="mb-4 mt-0.5 text-xs text-slate-500">
                        Active security findings grouped by severity.
                    </p>
                    {severityData.length === 0 ? (
                        <div className="flex h-52 flex-col items-center justify-center gap-2 text-center">
                            <ShieldCheck className="h-8 w-8 text-emerald-700" />
                            <p className="text-sm text-slate-500">No active security findings</p>
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height={220}>
                            <BarChart data={severityData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.gridColor} vertical={false} />
                                <XAxis
                                    dataKey="name"
                                    tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }}
                                    axisLine={false}
                                    tickLine={false}
                                    tickFormatter={(value: string) => formatLabel(value)}
                                />
                                <YAxis
                                    allowDecimals={false}
                                    tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }}
                                    axisLine={false}
                                    tickLine={false}
                                    width={28}
                                />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: CHART_STYLE.tooltipBg,
                                        border: `1px solid ${TOOLTIP_BORDER}`,
                                        borderRadius: "10px",
                                        fontSize: "12px",
                                    }}
                                    cursor={{ fill: "rgba(255,255,255,0.04)" }}
                                    labelFormatter={(value) => formatLabel(String(value))}
                                />
                                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                                    {severityData.map((entry, index) => (
                                        <Cell
                                            key={`severity-${entry.name}-${index}`}
                                            fill={SEVERITY_COLORS[entry.name as SecuritySeverity] ?? "#94a3b8"}
                                        />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </div>

                <div className="rounded-2xl border border-white/10 border-t-2 border-t-indigo-500/60 bg-slate-900/50 p-5">
                    <h3 className="font-semibold text-white">Findings by Category</h3>
                    <p className="mb-4 mt-0.5 text-xs text-slate-500">
                        Security and permission issues grouped by control area.
                    </p>
                    {categoryData.length === 0 ? (
                        <div className="flex h-52 flex-col items-center justify-center gap-2 text-center">
                            <ShieldCheck className="h-8 w-8 text-emerald-700" />
                            <p className="text-sm text-slate-500">No category data yet</p>
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height={220}>
                            <BarChart data={categoryData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.gridColor} vertical={false} />
                                <XAxis
                                    dataKey="name"
                                    tick={{ fill: CHART_STYLE.tickColor, fontSize: 10 }}
                                    axisLine={false}
                                    tickLine={false}
                                    tickFormatter={(value: string) => formatLabel(value)}
                                />
                                <YAxis
                                    allowDecimals={false}
                                    tick={{ fill: CHART_STYLE.tickColor, fontSize: 11 }}
                                    axisLine={false}
                                    tickLine={false}
                                    width={28}
                                />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: CHART_STYLE.tooltipBg,
                                        border: `1px solid ${TOOLTIP_BORDER}`,
                                        borderRadius: "10px",
                                        fontSize: "12px",
                                    }}
                                    cursor={{ fill: "rgba(255,255,255,0.04)" }}
                                    labelFormatter={(value) => formatLabel(String(value))}
                                />
                                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                                    {categoryData.map((entry, index) => (
                                        <Cell
                                            key={`category-${entry.name}-${index}`}
                                            fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]}
                                        />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </div>

            <div className="rounded-2xl border border-white/10 border-t-2 border-t-rose-500/60 bg-slate-900/50 p-5">
                <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                    <div>
                        <h3 className="flex items-center gap-2 font-semibold text-white">
                            <ShieldAlert className="h-5 w-5 text-rose-400" />
                            Active Findings
                        </h3>
                        <p className="mt-0.5 text-xs text-slate-500">
                            Security-only policy violations and permission alerts requiring action.
                        </p>
                    </div>
                    <span className="rounded-full border border-white/10 bg-slate-900 px-3 py-1 text-xs text-slate-400">
                        Last detected {formatDetectedDate(summary.lastDetectedAt)}
                    </span>
                </div>

                {posture.activeFindings.length === 0 ? (
                    <div className="flex h-32 flex-col items-center justify-center gap-2 text-center">
                        <ShieldCheck className="h-8 w-8 text-emerald-700" />
                        <p className="text-sm text-slate-500">No active security findings</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full min-w-[920px] text-sm">
                            <thead>
                                <tr className="border-b border-white/5">
                                    {["Resource", "Provider", "Category", "Severity", "Finding", "Remediation", "Detected", "Status"].map((header) => (
                                        <th key={header} className="pb-3 pr-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                                            {header}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {posture.activeFindings.map((finding) => {
                                    const severityColor = SEVERITY_COLORS[finding.severity] ?? "#94a3b8";
                                    const providerColor = getProviderColor(finding.provider);

                                    return (
                                        <tr key={`${finding.source}-${finding.id}`} className="transition-colors hover:bg-white/[0.02]">
                                            <td className="py-3 pr-4">
                                                <div className="flex items-center gap-2">
                                                    <Server className="h-3.5 w-3.5 flex-shrink-0 text-slate-500" />
                                                    <div>
                                                        <p className="font-mono text-xs text-slate-300">{finding.resource}</p>
                                                        <p className="text-[10px] uppercase tracking-wider text-slate-600">{sourceLabel(finding)}</p>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="py-3 pr-4">
                                                {finding.provider ? (
                                                    <span
                                                        className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase"
                                                        style={{
                                                            backgroundColor: `${providerColor}25`,
                                                            color: providerColor,
                                                        }}
                                                    >
                                                        {finding.provider.toUpperCase()}
                                                    </span>
                                                ) : (
                                                    <span className="text-slate-600">-</span>
                                                )}
                                            </td>
                                            <td className="py-3 pr-4 text-xs text-slate-400">{formatLabel(finding.category)}</td>
                                            <td className="py-3 pr-4">
                                                <span
                                                    className="rounded-full px-2 py-0.5 text-xs font-medium"
                                                    style={{
                                                        backgroundColor: `${severityColor}20`,
                                                        color: severityColor,
                                                    }}
                                                >
                                                    {finding.severity}
                                                </span>
                                            </td>
                                            <td className="max-w-xs py-3 pr-4 text-xs text-slate-400">{finding.description}</td>
                                            <td className="max-w-xs py-3 pr-4 text-xs text-slate-400">{finding.remediation}</td>
                                            <td className="py-3 pr-4 text-xs text-slate-500">{formatDetectedDate(finding.detected_at)}</td>
                                            <td className="py-3">
                                                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusTone(finding.status)}`}>
                                                    {formatLabel(finding.status)}
                                                </span>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            <div className="rounded-2xl border border-white/10 border-t-2 border-t-amber-500/60 bg-slate-900/50 p-5">
                <div className="mb-4">
                    <h3 className="flex items-center gap-2 font-semibold text-white">
                        <Eye className="h-5 w-5 text-amber-400" />
                        Exposed Resources
                    </h3>
                    <p className="mt-0.5 text-xs text-slate-500">
                        Resources with active security findings or scanner-detected exposure.
                    </p>
                </div>

                {posture.exposedResources.length === 0 ? (
                    <div className="flex h-28 flex-col items-center justify-center gap-2 text-center">
                        <ShieldCheck className="h-8 w-8 text-emerald-700" />
                        <p className="text-sm text-slate-500">No exposed resources detected</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full min-w-[760px] text-sm">
                            <thead>
                                <tr className="border-b border-white/5">
                                    {["Resource", "Type", "Provider", "Region", "Exposure", "Risks", "Severity", "Status"].map((header) => (
                                        <th key={header} className="pb-3 pr-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                                            {header}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {posture.exposedResources.map((resource) => {
                                    const severityColor = SEVERITY_COLORS[resource.highest_severity] ?? "#94a3b8";
                                    const providerColor = getProviderColor(resource.provider);

                                    return (
                                        <tr key={resource.id} className="transition-colors hover:bg-white/[0.02]">
                                            <td className="py-3 pr-4 font-mono text-xs text-slate-300">{resource.resource_name}</td>
                                            <td className="py-3 pr-4 text-xs text-slate-400">{formatLabel(resource.resource_type)}</td>
                                            <td className="py-3 pr-4">
                                                {resource.provider ? (
                                                    <span
                                                        className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase"
                                                        style={{
                                                            backgroundColor: `${providerColor}25`,
                                                            color: providerColor,
                                                        }}
                                                    >
                                                        {resource.provider.toUpperCase()}
                                                    </span>
                                                ) : (
                                                    <span className="text-slate-600">-</span>
                                                )}
                                            </td>
                                            <td className="py-3 pr-4 text-xs text-slate-500">{resource.region || "-"}</td>
                                            <td className="max-w-xs py-3 pr-4 text-xs text-slate-400">{resource.exposure}</td>
                                            <td className="py-3 pr-4 text-xs text-slate-300">{resource.risk_count}</td>
                                            <td className="py-3 pr-4">
                                                <span
                                                    className="rounded-full px-2 py-0.5 text-xs font-medium"
                                                    style={{
                                                        backgroundColor: `${severityColor}20`,
                                                        color: severityColor,
                                                    }}
                                                >
                                                    {resource.highest_severity}
                                                </span>
                                            </td>
                                            <td className="py-3 text-xs text-slate-400">{formatLabel(resource.status)}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
