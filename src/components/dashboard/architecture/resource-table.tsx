'use client';

import { useState, useMemo } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';
import type { GraphNode } from '@/lib/architecture-types';
import { formatInrCurrency, toDisplayInrAmount } from '@/lib/resources/contract';

type SortField = 'name' | 'service_type' | 'cost' | 'status';
type SortDir = 'asc' | 'desc';

interface Props {
    nodes: GraphNode[];
    selectedNodeId: string | null;
    onNodeSelect: (node: GraphNode) => void;
    provider: string;
}

const PAGE_SIZE = 25;

function deriveStatus(node: GraphNode): "Active" | "Zombie" | "Stopped" | "Unknown" {
    const raw = (node.status || "").toLowerCase();
    const hasWaste = Boolean(node.waste_type);

    if (hasWaste || raw === "zombie" || raw === "idle/zombie" || raw === "waste" || raw === "idle" || raw === "non_compliant") {
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
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

export function ResourceTable({ nodes, selectedNodeId, onNodeSelect, provider }: Props) {
    const [sortField, setSortField] = useState<SortField>('cost');
    const [sortDir, setSortDir] = useState<SortDir>('desc');
    const [page, setPage] = useState(0);
    const [filterType, setFilterType] = useState('');

    // Filter to resources only
    const resourceNodes = useMemo(() =>
        nodes.filter(n => n.node_type === 'resource' || n.node_type === 'standalone'),
        [nodes]
    );

    // Unique service types for filter
    const serviceTypes = useMemo(() =>
        [...new Set(resourceNodes.map(n => n.service_type))].sort(),
        [resourceNodes]
    );

    // Filter
    const filtered = useMemo(() =>
        filterType ? resourceNodes.filter(n => n.service_type === filterType) : resourceNodes,
        [resourceNodes, filterType]
    );

    // Sort
    const sorted = useMemo(() => {
        return [...filtered].sort((a, b) => {
            let cmp = 0;
            switch (sortField) {
                case 'name': cmp = a.name.localeCompare(b.name); break;
                case 'service_type': cmp = a.service_type.localeCompare(b.service_type); break;
                case 'cost': cmp = a.cost - b.cost; break;
                case 'status': cmp = a.status.localeCompare(b.status); break;
            }
            return sortDir === 'asc' ? cmp : -cmp;
        });
    }, [filtered, sortField, sortDir]);

    // Paginate
    const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
    const pageData = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

    const toggleSort = (field: SortField) => {
        if (sortField === field) {
            setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        } else {
            setSortField(field);
            setSortDir('desc');
        }
        setPage(0);
    };

    const SortIcon = ({ field }: { field: SortField }) => {
        if (sortField !== field) return <ChevronDown className="w-3 h-3 text-slate-600" />;
        return sortDir === 'asc'
            ? <ChevronUp className="w-3 h-3 text-indigo-400" />
            : <ChevronDown className="w-3 h-3 text-indigo-400" />;
    };

    return (
        <div className="mt-3 overflow-hidden rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur-xl">
            {/* Table header bar */}
            <div className="flex items-center justify-between border-b border-white/10 bg-slate-900/60 px-4 py-2">
                <p className="text-xs text-slate-400">
                    {filtered.length} resource{filtered.length !== 1 ? 's' : ''}
                </p>
                <select
                    value={filterType}
                    onChange={e => { setFilterType(e.target.value); setPage(0); }}
                    className="rounded-xl border border-white/10 bg-slate-800 px-2 py-1 text-xs text-slate-300 focus:border-indigo-500 focus:outline-none"
                >
                    <option value="">All types</option>
                    {serviceTypes.map(t => (
                        <option key={t} value={t}>{t.toUpperCase()}</option>
                    ))}
                </select>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
                <table className="w-full text-xs">
                    <thead>
                        <tr className="border-b border-white/5 bg-white/5">
                            {([
                                ['service_type', 'Service'],
                                ['name', 'Name'],
                                ['cost', 'Cost/mo'],
                                ['status', 'Status'],
                            ] as [SortField, string][]).map(([field, label]) => (
                                <th
                                    key={field}
                                    onClick={() => toggleSort(field)}
                                    className="cursor-pointer select-none px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-400 transition-colors hover:text-white"
                                >
                                    <span className="flex items-center gap-1">
                                        {label}
                                        <SortIcon field={field} />
                                    </span>
                                </th>
                            ))}
                            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-400">Resource ID</th>
                            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-400">Waste</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.03]">
                        {pageData.map(node => {
                            const isSelected = selectedNodeId === node.id;
                            return (
                                <tr
                                    key={node.id}
                                    onClick={() => onNodeSelect(node)}
                                    className={`cursor-pointer transition-colors hover:bg-white/[0.03] ${isSelected ? 'bg-indigo-600/10' : ''
                                        }`}
                                >
                                    <td className="px-4 py-2">
                                        <span className="rounded-full border border-white/10 bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase text-slate-300">
                                            {node.service_type}
                                        </span>
                                    </td>
                                    <td className="px-4 py-2 text-white">{node.name}</td>
                                    <td className="px-4 py-2 text-amber-400 font-medium">
                                        {node.cost > 0 ? formatNodeCost(node, provider) : '—'}
                                    </td>
                                    <td className="px-4 py-2">
                                        {(() => {
                                            const displayStatus = deriveStatus(node);
                                            const textColor =
                                                displayStatus === "Active"
                                                    ? "text-emerald-400"
                                                    : displayStatus === "Zombie"
                                                        ? "text-rose-400"
                                                        : displayStatus === "Stopped"
                                                            ? "text-amber-400"
                                                            : "text-slate-400";
                                            return (
                                                <span className={textColor}>
                                                    {displayStatus}
                                                </span>
                                            );
                                        })()}
                                    </td>
                                    <td className="px-4 py-2 text-slate-500 font-mono text-[10px] max-w-[150px] truncate">
                                        {node.cloud_resource_id}
                                    </td>
                                    <td className="px-4 py-2">
                                        {node.waste_type ? (
                                            <span className="rounded-full border border-rose-500/20 bg-rose-500/10 px-2 py-0.5 text-[10px] text-rose-400">
                                                {node.waste_type.replace(/_/g, ' ')}
                                            </span>
                                        ) : '—'}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between border-t border-white/10 bg-slate-900/60 px-4 py-2">
                    <button
                        onClick={() => setPage(p => Math.max(0, p - 1))}
                        disabled={page === 0}
                        className="text-xs text-slate-400 hover:text-white disabled:text-slate-600 disabled:cursor-not-allowed transition-colors"
                    >
                        ← Previous
                    </button>
                    <span className="text-xs text-slate-500">
                        Page {page + 1} of {totalPages}
                    </span>
                    <button
                        onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                        disabled={page >= totalPages - 1}
                        className="text-xs text-slate-400 hover:text-white disabled:text-slate-600 disabled:cursor-not-allowed transition-colors"
                    >
                        Next →
                    </button>
                </div>
            )}
        </div>
    );
}
