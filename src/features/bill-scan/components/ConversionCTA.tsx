"use client";

import { Lock } from "lucide-react";
import Link from "next/link";

/** Glassmorphic conversion wall shown below the redacted teaser report. */
export function ConversionCTA() {
  return (
    <div
      id="bill-scan-cta"
      className="relative overflow-hidden rounded-2xl border border-indigo-500/30 bg-gradient-to-br from-indigo-600/10 via-indigo-500/5 to-slate-900/50 p-8 text-center"
    >
      {/* Subtle radial glow */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.12),transparent_70%)]" />

      <div className="relative space-y-5">
        {/* Lock icon */}
        <div className="flex justify-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-indigo-500/30 bg-indigo-500/10">
            <Lock className="h-6 w-6 text-indigo-400" />
          </div>
        </div>

        <div className="space-y-2">
          <h3 className="text-xl font-bold text-white">Your full report is ready</h3>
          <p className="mx-auto max-w-sm text-sm text-slate-400">
            Resource-level findings, remediation scripts, and cross-cloud arbitrage tables are
            locked. Sign up free to unlock everything — no credit card required.
          </p>
        </div>

        {/* What's behind the wall */}
        <div className="mx-auto flex max-w-md flex-col gap-2 text-left sm:flex-row sm:flex-wrap sm:justify-center">
          {[
            "Full resource inventory",
            "Executable CLI fix scripts",
            "Cross-cloud pricing tables",
            "All findings (not just top 3)",
            "Continuous monitoring",
            "AI recommendations",
          ].map((item) => (
            <span
              key={item}
              className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
              {item}
            </span>
          ))}
        </div>

        {/* CTA button */}
        <Link
          id="bill-scan-signup-cta"
          href="/login"
          className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-8 py-3.5 text-sm font-semibold text-white shadow-lg shadow-indigo-600/25 transition-all hover:bg-indigo-500 hover:shadow-indigo-500/30 active:scale-[0.98]"
        >
          Get full breakdown — Sign up free
        </Link>

        <p className="text-xs text-slate-500">
          Free forever · No credit card · Setup in under 2 minutes
        </p>
      </div>
    </div>
  );
}
