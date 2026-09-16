"use client";

import { useState, useEffect, useCallback } from "react";
import {
  TrendingDown,
  ShieldCheck,
  AlertTriangle,
  Clock,
  ArrowRight,
  ChevronRight,
  X,
  Sparkles,
  RefreshCw,
  Layers,
  CheckCircle2,
  DollarSign,
  Percent,
} from "lucide-react";
import type {
  CommitmentPortfolio,
  CommitmentRecommendation,
  UnderutilizedCommitment,
  ExpiringCommitment,
  CommitmentRiskLevel,
} from "./types";

const PROVIDER_COLORS: Record<string, { label: string; badge: string }> = {
  aws: {
    label: "AWS",
    badge: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  },
  azure: {
    label: "Azure",
    badge: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  },
  gcp: {
    label: "GCP",
    badge: "border-blue-500/30 bg-blue-500/10 text-blue-300",
  },
};

const RISK_BADGES: Record<CommitmentRiskLevel, { label: string; className: string }> = {
  low: {
    label: "Low Risk",
    className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  },
  medium: {
    label: "Medium Risk",
    className: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  },
  high: {
    label: "High Risk",
    className: "border-rose-500/30 bg-rose-500/10 text-rose-400",
  },
};

function formatTypeShort(type: string): string {
  const map: Record<string, string> = {
    aws_compute_savings_plan: "Compute SP",
    aws_ec2_instance_savings_plan: "EC2 Instance SP",
    aws_reserved_instance: "Reserved Instance",
    azure_reserved_instance: "Azure RI",
    gcp_resource_cud: "Resource CUD",
    gcp_flexible_cud: "Flexible CUD",
  };
  return map[type] || type.replace(/_/g, " ").toUpperCase();
}

function formatUSD(val: number): string {
  return `$${Math.round(val).toLocaleString()}`;
}

interface CommitmentOptimizerCardProps {
  initialPortfolio?: CommitmentPortfolio | null;
}

