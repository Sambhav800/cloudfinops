'use client';

import { useState, useEffect, useCallback } from 'react';
import { getGraphAction, generateProposedAction } from '@/app/actions/architecture';
import type {
    GraphResponse,
    RegionGraphResult,
    ViewData,
    GraphNode,
    ProposedResult,
    ViewId,
    CurrentViewId,
    ProposedMode,
    CoverageWarning,
} from '@/lib/architecture-types';
import { TopBar } from './top-bar';
import { ViewRail } from './view-rail';
import { MainCanvas } from './main-canvas';
import { InspectorPanel } from './inspector-panel';
import { ResourceTable } from './resource-table';
import { ChangeListPanel } from './change-list-panel';
import { GenerateModal } from './generate-modal';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';

interface Integration {
    id: string;
    provider: string;
    name: string | null;
    last_scan?: string | null;
}

interface Props {
    integrations: Integration[];
}

const loadingSurfaceClassName = "rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-xl";

export function ArchitecturePageV2({ integrations }: Props) {
    // ---- state ----
    const [activeIntegrationIndex, setActiveIntegrationIndex] = useState(0);
    const activeIntegration = integrations[activeIntegrationIndex] || integrations[0];

    const integrationId = activeIntegration.id;
    const integrationProvider = activeIntegration.provider;
    const integrationName = activeIntegration.name || `${integrationProvider.toUpperCase()} Integration`;
    const lastScan = activeIntegration.last_scan || undefined;

    const [graphData, setGraphData] = useState<GraphResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [activeRegion, setActiveRegion] = useState('');
    const [activeView, setActiveView] = useState<ViewId>('topology_summary');
    const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

    // Proposed state
    const [proposedCost, setProposedCost] = useState<ProposedResult | null>(null);
    const [proposedReliability, setProposedReliability] = useState<ProposedResult | null>(null);
    const [proposedLoading, setProposedLoading] = useState(false);
    const [generateModalMode, setGenerateModalMode] = useState<ProposedMode | null>(null);

    // Reset proposed state when integration changes
    useEffect(() => {
        setProposedCost(null);
        setProposedReliability(null);
        setActiveView('topology_summary');
    }, [integrationId]);

    // ---- fetch graph ----
    const fetchGraph = useCallback(async () => {
        setLoading(true);
        setError(null);
        const { data, error: err } = await getGraphAction(integrationId, integrationProvider);
        if (err || !data) {
            setError(err || 'Failed to load architecture data');
        } else {
            setGraphData(data);
            if (data.regions.length > 0 && !activeRegion) {
                setActiveRegion(data.regions[0].region);
            }
        }
        setLoading(false);
    }, [integrationId, integrationProvider, activeRegion]);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            void fetchGraph();
        }, 0);
        return () => window.clearTimeout(timer);
    }, [fetchGraph]);

    // ---- derived state ----
    const currentRegion: RegionGraphResult | undefined =
        graphData?.regions.find(r => r.region === activeRegion) ?? graphData?.regions[0];

    const isProposedView = activeView === 'proposed_cost' || activeView === 'proposed_reliability';
    const currentProposed = activeView === 'proposed_cost' ? proposedCost : proposedReliability;

    // get the view data for current/non-proposed views
    let currentViewData: ViewData | undefined;
    if (!isProposedView && currentRegion) {
        const viewKey = activeView as CurrentViewId;
        currentViewData = currentRegion.views[viewKey];
    }

    const mermaidCode = isProposedView
        ? currentProposed?.proposed_mermaid ?? ''
        : currentViewData?.mermaid ?? '';

    const coverage = currentRegion?.coverage;
    const microservicesAvailable = coverage?.microservices_available ?? false;
    const warningSource: CoverageWarning[] = isProposedView
        ? currentProposed?.warnings ?? []
        : [...(currentViewData?.warnings ?? []), ...(coverage?.warnings ?? [])];
    const canvasWarnings = Array.from(
        new Map(warningSource.map((warning) => [`${warning.type}:${warning.message}`, warning] as const)).values(),
    );

    // ---- handle proposed generation ----
    const handleGenerate = async (mode: ProposedMode) => {
        const targetRegion = activeRegion || graphData?.regions[0]?.region || '';
        if (!targetRegion) {
            setError('No region available for proposed architecture generation');
            return;
        }
        setGenerateModalMode(null);
        setProposedLoading(true);
        const { data, error: err } = await generateProposedAction(
            integrationId,
            integrationProvider,
            targetRegion,
            mode,
        );
        setProposedLoading(false);
        if (data) {
            if (mode === 'cost_optimized') {
                setProposedCost(data);
                setActiveView('proposed_cost');
            } else {
                setProposedReliability(data);
                setActiveView('proposed_reliability');
            }
        } else if (err) {
            setError(err);
        }
    };

    // ---- loading ----
    if (loading) {
        return (
            <>
                <div className={`${loadingSurfaceClassName} p-4`}>
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                        <div className="space-y-2">
                            <Skeleton className="h-6 w-52 bg-slate-800" />
                            <Skeleton className="h-4 w-40 bg-slate-800" />
                        </div>
                        <div className="flex flex-wrap gap-3">
                            <Skeleton className="h-10 w-40 rounded-xl bg-slate-800" />
                            <Skeleton className="h-10 w-36 rounded-xl bg-slate-800" />
                        </div>
                    </div>

                    <div className="mt-4 flex flex-wrap gap-3">
                        {Array.from({ length: 3 }, (_, index) => (
                            <div
                                key={index}
                                className="rounded-xl border border-white/10 bg-slate-900 px-4 py-3"
                            >
                                <Skeleton className="mb-2 h-3 w-20 bg-slate-800" />
                                <Skeleton className="h-4 w-28 bg-slate-800" />
                            </div>
                        ))}
                    </div>
                </div>

                <div className="mt-3 flex flex-col overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50 xl:flex-row">
                    <div className="border-b border-white/10 p-4 xl:w-64 xl:border-b-0 xl:border-r">
                        <Skeleton className="mb-4 h-4 w-24 bg-slate-800" />
                        <div className="space-y-2">
                            {Array.from({ length: 5 }, (_, index) => (
                                <div
                                    key={index}
                                    className="rounded-xl border border-white/10 bg-slate-900 p-3"
                                >
                                    <Skeleton className="mb-2 h-4 w-28 bg-slate-800" />
                                    <Skeleton className="h-3 w-20 bg-slate-800" />
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="flex-1 border-b border-white/10 p-4 xl:border-b-0 xl:border-r">
                        <div className="mb-4 flex flex-wrap gap-2">
                            <Skeleton className="h-9 w-28 rounded-lg bg-slate-800" />
                            <Skeleton className="h-9 w-24 rounded-lg bg-slate-800" />
                            <Skeleton className="h-9 w-32 rounded-lg bg-slate-800" />
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-slate-900 p-4">
                            <Skeleton className="h-[420px] w-full rounded-2xl bg-slate-800/70" />
                        </div>
                    </div>

                    <div className="p-4 xl:w-80">
                        <Skeleton className="mb-4 h-5 w-32 bg-slate-800" />
                        <div className="space-y-3">
                            {Array.from({ length: 4 }, (_, index) => (
                                <div
                                    key={index}
                                    className="rounded-xl border border-white/10 bg-slate-900 p-4"
                                >
                                    <Skeleton className="mb-2 h-4 w-24 bg-slate-800" />
                                    <Skeleton className="mb-2 h-4 w-full bg-slate-800" />
                                    <Skeleton className="h-4 w-5/6 bg-slate-800" />
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                <div className={`${loadingSurfaceClassName} mt-4 overflow-hidden`}>
                    <div className="border-b border-white/10 p-4">
                        <Skeleton className="mb-2 h-5 w-40 bg-slate-800" />
                        <Skeleton className="h-4 w-64 bg-slate-800" />
                    </div>
                    <div className="grid grid-cols-[1.2fr_repeat(3,minmax(0,1fr))] gap-4 border-b border-white/10 px-4 py-3">
                        {Array.from({ length: 4 }, (_, index) => (
                            <Skeleton key={index} className="h-4 w-full bg-slate-800" />
                        ))}
                    </div>
                    <div className="divide-y divide-white/5">
                        {Array.from({ length: 5 }, (_, row) => (
                            <div key={row} className="grid grid-cols-[1.2fr_repeat(3,minmax(0,1fr))] gap-4 px-4 py-4">
                                {Array.from({ length: 4 }, (_, column) => (
                                    <Skeleton key={column} className="h-4 w-full bg-slate-800" />
                                ))}
                            </div>
                        ))}
                    </div>
                </div>
            </>
        );
    }

    // ---- error ----
    if (error && !graphData) {
        return (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-rose-500/20 bg-slate-900/50 p-12 backdrop-blur-xl">
                <AlertCircle className="w-12 h-12 text-rose-500 mb-4" />
                <h3 className="text-white font-medium text-lg mb-2">Failed to Load Architecture</h3>
                <p className="text-rose-400 text-sm mb-4">{error}</p>
                <button
                    onClick={fetchGraph}
                    className="flex items-center gap-2 rounded-xl border border-white/10 bg-slate-800 px-4 py-2 text-slate-300 transition-colors hover:bg-slate-700 hover:text-white"
                >
                    <RefreshCw className="w-4 h-4" /> Retry
                </button>
            </div>
        );
    }

    // ---- main layout ----
    return (
        <div className="flex flex-col gap-0 min-h-[80vh]">
            {integrations.length > 1 && (
                <div className="mb-4 flex gap-2 overflow-x-auto rounded-2xl border border-white/10 bg-slate-900/50 p-2 backdrop-blur-xl">
                    {integrations.map((integ, index) => (
                        <button
                            key={integ.id}
                            onClick={() => setActiveIntegrationIndex(index)}
                            className={`flex items-center gap-2 whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                                index === activeIntegrationIndex
                                    ? 'border border-indigo-500/30 bg-indigo-600/20 text-indigo-400'
                                    : 'border border-transparent bg-slate-800/50 text-slate-400 hover:bg-slate-800/70 hover:text-white'
                            }`}
                        >
                            <span className="rounded-full border border-white/10 bg-slate-900 px-2 py-0.5 text-xs uppercase text-slate-300">
                                {integ.provider}
                            </span>
                            {integ.name || `${integ.provider.toUpperCase()} Integration`}
                        </button>
                    ))}
                </div>
            )}
            {/* Top Bar */}
            <TopBar
                integrationName={integrationName ?? `${integrationProvider.toUpperCase()} Integration`}
                provider={integrationProvider}
                lastScan={lastScan}
                regions={graphData?.regions.map(r => r.region) ?? []}
                activeRegion={activeRegion}
                onRegionChange={(r) => { setActiveRegion(r); setSelectedNode(null); }}
                coverage={coverage ?? null}
            />

            {/* Content: Rail + Canvas + Inspector */}
            <div className="mt-3 flex flex-1 gap-0 overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-xl">
                {/* Left Rail */}
                <ViewRail
                    activeView={activeView}
                    onViewChange={(v) => { setActiveView(v); setSelectedNode(null); }}
                    microservicesAvailable={microservicesAvailable}
                    proposedCostCached={!!proposedCost}
                    proposedReliabilityCached={!!proposedReliability}
                    onGenerateClick={(mode) => setGenerateModalMode(mode)}
                    proposedLoading={proposedLoading}
                />

                {/* Main Canvas */}
                <MainCanvas
                    mermaidCode={mermaidCode}
                    nodes={isProposedView ? [] : (currentViewData?.graph.nodes ?? [])}
                    activeView={activeView}
                    selectedNodeId={selectedNode?.id ?? null}
                    onNodeSelect={setSelectedNode}
                    microservicesAvailable={microservicesAvailable}
                    loading={proposedLoading && isProposedView}
                    provider={integrationProvider}
                    region={currentRegion?.region ?? activeRegion}
                    warnings={canvasWarnings}
                    proposed={isProposedView ? currentProposed : null}
                />

                {/* Inspector */}
                <InspectorPanel
                    node={selectedNode}
                    onClose={() => setSelectedNode(null)}
                    provider={integrationProvider}
                />
            </div>

            {/* Bottom Panel */}
            {isProposedView && currentProposed ? (
                <ChangeListPanel proposed={currentProposed} provider={integrationProvider} />
            ) : (
                <ResourceTable
                    nodes={currentViewData?.graph.nodes ?? []}
                    selectedNodeId={selectedNode?.id ?? null}
                    onNodeSelect={setSelectedNode}
                    provider={integrationProvider}
                />
            )}

            {/* Generate Modal */}
            {generateModalMode && (
                <GenerateModal
                    mode={generateModalMode}
                    onConfirm={() => handleGenerate(generateModalMode)}
                    onCancel={() => setGenerateModalMode(null)}
                />
            )}
        </div>
    );
}
