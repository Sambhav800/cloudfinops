'use server';

import { getArchitecture, getArchitectureGraph, generateProposedArchitecture, generateArchitectureReport } from '@/lib/api';
import type { GraphResponse, ProposedResult, ProposedMode } from '@/lib/architecture-types';

// ---------------------------------------------------------------------------
// Legacy Mermaid-only endpoint (backward compat)
// ---------------------------------------------------------------------------

export async function getArchitectureAction(
    integrationId: string,
    region?: string,
    vpcId?: string,
    viewType: 'summary' | 'hotspots' | 'vpc_detail' = 'summary'
) {
    return getArchitecture(integrationId, region, vpcId, viewType);
}

// ---------------------------------------------------------------------------
// Graph JSON endpoint (Architecture V2)
// ---------------------------------------------------------------------------

export async function getGraphAction(
    integrationId: string,
    provider: string,
    region?: string,
    view?: string,
    vpcId?: string,
): Promise<{ data: GraphResponse | null; error: string | null }> {
    const result = await getArchitectureGraph(integrationId, provider, region, view, vpcId);

    if ('error' in result) {
        return { data: null, error: result.error.detail };
    }

    return { data: result.data as GraphResponse, error: null };
}

// ---------------------------------------------------------------------------
// Proposed architecture generation (user-triggered)
// ---------------------------------------------------------------------------

export async function generateProposedAction(
    integrationId: string,
    provider: string,
    region: string,
    mode: ProposedMode,
    constraints?: string[],
): Promise<{ data: ProposedResult | null; error: string | null }> {
    const result = await generateProposedArchitecture(integrationId, provider, region, mode, constraints);

    if ('error' in result) {
        return { data: null, error: result.error.detail };
    }

    return { data: result.data as ProposedResult, error: null };
}

// ---------------------------------------------------------------------------
// Architecture Report Generation (AI-powered PDF export)
// ---------------------------------------------------------------------------

export type ArchitectureReportResult = {
    status: string;
    report_markdown: string;
    title: string;
    generated_at: string;
    provider: string;
    region: string;
    integration_name: string;
};

export async function generateReportAction(
    integrationId: string,
    provider: string,
    region: string,
): Promise<{ data: ArchitectureReportResult | null; error: string | null }> {
    const result = await generateArchitectureReport(integrationId, provider, region);

    if ('error' in result) {
        return { data: null, error: result.error.detail };
    }

    return { data: result.data as ArchitectureReportResult, error: null };
}
