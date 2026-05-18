'use client';

import {
    Network,
    Flame,
    Boxes,
    TrendingDown,
    Shield,
    Loader2,
    Lock,
    Sparkles,
} from 'lucide-react';
import type { ViewId, ProposedMode } from '@/lib/architecture-types';

interface Props {
    activeView: ViewId;
    onViewChange: (view: ViewId) => void;
    microservicesAvailable: boolean;
    proposedCostCached: boolean;
    proposedReliabilityCached: boolean;
    onGenerateClick: (mode: ProposedMode) => void;
    proposedLoading: boolean;
}

interface NavItem {
    id: ViewId;
    label: string;
    icon: React.ElementType;
    gated?: boolean;
    gatedMessage?: string;
    isProposed?: boolean;
    proposedMode?: ProposedMode;
    cached?: boolean;
}

export function ViewRail({
    activeView,
    onViewChange,
    microservicesAvailable,
    proposedCostCached,
    proposedReliabilityCached,
    onGenerateClick,
    proposedLoading,
}: Props) {
    const currentViews: NavItem[] = [
        { id: 'topology_summary', label: 'Topology', icon: Network },
        { id: 'cost_hotspots', label: 'Cost Hotspots', icon: Flame },
        {
            id: 'microservices',
            label: 'Microservices',
            icon: Boxes,
            gated: !microservicesAvailable,
            gatedMessage: 'Requires EKS or ECS scan permissions',
        },
    ];

    const proposedViews: NavItem[] = [
        {
            id: 'proposed_cost',
            label: 'Cost-Optimized',
            icon: TrendingDown,
            isProposed: true,
            proposedMode: 'cost_optimized',
            cached: proposedCostCached,
        },
        {
            id: 'proposed_reliability',
            label: 'Reliability / Security',
            icon: Shield,
            isProposed: true,
            proposedMode: 'reliability_security_optimized',
            cached: proposedReliabilityCached,
        },
    ];

    const renderItem = (item: NavItem) => {
        const isActive = activeView === item.id;
        const isGated = item.gated;
        const Icon = item.icon;

        // Gated (locked) item
        if (isGated) {
            return (
                <div
                    key={item.id}
                    className="group relative flex cursor-not-allowed items-center gap-2.5 px-3 py-2 text-slate-500"
                    title={item.gatedMessage}
                >
                    <Lock className="w-4 h-4" />
                    <span className="text-xs">{item.label}</span>
                    {/* Tooltip */}
                    <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                        <div className="whitespace-nowrap rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-[10px] text-slate-300 shadow-xl">
                            {item.gatedMessage}
                        </div>
                    </div>
                </div>
            );
        }

        // Proposed item — not yet generated
        if (item.isProposed && !item.cached) {
            return (
                <button
                    key={item.id}
                    onClick={() => item.proposedMode && onGenerateClick(item.proposedMode)}
                    disabled={proposedLoading}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-slate-400 transition-all hover:bg-slate-800/50 hover:text-white"
                >
                    {proposedLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                    ) : (
                        <Sparkles className="w-4 h-4 text-indigo-400/60" />
                    )}
                    <span className="text-xs">{item.label}</span>
                    <span className="ml-auto rounded-full border border-indigo-500/20 bg-indigo-500/10 px-1.5 py-0.5 text-[9px] text-indigo-400">
                        Generate
                    </span>
                </button>
            );
        }

        // Normal or cached proposed item
        return (
            <button
                key={item.id}
                onClick={() => onViewChange(item.id)}
                className={`flex w-full items-center gap-2.5 rounded-lg border-l-4 px-3 py-2 text-left transition-all ${isActive
                        ? 'border-l-indigo-500 bg-indigo-600/20 text-indigo-400'
                        : 'border-l-transparent text-slate-400 hover:bg-slate-800/50 hover:text-white'
                    }`}
            >
                <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-400' : ''}`} />
                <span className="text-xs font-medium">{item.label}</span>
                {item.isProposed && item.cached && (
                    <span className="ml-auto rounded-full border border-emerald-500/20 bg-emerald-500/10 px-1.5 py-0.5 text-[9px] text-emerald-400">
                        Cached
                    </span>
                )}
            </button>
        );
    };

    return (
        <div className="flex w-52 shrink-0 flex-col border-r border-white/10 bg-slate-900 py-3">
            {/* Current section */}
            <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                Current
            </p>
            {currentViews.map(renderItem)}

            {/* Divider */}
            <div className="mx-3 my-3 border-t border-white/5" />

            {/* Proposed section */}
            <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                Proposed
            </p>
            {proposedViews.map(renderItem)}
        </div>
    );
}
