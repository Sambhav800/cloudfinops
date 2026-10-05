"use client";


import { TrendingDown, DollarSign, Cloud, BarChart3, Lock, AlertTriangle, Zap, PieChart, ArrowRight, Clock, Target, Flame, ArrowRightLeft } from "lucide-react";
import type { TeaserReportPayload, FindingTeaser } from "../types";

import { WASTE_GRADE_META } from "../constants";

interface TeaserReportProps {
  data: TeaserReportPayload;
  fileName: string;
}

const PROVIDER_LABELS: Record<string, string> = {
  aws: "Amazon Web Services",
  azure: "Microsoft Azure",
  gcp: "Google Cloud Platform",
  generic: "Cloud Provider",
};


const RISK_COLORS: Record<string, { border: string; bg: string; text: string; dot: string }> = {
  high: { border: "border-rose-500/30", bg: "bg-rose-500/5", text: "text-rose-400", dot: "bg-rose-500" },
  medium: { border: "border-amber-500/30", bg: "bg-amber-500/5", text: "text-amber-400", dot: "bg-amber-500" },
  low: { border: "border-emerald-500/30", bg: "bg-emerald-500/5", text: "text-emerald-400", dot: "bg-emerald-500" },
};


function formatCurrency(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}


function FindingCard({ finding, currency, index }: { finding: FindingTeaser; currency: string; index: number }) {
  const risk = RISK_COLORS[finding.risk_level] || RISK_COLORS.medium;

  return (
    <div className={`rounded-2xl border ${risk.border} ${risk.bg} p-5 transition-all hover:border-white/20`}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-mono text-slate-400 uppercase">
              {finding.category}
            </span>
            <div className={`flex items-center gap-1 rounded-full px-2 py-0.5 ${risk.bg} border ${risk.border}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${risk.dot}`} />
              <span className={`text-[10px] font-medium ${risk.text}`}>{finding.risk_level}</span>
            </div>
          </div>
          <h4 className="text-sm font-semibold text-white">{finding.service}</h4>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-lg font-bold text-white">
            {formatCurrency(finding.cost, currency)}
          </p>
          <p className="text-[11px] text-slate-500">{finding.pct_of_total}% of total</p>
        </div>
      </div>

      <p className="text-sm leading-relaxed text-slate-300 mb-3">{finding.what_we_found}</p>

      <div className="rounded-xl border border-white/[0.06] bg-black/20 px-4 py-3 mb-3">
        <p className="text-xs font-medium text-indigo-300 mb-1">Optimization paths:</p>
        <p className="text-xs text-slate-400 leading-relaxed">{finding.optimization_options}</p>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-rose-400 font-medium">
          ~{formatCurrency(finding.estimated_impact, currency)}/mo recoverable
        </span>
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <Lock className="h-3 w-3" />
          <span>CLI scripts unlocked after signup</span>
        </div>
      </div>
    </div>
  );
}

