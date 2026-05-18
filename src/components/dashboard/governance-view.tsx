"use client";

import {
    Shield,
    CheckCircle,
    XCircle,
    AlertTriangle,
    Tag,
    IndianRupee,
    Server,
    Clock,
    TrendingUp,
    TrendingDown,
    BookOpen,
    AlertOctagon,
    Lightbulb
} from "lucide-react";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { GovernanceData } from "@/lib/dashboard/data";
import { formatInrCurrency } from "@/lib/resources/contract";

const formatGovernanceCurrency = (value: number) =>
    formatInrCurrency(value, { maximumFractionDigits: 0 });

export function GovernanceView({ initialAnalysis }: { initialAnalysis: GovernanceData }) {
    const analysis = initialAnalysis;
    const [officeHoursEnabled, setOfficeHoursEnabled] = useState(initialAnalysis.officeHours.enabled);

    useEffect(() => {
        setOfficeHoursEnabled(initialAnalysis.officeHours.enabled);
    }, [initialAnalysis.officeHours.enabled]);

    // Color helpers
    const getScoreColor = (score: number) => {
        if (score >= 80) return "text-emerald-500";
        if (score >= 50) return "text-amber-500";
        return "text-rose-500";
    };

    const getScoreBg = (score: number) => {
        if (score >= 80) return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
        if (score >= 50) return "bg-amber-500/10 text-amber-400 border-amber-500/20";
        return "bg-rose-500/10 text-rose-400 border-rose-500/20";
    };

    const getScoreStroke = (score: number) => {
        if (score >= 80) return "stroke-emerald-500";
        if (score >= 50) return "stroke-amber-500";
        return "stroke-rose-500";
    };

    const getBurnRateTone = (burnRate: number) => {
        if (burnRate > 100) {
            return {
                bar: "bg-rose-500",
                text: "text-rose-400",
            };
        }

        if (burnRate > 80) {
            return {
                bar: "bg-amber-500",
                text: "text-amber-400",
            };
        }

        return {
            bar: "bg-emerald-500",
            text: "text-emerald-400",
        };
    };

    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case "Critical":
            case "High": return <XCircle className="w-5 h-5 text-rose-500" />;
            case "Medium": return <AlertTriangle className="w-5 h-5 text-amber-500" />;
            default: return <CheckCircle className="w-5 h-5 text-emerald-500" />;
        }
    };

    const scoreCircumference = 2 * Math.PI * 42;
    const scoreDashOffset = scoreCircumference - (Math.min(Math.max(analysis.score.value, 0), 100) / 100) * scoreCircumference;
    const burnRate = analysis.budget.budgetLimit > 0
        ? Math.min(Math.round((analysis.budget.projectedSpend / analysis.budget.budgetLimit) * 100), 999)
        : 0;
    const burnRateTone = getBurnRateTone(burnRate);

    return (
        <div className="p-6 space-y-8">

            {/* Top Level Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* 1. Governance Score */}
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
                    <div className="bg-slate-900/50 border border-white/10 border-t-2 border-t-emerald-500/60 rounded-2xl p-6 relative overflow-hidden h-full flex flex-col justify-between">
                        <div>
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-white text-lg font-medium">Governance Score</h3>
                                <Shield className={`w-6 h-6 ${getScoreColor(analysis.score.value)}`} />
                            </div>
                            <div className="flex items-center gap-4">
                                <div className="relative flex h-28 w-28 items-center justify-center">
                                    <svg className="h-28 w-28 -rotate-90" viewBox="0 0 100 100">
                                        <circle cx="50" cy="50" r="42" className="stroke-slate-800" strokeWidth="8" fill="none" />
                                        <circle
                                            cx="50"
                                            cy="50"
                                            r="42"
                                            className={getScoreStroke(analysis.score.value)}
                                            strokeWidth="8"
                                            strokeLinecap="round"
                                            fill="none"
                                            strokeDasharray={scoreCircumference}
                                            strokeDashoffset={scoreDashOffset}
                                        />
                                    </svg>
                                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                                        <span className={`text-4xl font-bold ${getScoreColor(analysis.score.value)}`}>
                                            {analysis.score.value}
                                        </span>
                                        <span className="text-xs text-slate-500">/ 100</span>
                                    </div>
                                </div>
                                <div className="mb-2">
                                    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${getScoreBg(analysis.score.value)}`}>
                                        {analysis.score.rating} Risk
                                    </span>
                                </div>
                            </div>
                        </div>
                        <p className="mt-4 text-slate-500 text-sm flex items-center gap-2">
                            {analysis.score.trend === 'down' ? <TrendingDown className="w-4 h-4 text-rose-500" /> : <TrendingUp className="w-4 h-4 text-emerald-500" />}
                            Trend: {analysis.score.trend === 'down' ? 'Worsening' : 'Improving'}
                        </p>
                    </div>
                </motion.div>

                {/* 2. Budget Health */}
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
                    <div className="bg-slate-900/50 border border-white/10 border-t-2 border-t-blue-500/60 rounded-2xl p-6 relative overflow-hidden h-full flex flex-col justify-between">
                        <div>
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-white text-lg font-medium">Budget Velocity</h3>
                                <IndianRupee className="w-6 h-6 text-indigo-400" />
                            </div>
                            <div className="space-y-3">
                                <div className="flex justify-between text-sm">
                                    <span className="text-slate-400">Projected Spend</span>
                                    <span className="text-white font-mono">{formatGovernanceCurrency(analysis.budget.projectedSpend)}</span>
                                </div>

                                {/* Native Progress Bar */}
                                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-800">
                                    <div
                                        className={`h-2 rounded-full ${burnRateTone.bar}`}
                                        style={{ width: `${Math.min(burnRate, 100)}%` }}
                                    ></div>
                                </div>

                                <div className="flex justify-between text-xs text-slate-500">
                                    <span>Limit: {formatGovernanceCurrency(analysis.budget.budgetLimit)}</span>
                                    <span className={burnRateTone.text}>{burnRate}% of budget used</span>
                                </div>
                            </div>
                        </div>

                        <div className="p-3 mt-4 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-start gap-2">
                            <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                            <p className="text-rose-400 text-xs leading-snug">
                                {analysis.budget.alert}
                            </p>
                        </div>
                    </div>
                </motion.div>

                {/* 3. Cost Impact */}
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
                    <div className="bg-slate-900/50 border border-white/10 border-t-2 border-t-amber-500/60 rounded-2xl p-6 relative overflow-hidden h-full flex flex-col justify-between">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-white text-lg font-medium">Cost at Risk</h3>
                            <AlertOctagon className="w-6 h-6 text-amber-500" />
                        </div>
                        <div className="flex flex-col justify-between h-[120px]">
                            <div>
                                <span className="text-4xl font-bold text-white">{formatGovernanceCurrency(analysis.tagging.costImpact)}</span>
                                <p className="text-slate-400 mt-1 text-sm">Monthly unaccounted spend</p>
                            </div>
                            <div className="flex gap-2 mt-4">
                                <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-400">
                                    <Tag className="w-3 h-3" />
                                    {analysis.tagging.missingTags} Untagged Assets
                                </span>
                            </div>
                        </div>
                    </div>
                </motion.div>
            </div>

            {/* Modules Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                {/* Tagging Compliance Engine */}
                <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4 }}>
                    <div className="bg-slate-900/50 border border-white/10 border-t-2 border-t-violet-500/60 rounded-2xl p-6 relative overflow-hidden h-full">
                        <div className="flex items-center gap-3 mb-6">
                            <div className="rounded-lg bg-violet-500/10 p-2">
                                <Tag className="w-5 h-5 text-violet-400" />
                            </div>
                            <div>
                                <h3 className="text-white text-lg font-medium">Tagging Compliance Engine</h3>
                                <p className="text-slate-400 text-xs mt-0.5">Ownership & Accountability Tracker</p>
                            </div>
                        </div>

                        <div className="space-y-4">
                            <div className="rounded-xl border border-white/10 bg-slate-900 p-4">
                                <h4 className="text-sm font-medium text-slate-300 mb-3">Top Violators</h4>
                                <ul className="space-y-3">
                                    {analysis.tagging.assets.map((asset, i) => (
                                        <li key={i} className="flex items-center justify-between text-sm">
                                            <div className="flex items-center gap-2">
                                                <Server className="w-4 h-4 text-slate-500" />
                                                <span className="text-white font-mono">{asset.name}</span>
                                            </div>
                                            <div className="flex gap-1">
                                                {asset.missing.map(tag => (
                                                    <span key={tag} className="px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 text-[10px] border border-rose-500/20">
                                                        Missing {tag}
                                                    </span>
                                                ))}
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            <p className="text-xs text-slate-500 italic mt-4">
                                &quot;No owner = no accountability = guaranteed waste.&quot;
                            </p>
                        </div>
                    </div>
                </motion.div>

                {/* Smart Office Hours */}
                <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5 }}>
                    <div className="bg-slate-900/50 border border-white/10 border-t-2 border-t-teal-500/60 rounded-2xl p-6 relative overflow-hidden h-full">
                        <div className="flex items-center gap-3 mb-6">
                            <div className="p-2 bg-teal-500/10 rounded-lg">
                                <Clock className="w-5 h-5 text-teal-500" />
                            </div>
                            <div>
                                <h3 className="text-white text-lg font-medium">Smart Office Hours</h3>
                                <p className="text-slate-400 text-xs mt-0.5">Detects non-prod resources running 24/7</p>
                            </div>
                        </div>

                        <div className="space-y-6">
                            <div className="flex items-center justify-between p-4 bg-teal-500/5 rounded-xl border border-teal-500/20">
                                <div className="flex items-center gap-4">
                                    <div className="flex flex-col">
                                        <span className="text-white font-semibold flex items-center gap-2">
                                            <Clock className="w-4 h-4 text-teal-500" />
                                            Dev/Test Workload Enforcement
                                        </span>
                                        <span className="text-xs text-teal-400 mt-1">Est. Savings: {formatGovernanceCurrency(analysis.officeHours.savings)}/mo</span>
                                    </div>
                                </div>

                                <button
                                    type="button"
                                    aria-readonly="true"
                                    className={`relative inline-flex h-6 w-11 items-center rounded-full cursor-default transition-colors ${officeHoursEnabled ? 'bg-teal-500' : 'bg-slate-700'}`}
                                >
                                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${officeHoursEnabled ? 'translate-x-6' : 'translate-x-1'}`} />
                                </button>
                            </div>

                            <div className="flex items-start gap-3 rounded-xl border border-white/10 bg-slate-900 p-4">
                                <Lightbulb className="mt-0.5 w-5 h-5 flex-shrink-0 text-amber-400" />
                                <div>
                                    <p className="text-white font-medium text-sm">AI Recommendation</p>
                                    <p className="text-slate-400 text-sm mt-1">{analysis.officeHours.recommendation}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </motion.div>
            </div>

            {/* Compliance Trends & Framework Risk */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Compliance Score Trend */}
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.55 }}>
                    <div className="bg-slate-900/50 border border-white/10 border-t-2 border-t-cyan-500/60 rounded-2xl p-6 relative overflow-hidden h-full">
                        <div className="flex items-center gap-3 mb-6">
                            <div className="rounded-lg bg-indigo-500/10 p-2">
                                <TrendingUp className="w-5 h-5 text-indigo-400" />
                            </div>
                            <div>
                                <h3 className="text-white text-lg font-medium">Compliance Score Trend</h3>
                                <p className="text-slate-400 text-xs mt-0.5">7-day governance score history</p>
                            </div>
                        </div>
                        {analysis.trends.length > 0 ? (
                            <div className="space-y-4">
                                <div className="flex items-end gap-1 h-24">
                                    {analysis.trends.map((t, i) => {
                                        const height = Math.max(4, (t.score / 100) * 96);
                                        const color = t.score >= 80 ? 'bg-emerald-500' : t.score >= 50 ? 'bg-amber-500' : 'bg-rose-500';
                                        return (
                                            <div key={i} className="flex-1 flex flex-col items-center gap-1">
                                                <span className="text-[9px] text-slate-400 font-mono">{t.score}</span>
                                                <div className="w-full rounded-t-sm relative" style={{ height: `${height}%` }}>
                                                    <div className={`absolute inset-0 ${color} rounded-t-sm opacity-80`} />
                                                </div>
                                                <span className="text-[8px] text-slate-500">{t.date.split(' ')[1] || t.date}</span>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        ) : (
                            <div className="flex h-28 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-white/5 bg-white/[0.02]">
                                <TrendingUp className="w-8 h-8 text-slate-700" />
                                <p className="text-sm text-slate-500">
                                    No trend data yet
                                </p>
                                <p className="text-xs text-slate-600">
                                    Run a scan to start tracking governance score history
                                </p>
                            </div>
                        )}
                    </div>
                </motion.div>

                {/* Framework Risk Heatmap */}
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}>
                    <div className="bg-slate-900/50 border border-white/10 border-t-2 border-t-indigo-500/60 rounded-2xl p-6 relative overflow-hidden h-full">
                        <div className="flex items-center gap-3 mb-6">
                            <div className="rounded-lg bg-amber-500/10 p-2">
                                <Shield className="w-5 h-5 text-amber-400" />
                            </div>
                            <div>
                                <h3 className="text-white text-lg font-medium">Framework Compliance</h3>
                                <p className="text-slate-400 text-xs mt-0.5">Pass/fail ratio by compliance framework</p>
                            </div>
                        </div>
                        {analysis.frameworkSummary.length > 0 ? (
                            <div className="space-y-4">
                                {analysis.frameworkSummary.map((fw, i) => {
                                    const passRate = fw.total > 0 ? Math.round((fw.pass / fw.total) * 100) : 0;
                                    return (
                                        <div key={i} className="space-y-2">
                                            <div className="flex items-center justify-between text-sm">
                                                <span className="text-white font-mono flex items-center gap-2">
                                                    <Shield className="w-3 h-3 text-slate-500" />
                                                    {fw.framework}
                                                </span>
                                                <span className={`text-xs font-medium ${passRate >= 80 ? 'text-emerald-400' : passRate >= 50 ? 'text-amber-400' : 'text-rose-400'}`}>
                                                    {passRate}% ({fw.pass}/{fw.total})
                                                </span>
                                            </div>

                                            {/* Native Progress Bar */}
                                            <div className="h-2 w-full rounded-full bg-slate-800">
                                                <div
                                                    className={`h-2 rounded-full ${passRate >= 80 ? 'bg-emerald-500' : passRate >= 50 ? 'bg-amber-500' : 'bg-rose-500'}`}
                                                    style={{ width: `${passRate}%` }}
                                                ></div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="text-center py-8 text-slate-500 text-sm">
                                No framework data available yet.
                            </div>
                        )}
                    </div>
                </motion.div>
            </div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}>
                <div className="bg-slate-900/50 border border-white/10 border-t-2 border-t-blue-500/60 rounded-2xl p-6 relative overflow-hidden h-full">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                            <div className="rounded-lg bg-indigo-500/10 p-2">
                                <BookOpen className="w-5 h-5 text-indigo-400" />
                            </div>
                            <div>
                                <h3 className="text-white text-lg font-medium">Explainability & Compliance Layer</h3>
                                <p className="text-slate-400 text-xs mt-0.5">Trust needs verification. See the &quot;Why&quot; behind every alert.</p>
                            </div>
                        </div>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="border-b border-white/5 bg-white/5 text-xs uppercase tracking-wider text-slate-400">
                                    <th className="p-4 font-medium">Rule Name</th>
                                    <th className="p-4 font-medium">Status</th>
                                    <th className="p-4 font-medium">Severity</th>
                                    <th className="p-4 font-medium">Reason & Impact</th>
                                    <th className="p-4 font-medium">Compliance Mapping</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5 text-sm">
                                {analysis.policies.map((policy) => (
                                    <tr key={policy.id} className="border-b border-white/5 transition-colors hover:bg-white/[0.03] group">
                                        <td className="p-4 text-white font-medium">{policy.name}</td>
                                        <td className="p-4">
                                            {policy.status === 'Pass' ? (
                                                <div className="flex items-center gap-2 text-emerald-400">
                                                    <CheckCircle className="w-4 h-4" />
                                                    <span>Pass</span>
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-2 text-rose-400">
                                                    <XCircle className="w-4 h-4" />
                                                    <span>Fail</span>
                                                </div>
                                            )}
                                        </td>
                                        <td className="p-4">
                                            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium border ${policy.severity === 'Critical' || policy.severity === 'High'
                                                ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                                                : policy.severity === 'Medium'
                                                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                                                    : 'bg-slate-500/10 text-slate-400 border-slate-500/20'
                                                }`}>
                                                {policy.severity}
                                            </span>
                                        </td>
                                        <td className="p-4 max-w-sm">
                                            <p className="text-slate-300 group-hover:text-white transition-colors">{policy.reason}</p>
                                        </td>
                                        <td className="p-4">
                                            <span className="flex w-fit items-center gap-1.5 rounded-full border border-white/10 bg-slate-800 px-2.5 py-1 text-xs font-mono text-slate-300 transition-colors group-hover:border-white/20">
                                                <Shield className="w-3 h-3" />
                                                {policy.framework}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {analysis.policies.length === 0 && (
                            <div className="rounded-b-2xl border-x border-b border-white/5 py-12 text-center">
                                <Shield className="w-12 h-12 text-slate-600 mx-auto mb-4 opacity-50" />
                                <h3 className="text-lg font-medium text-slate-300 mb-1">No AI Rationale Available</h3>
                                <p className="text-slate-500 text-sm max-w-md mx-auto">
                                    Trigger a scan for Gemini to process the compliance rules against your infrastructure.
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            </motion.div>

        </div>
    );
}

