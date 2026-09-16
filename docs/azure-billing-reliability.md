# Azure Billing Reliability

## Request Contract

- `AzureBillingReader` sends a stable `ClientType: CloudFinOps` on every Cost Management request. `AZURE_COST_CLIENT_TYPE` can override this application identifier; do not rotate it per request or customer.
- SDK retries are disabled. A failed billing request stops that refresh. The Mongo-backed coordinator schedules the next eligible refresh instead of sleeping through repeated 429s.
- Two daily queries replace four queries: subscription costs grouped by service, then resource costs grouped by resource ID. Subscription totals include charges that cannot be attributed to inventory.
- Each query follows validated continuation tokens. Required columns, finite costs, currencies, and dates are validated before a query's totals are accepted. An incomplete page sequence is not a complete bill.
- Requests/pages are spaced by 16 seconds. A refresh has a 180-second admission budget, bounded transport timeouts, and a continuation-page limit. Very large accounts may require billing exports; limits must not silently truncate their totals.

## Persistence Contract

- `azure_billing_refresh` stores a cache and lease scoped to authenticated user plus normalized subscription. A deterministic Mongo `_id` makes bootstrap uniqueness independent of application startup indexes.
- Conditional lease updates and ownership checks prevent overlapping billing refreshes across processes for that scope. A ten-minute lease outlives the reader budget. Cancellation must not release a lease while a provider thread is still running.
- Complete results are cached for six hours. Failures have a fifteen-minute cooldown, extended when Azure requests a longer delay. Configuration lives in `BillingRefreshConfig`.
- Same-month successful parts can survive later failures. Observation timestamps stay attached to the data, not the latest inventory scan. Previous-month data must not become current MTD.
- An inventory rescan can complete while billing is stale/unavailable. Resource and subscription cost provenance records that distinction.
- Daily spend is upserted in batches, never erased by an empty/failed response. A successful zero-cost query supplies explicit zero daily rows.
- Dashboard MTD is aggregated by the backend from current-month `daily_spend_history`, not inventory prices. Missing billing is unavailable, not zero; partial provider coverage cannot be labeled a complete portfolio total.

## Validation And Operations

Focused tests:

```sh
cd backend
venv/bin/python -m pytest tests/test_retry.py tests/test_azure_billing_reader.py tests/test_azure_billing_refresh.py tests/test_azure_scan_billing.py tests/test_dashboard_billing_summary.py -q
```

On a 429, inspect the allowlisted quota headers and request ID in backend logs. The exhausted quota may be client-type, tenant, entity, or QPU; elapsed time since a manual scan does not identify the caller consuming that quota. Honor the longest valid retry header.

Microsoft support describes the missing-client-type shared quota behavior here:
https://learn.microsoft.com/en-us/answers/questions/1340993/exception-429-too-many-requests-for-azure-cost-manage

General Cost Management automation guidance:
https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/manage-automation

This change cannot guarantee Azure never returns 429. It prevents our scanner from amplifying throttling or presenting failed billing retrieval as a zero bill. Deploy backend and frontend together, then rescan to replace previously corrupted zero values with actual provider data. Do not reconstruct missing historical costs from estimates.
