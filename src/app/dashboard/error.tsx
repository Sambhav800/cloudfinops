"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center gap-4 p-8">
      <div className="rounded-full bg-rose-500/10 p-4 border border-rose-500/20">
        <AlertTriangle className="h-8 w-8 text-rose-400" />
      </div>
      <h2 className="text-xl text-white font-semibold">Something went wrong</h2>
      <p className="text-gray-400 max-w-md text-sm">
        An unexpected error occurred while loading this page. This has been logged automatically.
      </p>
      {process.env.NODE_ENV === "development" && error.message && (
        <pre className="mt-2 max-w-lg text-xs text-rose-300/70 bg-rose-500/5 border border-rose-500/10 rounded-lg p-3 overflow-x-auto">
          {error.message}
        </pre>
      )}
      <button
        onClick={reset}
        className="mt-2 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm hover:bg-white/10 transition-colors"
      >
        <RotateCcw className="h-4 w-4" />
        Try again
      </button>
    </div>
  );
}
