# Commitment Engine Review

Date: 2026-09-15

## Verdict

The previous implementation was not suitable for commitment purchase decisions.
Its primary recommendation endpoint manufactured discounts, used all-account
daily spend as a compute baseline, and could label INR-converted values as USD.
The copilot independently invented recommendations. Inventory normalization and
failure handling also had defects. An LLM was not the only source of unreliable
claims: deterministic financial calculations were wrong too.

This change makes the live surface a read-only, provider-evidence-backed system.
It does not establish Usage.ai parity, guaranteed savings, or production purchase
readiness. No commitments were purchased and no customer cloud APIs were queried
as part of verification.

## Corrected Paths

| Area | Correction |
| --- | --- |
| Purchase estimates | Persist AWS Cost Explorer Compute Savings Plan estimates for 1/3-year, no-upfront alternatives. No fixed discount, inferred compute fraction, invented confidence, or automatic winner. |
| Source of truth | API, optimizer page, and MCP commitment tool use `commitment_purchase_snapshots`; inventory reads use `commitment_snapshots`. No cloud/LLM calls on dashboard reads. |
| Scope | Query by authenticated user and active integration; validate AWS caller identity and returned account; deduplicate recommendations from duplicate account connections. |
| Financial units | Hourly commitments normalize to a clearly identified 730-hour monthly equivalent. Provider monthly savings stay monthly; trailing seven-day savings retain their dates. Mixed-currency totals remain unknown. |
| Inventory | Correct AWS `state`/`currency` fields, pagination, enabled-region discovery, RI instance counts and term amortization, and explicit provider failures. |
| AWS dates | Utilization uses a completed seven-day, end-exclusive window ending before today, as required by the API. |
| Role credentials | Reuse existing AssumeRole helper, require ExternalId, and carry temporary SessionToken into inventory and recommendation calls. Do not persist credentials in snapshots. |
| Portfolio | Verify inventory account identity with STS. The newest complete account/region-scope snapshot supersedes older duplicate connections, including empty results. Deduplicate commitment identities, honor contractual dates, and aggregate SP utilization using measured UsedCommitment/TotalCommitment. Do not blend RI hours with SP dollars. |
| Freshness | Withhold purchase estimates with failed refreshes, stale/future timestamps, malformed amounts, contradictory statuses, or mismatched account scope. Successful empty refreshes clear obsolete estimates. |
| UI | Show unknown measurements explicitly, provider/source/freshness, account sync failures and alternatives. Preserve account filtering, retry, and escaped PDF/print export. |
| Dormant optimizer | Replace fixed-discount logic with an evidence-gated historical backtest requiring complete hourly residual usage, reconciled inventory, and a matching fresh live quote. |
| Dormant coverage helper | Require explicit current resource billing allocation; family matching and account utilization no longer establish resource coverage or stranded cost. |

## Actual Runtime Flow

1. A successful cloud scan invokes the existing commitment sync hook.
2. Sync reads encrypted integration credentials and retrieves provider inventory.
3. Inventory success replaces its scoped snapshot; failure retains last-known
   inventory with a visible failure/staleness status.
4. Successful real AWS inventory sync requests purchase estimates from Cost
   Explorer and persists them separately. Recommendation failures do not erase
   successful inventory. This is a scan-triggered refresh, not a new scheduler.
5. Dashboard and MCP reads validate persisted evidence and return it without
   invoking Gemini. Alternative terms for one account must never be summed.

The offline optimizer and resource allocation helper currently have no production
callers. Their tests prove their supplied-input behavior, not a deployed hourly
billing ingestion or coverage allocation service.

## Support And Limitations

- AWS: Savings Plans and EC2 RI inventory; Compute Savings Plan purchase estimates.
  Database reservations, organization-wide optimization, every SP product, and
  amortized billing reconciliation are not fully implemented.
- Azure: commitment inventory and purchase estimates remain explicitly unsupported.
  Azure Advisor recommendations elsewhere are not a substitute for these APIs.
- GCP: regional Compute Engine CUD inventory only. Financial fields remain unknown
  without a billing export adapter. This is not complete GCP CUD coverage.
- Provider estimates describe historical usage and may not reflect a planned
  migration, shutdown, rightsizing, growth change, or negotiated rate agreement.