export function TeaserReport({ data, fileName }: TeaserReportProps) {
  const gradeMeta = WASTE_GRADE_META[data.waste_grade] ?? WASTE_GRADE_META["C"];
  const providerLabel = PROVIDER_LABELS[data.provider_detected] ?? "Cloud Provider";
  const annualSavingsMin = data.estimated_monthly_savings_min * 12;
  const annualSavingsMax = data.estimated_monthly_savings_max * 12;

  return (
    <div id="bill-scan-teaser-report" className="space-y-6">

      {/* ── Header ── */}
      <div className="flex flex-col items-start gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Scan Results</h2>

          <p className="text-sm text-slate-400">
            {providerLabel} · {fileName}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
            {data.rows_parsed.toLocaleString()} rows parsed
          </span>
          <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs font-medium text-indigo-400">
            {data.total_services_detected} services detected
          </span>
        </div>
      </div>

      {/* Headline metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className={`flex flex-col items-center justify-center gap-1 rounded-2xl border p-6 ${gradeMeta.bg}`}>
          <span className="text-xs font-medium uppercase tracking-widest text-slate-400">Waste Grade</span>
          <span className={`text-6xl font-black tabular-nums ${gradeMeta.color}`}>{data.waste_grade}</span>
          <span className="text-center text-xs text-slate-400">{gradeMeta.description}</span>
        </div>

        <div className="flex flex-col items-center justify-center gap-1 rounded-2xl border border-white/10 bg-slate-900/50 p-6">
          <DollarSign className="mb-1 h-5 w-5 text-slate-500" />
          <span className="text-xs font-medium uppercase tracking-widest text-slate-400">Monthly Spend</span>
          <span className="text-2xl font-bold text-white">
            {formatCurrency(data.total_analyzed_spend, data.currency)}
          </span>
          <span className="text-xs text-slate-500">{data.currency} · {data.rows_parsed} line items</span>
        </div>

        <div className="flex flex-col items-center justify-center gap-1 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-6">
          <TrendingDown className="mb-1 h-5 w-5 text-emerald-500" />
          <span className="text-xs font-medium uppercase tracking-widest text-slate-400">Est. Monthly Savings</span>

          <span className="text-2xl font-bold text-emerald-400">
            {formatCurrency(data.estimated_monthly_savings_min, data.currency)}
            {" – "}
            {formatCurrency(data.estimated_monthly_savings_max, data.currency)}
          </span>
          <span className="text-xs text-slate-500">

            {formatCurrency(annualSavingsMin, data.currency)} –{" "}
            {formatCurrency(annualSavingsMax, data.currency)} / year

          </span>
        </div>
      </div>


      {/* Urgency banner — "you've already burned $X" */}
      {data.annual_waste_so_far && data.annual_waste_so_far > 0 && (
        <div className="rounded-2xl border border-rose-500/20 bg-gradient-to-r from-rose-500/10 via-rose-500/5 to-transparent p-5">
          <div className="flex items-start gap-4">
            <div className="shrink-0 rounded-xl bg-rose-500/20 p-2.5">
              <Flame className="h-5 w-5 text-rose-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-rose-300">
                You&apos;ve burned ~{formatCurrency(data.annual_waste_so_far, data.currency)} in waste this year
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Every 30 days you wait costs another {formatCurrency(data.cost_of_waiting_30d ?? 0, data.currency)} in recoverable spend.
                {data.benchmark_label && (
                  <span className="text-slate-500"> Your efficiency is {data.benchmark_label}.</span>
                )}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Free quick win — taste of remediation */}
      {data.quick_win && (
        <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Target className="h-4 w-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-white">Free Quick Win</h3>
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
              {data.quick_win.risk} risk
            </span>
          </div>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white">{data.quick_win.title}</p>
              <p className="text-xs text-slate-400 mt-1">{data.quick_win.description}</p>
              <div className="flex items-center gap-3 mt-2">
                <span className="flex items-center gap-1 text-xs text-slate-500">
                  <Clock className="h-3 w-3" /> {data.quick_win.time_required}
                </span>
              </div>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-lg font-bold text-emerald-400">
                {formatCurrency(data.quick_win.saving_estimate, data.currency)}
              </p>
              <p className="text-[10px] text-slate-500">/mo savings</p>
            </div>
          </div>
        </div>
      )}

      {/* Cross-cloud hint */}
      {data.cross_cloud_hint && (
        <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/5 p-4">
          <div className="flex items-center gap-3">
            <ArrowRightLeft className="h-4 w-4 text-indigo-400 shrink-0" />
            <p className="text-sm text-slate-300">{data.cross_cloud_hint.message}</p>
            <div className="shrink-0 flex items-center gap-1.5">
              <Lock className="h-3 w-3 text-slate-500" />
              <span className="text-[10px] text-slate-500">Full comparison after signup</span>
            </div>
          </div>
        </div>
      )}

      {/* Quick insights row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-white/10 bg-slate-900/50 p-4 text-center">
          <p className="text-lg font-bold text-white">{data.services_above_5pct}</p>
          <p className="text-[11px] text-slate-500">Services &gt;5% of bill</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-900/50 p-4 text-center">
          <p className="text-lg font-bold text-white">{data.cost_concentration_top3_pct}%</p>
          <p className="text-[11px] text-slate-500">Top 3 concentration</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-900/50 p-4 text-center">
          <p className="text-lg font-bold text-white">
            {data.existing_credits_detected > 0 ? formatCurrency(data.existing_credits_detected, data.currency) : "None"}
          </p>
          <p className="text-[11px] text-slate-500">Credits detected</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-900/50 p-4 text-center">
          <p className="text-lg font-bold text-white">{data.top_findings_teaser.filter(f => f.risk_level === "high").length}</p>
          <p className="text-[11px] text-slate-500">High-risk findings</p>
        </div>
      </div>

      {/* Spend by category */}
      {Object.keys(data.by_category).length > 0 && (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
          <div className="mb-4 flex items-center gap-2">
            <PieChart className="h-4 w-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">Spend Distribution</h3>

          </div>
          <div className="space-y-3">
            {Object.entries(data.by_category)
              .sort(([, a], [, b]) => b - a)

              .slice(0, 8)

              .map(([category, amount]) => {
                const pct = Math.round((amount / data.total_analyzed_spend) * 100);
                return (
                  <div key={category} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-300">{category}</span>
                      <span className="tabular-nums text-slate-400">
                        {formatCurrency(amount, data.currency)}{" "}
                        <span className="text-xs text-slate-500">({pct}%)</span>
                      </span>
                    </div>

                    <div className="h-1 w-full overflow-hidden rounded-full bg-white/10">

                      <div
                        className="h-full rounded-full bg-gradient-to-r from-indigo-600 to-indigo-400"
                        style={{ width: `${Math.max(pct, 2)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      )}


      {/* Service-level findings */}
      {data.top_findings_teaser.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400" />
              <h3 className="text-sm font-semibold text-white">
                Complete Service-Level Analysis
              </h3>
            </div>
            <span className="text-xs text-slate-500">
              {data.top_findings_teaser.length} services · sorted by cost impact
            </span>
          </div>

          <div className="space-y-3">
            {data.top_findings_teaser.map((finding, idx) => (
              <FindingCard key={`${finding.service}-${idx}`} finding={finding} currency={data.currency} index={idx} />
            ))}
          </div>
        </div>
      )}

      {/* CloudFront insights */}
      {data.cloudfront_insights && (
        <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/5 p-5">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="h-4 w-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">CloudFront Deep Analysis</h3>
          </div>
          {data.cloudfront_insights.cache_hit_opportunity && (
            <p className="text-sm text-slate-300">{data.cloudfront_insights.cache_hit_opportunity}</p>
          )}
          {data.cloudfront_insights.top_recommendation && (
            <p className="text-sm text-indigo-300 mt-1">{data.cloudfront_insights.top_recommendation}</p>
          )}
        </div>
      )}

      {/* GPU insights */}
      {data.gpu_insights && (
        <div className="rounded-2xl border border-purple-500/20 bg-purple-500/5 p-5">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="h-4 w-4 text-purple-400" />
            <h3 className="text-sm font-semibold text-white">GPU Cost Intelligence</h3>
          </div>
          {data.gpu_insights.total_gpu_cost && (
            <p className="text-sm text-slate-300">
              GPU spend: {formatCurrency(data.gpu_insights.total_gpu_cost, data.currency)}/mo
            </p>
          )}
          {data.gpu_insights.spot_savings_opportunity && (
            <p className="text-sm text-purple-300 mt-1">
              Spot/preemptible potential: {formatCurrency(data.gpu_insights.spot_savings_opportunity, data.currency)}/mo
            </p>
          )}
        </div>
      )}

      {/* What's locked teaser */}
      <div className="rounded-2xl border border-white/[0.06] bg-gradient-to-br from-white/[0.02] to-transparent p-5">
        <div className="flex items-center gap-2 mb-3">
          <Lock className="h-4 w-4 text-slate-500" />
          <h3 className="text-sm font-medium text-slate-400">Unlock with free account</h3>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {["Resource-level inventory", "CLI remediation scripts", "Autoscaling configs", "Cross-cloud pricing", "30-day trend analysis", "Continuous monitoring"].map((item) => (
            <div key={item} className="flex items-center gap-1.5">
              <ArrowRight className="h-3 w-3 text-indigo-400 shrink-0" />
              <span className="text-xs text-slate-500">{item}</span>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
