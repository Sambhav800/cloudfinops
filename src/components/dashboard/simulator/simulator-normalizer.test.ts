import assert from 'node:assert/strict';
import test from 'node:test';

async function loadNormalizer() {
    return import(new URL('./simulator-normalizer.ts', import.meta.url).href) as Promise<
        typeof import('./simulator-normalizer')
    >;
}

test('normalizeSimulationData derives a safe v2-shaped summary from older v1 payloads', async () => {
    const { normalizeSimulationData } = await loadNormalizer();
    const result = normalizeSimulationData({
        delta_monthly_cost: 25,
        currency: 'USD',
        resources: [
            {
                name: 'aws_instance.web',
                type: 'aws_instance',
                before: 10,
                after: 35,
                notes: 'Estimated from EC2 instance class reference pricing.',
            },
        ],
    });

    assert.equal(result.summary.exact_resources, 0);
    assert.equal(result.summary.exact_pricing_resources, 0);
    assert.equal(result.summary.estimated_resources, 1);
    assert.equal(result.summary.usage_based_resources, 0);
    assert.equal(result.summary.unestimated_resources, 0);
    assert.equal(result.resources[0].provider, 'generic');
    assert.equal(result.resources[0].resource_address, 'aws_instance.web');
    assert.equal(result.resources[0].pricing_source, 'heuristic_estimate');
    assert.equal(result.monthly.delta, 25);
    assert.equal(result.annual.delta, 300);
    assert.deepEqual(result.findings, []);
    assert.equal(result.policy, null);
});

test('normalizeSimulationData preserves v2 fields and unestimated resources on the happy path', async () => {
    const { normalizeSimulationData } = await loadNormalizer();
    const result = normalizeSimulationData({
        schema_version: '2026-04-simulator-v2',
        currency: 'USD',
        monthly: { before: 0, after: 48.91, delta: 48.91 },
        annual: { before: 0, after: 586.92, delta: 586.92 },
        summary: {
            total_resources: 2,
            priced_resources: 1,
            exact_resources: 1,
            estimated_resources: 0,
            usage_based_resources: 0,
            unestimated_resources: 1,
        },
        resources: [
            {
                resource_address: 'google_compute_instance.api',
                resource_type: 'google_compute_instance',
                provider: 'gcp',
                region: 'us-central1',
                action: 'create',
                resource_family: 'compute',
                pricing_source: 'exact_api',
                before_monthly: 0,
                after_monthly: 48.91,
                delta_monthly: 48.91,
                hourly_rate: null,
                pricing_basis: null,
                confidence: 'high',
                notes: null,
                source_provenance: 'provider catalog',
            },
        ],
        unestimated_resources: [
            {
                resource_address: 'aws_new_unmodeled_service.preview',
                resource_type: 'aws_new_unmodeled_service',
                provider: 'aws',
                region: 'us-east-1',
                action: 'create',
                reason: 'resource type not in simulator pricing catalog',
            },
        ],
        findings: [
            {
                resource_address: 'google_compute_instance.api',
                finding_id: 'ec2-old-generation',
                severity: 'medium',
                monthly_impact: null,
                annual_impact: null,
                evidence: 'Previous generation resource detected.',
                remediation: 'Validate a newer generation.',
                confidence: 'medium',
            },
        ],
        policy: {
            status: 'warn',
            blocking_reasons: [],
            warnings: ['Only 50.0% exact pricing.'],
            markdown_summary: '## Cost policy: WARN',
        },
    });

    assert.equal(result.schema_version, '2026-04-simulator-v2');
    assert.equal(result.summary.exact_resources, 1);
    assert.equal(result.summary.exact_pricing_resources, 1);
    assert.equal(result.resources[0].provider, 'gcp');
    assert.equal(result.resources[0].region, 'us-central1');
    assert.equal(result.resources[0].pricing_source, 'exact_api');
    assert.equal(result.unestimated_resources[0].resource_type, 'aws_new_unmodeled_service');
    assert.equal(result.findings[0].finding_id, 'ec2-old-generation');
    assert.equal(result.policy?.status, 'warn');
});

test('normalizeSimulationData returns empty defaults for empty or malformed payloads', async () => {
    const { EMPTY_SIMULATOR_SUMMARY, normalizeSimulationData } = await loadNormalizer();
    const result = normalizeSimulationData({});

    assert.deepEqual(result.summary, EMPTY_SIMULATOR_SUMMARY);
    assert.equal(result.currency, 'USD');
    assert.equal(result.monthly.before, 0);
    assert.equal(result.monthly.after, 0);
    assert.deepEqual(result.resources, []);
    assert.deepEqual(result.unestimated_resources, []);
    assert.deepEqual(result.findings, []);
    assert.equal(result.policy, null);
});
