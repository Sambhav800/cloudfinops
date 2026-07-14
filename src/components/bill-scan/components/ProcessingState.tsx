"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { PROCESSING_STAGES } from "../constants";

/** Deterministic progress bar that steps through labeled analysis stages. */
export function ProcessingState() {
  const [stageIndex, setStageIndex] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Advance one stage roughly every 5 seconds.
    intervalRef.current = setInterval(() => {
      setStageIndex((prev) => Math.min(prev + 1, PROCESSING_STAGES.length - 1));
    }, 5_000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  // Derive progress percentage directly — no second setState needed.
  const progress = useMemo(
    () => Math.round(((stageIndex + 1) / PROCESSING_STAGES.length) * 92),
    [stageIndex],
  );

  const currentStageLabel = PROCESSING_STAGES[stageIndex];

  return (
    <div className="w-full space-y-6 rounded-2xl border border-white/10 bg-slate-900/50 p-8 text-center">
      {/* Animated spinner */}
      <div className="flex justify-center">
        <div className="relative h-16 w-16">
          <div className="absolute inset-0 animate-spin rounded-full border-2 border-indigo-500/20 border-t-indigo-500" />
          <div className="absolute inset-2 animate-spin rounded-full border-2 border-indigo-400/10 border-t-indigo-400 [animation-direction:reverse] [animation-duration:1.5s]" />
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-3 w-3 animate-pulse rounded-full bg-indigo-500" />
          </div>
        </div>
      </div>

      {/* Stage label */}
      <div className="space-y-1.5">
        <p className="text-base font-semibold text-white">{currentStageLabel}</p>
        <p className="text-sm text-slate-400">
          This typically takes 10–30 seconds depending on file size.
        </p>
      </div>

      {/* Progress bar */}
      <div className="space-y-2">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-indigo-600 to-indigo-400 transition-all duration-[1500ms] ease-out"
            style={{ width: `${progress}%` }}
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>

        {/* Stage pills */}
        <div className="flex items-center justify-between">
          {PROCESSING_STAGES.map((stage, i) => (
            <div
              key={stage}
              className={[
                "h-1.5 w-1.5 rounded-full transition-all duration-500",
                i <= stageIndex ? "bg-indigo-500 scale-125" : "bg-white/20",
              ].join(" ")}
              title={stage}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
