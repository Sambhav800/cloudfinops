'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
    X, Server, Database, HardDrive, Cloud, Zap, Globe,
    Shield, Box, Container, Network as NetworkIcon, ExternalLink,
} from 'lucide-react';
import type { GraphNode } from '@/lib/architecture-types';
import { formatInrCurrency, toDisplayInrAmount } from '@/lib/resources/contract';

const SERVICE_ICONS: Record<string, React.ElementType> = {
    ec2: Server, rds: Database, ebs: HardDrive, s3: Cloud,
    lambda: Zap, igw: Globe, sg: Shield, vpc: Shield,
    subnet: Box, alb: NetworkIcon, eks: Container, ecs: Container, iam: Shield,
};

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
    Active: { bg: 'bg-emerald-500/10 border-emerald-500/20', text: 'text-emerald-400' },
    Zombie: { bg: 'bg-rose-500/10 border-rose-500/20', text: 'text-rose-400' },
    Stopped: { bg: 'bg-amber-500/10 border-amber-500/20', text: 'text-amber-400' },
};

interface Props {
    node: GraphNode | null;
    onClose: () => void;
    provider: string;
}

function deriveStatus(node: GraphNode): "Active" | "Zombie" | "Stopped" | "Unknown" {
    const raw = (node.status || "").toLowerCase();
    if (node.waste_type || raw === "zombie" || raw === "idle/zombie" || raw === "waste" || raw === "idle" || raw === "non_compliant") {
        return "Zombie";
    }
    if (raw === "stopped") {
        return "Stopped";
    }
    if (raw === "active" || raw === "healthy" || raw === "running") {
        return "Active";
    }
    return "Unknown";
}

function inferSourceCurrency(node: GraphNode, provider: string): string {
    const metadata = node.metadata ?? {};
    const nodeProvider = String(
        metadata.provider ??
        metadata.cloud_provider ??
        metadata.cloudProvider ??
        provider
    ).trim().toLowerCase();

    return nodeProvider === 'gcp' ? 'INR' : 'USD';
}

function getNodeCostCurrency(node: GraphNode, provider: string): string {
    const metadata = node.metadata ?? {};
    return String(
        metadata.currency ??
        metadata.billing_currency ??
        metadata.cost_currency ??
        inferSourceCurrency(node, provider)
    ).toUpperCase();
}

function formatNodeCost(node: GraphNode, provider: string): string {
    return `${formatInrCurrency(
        toDisplayInrAmount(node.cost, getNodeCostCurrency(node, provider)),
        { minimumFractionDigits: 2, maximumFractionDigits: 2 },
    )}/mo`;
}

export function InspectorPanel({ node, onClose, provider }: Props) {
    return (
        <AnimatePresence>
            {node && (
                <motion.div
                    key={node.id}
                    initial={{ width: 0, opacity: 0 }}
                    animate={{ width: 320, opacity: 1 }}
                    exit={{ width: 0, opacity: 0 }}
                    transition={{ duration: 0.2, ease: 'easeOut' }}
                    className="shrink-0 overflow-y-auto overflow-x-hidden border-l border-white/10 bg-slate-900"
                >
                    <div className="w-[320px] p-4 space-y-4">
                        {/* Header */}
                        <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2.5">
                                {(() => {
                                    const Icon = SERVICE_ICONS[node.service_type] ?? Box;
                                    return <Icon className="w-5 h-5 shrink-0 text-indigo-400" />;
                                })()}
                                <div>
                                    <h3 className="text-white font-medium text-sm">{node.name}</h3>
                                    <p className="text-[10px] text-slate-500 uppercase tracking-wider">{node.service_type}</p>
                                </div>
                            </div>
                            <button onClick={onClose} className="-mr-1 rounded-xl p-1 text-slate-500 transition hover:bg-white/5 hover:text-white">
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        {/* Status */}
                        {(() => {
                            const displayStatus = deriveStatus(node);
                            const style = STATUS_STYLES[displayStatus] ?? { bg: 'bg-slate-400/10 border-slate-500/30', text: 'text-slate-400' };
                            return (
                                <div className={`flex items-center justify-between rounded-xl border px-3 py-2 ${style.bg}`}>
                                    <span className={`text-xs font-medium ${style.text}`}>{displayStatus}</span>
                                    {node.waste_type && (
                                        <span className="rounded-full border border-rose-500/20 bg-rose-500/10 px-2 py-0.5 text-[10px] text-rose-400">
                                            {node.waste_type.replace(/_/g, ' ')}
                                        </span>
                                    )}
                                </div>
                            );
                        })()}

                        {/* Key/Value Pairs */}
                        <div className="space-y-2">
                            <Row label="Resource ID" value={node.cloud_resource_id} mono />
                            <Row label="Region" value={node.region} />
                            {node.cost > 0 && <Row label="Cost" value={formatNodeCost(node, provider)} highlight />}
                            {node.severity !== 'none' && (
                                <Row label="Severity" value={node.severity} badge badgeColor={
                                    node.severity === 'critical' ? 'border border-rose-500/20 bg-rose-500/10 text-rose-400' :
                                        node.severity === 'high' ? 'border border-rose-500/20 bg-rose-500/10 text-rose-400' :
                                            node.severity === 'medium' ? 'border border-amber-500/20 bg-amber-500/10 text-amber-400' :
                                                'border border-slate-500/20 bg-slate-500/10 text-slate-400'
                                } />
                            )}
                        </div>

                        {/* Metadata */}
                        {Object.keys(node.metadata).length > 0 && (
                            <div>
                                <p className="mb-1.5 text-[10px] uppercase tracking-wider text-slate-500">Metadata</p>
                                <div className="space-y-1 rounded-xl border border-white/10 bg-slate-950/80 p-2.5">
                                    {Object.entries(node.metadata).map(([k, v]) => (
                                        <div key={k} className="flex justify-between text-xs">
                                            <span className="text-slate-500">{k}</span>
                                            <span className="text-slate-300 text-right max-w-[150px] truncate">
                                                {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Tags */}
                        {Object.keys(node.tags).length > 0 && (
                            <div>
                                <p className="mb-1.5 text-[10px] uppercase tracking-wider text-slate-500">Tags</p>
                                <div className="flex flex-wrap gap-1">
                                    {Object.entries(node.tags).map(([k, v]) => (
                                        <span key={k} className="rounded-full border border-white/10 bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300">
                                            {k}: {v}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Action */}
                        <button className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-slate-800 px-3 py-2 text-xs text-slate-300 transition-colors hover:bg-slate-700 hover:text-white">
                            <ExternalLink className="w-3.5 h-3.5" />
                            View in Resources Table
                        </button>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}

// Helper row component
function Row({
    label, value, mono, highlight, badge, badgeColor
}: {
    label: string;
    value: string;
    mono?: boolean;
    highlight?: boolean;
    badge?: boolean;
    badgeColor?: string;
}) {
    return (
        <div className="flex justify-between items-center">
            <span className="text-[11px] text-slate-500">{label}</span>
            {badge ? (
                <span className={`rounded-full px-2 py-0.5 text-[10px] ${badgeColor}`}>{value}</span>
            ) : (
                <span className={`text-xs ${highlight ? 'text-amber-400 font-medium' :
                        mono ? 'text-indigo-300 font-mono text-[10px]' :
                            'text-slate-300'
                    }`}>
                    {value}
                </span>
            )}
        </div>
    );
}
