'use client';

import { AlertTriangle } from 'lucide-react';

import type { SimulatorUnestimatedResource } from './cost-delta-view';

type UnestimatedListProps = {
    resources: SimulatorUnestimatedResource[];
};

export function UnestimatedList({ resources }: UnestimatedListProps) {
    if (resources.length === 0) {
        return null;
    }

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl shadow-black/40">
            <div className="mb-5 flex items-start gap-3">
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-2 text-amber-400">
                    <AlertTriangle className="h-5 w-5" />
                </div>
                <div>
                    <h3 className="text-base font-semibold text-white">
                        {resources.length} resource{resources.length > 1 ? 's' : ''} not priced
                    </h3>
                    <p className="mt-1 text-sm text-slate-400">
                        These Terraform resources were retained for review because no simulator pricing path matched them.
                    </p>
                </div>
            </div>
            <div className="space-y-3">
                {resources.map((resource, index) => (
                    <div
                        key={`${resource.resource_address}-${index}`}
                        className="flex flex-col gap-3 rounded-2xl border border-white/5 bg-slate-800/30 p-4 xl:flex-row xl:items-start xl:justify-between"
                    >
                        <div className="min-w-0">
                            <p className="break-all text-sm font-medium text-white">
                                {resource.resource_address}
                            </p>
                            <p className="mt-1 break-all text-xs text-slate-500">
                                {resource.resource_type} / {resource.provider} / {resource.region ?? 'global'} / {resource.action}
                            </p>
                        </div>
                        <p className="max-w-xl text-sm text-slate-400 xl:text-right">
                            {resource.reason}
                        </p>
                    </div>
                ))}
            </div>
        </div>
    );
}
