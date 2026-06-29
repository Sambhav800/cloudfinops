'use client';

import type { ReactNode } from 'react';
import { AlertCircle, Loader2, Lock } from 'lucide-react';
import { ArchitectureMermaid } from '../architecture-mermaid';
import { NodeList } from './node-list';
import type { CoverageWarning, GraphNode, ProposedResult, ViewId } from '@/lib/architecture-types';
import { formatInrCurrency, toDisplayInrAmount } from '@/lib/resources/contract';

interface Props {
    mermaidCode: string;
    nodes: GraphNode[];
    activeView: ViewId;
    selectedNodeId: string | null;
    onNodeSelect: (node: GraphNode) => void;
    microservicesAvailable: boolean;
    loading: boolean;
    provider: string;
    region: string;
    warnings: CoverageWarning[];
    proposed: ProposedResult | null;
}

type Tone = 'slate' | 'sky' | 'emerald' | 'amber' | 'rose';

interface StatItem {
    label: string;
    value: string;
    tone?: Tone;
}

interface LegendItem {
    label: string;
    description: string;
    tone: Tone;
}

interface Presentation {
    categoryLabel: string;
    title: string;
    description: string;
    supportingText?: string;
    stats: StatItem[];
    legend: LegendItem[];
}

const toneClasses: Record<Tone, string> = {
    slate: 'border-white/10 bg-slate-900 text-slate-200',
    sky: 'border-sky-400/20 bg-sky-500/10 text-sky-200',
    emerald: 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
    amber: 'border-amber-400/20 bg-amber-500/10 text-amber-100',
    rose: 'border-rose-400/20 bg-rose-500/10 text-rose-100',
};

const dotClasses: Record<Tone, string> = {
    slate: 'bg-white/60',
    sky: 'bg-sky-400',
    emerald: 'bg-emerald-400',
    amber: 'bg-amber-400',
    rose: 'bg-rose-400',
};

function formatProvider(provider: string): string {
    const normalized = provider.trim().toLowerCase();
    if (normalized === 'aws') {
        return 'AWS';
    }
    if (normalized === 'gcp') {
        return 'GCP';
    }
    if (normalized === 'azure') {
        return 'Azure';
    }
    return provider.toUpperCase();
}

function architectureSourceCurrency(provider: string): string {
    return provider.trim().toLowerCase() === 'gcp' ? 'INR' : 'USD';
}

function formatMonthlyDelta(value: number, provider: string): string {
    if (value > 0) {
        return `${formatArchitectureCurrency(value, provider)}/mo saved`;
    }
    if (value < 0) {
        return `${formatArchitectureCurrency(Math.abs(value), provider)}/mo added`;
    }
    return `${formatArchitectureCurrency(0, provider)}/mo`;
}

function formatArchitectureCurrency(value: number, provider: string): string {
    return formatInrCurrency(toDisplayInrAmount(Math.abs(value), architectureSourceCurrency(provider)), {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });
}

function countWorkloads(nodes: GraphNode[]): number {
    return nodes.filter((node) => node.node_type !== 'group').length;
}

function countGroups(nodes: GraphNode[]): number {
    return nodes.filter((node) => node.node_type === 'group').length;
}

function countWasteSignals(nodes: GraphNode[]): number {
    return nodes.filter((node) => {
        const status = node.status.trim().toLowerCase();
        return Boolean(node.waste_type) || status === 'zombie' || status === 'stopped';
    }).length;
}

function countElevatedSeverity(nodes: GraphNode[]): number {
    return nodes.filter((node) => node.severity === 'high' || node.severity === 'critical').length;
}

function countMediumOrHighRisk(proposed: ProposedResult | null): number {
    return proposed?.change_list.filter((item) => item.risk_level !== 'low').length ?? 0;
}

function buildEvidenceNote(warnings: CoverageWarning[]): string | undefined {
    const inferred = warnings.find((warning) => warning.type === 'inferred_relationships')?.message;
    const estimated = warnings.find((warning) => warning.type === 'estimated_cost_data')?.message;
    const deterministic = warnings.find((warning) => warning.type === 'deterministic_proposed')?.message;

    const notes = [deterministic, inferred, estimated].filter(Boolean);
    return notes.length > 0 ? notes.join(' ') : undefined;
}

