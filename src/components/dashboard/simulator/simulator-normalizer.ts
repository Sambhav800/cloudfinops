import type {
    SimulatorConfidence,
    SimulatorData,
    SimulatorFinding,
    SimulatorPolicyResult,
    SimulatorPricingSource,
    SimulatorResourceItem,
    SimulatorSummary,
    SimulatorUnestimatedResource,
} from './cost-delta-view';

type UnknownRecord = Record<string, unknown>;

export const EMPTY_SIMULATOR_SUMMARY: SimulatorSummary = {
    total_resources: 0,
    priced_resources: 0,
    exact_resources: 0,
    exact_pricing_resources: 0,
    estimated_resources: 0,
    usage_based_resources: 0,
    unsupported_resources: 0,
    unestimated_resources: 0,
};

function isRecord(value: unknown): value is UnknownRecord {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function toFiniteNumber(value: unknown): number {
    return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function toNullableNumber(value: unknown): number | null {
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function toNullableString(value: unknown): string | null {
    return typeof value === 'string' && value.trim() ? value : null;
}

function toPricingSource(source: unknown, notes: string | null): SimulatorPricingSource {
    if (
        source === 'exact_api' ||
        source === 'heuristic_estimate' ||
        source === 'usage_based' ||
        source === 'unsupported'
    ) {
        return source;
    }

    const normalizedNotes = (notes ?? '').toLowerCase();
    if (normalizedNotes.includes('usage-based') || normalizedNotes.includes('control-plane')) {
        return 'usage_based';
    }
    if (normalizedNotes.includes('estimate')) {
        return 'heuristic_estimate';
    }
    return 'unsupported';
}

function confidenceForSource(source: SimulatorPricingSource): SimulatorConfidence {
    if (source === 'exact_api') {
        return 'high';
    }
    if (source === 'usage_based') {
        return 'medium';
    }
    return 'low';
}

function toSeverity(value: unknown): SimulatorFinding['severity'] {
    return value === 'critical' || value === 'high' || value === 'medium' || value === 'low'
        ? value
        : 'low';
}

function toConfidence(value: unknown): SimulatorConfidence {
    return value === 'high' || value === 'medium' || value === 'low'
        ? value
        : 'low';
}

function toPolicyStatus(value: unknown): SimulatorPolicyResult['status'] {
    return value === 'fail' || value === 'warn' || value === 'pass' ? value : 'warn';
}

export function normalizeSimulationResource(
    resource: Partial<SimulatorResourceItem> | UnknownRecord | null | undefined,
): SimulatorResourceItem {
    const notes = toNullableString(resource?.notes);
    const resourceAddress =
        toNullableString(resource?.resource_address) ??
        toNullableString(resource?.name) ??
        'unknown';
    const resourceType =
        toNullableString(resource?.resource_type) ??
        toNullableString(resource?.type) ??
        'unknown';
    const pricingSource = toPricingSource(resource?.pricing_source, notes);
    const beforeMonthly = toFiniteNumber(resource?.before_monthly ?? resource?.before);
    const afterMonthly = toFiniteNumber(resource?.after_monthly ?? resource?.after);

    return {
        resource_address: resourceAddress,
        resource_type: resourceType,
        action: toNullableString(resource?.action) ?? 'no-op',
        provider: toNullableString(resource?.provider) ?? 'generic',
        region: toNullableString(resource?.region) ?? 'global',
        resource_family: toNullableString(resource?.resource_family) ?? 'other',
        before_monthly: beforeMonthly,
        after_monthly: afterMonthly,
        delta_monthly: toFiniteNumber(resource?.delta_monthly) || Number((afterMonthly - beforeMonthly).toFixed(2)),
        hourly_rate: toFiniteNumber(resource?.hourly_rate) || null,
        pricing_source: pricingSource,
        pricing_basis: toNullableString(resource?.pricing_basis),
        confidence:
            resource?.confidence === 'high' || resource?.confidence === 'medium' || resource?.confidence === 'low'
                ? resource.confidence
                : confidenceForSource(pricingSource),
        notes,
        source_provenance: toNullableString(resource?.source_provenance),
        name: resourceAddress,
        type: resourceType,
        before: beforeMonthly,
        after: afterMonthly,
    };
}

export function normalizeUnestimatedResource(
    resource: Partial<SimulatorUnestimatedResource> | UnknownRecord | null | undefined,
): SimulatorUnestimatedResource {
    const rawResource = isRecord(resource) ? (resource as UnknownRecord) : {};
    const rawAddress = rawResource.address;
    const rawType = rawResource.type;

    return {
        resource_address:
            toNullableString(resource?.resource_address) ??
            toNullableString(rawAddress) ??
            'unknown',
        resource_type:
            toNullableString(resource?.resource_type) ??
            toNullableString(rawType) ??
            'unknown',
        provider: toNullableString(resource?.provider) ?? 'generic',
        region: toNullableString(resource?.region),
        action: toNullableString(resource?.action) ?? 'unknown',
        reason: toNullableString(resource?.reason) ?? 'resource type not in simulator pricing catalog',
    };
}

export function normalizeFinding(
    finding: Partial<SimulatorFinding> | UnknownRecord | null | undefined,
): SimulatorFinding {
    return {
        resource_address: toNullableString(finding?.resource_address) ?? 'unknown',
        finding_id: toNullableString(finding?.finding_id) ?? 'simulator-finding',
        severity: toSeverity(finding?.severity),
        monthly_impact: toNullableNumber(finding?.monthly_impact),
        annual_impact: toNullableNumber(finding?.annual_impact),
        evidence: toNullableString(finding?.evidence) ?? 'Simulator finding generated from Terraform plan attributes.',
        remediation: toNullableString(finding?.remediation) ?? 'Review this resource before applying the Terraform plan.',
        confidence: toConfidence(finding?.confidence),
    };
}

export function normalizePolicy(
    policy: Partial<SimulatorPolicyResult> | UnknownRecord | null | undefined,
): SimulatorPolicyResult | null {
    if (!isRecord(policy)) {
        return null;
    }

    return {
        status: toPolicyStatus(policy.status),
        blocking_reasons: Array.isArray(policy.blocking_reasons)
            ? policy.blocking_reasons.filter((item): item is string => typeof item === 'string')
            : [],
        warnings: Array.isArray(policy.warnings)
            ? policy.warnings.filter((item): item is string => typeof item === 'string')
            : [],
        markdown_summary: toNullableString(policy.markdown_summary) ?? '',
    };
}

export function normalizeSimulationSummary(
    summary: Partial<SimulatorSummary> | UnknownRecord | null | undefined,
    resources: SimulatorResourceItem[],
    unestimatedResources: SimulatorUnestimatedResource[],
): SimulatorSummary {
    const exactResources = resources.filter((resource) => resource.pricing_source === 'exact_api').length;
    const estimatedResources = resources.filter((resource) => resource.pricing_source === 'heuristic_estimate').length;
    const usageBasedResources = resources.filter((resource) => resource.pricing_source === 'usage_based').length;
    const unsupportedResources = resources.filter((resource) => resource.pricing_source === 'unsupported').length;
    const suppliedExactResources = toFiniteNumber(summary?.exact_resources ?? summary?.exact_pricing_resources);
    const suppliedUnestimatedResources = toFiniteNumber(summary?.unestimated_resources);

    return {
        total_resources:
            toFiniteNumber(summary?.total_resources) ||
            resources.length + unestimatedResources.length,
        priced_resources: toFiniteNumber(summary?.priced_resources) || resources.length,
        exact_resources: suppliedExactResources || exactResources,
        exact_pricing_resources: suppliedExactResources || exactResources,
        estimated_resources: toFiniteNumber(summary?.estimated_resources) || estimatedResources,
        usage_based_resources: toFiniteNumber(summary?.usage_based_resources) || usageBasedResources,
        unsupported_resources:
            toFiniteNumber(summary?.unsupported_resources) ||
            unsupportedResources + unestimatedResources.length,
        unestimated_resources: suppliedUnestimatedResources || unestimatedResources.length,
    };
}

export function normalizeSimulationData(data: UnknownRecord): SimulatorData {
    const rawResources = Array.isArray(data.resources) ? data.resources : [];
    const resources = rawResources.map((resource) => normalizeSimulationResource(resource as UnknownRecord));
    const rawUnestimated = Array.isArray(data.unestimated_resources) ? data.unestimated_resources : [];
    const unestimatedResources = rawUnestimated.map((resource) =>
        normalizeUnestimatedResource(resource as UnknownRecord),
    );
    const rawFindings = Array.isArray(data.findings) ? data.findings : [];
    const findings = rawFindings.map((finding) => normalizeFinding(finding as UnknownRecord));

    const monthlyRecord = isRecord(data.monthly) ? data.monthly : {};
    const annualRecord = isRecord(data.annual) ? data.annual : {};
    const before = toFiniteNumber(monthlyRecord.before) || resources.reduce((sum, resource) => sum + resource.before_monthly, 0);
    const after = toFiniteNumber(monthlyRecord.after) || resources.reduce((sum, resource) => sum + resource.after_monthly, 0);
    const delta = toFiniteNumber(monthlyRecord.delta) || toFiniteNumber(data.delta_monthly_cost) || Number((after - before).toFixed(2));

    const annualBefore = toFiniteNumber(annualRecord.before) || Number((before * 12).toFixed(2));
    const annualAfter = toFiniteNumber(annualRecord.after) || Number((after * 12).toFixed(2));
    const annualDelta = toFiniteNumber(annualRecord.delta) || Number((delta * 12).toFixed(2));

    return {
        schema_version: data.schema_version === '2026-04-simulator-v2' ? data.schema_version : undefined,
        currency: toNullableString(data.currency) ?? 'USD',
        monthly: {
            before,
            after,
            delta,
        },
        annual: {
            before: annualBefore,
            after: annualAfter,
            delta: annualDelta,
        },
        summary: normalizeSimulationSummary(
            isRecord(data.summary) ? data.summary : null,
            resources,
            unestimatedResources,
        ),
        resources,
        unestimated_resources: unestimatedResources,
        findings,
        policy: normalizePolicy(isRecord(data.policy) ? data.policy : null),
        before,
        after,
        delta_monthly_cost: delta,
    };
}
