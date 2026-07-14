"use client";

import { TrendingDown, DollarSign, Cloud, BarChart3, Lock } from "lucide-react";
import type { TeaserReportPayload } from "../types";
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

function formatCurrency(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/** Renders the redacted teaser report panel. */
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
        <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
          {data.rows_parsed.toLocaleString()} rows parsed
        </span>
      </div>

      {/* ── Headline metrics ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {/* Waste Grade */}
        <div
          className={`flex flex-col items-center justify-center gap-1 rounded-2xl border p-6 ${gradeMeta.bg}`}
        >
          <span className="text-xs font-medium uppercase tracking-widest text-slate-400">
            Waste Grade
          </span>
          <span className={`text-6xl font-black tabular-nums ${gradeMeta.color}`}>
            {data.waste_grade}
          </span>
          <span className="text-center text-xs text-slate-400">{gradeMeta.description}</span>
        </div>

        {/* Total Spend */}
        <div className="flex flex-col items-center justify-center gap-1 rounded-2xl border border-white/10 bg-slate-900/50 p-6">
          <DollarSign className="mb-1 h-5 w-5 text-slate-500" />
          <span className="text-xs font-medium uppercase tracking-widest text-slate-400">
            Monthly Spend Analyzed
          </span>
          <span className="text-2xl font-bold text-white">
            {formatCurrency(data.total_analyzed_spend, data.currency)}
          </span>
          <span className="text-xs text-slate-500">{data.currency}</span>
        </div>

        {/* Savings Potential */}
        <div className="flex flex-col items-center justify-center gap-1 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-6">
          <TrendingDown className="mb-1 h-5 w-5 text-emerald-500" />
          <span className="text-xs font-medium uppercase tracking-widest text-slate-400">
            Est. Monthly Savings
          </span>
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

      {/* ── Spend by category ── */}
      {Object.keys(data.by_category).length > 0 && (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
          <div className="mb-4 flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">Spend by Category</h3>
          </div>
          <div className="space-y-3">
            {Object.entries(data.by_category)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 6)
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

      {/* ── Top 3 findings (redacted) ── */}
      {data.top_findings_teaser.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Cloud className="h-4 w-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-white">
              Top Findings{" "}
              <span className="font-normal text-slate-500">
                (showing {data.top_findings_teaser.length} of many)
              </span>
            </h3>
          </div>

          {data.top_findings_teaser.map((finding, idx) => (
            <div
              key={`${finding.service}-${idx}`}
              className="rounded-2xl border border-white/10 bg-slate-900/50 p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-xs font-mono text-slate-400">
                      {finding.category}
                    </span>
                    <h4 className="truncate text-sm font-semibold text-white">{finding.service}</h4>
                  </div>
                  <p className="text-sm leading-relaxed text-slate-400">{finding.what_we_found}</p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-base font-bold text-rose-400">
                    {formatCurrency(finding.estimated_impact, data.currency)}
                  </p>
                  <p className="text-xs text-slate-500">/mo at risk</p>
                </div>
              </div>

              {/* Redacted fix steps */}
              <div className="mt-4 flex items-center gap-2 rounded-xl border border-white/10 bg-black/30 px-4 py-3">
                <Lock className="h-3.5 w-3.5 shrink-0 text-slate-500" />
                <p className="text-xs text-slate-500">
                  Remediation steps and resource IDs unlocked after signup
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
