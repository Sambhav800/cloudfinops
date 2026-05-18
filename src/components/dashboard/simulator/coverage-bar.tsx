'use client';

import type { SimulatorSummary } from './cost-delta-view';

type CoverageBarProps = {
    summary: SimulatorSummary;
};

const SEGMENT_COLORS = {
    exact: '#34d399',
    estimated: '#f59e0b',
    usage: '#6366f1',
    unestimated: '#94a3b8',
} as const;

export function CoverageBar({ summary }: CoverageBarProps) {
    const total = summary.total_resources || 1;
    const pct = (count: number) => Number(((count / total) * 100).toFixed(1));
    const segments = [
        { label: 'Exact price', count: summary.exact_resources, color: SEGMENT_COLORS.exact },
        { label: 'Estimated', count: summary.estimated_resources, color: SEGMENT_COLORS.estimated },
        { label: 'Usage-based', count: summary.usage_based_resources, color: SEGMENT_COLORS.usage },
        { label: 'Not priced', count: summary.unestimated_resources, color: SEGMENT_COLORS.unestimated },
    ]
        .map((segment) => ({ ...segment, pct: pct(segment.count) }))
        .filter((segment) => segment.count > 0);

    return (
        <div>
            <p className="mb-2 text-sm text-slate-400">
                Pricing coverage: {summary.priced_resources} of {summary.total_resources} resources priced
            </p>
            <div className="flex h-2 overflow-hidden rounded-full bg-slate-950/70">
                {segments.length > 0 ? (
                    segments.map((segment) => (
                        <div
                            key={segment.label}
                            style={{ width: `${segment.pct}%`, backgroundColor: segment.color }}
                        />
                    ))
                ) : (
                    <div className="w-full bg-slate-700" />
                )}
            </div>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
                {segments.map((segment) => (
                    <div key={segment.label} className="flex items-center gap-2">
                        <span
                            className="h-2 w-2 rounded-sm"
                            style={{ backgroundColor: segment.color }}
                        />
                        <span className="text-xs text-slate-400">
                            {segment.label} {segment.pct}%
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
