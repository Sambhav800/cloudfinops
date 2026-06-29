"use client";

import { useState, useEffect } from "react";
import { PiggyBank, AlertTriangle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { CloudCommitment, FinanceCommitmentsResponse } from "@/lib/api";
import { formatInrCurrency, toDisplayInrAmount } from "@/lib/resources/contract";

import { CommitmentsKpiStrip } from "@/components/dashboard/commitments/kpi-strip";
import { CoverageDonut } from "@/components/dashboard/commitments/coverage-donut";
import { InvestmentReturn } from "@/components/dashboard/commitments/investment-return";
import { ExpiryTimeline } from "@/components/dashboard/commitments/expiry-timeline";
import type { ExpiryBucket } from "@/components/dashboard/commitments/expiry-timeline";
import { InventoryTable } from "@/components/dashboard/commitments/inventory-table";
import type { FormattedCommitment } from "@/components/dashboard/commitments/inventory-table";
import { AiCopilotCard } from "@/components/dashboard/commitments/ai-copilot-card";
import { ScenarioComparison } from "@/components/dashboard/commitments/scenario-comparison";

const formatMoney = (usd: number) =>
    formatInrCurrency(toDisplayInrAmount(usd, "USD"), {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });

type CommitmentScenario = {
    label: string;
    commitment_pct: number;
    monthly_commitment_usd: number;
    monthly_saving_usd: number;
    annual_saving_usd: number;
    effective_discount_pct: number;
    over_commitment_risk_pct: number;
    risk_level: "Low" | "Medium" | "High";
    term_years: number;
};

type CommitmentRecommendationResponse = {
    status: "ready" | "insufficient_history" | "no_spend_data";
    message?: string | null;
    days_available?: number | null;
    analysis_basis_days?: number | null;
    forecast_eom_spend_usd?: number | null;
    scenarios?: CommitmentScenario[];
    recommended_scenario?: CommitmentScenario | null;
};

function computeRiskLevel(utilization: number, daysRemaining: number): "Low" | "Medium" | "High" {
    if (utilization < 50 || daysRemaining < 30) return "High";
    if (utilization < 70 || daysRemaining < 90) return "Medium";
    return "Low";
}

function buildExpiryBuckets(commitments: FormattedCommitment[]): ExpiryBucket[] {
    const now = new Date();
    const buckets: ExpiryBucket[] = [];

    for (let i = 0; i < 6; i++) {
        const month = new Date(now.getFullYear(), now.getMonth() + i, 1);
        const label = month.toLocaleDateString("en-US", { month: "short" });
        buckets.push({
            month: label,
            count: 0,
            urgency: i === 0 ? "critical" : i <= 2 ? "warning" : "stable",
        });
    }

    for (const c of commitments) {
        if (c.status !== "active") continue;
        const endDate = new Date(c.end_date);
        const monthDiff =
            (endDate.getFullYear() - now.getFullYear()) * 12 +
            (endDate.getMonth() - now.getMonth());
        if (monthDiff >= 0 && monthDiff < 6) {
            buckets[monthDiff].count++;
        }
    }

    return buckets;
}

export default function CommitmentsPage() {
    const [commitments, setCommitments] = useState<CloudCommitment[]>([]);
    const [recommendation, setRecommendation] = useState<CommitmentRecommendationResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const loadData = async () => {
            setLoading(true);
            setError(null);

            try {
                const [commitmentsResponse, recommendationResponse] = await Promise.all([
                    fetch("/api/finance/commitments", { cache: "no-store" }),
                    fetch("/api/finance/commitment-recommendation", { cache: "no-store" }),
                ]);

                if (!commitmentsResponse.ok) {
                    const payload = await commitmentsResponse.json().catch(() => ({}));
                    setError(
                        typeof payload?.detail === "string"
                            ? payload.detail
                            : "Failed to load commitments"
                    );
                    setCommitments([]);
                } else {
                    const payload = (await commitmentsResponse.json()) as FinanceCommitmentsResponse;
                    setCommitments(payload.commitments ?? []);
                }

                if (recommendationResponse.ok) {
                    const payload = await recommendationResponse.json();
                    setRecommendation(payload as CommitmentRecommendationResponse);
                } else {
                    setRecommendation(null);
                }
            } catch (requestError) {
                setError(
                    requestError instanceof Error
                        ? requestError.message
                        : "Failed to load commitments"
                );
            } finally {
                setLoading(false);
            }
        };
        void loadData();
    }, []);

    // Derived metrics
    const formattedCommitments: FormattedCommitment[] = commitments.map((item) => {
        const endDate = new Date(item.end_date);
        const now = new Date();
        const daysRemaining = Math.ceil((endDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

        let displayStatus: "Critical" | "Warning" | "Stable" = "Stable";
        if (daysRemaining < 30) displayStatus = "Critical";
        else if (daysRemaining < 90) displayStatus = "Warning";

        return {
            ...item,
            region: item.region ?? null,
            daysRemaining,
            displayStatus,
            endDateStr: endDate.toLocaleDateString("en-US", {
                year: "numeric",
                month: "short",
                day: "numeric",
            }),
            formattedAmount: formatMoney(item.commitment_amount),
            formattedSavings: formatMoney(item.savings_amount),
            riskLevel: computeRiskLevel(item.utilization_pct, daysRemaining),
        };
    });

    const activeCommitments = formattedCommitments.filter((c) => c.status === "active");
    const hasCommitments = activeCommitments.length > 0;

    const totalPortfolioValue = activeCommitments.reduce((acc, c) => acc + c.commitment_amount, 0);
    const totalMonthlySavings = activeCommitments.reduce((acc, c) => acc + c.savings_amount, 0);
    const totalWaste = activeCommitments.reduce(
        (acc, c) => acc + c.commitment_amount * (1 - c.utilization_pct / 100),
        0
    );
    const wastePct = totalPortfolioValue > 0 ? (totalWaste / totalPortfolioValue) * 100 : 0;

    // Weighted average utilization
    const avgUtilization =
        totalPortfolioValue > 0
            ? Math.round(
                  activeCommitments.reduce(
                      (acc, c) => acc + c.utilization_pct * c.commitment_amount,
                      0
                  ) / totalPortfolioValue
              )
            : 0;

    // ESR: Effective Savings Rate = savings / (savings + total commitment cost)
    const esr =
        totalMonthlySavings + totalPortfolioValue > 0
            ? (totalMonthlySavings / (totalMonthlySavings + totalPortfolioValue)) * 100
            : 0;

    // ROI
    const roi = totalPortfolioValue > 0 ? (totalMonthlySavings / totalPortfolioValue) * 100 : 0;

    // Coverage data from recommendation
    const recommendedScenario =
        recommendation?.status === "ready" ? (recommendation.recommended_scenario ?? null) : null;
    const forecastSpend = recommendation?.forecast_eom_spend_usd ?? 0;
    const coveredSpend = recommendedScenario?.monthly_commitment_usd ?? 0;
    const uncoveredSpend = Math.max(forecastSpend - coveredSpend, 0);
    const coveragePct = recommendedScenario?.commitment_pct ?? 0;
    const hasCoverageData = Boolean(
        recommendation?.status === "ready" && recommendedScenario && forecastSpend > 0
    );
    const coverageEmptyMessage =
        recommendation?.message || "Connect a cloud account and run a scan to see coverage data.";
    const analysisDays = recommendation?.analysis_basis_days ?? 0;

    // Expiry buckets
    const expiryBuckets = buildExpiryBuckets(formattedCommitments);
    const criticalCount = formattedCommitments.filter(
        (c) => c.status === "active" && c.daysRemaining > 0 && c.daysRemaining < 30
    ).length;
    const warningCount = formattedCommitments.filter(
        (c) => c.status === "active" && c.daysRemaining >= 30 && c.daysRemaining < 90
    ).length;

    return (
        <main className="min-h-screen w-full bg-slate-950 p-6 text-slate-200 md:p-10">
            {/* Header */}
            <div className="mb-8">
                <div className="mb-2 flex items-center gap-3">
                    <div className="rounded-lg bg-emerald-500/20 p-2 text-emerald-400">
                        <PiggyBank className="h-6 w-6" />
                    </div>
                    <h1 className="text-3xl font-bold text-white">Commitment Command Center</h1>
                </div>
                <p className="text-lg text-slate-400">
                    Manage Reserved Instances, Savings Plans, and automated discount coverage.
                </p>
            </div>

            <AnimatePresence mode="wait">
                {error ? (
                    <motion.div
                        key="error"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="rounded-2xl border border-white/10 bg-slate-900/50 p-12 text-center backdrop-blur-xl"
                    >
                        <AlertTriangle className="mx-auto mb-4 h-12 w-12 text-rose-500" />
                        <h2 className="text-lg font-bold text-white">Failed to load commitments</h2>
                        <p className="mt-2 text-sm text-slate-400">{error}</p>
                        <button
                            onClick={() => window.location.reload()}
                            className="mt-6 rounded-xl bg-indigo-600 px-6 py-2 font-bold text-white transition-colors hover:bg-indigo-500"
                        >
                            Retry
                        </button>
                    </motion.div>
                ) : (
                    <motion.div
                        key="content"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="space-y-8"
                    >
                        {/* Section 2: KPI Strip */}
                        <CommitmentsKpiStrip
                            esr={esr}
                            monthlySavings={formatMoney(totalMonthlySavings)}
                            coverageRate={coveragePct}
                            waste={formatMoney(totalWaste)}
                            wastePct={wastePct}
                            isLoading={loading}
                            isEmpty={!hasCommitments && !loading}
                        />

                        {/* Section 3: Portfolio Health */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.2 }}
                            className="grid grid-cols-1 gap-6 lg:grid-cols-3"
                        >
                            <CoverageDonut
                                coveragePct={coveragePct}
                                coveredSpend={formatMoney(coveredSpend)}
                                uncoveredSpend={formatMoney(uncoveredSpend)}
                                isEmpty={!hasCoverageData && !loading}
                                emptyMessage={coverageEmptyMessage}
                            />
                            <InvestmentReturn
                                totalCommitted={formatMoney(totalPortfolioValue)}
                                totalSavings={formatMoney(totalMonthlySavings)}
                                roi={roi}
                                avgUtilization={avgUtilization}
                                isEmpty={!hasCommitments && !loading}
                            />
                            <ExpiryTimeline
                                buckets={expiryBuckets}
                                criticalCount={criticalCount}
                                warningCount={warningCount}
                                isEmpty={!hasCommitments && !loading}
                            />
                        </motion.div>

                        {/* Section 4: Inventory Table */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3 }}
                        >
                            <InventoryTable
                                commitments={formattedCommitments}
                                isLoading={loading}
                            />
                        </motion.div>

                        {/* Section 5: AI Recommendations + Scenarios */}
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.4 }}
                            className="grid grid-cols-1 gap-6 lg:grid-cols-5"
                        >
                            <AiCopilotCard
                                recommendedScenario={recommendedScenario}
                                uncoveredSpend={formatMoney(uncoveredSpend)}
                                coveragePct={coveragePct}
                                analysisDays={analysisDays}
                                formatMoney={formatMoney}
                                isEmpty={!hasCoverageData && !loading}
                                emptyMessage={coverageEmptyMessage}
                            />
                            <ScenarioComparison
                                scenarios={recommendation?.scenarios ?? []}
                                recommendedLabel={recommendedScenario?.label ?? null}
                                formatMoney={formatMoney}
                                isEmpty={!hasCoverageData && !loading}
                                emptyMessage={coverageEmptyMessage}
                            />
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </main>
    );
}
