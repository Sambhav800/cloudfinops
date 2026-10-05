# Commitment Optimizer Integration Review

Reviewed the integration introduced by `f5adc5b7` against the current commitment trust checks.

## Corrected Behavior

- The dashboard reads the same persisted provider estimates as the commitments and optimizer pages. It no longer derives purchase targets from daily spending.
- `/api/commitment-recommendations` returns the canonical `CommitmentRecommendationResult`, matching `/api/finance/commitment-recommendation`. It accepts `integration_id` and requires authentication. Missing or foreign scopes return 404; read failures return sanitized 503 responses.
- The former `coverage_target`, `max_term`, and `payment_option` query parameters return 422. Callers must adopt the canonical response and stop sending unsupported customization parameters.
- Provider term alternatives remain separate. Unknown coverage, risk, confidence, and break-even periods are not replaced with invented values.
- Purchase estimates currently support AWS Compute Savings Plans. Active Azure/GCP-only portfolios report unsupported, not missing billing data.
- Frontend responses are validated before rendering. Requests have deadlines, cancellation, and retryable error states.
- The common scan path no longer references an Azure-only optimizer variable, which previously stopped non-empty AWS scans before completion.

## Verification

- Focused backend suite: 621 passed, covering commitments, Azure billing, retry behavior, scan persistence, and MCP tools.
- Focused frontend suite: 74 passed, covering rendered states, proxy authentication, cancellation, malformed responses, billing, and bill-scan contracts.
- TypeScript typecheck and targeted ESLint: passed.
- Initial full backend suite: 1001 passed, 28 failed, 1 skipped. The follow-up below resolves those failures.
- Local `dev --webpack` HTTP checks: `/` and `/login` returned 200; unauthenticated `/dashboard` returned 307 and `/api/commitment-recommendations` returned 401.

No live purchase was attempted. Authenticated customer-data reconciliation and production deployment were not verified.

## Pre-Push Follow-Up

The 28 failing tests were investigated rather than skipped:

- Eleven finance/report/agent tests used obsolete currency expectations. Budget entry is INR; fixtures now use matching units. Separate mixed-USD/INR tests prove conversion happens once and budgets are not converted again.
- Eight catalog tests expected unavailable billing to be replaced with market estimates. Fixtures now distinguish `pricing_unavailable` from protected `billing_unavailable`, with explicit tests for tenant isolation and preservation of actual costs.
- Five credential-validation tests mocked obsolete scanner imports or incomplete HTTPX responses. Tests now exercise real HTTP status exceptions, correct scanner boundaries, denial, throttling, and malformed responses.
- Three parser/upload tests required an invented USD currency or leaked raw parser exceptions. Updated tests preserve unknown currency and sanitized 422 responses while retaining downstream no-call checks.
- One timestamp guard exposed a deprecated AWS API Gateway timestamp. The scanner now sends an aware UTC seven-day CloudWatch window.

Additional regression coverage exposed genuine product issues, corrected here:

- Empty finance responses labelled INR budgets as USD. Forecast and history responses now keep the configured display currency, even with no rows.
- Agent summary duplicated the finance conversion rate. Both now use the existing backend conversion helper. This removes drift, not the broader legacy FX fallback policy.
- Failed or empty CloudWatch measurements could become zero traffic and a zombie finding. Unknown measurements now remain null with per-metric collection status. Failure of a secondary metric does not discard a measured request count.
- API intelligence withholds ghost/throttle/efficiency conclusions without measured invocation counts. The API inventory UI handles nullable measurements and sorts unknown values separately.

The final backend run passed 1130 tests, with one skipped because its reference AWS PDF is absent locally. The full frontend run passed 228 tests, and TypeScript typecheck passed. A backend dependency deprecation warning remains; no tests were disabled to reach these results. Stale frontend source-contract and FX fixtures were corrected without restoring synthetic coverage or pricing.

Rollout: deploy the nullable-metric frontend reader before the corresponding backend writer, or coordinate both deployments. No stored inventory is deleted or migrated. Existing API rows that recorded missing telemetry as zero require a fresh scan; their measurements cannot be reconstructed safely.
