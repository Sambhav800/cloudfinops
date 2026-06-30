"use client";

import { ShieldCheck } from "lucide-react";

export function PrivacyBanner() {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 px-5 py-4">
      <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" aria-hidden />
      <p className="text-sm leading-relaxed text-slate-300">
        <span className="font-semibold text-emerald-400">Your data stays private.</span>{" "}
        Your bill is analyzed strictly in-memory and deleted immediately after the report is
        generated. No storage retention applied — we never write your file to disk or cloud storage.
      </p>
    </div>
  );
}
