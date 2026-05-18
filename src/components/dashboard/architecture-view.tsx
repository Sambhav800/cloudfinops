'use client';

import { useState, useEffect } from 'react';
import { Title, Text, Card } from '@tremor/react';
import { Network, AlertCircle, RefreshCw } from 'lucide-react';
import { getArchitectureAction } from '@/app/actions/architecture';
import { ArchitectureMermaid } from './architecture-mermaid';
import { motion } from 'framer-motion';

interface ArchitectureViewProps {
    integrationId: string;
}

export function ArchitectureView({ integrationId }: ArchitectureViewProps) {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    // Filter controls
    const [activeRegion, setActiveRegion] = useState<string>('');
    const [activeView, setActiveView] = useState<'summary' | 'hotspots' | 'vpc_detail'>('summary');
    const [activeVpc, setActiveVpc] = useState<string>('');

    const fetchArchitecture = async (region?: string, vpcId?: string, viewType: 'summary' | 'hotspots' | 'vpc_detail' = 'summary') => {
        setLoading(true);
        setError(null);
        try {
            const res = await getArchitectureAction(integrationId, region, vpcId, viewType);
            if (!res) {
                setError("Failed to generate architecture diagram.");
            } else {
                setData(res);

                // Set default region on first load
                if (!region && res.regions?.length > 0 && !activeRegion) {
                    setActiveRegion(res.regions[0].region);
                }
            }
        } catch (err: any) {
            setError(err.message || "An error occurred fetching the architecture.");
        } finally {
            setLoading(false);
        }
    };

    // Initial load
    useEffect(() => {
        fetchArchitecture(activeRegion || undefined, undefined, 'summary');
    }, [integrationId]);

    // Handle view/region changes
    const handleFilterChange = (region: string, view: 'summary' | 'hotspots' | 'vpc_detail', vpcId: string) => {
        setActiveRegion(region);
        setActiveView(view);
        setActiveVpc(vpcId);
        fetchArchitecture(region, view === 'vpc_detail' ? vpcId : undefined, view);
    };

    if (error) {
        return (
            <Card className="bg-slate-900/50 border-rose-500/20 p-6 flex flex-col items-center">
                <AlertCircle className="w-12 h-12 text-rose-500 mb-4" />
                <Title className="text-white">Failed to Load Architecture</Title>
                <Text className="text-rose-400 mt-2">{error}</Text>
                <button
                    onClick={() => fetchArchitecture(activeRegion, activeView === 'vpc_detail' ? activeVpc : undefined, activeView)}
                    className="mt-4 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors flex items-center gap-2"
                >
                    <RefreshCw className="w-4 h-4" /> Try Again
                </button>
            </Card>
        );
    }

    // Extract current region data
    const currentRegionData = data?.regions?.find((r: any) => r.region === activeRegion) || data?.regions?.[0];
    const mermaidCode = currentRegionData?.views?.[activeView]?.mermaid;
    const warnings = currentRegionData?.views?.[activeView]?.warnings || [];

    // For VPC detail
    const vpcDetailMermaid = activeView === 'vpc_detail' && data?.regions?.[0]?.views?.vpc_detail?.mermaid;
    const finalMermaid = activeView === 'vpc_detail' ? vpcDetailMermaid : mermaidCode;

    return (
        <div className="space-y-6">
            <div className="flex flex-col md:flex-row gap-4 items-start md:items-end justify-between bg-slate-900/40 p-4 rounded-xl border border-white/5">
                {/* Region Selector */}
                <div className="w-full md:w-auto">
                    <Text className="text-slate-400 mb-1.5 text-xs font-medium uppercase tracking-wider">Region</Text>
                    <div className="flex flex-wrap gap-2">
                        {data?.regions?.map((r: any) => (
                            <button
                                key={r.region}
                                onClick={() => handleFilterChange(r.region, activeView, activeVpc)}
                                className={`px-3 py-1.5 rounded-md text-sm transition-colors border ${activeRegion === r.region
                                    ? 'bg-cyan-900/30 text-cyan-400 border-cyan-500/30'
                                    : 'bg-slate-800/50 text-slate-300 border-white/5 hover:bg-slate-800 hover:border-white/10'
                                    }`}
                            >
                                {r.region}
                            </button>
                        ))}
                        {(!data?.regions || data.regions.length === 0) && !loading && (
                            <Text className="text-slate-500 py-1.5">No regions found</Text>
                        )}
                    </div>
                </div>

                {/* View Toggles */}
                <div className="w-full md:w-auto">
                    <Text className="text-slate-400 mb-1.5 text-xs font-medium uppercase tracking-wider">Topology View</Text>
                    <div className="flex bg-slate-800/50 rounded-lg p-1 border border-white/5 w-fit">
                        <button
                            onClick={() => handleFilterChange(activeRegion, 'summary', '')}
                            className={`px-4 py-1.5 rounded-md text-sm transition-all ${activeView === 'summary'
                                ? 'bg-split-solid bg-slate-700 text-white shadow-sm'
                                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                                }`}
                        >
                            Summary
                        </button>
                        <button
                            onClick={() => handleFilterChange(activeRegion, 'hotspots', '')}
                            className={`px-4 py-1.5 rounded-md text-sm transition-all ${activeView === 'hotspots'
                                ? 'bg-slate-700 text-amber-400 shadow-sm'
                                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                                }`}
                        >
                            Cost Hotspots
                        </button>
                    </div>
                </div>
            </div>

            {/* Warnings Alert */}
            {warnings.length > 0 && (
                <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 flex gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                    <div>
                        <h4 className="text-amber-500 font-medium text-sm">Diagram Notice</h4>
                        <ul className="mt-1 text-amber-400/80 text-xs space-y-1">
                            {warnings.map((w: any, i: number) => (
                                <li key={i}>
                                    {w.type === 'diagram_truncated' && `Diagram truncated to top ${w.shown} nodes for performance. Please use VPC Drilldown.`}
                                    {w.type === 'services_collapsed' && `${w.count} minor network resources hidden for clarity (${w.reason}).`}
                                    {w.type === 'unresolved_reference' && `Could not resolve link for ${w.source} (${w.reason || 'Missing parent'}).`}
                                    {w.type !== 'diagram_truncated' && w.type !== 'services_collapsed' && w.type !== 'unresolved_reference' && JSON.stringify(w)}
                                </li>
                            ))}
                        </ul>
                    </div>
                </motion.div>
            )}

            {/* Diagram Area */}
            <Card className="p-0 border-white/10 bg-slate-900/30 overflow-hidden shadow-2xl relative">
                {/* Header for VPC Drilldown (Mocking a dropdown for specific VPCs if needed later, right now forcing summary/hotspots unless passed directly via URL) */}
                <div className="absolute top-4 right-4 z-20">
                    <div className="bg-slate-900/80 backdrop-blur border border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-300 flex items-center gap-2">
                        <Network className="w-4 h-4 text-cyan-400" />
                        {activeView === 'summary' ? 'Standard Topology' : activeView === 'hotspots' ? 'Cost Intensity' : `VPC: ${activeVpc}`}
                    </div>
                </div>

                <div className="h-[650px] w-full">
                    {loading && !finalMermaid ? (
                        <div className="w-full h-full flex flex-col items-center justify-center">
                            <RefreshCw className="w-8 h-8 text-slate-500 animate-spin mb-4" />
                            <Text className="text-slate-400">Loading topology data...</Text>
                        </div>
                    ) : (
                        finalMermaid ? (
                            <ArchitectureMermaid
                                mermaidCode={finalMermaid}
                                id={`arch-${activeRegion}-${activeView}-${activeVpc}`}
                            />
                        ) : (
                            <div className="w-full h-full flex flex-col items-center justify-center">
                                <AlertCircle className="w-8 h-8 text-slate-500 mb-4" />
                                <Text className="text-slate-400">No diagram data available for this view.</Text>
                            </div>
                        )
                    )}
                </div>
            </Card>
        </div>
    );
}
