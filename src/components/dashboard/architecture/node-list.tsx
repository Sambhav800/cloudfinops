'use client';

import {
    Server, Database, HardDrive, Globe, Shield, Cloud,
    Zap, Container, Box, Network as NetworkIcon,
} from 'lucide-react';
import type { GraphNode } from '@/lib/architecture-types';
import { formatInrCurrency, toDisplayInrAmount } from '@/lib/resources/contract';

const SERVICE_ICONS: Record<string, React.ElementType> = {
    ec2: Server,
    rds: Database,
    ebs: HardDrive,
    s3: Cloud,
    lambda: Zap,
    igw: Globe,
    sg: Shield,
    vpc: Shield,
    subnet: Box,
    alb: NetworkIcon,
    eks: Container,
    ecs: Container,
    iam: Shield,
};

const STATUS_COLORS: Record<string, string> = {
    Active: 'border border-emerald-500/20 bg-emerald-500/10 text-emerald-400',
    Zombie: 'border border-rose-500/20 bg-rose-500/10 text-rose-400',
    Stopped: 'border border-amber-500/20 bg-amber-500/10 text-amber-400',
};

interface Props {
    nodes: GraphNode[];
    selectedNodeId: string | null;
    onNodeSelect: (node: GraphNode) => void;
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
    const nodeProvider = String(
        node.metadata?.provider ??
        node.metadata?.cloud_provider ??
        node.metadata?.cloudProvider ??
        provider
    ).trim().toLowerCase();

    return nodeProvider === 'gcp' ? 'INR' : 'USD';
}

function formatNodeCost(node: GraphNode, provider: string): string {
    const currency = String(
        node.metadata?.currency ??
        node.metadata?.billing_currency ??
        node.metadata?.cost_currency ??
        inferSourceCurrency(node, provider)
    ).toUpperCase();

    return formatInrCurrency(toDisplayInrAmount(node.cost, currency), {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });
}

export function NodeList({ nodes, selectedNodeId, onNodeSelect, provider }: Props) {
    // Filter to resource-level nodes (skip groups)
    const resourceNodes = nodes.filter(n => n.node_type === 'resource' || n.node_type === 'standalone');

    // Sort: waste/zombie first, then by cost descending
    const sorted = [...resourceNodes].sort((a, b) => {
        if (a.waste_type && !b.waste_type) return -1;
        if (!a.waste_type && b.waste_type) return 1;
        return b.cost - a.cost;
    });

    return (
        <div className="w-56 shrink-0 overflow-y-auto border-l border-white/10 bg-slate-900">
            <p className="sticky top-0 z-10 border-b border-white/5 bg-slate-900/95 px-3 py-2 text-[10px] font-semibold uppercase tracking-widest text-slate-500 backdrop-blur">
                Nodes ({resourceNodes.length})
            </p>
            <div className="divide-y divide-white/[0.03]">
                {sorted.map(node => {
                    const Icon = SERVICE_ICONS[node.service_type] ?? Box;
                    const isSelected = selectedNodeId === node.id;
                    const displayStatus = deriveStatus(node);
                    const statusClass = STATUS_COLORS[displayStatus] ?? 'text-slate-400 bg-slate-400/10';

                    return (
                        <button
                            key={node.id}
                            onClick={() => onNodeSelect(node)}
                            className={`flex w-full items-start gap-2.5 border-l-4 px-3 py-2 text-left text-slate-300 transition-all hover:bg-slate-800/50 ${isSelected ? 'border-l-indigo-500 bg-slate-800/70 text-white' : 'border-l-transparent'
                                }`}
                        >
                            <Icon className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${node.waste_type ? 'text-rose-400' :
                                    node.severity === 'critical' ? 'text-red-400' :
                                        'text-slate-500'
                                }`} />
                            <div className="min-w-0 flex-1">
                                <p className="truncate text-xs text-slate-300">{node.name}</p>
                                <div className="flex items-center gap-1.5 mt-0.5">
                                    <span className={`rounded-full px-2 py-0.5 text-[9px] ${statusClass}`}>
                                        {displayStatus}
                                    </span>
                                    {node.cost > 0 && (
                                        <span className="text-[9px] text-slate-500">{formatNodeCost(node, provider)}/mo</span>
                                    )}
                                </div>
                            </div>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