function buildPresentation(
    activeView: ViewId,
    provider: string,
    region: string,
    nodes: GraphNode[],
    warnings: CoverageWarning[],
    proposed: ProposedResult | null,
): Presentation {
    const providerLabel = formatProvider(provider);
    const workloadCount = countWorkloads(nodes);
    const groupCount = countGroups(nodes);
    const wasteSignals = countWasteSignals(nodes);
    const elevatedSeverity = countElevatedSeverity(nodes);
    const warningCount = warnings.length;
    const changeCount = proposed?.change_list.length ?? 0;
    const riskCount = countMediumOrHighRisk(proposed);
    const evidenceNote = buildEvidenceNote(warnings);

    if (activeView === 'cost_hotspots') {
        return {
            categoryLabel: 'Current architecture',
            title: 'Cost Hotspots',
            description: `${providerLabel} spend concentration for ${region}. This view highlights the nodes most likely to move the monthly bill, with warmer tones reserved for high-cost or waste-heavy components that merit executive review.`,
            supportingText: evidenceNote ?? 'Use this diagram to align FinOps, platform, and engineering teams on where optimization effort will produce the clearest business impact first.',
            stats: [
                { label: 'Resources ranked', value: String(workloadCount), tone: 'sky' },
                { label: 'Waste signals', value: String(wasteSignals), tone: 'amber' },
                { label: 'High-risk nodes', value: String(elevatedSeverity), tone: 'rose' },
            ],
            legend: [
                { label: 'Baseline spend', description: 'Healthy or comparatively low-cost footprint.', tone: 'emerald' },
                { label: 'Optimization candidate', description: 'Meaningful spend or early waste signal.', tone: 'amber' },
                { label: 'High-cost driver', description: 'Top bill contributor requiring active review.', tone: 'rose' },
            ],
        };
    }

    if (activeView === 'microservices') {
        return {
            categoryLabel: 'Current architecture',
            title: 'Microservices Landscape',
            description: `${providerLabel} workload view for ${region}. This diagram is intended to show service boundaries, grouped workloads, and operational blast radius once container or orchestrated-service coverage is available.`,
            supportingText: evidenceNote ?? 'When present, use this view to validate ownership boundaries, service adjacency, and the likely path of operational incidents across the estate.',
            stats: [
                { label: 'Workloads mapped', value: String(workloadCount), tone: 'sky' },
                { label: 'Service groups', value: String(groupCount), tone: 'emerald' },
                { label: 'Coverage notes', value: String(warningCount), tone: 'amber' },
            ],
            legend: [
                { label: 'Active service', description: 'Healthy workload or service boundary.', tone: 'emerald' },
                { label: 'Shared platform edge', description: 'Ingress, routing, or shared control plane.', tone: 'sky' },
                { label: 'Coverage gap', description: 'Missing permissions or incomplete service visibility.', tone: 'amber' },
            ],
        };
    }

    if (activeView === 'proposed_cost') {
        return {
            categoryLabel: 'Proposed architecture',
            title: 'Cost-Optimized Scenario',
            description: `AI-assisted optimization proposal for ${providerLabel} in ${region}. The diagram focuses on high-confidence savings moves first, then shows the architectural shape after rightsizing, removal, or targeted migration changes.`,
            supportingText: [proposed?.risk_tradeoffs, evidenceNote].filter(Boolean).join(' '),
            stats: [
                { label: 'Changes recommended', value: String(changeCount), tone: 'sky' },
                { label: 'Estimated impact', value: `${formatArchitectureCurrency(Math.max(proposed?.estimated_savings ?? 0, 0), provider)}/mo`, tone: 'emerald' },
                { label: 'Medium+ risk items', value: String(riskCount), tone: 'amber' },
            ],
            legend: [
                { label: 'Retain / efficient state', description: 'Healthy resources kept in the optimized design.', tone: 'emerald' },
                { label: 'Resize or migrate', description: 'Targeted efficiency move with operational review.', tone: 'amber' },
                { label: 'Retire or remove', description: 'Waste-heavy component removed from the target state.', tone: 'rose' },
            ],
        };
    }

    if (activeView === 'proposed_reliability') {
        return {
            categoryLabel: 'Proposed architecture',
            title: 'Reliability & Security Scenario',
            description: `Resilience and hardening proposal for ${providerLabel} in ${region}. This view emphasizes protective architecture changes, configuration tightening, and coverage improvements that reduce outage and exposure risk.`,
            supportingText: [proposed?.risk_tradeoffs, evidenceNote].filter(Boolean).join(' '),
            stats: [
                { label: 'Changes recommended', value: String(changeCount), tone: 'sky' },
                { label: 'Monthly cost delta', value: formatMonthlyDelta(proposed?.estimated_savings ?? 0, provider), tone: 'amber' },
                { label: 'Medium+ risk items', value: String(riskCount), tone: 'rose' },
            ],
            legend: [
                { label: 'Protected steady state', description: 'Healthy services retained in the hardened design.', tone: 'emerald' },
                { label: 'Hardening change', description: 'Configuration or policy shift requiring rollout discipline.', tone: 'amber' },
                { label: 'New reliability layer', description: 'Added component that improves failover or control coverage.', tone: 'sky' },
            ],
        };
    }

        return {
        categoryLabel: 'Current architecture',
        title: 'Topology Summary',
        description: `${providerLabel} estate summary for ${region}. This diagram groups the scanned footprint into network and service boundaries so engineering, security, and FinOps stakeholders can read structure, dependency shape, and concentration of operational risk at a glance.`,
        supportingText: evidenceNote ?? 'Use this as the executive baseline before drilling into hotspots, microservices, or proposed optimization scenarios.',
        stats: [
            { label: 'Resources mapped', value: String(workloadCount), tone: 'sky' },
            { label: 'Service groups', value: String(groupCount), tone: 'emerald' },
            { label: 'Coverage notes', value: String(warningCount), tone: 'amber' },
        ],
        legend: [
            { label: 'Healthy footprint', description: 'In-policy resources and grouped boundaries.', tone: 'emerald' },
            { label: 'Shared boundary', description: 'Region, VPC, or platform grouping that frames the estate.', tone: 'sky' },
            { label: 'Attention required', description: 'Coverage gap, risk signal, or degraded resource state.', tone: 'amber' },
        ],
    };
}

