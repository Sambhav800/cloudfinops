'use client';

import { useEffect, useMemo, useState } from 'react';
import {
    AlertCircle,
    CheckCircle,
    Clipboard,
    FileJson,
    Loader2,
    Play,
    Upload,
} from 'lucide-react';
import { motion } from 'framer-motion';

import { simulateTerraformCost } from '@/app/actions/simulator';
import { CostDeltaView, type SimulatorData } from './cost-delta-view';
import {
    EMPTY_SIMULATOR_SUMMARY,
    normalizeSimulationData,
} from './simulator-normalizer';
import { formatInrCurrency, toDisplayInrAmount } from '@/lib/resources/contract';

const PROVIDER_COLORS = {
    aws: '#FF9900',
    azure: '#0078D4',
    gcp: '#4285F4',
    generic: '#6366f1',
} as const;

type ShiftLeftSimulatorProps = {
    commitmentId?: string;
    action?: string;
    mode?: 'terraform_plan' | 'commitment';
};

type CommitmentContext = {
    id: string;
    provider: string;
    type: string;
    name: string;
    status: string;
    start_date: string;
    end_date: string;
    commitment_amount: number;
    currency: string;
    region?: string | null;
    utilization_pct: number;
    savings_amount: number;
    coverage_type: string;
};

