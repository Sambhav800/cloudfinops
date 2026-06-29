'use client';

import { useState } from 'react';
import { Cloud, Clock, Shield, ChevronDown, X, FileText, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { CoverageReport } from '@/lib/architecture-types';

interface Props {
    integrationName: string;
    provider: string;
    lastScan?: string;
    regions: string[];
    activeRegion: string;
    onRegionChange: (region: string) => void;
    coverage: CoverageReport | null;
    onExportReport?: () => void;
    exportingReport?: boolean;
}

export function TopBar({
    integrationName,
    provider,
    lastScan,
    regions,
    activeRegion,
    onRegionChange,
    coverage,
    onExportReport,
    exportingReport,
}: Props) {
    const [showCoverage, setShowCoverage] = useState(false);

    const detectedCount = coverage?.detected_services.length ?? 0;
    const totalCount = detectedCount + (coverage?.missing_services.length ?? 0);
    const missingCount = coverage?.missing_services.length ?? 0;
    const coverageBadgeClassName = missingCount > 0
        ? "border border-amber-500/20 bg-amber-500/10 text-amber-400"
        : "border border-emerald-500/20 bg-emerald-500/10 text-emerald-400";

    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4 backdrop-blur-xl">
            <div className="flex flex-wrap items-center gap-4">

                {/* Integration */}
                <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-slate-900 px-3 py-2">
                    <Cloud className="w-4 h-4 text-indigo-400" />
                    <span className="text-sm text-white font-medium">{integrationName}</span>
                    <span className="rounded-full border border-indigo-500/20 bg-indigo-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-indigo-400">
                        {provider.toUpperCase()}
                    </span>
                </div>

                {/* Separator */}
                <div className="w-px h-6 bg-white/10 hidden md:block" />

                {/* Region Pills */}
                <div className="flex items-center gap-1.5">
                    {regions.map(r => (
                        <button
                            key={r}
                            onClick={() => onRegionChange(r)}
                            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${activeRegion === r
                                    ? 'border border-indigo-500/30 bg-indigo-600/20 text-indigo-400'
                                    : 'border border-white/10 bg-slate-900 text-slate-400 hover:bg-slate-800/50 hover:text-white'
                                }`}
                        >
                            {r}
                        </button>
                    ))}
                </div>

                {/* Separator */}
                <div className="w-px h-6 bg-white/10 hidden md:block" />

                {/* Last Scan */}
                {lastScan && (
                    <div className="flex items-center gap-1.5 text-xs text-slate-400">
                        <Clock className="w-3.5 h-3.5" />
                        <span>Last scan: {new Date(lastScan).toLocaleString()}</span>
                    </div>
                )}

                {/* Export Report Button */}
                {onExportReport && (
                    <button
                        onClick={onExportReport}
                        disabled={exportingReport}
                        className="flex items-center gap-1.5 rounded-lg border border-indigo-500/30 bg-indigo-600/20 px-3 py-1.5 text-xs font-medium text-indigo-400 transition-colors hover:bg-indigo-600/30 disabled:opacity-50"
                    >
                        {exportingReport ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                            <FileText className="h-3.5 w-3.5" />
                        )}
                        {exportingReport ? 'Generating...' : 'Export Report'}
                    </button>
                )}

                {/* Coverage Badge */}
                <div className="relative ml-auto">
                    <button
                        onClick={() => setShowCoverage(!showCoverage)}
                        className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition-colors ${coverageBadgeClassName}`}
                    >
                        <Shield className="w-3.5 h-3.5" />
                        <span>
                            {detectedCount} / {totalCount} services
                        </span>
                        <ChevronDown className={`w-3 h-3 text-slate-500 transition-transform ${showCoverage ? 'rotate-180' : ''}`} />
                    </button>

                    {/* Coverage Popover */}
                    <AnimatePresence>
                        {showCoverage && coverage && (
                            <motion.div
                                initial={{ opacity: 0, y: 8, scale: 0.95 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, y: 8, scale: 0.95 }}
                                transition={{ duration: 0.15 }}
                                className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-2xl border border-white/10 bg-slate-900 shadow-2xl"
                            >
                                <div className="p-3 border-b border-white/10 flex justify-between items-center">
                                    <span className="text-sm font-medium text-white">Service Visibility</span>
                                    <button onClick={() => setShowCoverage(false)} className="text-slate-500 hover:text-white">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                                <div className="p-3 space-y-2 max-h-[300px] overflow-y-auto">
                                    {/* Detected */}
                                    <div className="grid grid-cols-3 gap-1">
                                        {coverage.detected_services.map(s => (
                                            <span key={s} className="text-xs text-emerald-400 flex items-center gap-1">
                                                <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full" /> {s.toUpperCase()}
                                            </span>
                                        ))}
                                    </div>
                                    {/* Missing */}
                                    {coverage.missing_services.length > 0 && (
                                        <div className="pt-2 border-t border-white/5">
                                            <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1.5">Not Detected</p>
                                            {coverage.missing_services.map(s => (
                                                <div key={s} className="flex items-center gap-1.5 py-0.5">
                                                    <span className="w-1.5 h-1.5 bg-amber-400 rounded-full" />
                                                    <span className="text-xs text-amber-400">{s.toUpperCase()}</span>
                                                    <span className="text-[10px] text-slate-600 ml-auto">
                                                        {coverage.access_denied_services.includes(s) ? 'access denied' : 'not scanned'}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {/* Warnings */}
                                    {coverage.warnings.map((w, i) => (
                                        <p key={i} className="text-[10px] text-slate-500 mt-2">{w.message}</p>
                                    ))}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

            </div>
        </div>
    );
}
