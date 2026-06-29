"use client";

import type { LucideIcon } from "lucide-react";

interface CommitmentEmptyStateProps {
    icon: LucideIcon;
    title: string;
    subtitle: string;
}

export function CommitmentEmptyState({ icon: Icon, title, subtitle }: CommitmentEmptyStateProps) {
    return (
        <div className="flex h-60 flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-center">
            <div className="mb-3 rounded-full bg-white/5 p-3">
                <Icon className="h-6 w-6 text-slate-400" />
            </div>
            <h4 className="text-sm font-medium text-white">{title}</h4>
            <p className="mt-1 max-w-xs text-xs text-slate-500">{subtitle}</p>
        </div>
    );
}