type CommitmentsApiResponse = {
    commitments?: CommitmentContext[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function formatCurrency(value: number, currency = 'USD'): string {
    return formatInrCurrency(toDisplayInrAmount(value, currency), {
        maximumFractionDigits: 2,
    });
}

function getRemainingMonths(endDate: string): string {
    const parsed = new Date(endDate);
    if (Number.isNaN(parsed.getTime())) {
        return 'Unknown';
    }

    const millisecondsPerMonth = 1000 * 60 * 60 * 24 * 30.4375;
    const months = Math.max(0, Math.ceil((parsed.getTime() - Date.now()) / millisecondsPerMonth));
    return `${months} mo`;
}

function resolveMode(props: ShiftLeftSimulatorProps): 'terraform_plan' | 'commitment' {
    if (props.mode === 'commitment') {
        return 'commitment';
    }
    if (props.commitmentId && props.action === 'renew') {
        return 'commitment';
    }
    return 'terraform_plan';
}

export function ShiftLeftSimulator(props: ShiftLeftSimulatorProps = {}) {
    const [planJson, setPlanJson] = useState('');
    const [fileName, setFileName] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [simulationResult, setSimulationResult] = useState<SimulatorData | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'paste' | 'upload'>('paste');
    const [commitmentData, setCommitmentData] = useState<CommitmentContext | null>(null);
    const [commitmentLoading, setCommitmentLoading] = useState(false);
    const [commitmentError, setCommitmentError] = useState<string | null>(null);

    const resolvedMode = resolveMode(props);
    const isCommitmentMode = resolvedMode === 'commitment' && Boolean(props.commitmentId);
    const simulationSummary = simulationResult?.summary ?? EMPTY_SIMULATOR_SUMMARY;

    useEffect(() => {
        if (!isCommitmentMode || !props.commitmentId) {
            setCommitmentData(null);
            setCommitmentError(null);
            setCommitmentLoading(false);
            return;
        }

        const controller = new AbortController();
        const loadCommitment = async () => {
            setCommitmentLoading(true);
            setCommitmentError(null);
            try {
                const response = await fetch('/api/finance/commitments', {
                    cache: 'no-store',
                    signal: controller.signal,
                });
                if (!response.ok) {
                    throw new Error(`Commitments API returned ${response.status}`);
                }

                const payload = (await response.json()) as CommitmentsApiResponse;
                const match = payload.commitments?.find((item) => item.id === props.commitmentId) ?? null;
                if (!match) {
                    throw new Error('Commitment was not found for this account.');
                }
                setCommitmentData(match);
            } catch (loadError) {
                if (controller.signal.aborted) {
                    return;
                }
                setCommitmentData(null);
                setCommitmentError(
                    loadError instanceof Error ? loadError.message : 'Failed to load commitment context.',
                );
            } finally {
                if (!controller.signal.aborted) {
                    setCommitmentLoading(false);
                }
            }
        };

        void loadCommitment();

        return () => {
            controller.abort();
        };
    }, [isCommitmentMode, props.commitmentId]);

    const commitmentProviderColor = useMemo(() => {
        const provider = commitmentData?.provider?.toLowerCase() as keyof typeof PROVIDER_COLORS | undefined;
        return provider && PROVIDER_COLORS[provider] ? PROVIDER_COLORS[provider] : PROVIDER_COLORS.generic;
    }, [commitmentData?.provider]);

    const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) {
            return;
        }

        if (!file.name.endsWith('.json')) {
            setError('Please upload a valid .json Terraform plan file.');
            return;
        }

        setFileName(file.name);
        setError(null);

        const reader = new FileReader();
        reader.onload = (loadEvent) => {
            const content = loadEvent.target?.result;
            if (typeof content === 'string') {
                setPlanJson(content);
            } else {
                setError('Failed to read the selected Terraform plan file.');
            }
        };
        reader.readAsText(file);
    };

    const runSimulation = async () => {
        if (!planJson.trim()) {
            setError('Please provide a Terraform plan JSON.');
            return;
        }

        try {
            setIsLoading(true);
            setError(null);

            let parsedPlan: unknown;
            try {
                parsedPlan = JSON.parse(planJson);
            } catch {
                throw new Error('Invalid JSON format. Please check your Terraform plan.');
            }

            if (!isRecord(parsedPlan)) {
                throw new Error('Terraform plan JSON must be an object.');
            }

            let planToSubmit = parsedPlan;
            let resolvedFilename = fileName;
            if (!('resource_changes' in parsedPlan) && isRecord(parsedPlan.plan)) {
                planToSubmit = parsedPlan.plan as Record<string, unknown>;
                if (!resolvedFilename && typeof parsedPlan.filename === 'string') {
                    resolvedFilename = parsedPlan.filename;
                }
            }

            const result = await simulateTerraformCost(planToSubmit, resolvedFilename);
            if (result.error) {
                setSimulationResult(null);
                setError(result.error);
                return;
            }

            if (result.data && isRecord(result.data)) {
                setSimulationResult(normalizeSimulationData(result.data));
            } else {
                setSimulationResult(null);
                setError('Simulator returned an empty response.');
            }
        } catch (simulationError) {
            setSimulationResult(null);
            setError(
                simulationError instanceof Error
                    ? simulationError.message
                    : 'An unexpected error occurred during simulation.',
            );
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            <section className="space-y-6">
                {isCommitmentMode ? (
                    <div
                        className="rounded-2xl border border-white/10 bg-slate-900/50 p-5 shadow-2xl shadow-black/40"
                        style={{ borderTopColor: commitmentProviderColor, borderTopWidth: 2 }}
                    >
                        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                            <div>
                                <p className="text-xs font-semibold uppercase tracking-wide text-indigo-300">
                                    Renewal scenario
                                </p>
                                <h2 className="mt-1 text-lg font-semibold text-white">
                                    Commitment {props.commitmentId}
                                </h2>
                                <p className="mt-1 text-sm text-slate-400">
                                    This context comes from the protected commitments API. Terraform plan input remains separate.
                                </p>
                            </div>
                            <button
                                type="button"
                                className="self-start rounded-xl border border-white/10 px-3 py-2 text-xs font-medium text-slate-300 transition hover:border-indigo-500/50 hover:text-white"
                                onClick={() => {
                                    window.location.href = '/dashboard/simulator';
                                }}
                            >
                                Switch to Terraform plan mode
                            </button>
                        </div>

                        {commitmentLoading ? (
                            <div className="mt-4 flex items-center gap-2 text-sm text-slate-400">
                                <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
                                Loading commitment data...
                            </div>
                        ) : null}

                        {commitmentError ? (
                            <div className="mt-4 rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-300">
                                {commitmentError}
                            </div>
                        ) : null}

                        {commitmentData ? (
                            <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
                                <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                                    <p className="text-xs text-slate-500">Commitment</p>
                                    <p className="mt-1 text-sm font-semibold text-white">
                                        {commitmentData.name}
                                    </p>
                                    <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                                        {commitmentData.provider} / {commitmentData.coverage_type}
                                    </p>
                                </div>
                                <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                                    <p className="text-xs text-slate-500">Amount</p>
                                    <p className="mt-1 text-sm font-semibold text-white">
                                        {formatCurrency(commitmentData.commitment_amount, commitmentData.currency)}
                                    </p>
                                    <p className="mt-1 text-xs text-slate-500">
                                        Savings {formatCurrency(commitmentData.savings_amount, commitmentData.currency)}
                                    </p>
                                </div>
                                <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                                    <p className="text-xs text-slate-500">Utilization</p>
                                    <p className="mt-1 text-sm font-semibold text-white">
                                        {commitmentData.utilization_pct.toFixed(1)}%
                                    </p>
                                    <p className="mt-1 text-xs text-slate-500">
                                        Remaining {getRemainingMonths(commitmentData.end_date)}
                                    </p>
                                </div>
                            </div>
                        ) : null}
                    </div>
                ) : null}

                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 shadow-2xl shadow-black/50 lg:p-8">
                    <div className="mb-2 flex items-center gap-2">
                        <FileJson className="h-5 w-5 text-indigo-400" />
                        <h2 className="text-base font-semibold text-white">Input Terraform Plan</h2>
                    </div>
                    <p className="mb-6 text-sm text-slate-400">
                        Paste `terraform show -json` output or upload a plan file.
                        CloudFinOps will use exact provider pricing where available and
                        transparent estimates everywhere else.
                    </p>

                    <div className="flex border-b border-white/10">
                        <button
                            type="button"
                            aria-pressed={activeTab === 'paste'}
                            className={`inline-flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition ${
                                activeTab === 'paste'
                                    ? 'border-indigo-400 text-white'
                                    : 'border-transparent text-slate-400 hover:text-white'
                            }`}
                            onClick={() => setActiveTab('paste')}
                        >
                            <Clipboard className="h-4 w-4" />
                            Paste JSON
                        </button>
                        <button
                            type="button"
                            aria-pressed={activeTab === 'upload'}
                            className={`inline-flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition ${
                                activeTab === 'upload'
                                    ? 'border-indigo-400 text-white'
                                    : 'border-transparent text-slate-400 hover:text-white'
                            }`}
                            onClick={() => setActiveTab('upload')}
                        >
                            <Upload className="h-4 w-4" />
                            Upload File
                        </button>
                    </div>

                    {activeTab === 'paste' ? (
                        <textarea
                            className="mt-4 min-h-[360px] w-full resize-y rounded-2xl border border-white/10 bg-slate-950/50 p-4 font-mono text-xs leading-5 text-slate-300 outline-none transition-all focus:ring-2 focus:ring-indigo-500 lg:min-h-[420px]"
                            placeholder='{ "format_version": "1.0", "resource_changes": [ ... ] }'
                            value={planJson}
                            onChange={(event) => setPlanJson(event.target.value)}
                        />
                    ) : (
                        <div className="group relative mt-4 flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-white/10 p-12 text-center transition-colors hover:border-indigo-500/50">
                            <input
                                type="file"
                                accept=".json"
                                className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                                onChange={handleFileUpload}
                            />
                            <div className="mb-4 rounded-full bg-indigo-500/10 p-4 transition-transform group-hover:scale-105">
                                <Upload className="h-8 w-8 text-indigo-400" />
                            </div>
                            <p className="text-base font-semibold text-white">
                                {fileName ?? 'Click or drag to upload'}
                            </p>
                            <p className="mt-1 text-sm text-slate-500">Only .json files are supported</p>
                        </div>
                    )}

                    {error ? (
                        <div className="mt-6 rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4">
                            <div className="flex items-start gap-3">
                                <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-rose-400" />
                                <div>
                                    <p className="font-medium text-rose-200">Simulation Error</p>
                                    <p className="mt-1 text-sm text-rose-300">{error}</p>
                                </div>
                            </div>
                        </div>
                    ) : null}

                    <div className="mt-8 flex justify-end">
                        <button
                            type="button"
                            disabled={isLoading}
                            onClick={runSimulation}
                            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {isLoading ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Play className="h-4 w-4" />
                            )}
                            Run Cost Simulation
                        </button>
                    </div>
                </div>

                {simulationResult && !isLoading ? (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.98 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4"
                    >
                        <div className="flex items-start gap-3">
                            <CheckCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-400" />
                            <div>
                                <p className="font-medium text-emerald-200">Simulation Complete</p>
                                <p className="mt-1 text-sm text-emerald-300">
                                    {simulationSummary.exact_resources} exact matches,{' '}
                                    {simulationSummary.estimated_resources} estimated resources,{' '}
                                    {simulationSummary.usage_based_resources} usage-based rows, and{' '}
                                    {simulationSummary.unestimated_resources} unpriced resources were retained for review.
                                </p>
                            </div>
                        </div>
                    </motion.div>
                ) : null}
            </section>

            <section className="space-y-6">
                <CostDeltaView data={simulationResult} isLoading={isLoading} />
            </section>
        </div>
    );
}