export function CommitmentOptimizerCard({ initialPortfolio }: CommitmentOptimizerCardProps) {
  const [portfolio, setPortfolio] = useState<CommitmentPortfolio | null>(initialPortfolio ?? null);
  const [loading, setLoading] = useState(!initialPortfolio);
  const [error, setError] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [selectedRec, setSelectedRec] = useState<CommitmentRecommendation | null>(null);

  // Config query state
  const [coverageTarget, setCoverageTarget] = useState<number>(75);
  const [maxTerm, setMaxTerm] = useState<"1_year" | "3_year">("1_year");
  const [paymentOption, setPaymentOption] = useState<"no_upfront" | "partial_upfront" | "all_upfront">("no_upfront");

  const fetchPortfolio = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        coverage_target: String(coverageTarget),
        max_term: maxTerm,
        payment_option: paymentOption,
      });
      const res = await fetch(`/api/commitment-recommendations?${params.toString()}`);
      if (!res.ok) {
        throw new Error(`Failed to load recommendations (${res.status})`);
      }
      const data: CommitmentPortfolio = await res.json();
      setPortfolio(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load commitments");
    } finally {
      setLoading(false);
    }
  }, [coverageTarget, maxTerm, paymentOption]);

  useEffect(() => {
    if (!initialPortfolio) {
      fetchPortfolio();
    }
  }, [fetchPortfolio, initialPortfolio]);

  const hasRecommendations = (portfolio?.recommendations?.length ?? 0) > 0;
  const underutilized = portfolio?.underutilized_commitments ?? [];
  const expiring = portfolio?.expiring_soon ?? [];

  return (
    <div
      id="commitment-optimizer-card"
      className="relative overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl shadow-2xl shadow-black/20"
    >
      {/* Background radial accent */}
      <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-indigo-600/10 blur-3xl" />

      {/* Header section */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-indigo-500/30 bg-indigo-500/10 text-indigo-400">
              <Sparkles className="h-4 w-4" />
            </div>
            <h3 className="text-xl font-bold text-white tracking-tight">Commitment Optimizer</h3>
            <span className="rounded-full border border-indigo-500/20 bg-indigo-500/10 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider text-indigo-300">
              Purchase Engine
            </span>
          </div>
          <p className="text-xs text-slate-400 max-w-xl">
            Multi-cloud usage baselines analyzed to recommend optimal Savings Plans, Reserved Instances, and Committed Use Discounts without committing to oversized workloads.
          </p>
        </div>

        {/* Controls / Refresh */}
        <div className="flex items-center gap-2">
          <select
            value={coverageTarget}
            onChange={(e) => setCoverageTarget(Number(e.target.value))}
            className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-white/20 focus:border-indigo-500 focus:outline-none"
            aria-label="Coverage target percentage"
          >
            <option value={60}>60% Coverage (Conservative)</option>
            <option value={75}>75% Coverage (Recommended)</option>
            <option value={85}>85% Coverage (Aggressive)</option>
          </select>

          <select
            value={maxTerm}
            onChange={(e) => setMaxTerm(e.target.value as "1_year" | "3_year")}
            className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-white/20 focus:border-indigo-500 focus:outline-none"
            aria-label="Maximum term"
          >
            <option value="1_year">1-Year Max Term</option>
            <option value="3_year">3-Year Max Term</option>
          </select>

          <button
            type="button"
            onClick={fetchPortfolio}
            disabled={loading}
            className="flex h-8 w-8 items-center justify-center rounded-xl border border-white/10 bg-slate-950/60 text-slate-400 transition hover:border-white/20 hover:text-white disabled:opacity-50"
            title="Refresh recommendations"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Loading state */}
      {loading && !portfolio && (
        <div className="mt-8 flex flex-col items-center justify-center py-12 text-slate-400 space-y-3">
          <RefreshCw className="h-7 w-7 animate-spin text-indigo-400" />
          <p className="text-sm">Analyzing steady-state usage baselines...</p>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="mt-6 flex items-start gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
          <AlertTriangle className="h-5 w-5 shrink-0 text-rose-400 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold">Failed to load commitment recommendations</p>
            <p className="text-xs text-rose-400/80">{error}</p>
          </div>
        </div>
      )}

      {/* Portfolio loaded */}
      {portfolio && !loading && (
        <div className="mt-6 space-y-5">
          {/* Top KPI row */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {/* Total Annual Savings */}
            <div className="rounded-xl border border-white/5 bg-slate-950/50 p-4">
              <p className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                <TrendingDown className="h-3.5 w-3.5 text-emerald-400" />
                Potential Annual Savings
              </p>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold tracking-tight text-emerald-400">
                  {formatUSD(portfolio.total_annual_savings)}
                </span>
                <span className="text-xs font-medium text-slate-500">/yr</span>
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                {formatUSD(portfolio.total_monthly_savings)} / month reduction
              </p>
            </div>

            {/* Recommendations Count */}
            <div className="rounded-xl border border-white/5 bg-slate-950/50 p-4">
              <p className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-indigo-400" />
                Active Recommendations
              </p>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold tracking-tight text-white">
                  {portfolio.recommendations.length}
                </span>
                <span className="text-xs text-slate-500">purchase targets</span>
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                {portfolio.overall_savings_pct}% spend reduction
              </p>
            </div>

            {/* Overall Coverage */}
            <div className="rounded-xl border border-white/5 bg-slate-950/50 p-4">
              <p className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                <Percent className="h-3.5 w-3.5 text-sky-400" />
                Target Coverage
              </p>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold tracking-tight text-white">
                  {portfolio.overall_coverage_pct.toFixed(1)}%
                </span>
                <span className="text-xs text-slate-500">baseline</span>
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                Conservative P10 steady-state
              </p>
            </div>

            {/* Projected Spend */}
            <div className="rounded-xl border border-white/5 bg-slate-950/50 p-4">
              <p className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                <DollarSign className="h-3.5 w-3.5 text-purple-400" />
                Projected Monthly Spend
              </p>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold tracking-tight text-white">
                  {formatUSD(portfolio.projected_monthly_after_commitments)}
                </span>
                <span className="text-xs text-slate-500">/mo</span>
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                Down from {formatUSD(portfolio.current_monthly_on_demand)}
              </p>
            </div>
          </div>

          {/* Strategy Summary strip */}
          {portfolio.strategy_summary && (
            <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-3 text-xs text-indigo-200/90 flex items-start gap-2">
              <ShieldCheck className="h-4 w-4 shrink-0 text-indigo-400 mt-0.5" />
              <span>{portfolio.strategy_summary}</span>
            </div>
          )}

          {/* Alerts: Underutilized Commitments */}
          {underutilized.length > 0 && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-amber-300">
                  {underutilized.length} Underutilized Commitment{underutilized.length > 1 ? "s" : ""}
                </span>
              </div>
              <div className="space-y-2">
                {underutilized.map((u, i) => (
                  <div
                    key={u.id || i}
                    className="flex flex-col sm:flex-row sm:items-center justify-between rounded-lg border border-amber-500/20 bg-slate-950/60 p-2.5 text-xs text-slate-300 gap-2"
                  >
                    <div>
                      <p className="font-semibold text-white">{u.name || u.type || "Commitment"}</p>
                      <p className="text-slate-400 text-[11px]">
                        Utilization: <span className="text-amber-400 font-bold">{u.utilization_pct.toFixed(0)}%</span> · Wasting {formatUSD(u.wasted_monthly)}/mo
                      </p>
                    </div>
                    <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] text-amber-300 self-start sm:self-auto">
                      {u.action}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Alerts: Expiring Soon */}
          {expiring.length > 0 && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-rose-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-rose-300">
                  {expiring.length} Commitment{expiring.length > 1 ? "s" : ""} Expiring Soon (&lt;60 days)
                </span>
              </div>
              <div className="space-y-2">
                {expiring.map((exp, i) => (
                  <div
                    key={exp.id || i}
                    className="flex flex-col sm:flex-row sm:items-center justify-between rounded-lg border border-rose-500/20 bg-slate-950/60 p-2.5 text-xs text-slate-300 gap-2"
                  >
                    <div>
                      <p className="font-semibold text-white">{exp.name || exp.type || "Commitment"}</p>
                      <p className="text-slate-400 text-[11px]">
                        Expires in <span className="text-rose-400 font-bold">{exp.days_left} days</span> · Utilization: {exp.utilization_pct.toFixed(0)}%
                      </p>
                    </div>
                    <span className="rounded-md border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-[11px] text-rose-300 self-start sm:self-auto">
                      {exp.action}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommendation Highlights & Drawer Trigger */}
          {hasRecommendations ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Purchase Recommendations
                </p>
                <button
                  type="button"
                  id="view-all-commitments-btn"
                  onClick={() => setIsDrawerOpen(true)}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition"
                >
                  View All &amp; Breakdown
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>

              {/* Recommendation summary preview cards */}
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {portfolio.recommendations.slice(0, 2).map((rec, index) => {
                  const providerMeta = PROVIDER_COLORS[rec.provider] || {
                    label: rec.provider.toUpperCase(),
                    badge: "border-white/10 bg-white/5 text-slate-300",
                  };
                  const riskMeta = RISK_BADGES[rec.risk_level] || RISK_BADGES.low;

                  return (
                    <div
                      key={`${rec.instance_family}-${index}`}
                      onClick={() => {
                        setSelectedRec(rec);
                        setIsDrawerOpen(true);
                      }}
                      className="group cursor-pointer rounded-xl border border-white/10 bg-slate-950/50 p-4 transition-all hover:border-indigo-500/50 hover:bg-slate-950/80 space-y-3"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2">
                          <span className={`rounded-md border px-2 py-0.5 text-[11px] font-bold ${providerMeta.badge}`}>
                            {providerMeta.label}
                          </span>
                          <span className="text-xs font-bold text-white">
                            {formatTypeShort(rec.commitment_type)}
                          </span>
                        </div>
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${riskMeta.className}`}>
                          {riskMeta.label}
                        </span>
                      </div>

                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-400">
                          {rec.instance_family} ({rec.region})
                        </span>
                        <span className="font-mono text-emerald-400 font-bold">
                          +{formatUSD(rec.estimated_annual_savings)}/yr
                        </span>
                      </div>

                      <div className="flex items-center justify-between rounded-lg bg-white/[0.02] p-2 text-[11px] text-slate-400">
                        <span>
                          {formatUSD(rec.math_breakdown.monthly_on_demand || 0)}/mo &rarr;{" "}
                          <strong className="text-white">
                            {formatUSD((rec.math_breakdown.monthly_on_demand || 0) - rec.estimated_monthly_savings)}/mo
                          </strong>
                        </span>
                        <span className="text-indigo-300">
                          Break-even: {rec.math_breakdown.break_even_months ?? 3}mo
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-white/10 bg-white/[0.01] p-8 text-center text-slate-400">
              <CheckCircle2 className="h-8 w-8 text-slate-500 mb-2" />
              <p className="text-sm font-semibold text-white">No new commitments required</p>
              <p className="text-xs text-slate-500 mt-1 max-w-md">
                Your current compute usage is either fully covered by existing reservations or currently below the threshold for commitment savings.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Slide-over Drawer for All Recommendations */}
      {isDrawerOpen && portfolio && (
        <div
          id="commitment-optimizer-drawer"
          className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm transition-all"
        >
          <div className="relative flex h-full w-full max-w-2xl flex-col bg-slate-900 border-l border-white/10 p-6 shadow-2xl overflow-y-auto">
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <div>
                <h4 className="text-lg font-bold text-white flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-indigo-400" />
                  Commitment Purchase Plan
                </h4>
                <p className="text-xs text-slate-400">
                  {portfolio.recommendations.length} recommendation{portfolio.recommendations.length > 1 ? "s" : ""} · Total savings:{" "}
                  <strong className="text-emerald-400">{formatUSD(portfolio.total_annual_savings)}/yr</strong>
                </p>
              </div>
              <button
                type="button"
                id="close-commitment-drawer-btn"
                onClick={() => {
                  setIsDrawerOpen(false);
                  setSelectedRec(null);
                }}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 text-slate-400 transition hover:bg-white/10 hover:text-white"
                aria-label="Close drawer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Drawer Content */}
            <div className="mt-6 space-y-6">
              {portfolio.recommendations.map((rec, idx) => {
                const providerMeta = PROVIDER_COLORS[rec.provider] || {
                  label: rec.provider.toUpperCase(),
                  badge: "border-white/10 bg-white/5 text-slate-300",
                };
                const riskMeta = RISK_BADGES[rec.risk_level] || RISK_BADGES.low;
                const isExpanded = selectedRec === rec || portfolio.recommendations.length === 1;

                return (
                  <div
                    key={`${rec.commitment_type}-${rec.instance_family}-${idx}`}
                    className="rounded-2xl border border-white/10 bg-slate-950/60 p-5 space-y-4 transition-all"
                  >
                    {/* Top line badges */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className={`rounded-md border px-2.5 py-0.5 text-xs font-bold ${providerMeta.badge}`}>
                          {providerMeta.label}
                        </span>
                        <span className="rounded-md border border-white/10 bg-white/5 px-2.5 py-0.5 text-xs font-semibold text-white">
                          {formatTypeShort(rec.commitment_type)}
                        </span>
                        <span className="text-xs text-slate-400">
                          {rec.instance_family} ({rec.region})
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-emerald-400">
                          +{formatUSD(rec.estimated_annual_savings)}/yr
                        </span>
                        <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold ${riskMeta.className}`}>
                          {riskMeta.label}
                        </span>
                      </div>
                    </div>

                    {/* Spend Transformation Box */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 rounded-xl border border-white/5 bg-slate-900/60 p-3 text-center">
                      <div>
                        <p className="text-[10px] text-slate-400 uppercase font-medium">Current Spend</p>
                        <p className="text-sm font-bold text-slate-300 mt-0.5">
                          {formatUSD(rec.math_breakdown.monthly_on_demand || 0)}/mo
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-400 uppercase font-medium">Projected Spend</p>
                        <p className="text-sm font-bold text-emerald-400 mt-0.5">
                          {formatUSD((rec.math_breakdown.monthly_on_demand || 0) - rec.estimated_monthly_savings)}/mo
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-400 uppercase font-medium">Discount</p>
                        <p className="text-sm font-bold text-indigo-300 mt-0.5">
                          {(rec.discount_rate * 100).toFixed(0)}% off
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-400 uppercase font-medium">Break-Even</p>
                        <p className="text-sm font-bold text-white mt-0.5">
                          {rec.math_breakdown.break_even_months ?? 3} mo
                        </p>
                      </div>
                    </div>

                    {/* Full Explanation from Engine */}
                    <div className="space-y-1.5">
                      <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                        Engine Explanation
                      </p>
                      <p className="rounded-xl border border-white/5 bg-slate-900/40 p-3.5 text-xs text-slate-300 leading-relaxed">
                        {rec.explanation}
                      </p>
                    </div>

                    {/* Math Breakdown Transparency */}
                    <div className="rounded-xl border border-white/5 bg-slate-950/40 p-3 space-y-2 text-xs text-slate-400">
                      <div className="flex items-center justify-between text-[11px]">
                        <span>Committed Hourly Target:</span>
                        <strong className="font-mono text-white">
                          ${rec.hourly_commitment.toFixed(3)}/hr ({rec.coverage_pct.toFixed(0)}% of P10 baseline)
                        </strong>
                      </div>
                      <div className="flex items-center justify-between text-[11px]">
                        <span>Term &amp; Payment Preference:</span>
                        <strong className="text-slate-300">
                          {rec.term === "1_year" ? "1-Year" : "3-Year"} · {rec.payment_option.replace(/_/g, " ")}
                        </strong>
                      </div>
                      <div className="flex items-center justify-between text-[11px]">
                        <span>Utilization Confidence:</span>
                        <strong className="text-emerald-400">
                          {(rec.utilization_confidence * 100).toFixed(0)}%
                        </strong>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Footer */}
            <div className="mt-auto border-t border-white/10 pt-4 flex items-center justify-between text-xs text-slate-400">
              <span>Full mathematical transparency enabled</span>
              <button
                type="button"
                onClick={() => setIsDrawerOpen(false)}
                className="rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-semibold text-white transition hover:bg-indigo-500 shadow-lg shadow-indigo-600/25"
              >
                Close Plan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
