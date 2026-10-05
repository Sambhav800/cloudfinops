"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, FileDown, TriangleAlert } from "lucide-react";
import type { CommitmentRecommendationResponse } from "@/lib/api";
import { loadCommitmentRecommendations } from "@/lib/commitments/client";
import { formatCommitmentDate, formatCommitmentMoney, formatCommitmentPercent } from "@/lib/commitments/presentation";
import { ProviderRecommendationsCard } from "@/components/dashboard/commitments/ai-copilot-card";
import { Skeleton } from "@/components/ui/skeleton";
import { buildCommitmentExport } from "@/lib/commitments/export";

export default function OptimizerPage() {
    const [data, setData] = useState<CommitmentRecommendationResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedAccount, setSelectedAccount] = useState("");
    const [exportError, setExportError] = useState<string | null>(null);

    useEffect(() => {
        const controller = new AbortController();
        const load = async () => {
            try {
                const response = await loadCommitmentRecommendations(
                    AbortSignal.any([controller.signal, AbortSignal.timeout(20_000)]),
                );
                if (!controller.signal.aborted) setData(response);
            } catch (requestError) {
                if (!controller.signal.aborted) setError(requestError instanceof Error ? requestError.message : "Failed to load provider recommendations.");
            } finally {
                if (!controller.signal.aborted) setLoading(false);
            }
        };
        void load();
        return () => controller.abort();
    }, []);

    const scenarios = data?.scenarios ?? [];
    const accounts = [...new Set(scenarios.map((scenario) => scenario.account_id))];
    const visibleScenarios = selectedAccount ? scenarios.filter((scenario) => scenario.account_id === selectedAccount) : scenarios;
    const handleExportPdf = () => {
        if (!data || visibleScenarios.length === 0) return;
        setExportError(null);
        try {
            const printWindow = window.open("", "_blank", "width=1200,height=900");
            if (!printWindow) throw new Error("Export window was blocked. Allow pop-ups and retry.");
            printWindow.opener = null;
            printWindow.document.write(buildCommitmentExport(data, visibleScenarios));
            printWindow.document.close();
            printWindow.focus();
            printWindow.print();
        } catch (exportFailure) {
            setExportError(exportFailure instanceof Error ? exportFailure.message : "Could not export provider alternatives.");
        }
    };

    return (
        <main className="min-h-screen bg-slate-950 p-6 text-slate-200 md:p-10">
            <div className="mx-auto max-w-7xl space-y-8">
                <header>
                    <h1 className="text-3xl font-bold text-white">Savings Plan Optimizer</h1>
                    <p className="mt-2 text-sm text-slate-400">AWS Compute Savings Plan purchase estimates</p>
                </header>

                {loading ? (
                    <div aria-label="Loading provider recommendations" className="space-y-6">
                        <Skeleton className="h-56 rounded-2xl bg-slate-800" />
                        <Skeleton className="h-80 rounded-2xl bg-slate-800" />
                    </div>
                ) : error ? (
                    <div role="alert" className="rounded-2xl border border-rose-500/20 bg-slate-900/50 p-6">
                        <TriangleAlert className="mb-3 h-5 w-5 text-rose-400" />
                        <h2 className="text-lg font-semibold text-white">Optimizer unavailable</h2>
                        <p className="mt-2 text-sm text-slate-400">{error}</p>
                        <button onClick={() => window.location.reload()} className="mt-4 rounded-xl bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500">Retry</button>
                    </div>
                ) : data ? (
                    <div className="space-y-8">
                        <ProviderRecommendationsCard data={data} showOptimizerLink={false} />
                        {scenarios.length > 0 ? (
                            <section>
                                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                                    <h2 className="text-xl font-semibold text-white">Provider alternatives</h2>
                                    <div className="flex flex-wrap gap-3">
                                        <label className="flex items-center gap-2 text-sm text-slate-400">
                                            Account
                                            <select value={selectedAccount} onChange={(event) => setSelectedAccount(event.target.value)} className="max-w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-white">
                                                <option value="">All accounts</option>
                                                {accounts.map((account) => <option key={account} value={account}>{account}</option>)}
                                            </select>
                                        </label>
                                        <a href="https://console.aws.amazon.com/costmanagement/home#/savings-plans/recommendations" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500">
                                            Review on AWS <ArrowUpRight className="h-4 w-4" />
                                        </a>
                                        <button onClick={handleExportPdf} className="inline-flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm text-white">
                                            Export PDF <FileDown className="h-4 w-4" />
                                        </button>
                                    </div>
                                </div>
                                {exportError && <p role="alert" className="mb-4 text-sm text-rose-400">{exportError}</p>}
                                <div className="overflow-x-auto rounded-2xl border border-white/10">
                                    <table className="w-full min-w-[1200px] text-left text-sm">
                                        <thead className="bg-slate-900/50 text-xs text-slate-400">
                                            <tr>
                                                <th className="px-4 py-3">Account / alternative</th>
                                                <th className="px-4 py-3">Hourly commitment</th>
                                                <th className="px-4 py-3">Monthly equivalent</th>
                                                <th className="px-4 py-3">Estimated monthly savings</th>
                                                <th className="px-4 py-3">Estimated annual savings</th>
                                                <th className="px-4 py-3">Estimated savings %</th>
                                                <th className="px-4 py-3">Estimated utilization</th>
                                                <th className="px-4 py-3">Over-commitment risk</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {visibleScenarios.map((scenario) => (
                                                <tr key={`${scenario.integration_id}-${scenario.term_years}-${scenario.recommendation_id}`} className="border-t border-white/10 align-top">
                                                    <td className="max-w-xs px-4 py-4">
                                                        <p className="font-medium text-white">{scenario.label}</p>
                                                        <p className="mt-1 text-xs text-slate-400">{scenario.term_years}-year | {scenario.payment_option.replaceAll("_", " ").toLowerCase()}</p>
                                                        <p className="mt-1 break-all text-xs text-slate-400">Account: {scenario.account_id}</p>
                                                        <p className="mt-1 break-all text-xs text-slate-500">Integration: {scenario.integration_id}</p>
                                                        <p className="mt-1 text-xs text-slate-500">Lookback: {scenario.lookback_days} days</p>
                                                        <p className="mt-1 text-xs text-slate-500">Generated: {formatCommitmentDate(scenario.generated_at, true)}</p>
                                                    </td>
                                                    <td className="px-4 py-4">{formatCommitmentMoney(scenario.hourly_commitment_usd, data.currency)}</td>
                                                    <td className="px-4 py-4">{formatCommitmentMoney(scenario.monthly_commitment_usd, data.currency)}</td>
                                                    <td className="px-4 py-4">{formatCommitmentMoney(scenario.monthly_saving_usd, data.currency)}</td>
                                                    <td className="px-4 py-4">{formatCommitmentMoney(scenario.annual_saving_usd, data.currency)}</td>
                                                    <td className="px-4 py-4">{formatCommitmentPercent(scenario.provider_estimated_savings_pct)}</td>
                                                    <td className="px-4 py-4">{formatCommitmentPercent(scenario.estimated_utilization_pct)}</td>
                                                    <td className="px-4 py-4 text-slate-400">Not measured</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </section>
                        ) : <p className="text-sm text-slate-400">No provider alternatives available.</p>}
                        {(data.important_notes ?? []).length > 0 && (
                            <section>
                                <h2 className="text-lg font-semibold text-white">Important notes</h2>
                                <ul className="mt-3 list-inside list-disc space-y-2 text-sm text-slate-400">
                                    {data.important_notes?.map((note) => <li key={note}>{note}</li>)}
                                </ul>
                            </section>
                        )}
                    </div>
                ) : <p role="alert" className="text-slate-400">No provider response returned.</p>}
            </div>
        </main>
    );
}
