import assert from "node:assert/strict";
import test from "node:test";

// @ts-expect-error node --test --experimental-strip-types resolves this source module directly.
import { normalizeResourceRow, toDisplayInrAmount } from "./contract.ts";

function withFixtureExchangeRate(assertions: () => void): void {
    const previousRate = process.env.NEXT_PUBLIC_USD_TO_INR_RATE;
    try {
        process.env.NEXT_PUBLIC_USD_TO_INR_RATE = "83";
        assertions();
    } finally {
        if (previousRate === undefined) {
            delete process.env.NEXT_PUBLIC_USD_TO_INR_RATE;
        } else {
            process.env.NEXT_PUBLIC_USD_TO_INR_RATE = previousRate;
        }
    }
}

test("control-plane resources render as no direct charge instead of billing unavailable", () => {
    const gcpService = normalizeResourceRow({
        user_id: "user-1",
        integration_id: "int-1",
        provider: "gcp",
        cloud_resource_id: "service-cloudapis",
        resource_name: "cloudapis.googleapis.com",
        service_type: "GCP Service",
        cost: 0,
        metadata: { cost_source: "billing_unavailable" },
    });
    const awsSubnet = normalizeResourceRow({
        user_id: "user-1",
        integration_id: "int-1",
        provider: "aws",
        cloud_resource_id: "subnet-123",
        resource_name: "subnet-123",
        service_type: "AWS Subnet",
        cost: 0,
        metadata: { cost_source: "billing_unavailable" },
    });
    const gcpEntryGroup = normalizeResourceRow({
        user_id: "user-1",
        integration_id: "int-1",
        provider: "gcp",
        cloud_resource_id: "entrygroup-1",
        resource_name: "@bigquery",
        service_type: "GCP EntryGroup",
        cost: 0,
        metadata: { cost_source: "billing_unavailable" },
    });
    const gcpLogBucket = normalizeResourceRow({
        user_id: "user-1",
        integration_id: "int-1",
        provider: "gcp",
        cloud_resource_id: "logbucket-1",
        resource_name: "_Default",
        service_type: "GCP LogBucket",
        cost: 0,
        metadata: { cost_source: "billing_unavailable" },
    });

    assert.equal(gcpService.cost_status, "no_direct_charge");
    assert.equal(gcpService.cost_label, "No direct charge");
    assert.equal(awsSubnet.cost_status, "no_direct_charge");
    assert.equal(gcpEntryGroup.cost_status, "no_direct_charge");
    assert.equal(gcpLogBucket.cost_label, "No direct charge");
});

test("billable resources without resource-level billing matches stay visibly unattributed", () => {
    const gcpDisk = normalizeResourceRow({
        user_id: "user-1",
        integration_id: "int-1",
        provider: "gcp",
        cloud_resource_id: "disk-1",
        resource_name: "disk-1",
        service_type: "GCP Persistent Disk",
        cost: 0,
        metadata: { cost_source: "billing_unavailable" },
    });
    const staleEstimate = normalizeResourceRow({
        user_id: "user-1",
        integration_id: "int-1",
        provider: "aws",
        cloud_resource_id: "i-123",
        resource_name: "i-123",
        service_type: "AWS EC2 Instance",
        cost: 50,
        metadata: { cost_source: "billing_unavailable" },
    });

    assert.equal(gcpDisk.cost_status, "unavailable");
    assert.equal(gcpDisk.cost_label, "No resource-level cost match");
    assert.equal(staleEstimate.cost_status, "unavailable");
    assert.equal(staleEstimate.monthly_cost_available, false);
});

test("actual billing source remains available even when the real cost is zero", () => {
    const zeroActual = normalizeResourceRow({
        user_id: "user-1",
        integration_id: "int-1",
        provider: "aws",
        cloud_resource_id: "i-actual-zero",
        resource_name: "i-actual-zero",
        service_type: "AWS EC2 Instance",
        cost: 0,
        metadata: { cost_source: "actual" },
    });

    assert.equal(zeroActual.cost_status, "actual");
    assert.equal(zeroActual.cost_label, "MTD actual ₹0.00");
    assert.equal(zeroActual.monthly_cost_available, true);
});

test("official catalog estimates are visible without becoming billed monthly cost", () => {
    withFixtureExchangeRate(() => {
        const catalogEstimate = normalizeResourceRow({
            user_id: "user-1",
            integration_id: "int-1",
            provider: "aws",
            cloud_resource_id: "i-catalog",
            resource_name: "i-catalog",
            service_type: "AWS EC2 Instance",
            cost: 14.25,
            metadata: { cost_source: "catalog_estimate", pricing_source: "provider_catalog" },
        });

        assert.equal(catalogEstimate.cost_status, "catalog_estimate");
        assert.equal(catalogEstimate.cost, 1182.75);
        assert.equal(catalogEstimate.cost_label, "Catalog/mo est. ₹1,183");
        assert.equal(catalogEstimate.annual_cost_label, "Catalog/yr est. ₹14,193");
        assert.equal(catalogEstimate.monthly_cost_available, false);
    });
});

test("gcp catalog estimates use stored provider-catalog currency before rupee display", () => {
    withFixtureExchangeRate(() => {
        const catalogEstimate = normalizeResourceRow({
            user_id: "user-1",
            integration_id: "int-1",
            provider: "gcp",
            cloud_resource_id: "vm-catalog",
            resource_name: "vm-catalog",
            service_type: "GCP Compute Instance",
            cost: 5.548,
            metadata: {
                cost_source: "catalog_estimate",
                pricing_source: "provider_catalog",
                currency: "USD",
            },
        });

        assert.equal(toDisplayInrAmount(5.548, "USD"), 460.48);
        assert.equal(catalogEstimate.cost_status, "catalog_estimate");
        assert.equal(catalogEstimate.cost, 460.48);
        assert.equal(catalogEstimate.cost_label, "Catalog/mo est. ₹460.48");
        assert.equal(catalogEstimate.monthly_cost_available, false);
    });
});

test("fixture FX leaves stored INR estimates unchanged and preserves zero and empty inputs", () => {
    withFixtureExchangeRate(() => {
        const catalogEstimate = normalizeResourceRow({
            user_id: "user-1",
            integration_id: "int-1",
            provider: "aws",
            cloud_resource_id: "i-inr-catalog",
            resource_name: "i-inr-catalog",
            service_type: "AWS EC2 Instance",
            cost: 14.25,
            metadata: { cost_source: "catalog_estimate", currency: "INR" },
        });

        assert.equal(catalogEstimate.cost, 14.25);
        assert.equal(catalogEstimate.cost_label, "Catalog/mo est. ₹14.25");
        assert.equal(catalogEstimate.annual_cost_label, "Catalog/yr est. ₹171");
        assert.equal(catalogEstimate.cost_status, "catalog_estimate");
        assert.equal(catalogEstimate.monthly_cost_available, false);
        assert.equal(toDisplayInrAmount(0, "USD"), 0);
        assert.equal(toDisplayInrAmount(null, "USD"), 0);
        assert.equal(toDisplayInrAmount("", "USD"), 0);
    });
});
