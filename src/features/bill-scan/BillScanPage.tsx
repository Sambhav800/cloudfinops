"use client";

import { useCallback, useState } from "react";
import { AlertCircle, RefreshCw, Zap } from "lucide-react";
import { PrivacyBanner } from "./components/PrivacyBanner";
import { BillDropzone } from "./components/BillDropzone";
import { ProcessingState } from "./components/ProcessingState";
import { TeaserReport } from "./components/TeaserReport";
import { ConversionCTA } from "./components/ConversionCTA";
import { executePublicScan } from "./api/publicScan";
import type { ScanState } from "./types";
import { RATE_LIMIT_COPY } from "./constants";

/** Top-level page composition for the public Bill Scanner. */
export function BillScanPage() {
  const [state, setState] = useState<ScanState>({ status: "idle" });

  const handleFileReady = useCallback(async (file: File) => {
    setState({ status: "uploading", file });
    try {
      const data = await executePublicScan(file);
      setState({ status: "results", data, fileName: file.name });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "An unexpected error occurred. Please try again.";
      setState({ status: "error", message });
    }
  }, []);

  const handleReset = useCallback(() => {
    setState({ status: "idle" });
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      {/* ── Background decoration ── */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -left-64 -top-64 h-[600px] w-[600px] rounded-full bg-indigo-600/5 blur-3xl" />
        <div className="absolute -right-64 top-1/3 h-[500px] w-[500px] rounded-full bg-indigo-500/5 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-3xl px-4 py-16 sm:px-6 lg:px-8">

        {/* ── Hero header ── */}
        <div className="mb-12 text-center">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-4 py-1.5">
            <Zap className="h-3.5 w-3.5 text-indigo-400" />
            <span className="text-xs font-medium text-indigo-300">Free · No signup required · {RATE_LIMIT_COPY}</span>
          </div>

          <h1 className="mb-4 text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
            Scan your cloud bill.{" "}
            <span className="bg-gradient-to-r from-indigo-400 to-indigo-300 bg-clip-text text-transparent">
              Find the waste.
            </span>
          </h1>

          <p className="mx-auto max-w-xl text-base text-slate-400 sm:text-lg">
            Drop your AWS, Azure, or GCP billing export and get an instant analysis of your
            spending patterns, waste grade, and savings potential — in seconds.
          </p>
        </div>

        {/* ── Main content area ── */}
        <div className="space-y-6">

          {/* Idle — show upload UI */}
          {state.status === "idle" && (
            <>
              <PrivacyBanner />
              <BillDropzone onFileReady={handleFileReady} />
            </>
          )}

          {/* Uploading — show progress indicator */}
          {state.status === "uploading" && (
            <ProcessingState />
          )}

          {/* Error state */}
          {state.status === "error" && (
            <div className="space-y-4">
              <div className="flex items-start gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-5">
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-400" />
                <div className="space-y-1">
                  <p className="font-semibold text-rose-300">Scan failed</p>
                  <p className="text-sm text-rose-400/80">{state.message}</p>
                </div>
              </div>
              <button
                id="bill-scan-retry-btn"
                type="button"
                onClick={handleReset}
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-medium text-slate-300 transition hover:bg-white/10 hover:text-white"
              >
                <RefreshCw className="h-4 w-4" />
                Try a different file
              </button>
            </div>
          )}

          {/* Results — show teaser report + CTA */}
          {state.status === "results" && (
            <div className="space-y-6">
              <TeaserReport data={state.data} fileName={state.fileName} />
              <ConversionCTA />

              {/* Scan another file link */}
              <div className="text-center">
                <button
                  id="bill-scan-another-btn"
                  type="button"
                  onClick={handleReset}
                  className="inline-flex items-center gap-2 text-sm text-slate-500 transition hover:text-slate-300"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Scan a different file
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ── Footer trust signals ── */}
        {state.status === "idle" && (
          <div className="mt-16 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-center">
            {[
              "AWS · Azure · GCP supported",
              "In-memory only — zero retention",
              "No account needed",
            ].map((item) => (
              <p key={item} className="text-xs text-slate-600">
                {item}
              </p>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