function StateCard({
    icon,
    title,
    body,
    detail,
}: {
    icon: ReactNode;
    title: string;
    body: string;
    detail?: string;
}) {
    return (
        <div className="flex-1 flex items-center justify-center bg-slate-950/50 p-8">
            <div className="max-w-xl rounded-3xl border border-white/10 bg-[linear-gradient(160deg,rgba(15,23,42,0.94),rgba(2,6,23,0.96))] p-8 text-center shadow-[0_24px_60px_rgba(2,6,23,0.45)]">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-slate-900">
                    {icon}
                </div>
                <h3 className="text-lg font-semibold text-white">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-300">{body}</p>
                {detail ? (
                    <p className="mt-3 text-xs uppercase tracking-[0.24em] text-slate-500">{detail}</p>
                ) : null}
            </div>
        </div>
    );
}

export function MainCanvas({
    mermaidCode,
    nodes,
    activeView,
    selectedNodeId,
    onNodeSelect,
    microservicesAvailable,
    loading,
    provider,
    region,
    warnings,
    proposed,
}: Props) {
    const presentation = buildPresentation(activeView, provider, region, nodes, warnings, proposed);
    const providerLabel = formatProvider(provider);
    const viewModeLabel = activeView.startsWith('proposed_') ? 'Proposed' : 'Current';
    const visibleWarnings = warnings.slice(0, 3);

    if (activeView === 'microservices' && !microservicesAvailable) {
        return (
            <StateCard
                icon={<Lock className="h-7 w-7 text-slate-400" />}
                title="Microservices View Unavailable"
                body="This surface is reserved for EKS or ECS-backed workloads. Add the required container-service permissions, rerun the scan, and the enterprise microservices diagram will populate automatically."
                detail="Requires EKS or ECS visibility"
            />
        );
    }

    if (loading) {
        return (
            <StateCard
                icon={<Loader2 className="h-7 w-7 animate-spin text-indigo-400" />}
                title="Generating Proposed Architecture"
                body="CloudFinOps is composing a structured target-state diagram and change set from the scanned graph. This typically completes within a few seconds."
                detail="AI proposal in progress"
            />
        );
    }

    if (!mermaidCode) {
        return (
            <StateCard
                icon={<AlertCircle className="h-7 w-7 text-slate-400" />}
                title="No Diagram Available"
                body={activeView.startsWith('proposed_')
                    ? 'Generate the proposed architecture from the left rail to produce a target-state diagram, recommendations, and tradeoff summary.'
                    : 'Run a fresh scan for this integration to populate the architecture graph, coverage signals, and diagram output for this view.'}
                detail={`${providerLabel} ${region}`}
            />
        );
    }

    return (
            <div className="flex min-h-[520px] flex-1 bg-slate-950/30">
            <div className={`min-w-0 flex-1 ${nodes.length > 0 ? 'border-r border-white/10' : ''}`}>
                <div className="border-b border-white/10 bg-[linear-gradient(135deg,rgba(2,6,23,0.98),rgba(15,23,42,0.96),rgba(2,6,23,0.98))] px-5 py-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                        <div className="max-w-3xl">
                            <div className="mb-3 flex flex-wrap items-center gap-2">
                                <span className="rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-indigo-300">
                                    {presentation.categoryLabel}
                                </span>
                                <span className="rounded-full border border-white/10 bg-slate-900 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-200">
                                    {providerLabel}
                                </span>
                                <span className="rounded-full border border-white/10 bg-slate-900 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-400">
                                    {region}
                                </span>
                            </div>
                            <h3 className="text-2xl font-semibold tracking-tight text-white">{presentation.title}</h3>
                            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">{presentation.description}</p>
                        </div>

                        <div className="grid min-w-[240px] gap-2 sm:grid-cols-3">
                            {presentation.stats.map((stat) => (
                                <div
                                    key={stat.label}
                                    className={`rounded-2xl border px-3 py-3 ${toneClasses[stat.tone ?? 'slate']}`}
                                >
                                    <p className="text-[10px] font-semibold uppercase tracking-[0.2em] opacity-70">
                                        {stat.label}
                                    </p>
                                    <p className="mt-1 text-base font-semibold text-white">{stat.value}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="relative max-h-[70vh] overflow-auto p-5">
                    <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.12),transparent_32%),radial-gradient(circle_at_bottom_right,rgba(148,163,184,0.12),transparent_34%)]" />
                    <div className="relative">
                        <div className="mb-3 flex flex-wrap items-center justify-between gap-3 px-1">
                            <div className="flex items-center gap-2">
                                <span className="rounded-full border border-white/10 bg-slate-900 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-300">
                                    {viewModeLabel} view
                                </span>
                                <span className="rounded-full border border-white/10 bg-slate-900 px-3 py-1 text-[10px] uppercase tracking-[0.2em] text-slate-500">
                                    Interactive Mermaid render
                                </span>
                            </div>
                            <span className="rounded-full border border-white/10 bg-slate-950/70 px-3 py-1 text-[10px] uppercase tracking-[0.2em] text-slate-400">
                                Scroll to inspect larger graphs
                            </span>
                        </div>

                        <ArchitectureMermaid
                            mermaidCode={mermaidCode}
                            id={`arch-v2-${activeView}`}
                            provider={provider}
                            viewKey={activeView}
                        />
                    </div>
                </div>

                <div className="border-t border-white/10 bg-slate-950/80 px-5 py-4">
                    <p className="text-sm leading-6 text-slate-300">{presentation.supportingText ?? presentation.description}</p>

                    <div className="mt-4 flex flex-wrap gap-2">
                        {presentation.legend.map((item) => (
                            <div
                                key={item.label}
                                className={`flex items-center gap-2 rounded-full border px-3 py-2 text-xs ${toneClasses[item.tone]}`}
                            >
                                <span className={`h-2.5 w-2.5 rounded-full ${dotClasses[item.tone]}`} />
                                <span className="font-medium text-white">{item.label}</span>
                                <span className="text-slate-300">{item.description}</span>
                            </div>
                        ))}
                    </div>

                    {visibleWarnings.length > 0 ? (
                        <div className="mt-4 flex flex-wrap gap-2">
                            {visibleWarnings.map((warning) => (
                                <div
                                    key={`${warning.type}:${warning.message}`}
                                    className="rounded-2xl border border-amber-400/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-100"
                                >
                                    <span className="mr-2 font-semibold uppercase tracking-[0.18em] text-amber-300">
                                        Coverage note
                                    </span>
                                    {warning.message}
                                </div>
                            ))}
                        </div>
                    ) : null}
                </div>
            </div>

            {nodes.length > 0 ? (
                <NodeList
                    nodes={nodes}
                    selectedNodeId={selectedNodeId}
                    onNodeSelect={onNodeSelect}
                    provider={provider}
                />
            ) : null}
        </div>
    );
}