- Missing permissions or inventory failure can prevent the subsequent AWS
  recommendation refresh. This is visible, not silently converted to zero waste.
- Legacy AWS inventory without verified account identity requires a rescan before
  portfolio totals are shown. Duplicate connections with different region scopes
  require a unified inventory scope; their financial totals are withheld.
- The offline optimizer currently supports only no-upfront AWS SP economics with
  homogeneous rate groups. Its adapter must authenticate source evidence and prove
  groups are disjoint and residual usage accounts for organization sharing.
- No calibrated future-demand risk model, hourly billing adapter, counterfactual
  realized-savings ledger, insurance, buyback, rebalancing, or purchase execution
  was added. No PR/IaC execution was added.
- Portfolio read latency, concurrent refresh ordering, unique snapshot indexes,
  large-account document sizing, and job scheduling need production load and
  database validation. They are not certified by unit tests.
- Other recommendation tools and unrelated finance pages were not certified as
  hallucination-free by this scoped review.

## Verification

- Focused commitment/API/MCP regression suite: 292 passed.
- Frontend commitment contract/render/proxy tests: 16 passed.
- Playwright: 13 checks passed using real components with temporary fixtures,
  at 1440px desktop and 390px mobile widths. Nine screenshots and a PDF export
  were produced. Filtering, account selection, exports, all non-ready states,
  retries, and the real 20-second timeout were checked. No page-level horizontal
  overflow, clipped controls/headings, or unexpected browser errors were found.
  Authenticated customer data and the dashboard's surrounding shell were not
  exercised by this offline component harness. Artifacts are under
  `/tmp/cloudfinops-commitment-browser/artifacts/`.
- TypeScript typecheck and `git diff --check`: passed.
- Full backend suite with `DEBUG=false`: 708 passed, 32 failed, 1 skipped.
- Untouched `HEAD` extracted into a separate directory: 465 passed, 34 failed,
  1 skipped. XML result comparison found no newly failing test identities. The
  remaining 32 failures occur in both trees. The two old failing demo tests were
  replaced by explicit demo-provenance and fail-visible inventory coverage.
- Actual local `npm run dev -- --hostname localhost --port 3000` requests:
  `/` and `/login` return 200; `/dashboard/commitments` redirects with 307.
- Actual local backend `/api/finance/commitments` rejects an unauthenticated
  request with 401. Both frontend commitment API proxies also return 401, and
  `/dashboard/optimizer` redirects with 307. No auth bypass was added.
- AWS request/response shapes tested against installed botocore models/Stubber.
  This does not prove account permissions, provider availability, or real bills.
- `graphify update .` completed using AST extraction. It reports an unrelated
  parse warning for `src/app/security/page.tsx` and zero-node JSON fixtures.

## Next Release Gates

1. Reconcile one consenting AWS pilot against Cost Explorer: inventory IDs,
   commitment fees, exact utilization windows, currency, and purchase estimates.
   Include role-only access, denied CE access, pagination, empty results, and expiry.
2. Validate scoped unique snapshot indexes, concurrent scan ordering, refresh
   scheduling, permission diagnostics, stale-data alerts, and read latency.
3. Build an authenticated hourly CUR/data-export adapter and allocation evidence
   before connecting the offline optimizer. Reconcile existing commitments and
   sharing first; test chronological holdouts and negative-savings cases.
4. Add rightsizing-first scenarios, business constraints, lifecycle approvals,
   and independently reconciled realized savings. Keep purchase execution off.
5. Add Azure and broader GCP billing-backed support with provider-specific tests.
6. Consider ML only after collecting trustworthy history: calibrated demand
   forecasts and downside scenarios with out-of-sample evaluation. LLMs may
   explain evidence but must not originate prices, utilization, or savings.

## Research

- [AWS purchase recommendation API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetSavingsPlansPurchaseRecommendation.html)
- [AWS SP utilization API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetSavingsPlansUtilizationDetails.html)
- [AWS RI inventory API](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeReservedInstances.html)
- [Usage.ai](https://usage.ai/) advertises insured commitments, buyback, automatic
  buying/rebalancing, and realized-savings-based fees. These are company claims,
  not independently verified here. Financial guarantees require contractual and
  commercial capabilities, not simply a better model or dashboard.
