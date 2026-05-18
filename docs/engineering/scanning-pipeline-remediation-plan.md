# Scanning Pipeline Remediation — Implementation Plan

| | |
|---|---|
| **Status** | Draft v1.0 — pending engineering approval |
| **Owner** | Backend Platform / FinOps Scanner team |
| **Co-owners** | Frontend Dashboard team, Data Platform team |
| **Reviewers needed** | Tech lead, SRE, QA lead, Product |
| **Target release** | 2 sprints (≈10 working days) |
| **Related docs** | Audit reports (DB Idempotency / Pricing Pipeline / Data Flow) |
| **Last updated** | 2026-05-04 |

---

## 1. Executive Summary

A multi-layer audit of the scanning pipeline (3 specialist agents, 17 source files, ~6,600 LOC reviewed) found **three independent root causes** that compound to produce the user-reported symptoms: fake "real prices" on the dashboard, duplicates after every rescan, and stale numbers that never refresh.

This document is the end-to-end remediation plan. It is structured as **3 phases × 5 stories each (15 stories)**, plus a Phase 0 foundation. Every story has a Definition of Ready (DoR), a Definition of Done (DoD), affected files with line refs, test requirements, and rollback steps.

**Total estimated effort:** 10 working days (1 senior backend + 1 senior frontend, in parallel where possible).

**Top-level success criteria:**
1. Zero duplicate resources after any sequence of rescans (verified via the duplicate audit query — see §6).
2. Every monetary value on the dashboard either comes from a billing API (`cost_source=actual`) or is visibly labeled as an estimate. No silent synthetic values.
3. After scan completes, every page (server- and client-rendered) shows fresh data within 5 seconds — no manual reload.

---

## 2. Goals and Non-Goals

### Goals (in scope)

- G1 — **Idempotent scans**: a rescan never creates duplicate rows, and partial-failure scans never leave orphans.
- G2 — **Truthful pricing**: separate "real" billing-derived costs from "list price estimate" costs throughout the stack and label them in the UI.
- G3 — **Correct currency math**: a single canonical currency at the storage and aggregation layer; conversion happens once, at the display edge.
- G4 — **Live data after rescan**: client-rendered pages re-fetch within 5 seconds of `scan_complete`. Caches that survive rescans are invalidated.
- G5 — **Permission feedback to users**: when a scanner falls back to estimates because of an IAM/RBAC gap, the integration card surfaces the specific permission and a remediation link.

### Non-goals (explicitly out of scope for this plan)

- N1 — Replacing the AI verification step. We will preserve current AI behavior and only fix the duplicate window around it.
- N2 — Adding real-time streaming costs. Polling-based scans remain the architecture.
- N3 — Re-architecting the integration credential storage. We treat existing credential decryption as a working contract.
- N4 — Adding new cloud providers. AWS / Azure / GCP / Kubernetes coverage stays as-is.
- N5 — UI redesign of the dashboard pages. Only the cost-source labeling and refresh hook are in scope on the frontend.

---

## 3. Phase 0 — Pre-flight (Day 0–1)

**Why this phase exists:** Any of the P0 fixes will quietly fail without baseline metrics, decisions locked in, and feature flags wired. A real release process pays this tax up front.

### Story 0.1 — Establish baseline metrics

**What:** Record the *current* values of the metrics this plan promises to improve, before any fix lands.

**Metrics to capture** (from a single staging scan of a multi-provider tenant):
- `resources.duplicates.before_dedupe` — duplicates produced by a single AWS scan, count
- `resources.duplicates.after_two_rescans` — total resources after two rescans / total unique cloud_resource_id values
- `resources.cost_source.distribution` — % of resources with `actual` vs `catalog_estimate` vs `billing_unavailable` per provider
- `resources.zero_cost_pct` — % of resources with `cost == 0` per provider
- `dashboard.totalbill.currency_consistency` — does `total_spend = sum(provider.monthly_spend)` within 0.5% rounding? (today: no)
- `frontend.refresh_latency_p95` — seconds from `scan_complete` event to dashboard showing new numbers (manual measurement: 5 sample rescans)

**Output:** `docs/engineering/scanning-pipeline-baseline-2026-05-04.md` with the table.

**Acceptance:** All six metrics captured for AWS (with valid Cost Explorer creds), AWS (with creds but no Cost Explorer permission), Azure, GCP, and a multi-provider tenant.

**Effort:** 0.5 day (one engineer + a tester running scans).

---

### Story 0.2 — DECISION: canonical storage currency

**What:** Lock in the *single* currency we use everywhere below the display layer.

**Recommendation:** **USD as canonical.** Rationale:
- Cost Explorer, Cost Management, and BigQuery billing exports all natively support USD.
- The catalog (`provider_pricing_catalog.py:123`) already emits USD by default.
- We only need to convert at display time, in a single place.

**What changes downstream:**
- GCP scanner stops storing INR; converts BigQuery rows to USD at scan time using the row-level FX from the export itself.
- Azure scanner uses Cost Management API's `convert` parameter to request USD directly (replacing the hard-coded `CURRENCY_TO_USD = 0.012`).
- `dashboard_stats.total_spend`, `resources.cost`, every aggregate field becomes USD.
- The frontend `toDisplayInrAmount` helper is the *only* INR conversion point.

**Decision is required before** Stories 1.3, 2.x, 3.2.

**Acceptance:** Decision recorded with sign-off from Tech Lead + Product. ADR (Architecture Decision Record) written: `docs/engineering/adr-001-canonical-currency-usd.md`.

---

### Story 0.3 — DECISION: catalog estimate policy

**What:** Decide the contract for `_apply_catalog_estimates_for_scan`.

Three policy options, **pick exactly one**:

- **Policy A — Off by default**: catalog estimates only run when integration metadata sets `enable_catalog_estimates: true`. Default behavior is `cost = 0` for unbilled resources. UI labels them "Cost data unavailable — see permissions."
- **Policy B — Side-channel field** (recommended): `_apply_catalog_estimates_for_scan` writes to a NEW field `catalog_cost_estimate` instead of `cost`. UI shows `cost` (real, possibly zero) prominently and `catalog_cost_estimate` as muted parenthetical.
- **Policy C — Status quo with strict labeling**: keep overwriting `cost`, but make the UI display unmistakably distinct (badge, color, "Est." prefix) for `cost_source ∈ {catalog_estimate, service_estimate}`.

**Recommendation:** **Policy B**. It cleanly separates the two values, is reversible, and unblocks future ML-based cost estimation without rebuilding the column semantics.

**Acceptance:** ADR `docs/engineering/adr-002-catalog-estimate-policy.md` with decision and downstream impact list (api fields, frontend rendering, aggregation logic).

---

### Story 0.4 — Feature flag wiring

**What:** Add a small `feature_flags.py` module so each Phase 1/2 fix can be gated.

**Flags introduced (all default off in production until Phase 4 ramp-up):**
- `SCAN_LOCK_ENABLED` — gate Story 1.1
- `STRICT_RESOURCE_INDEX_ENABLED` — gate Story 1.2 (must be flipped *after* migration in Story 6.2)
- `CURRENCY_NORMALIZATION_ENABLED` — gate Story 1.3
- `CATALOG_SIDECHANNEL_ENABLED` — gate Story 0.3 Policy B
- `MULTICLOUD_AUTO_REFRESH_ENABLED` — gate Story 1.5
- `STABLE_AWS_RESOURCE_ID_ENABLED` — gate Story 2.1

**Implementation:**
- Server side: env vars + Python module, override per-request via `X-Feature-Flag-Override` header for QA only (not prod).
- Frontend: build-time replacement via `NEXT_PUBLIC_FEATURE_*` env vars.

**Acceptance:** Flags read & log on startup; `/health` endpoint reports active flags; QA override mechanism documented.

**Effort:** 0.5 day.

---

### Story 0.5 — Observability hooks

**What:** Add structured event logging at every junction this plan touches, so we can measure the fixes in production.

**Structured events (JSON log lines + Prometheus counters):**
- `scan.started` — { user_id, integration_id, provider, batch_id, timestamp }
- `scan.lock.acquired` / `scan.lock.rejected` — { integration_id, reason, in_flight_batch_id }
- `scan.upsert.batch` — { integration_id, batch_id, attempted, succeeded, deduped }
- `scan.delete.stale_batch` — { integration_id, batch_id, removed_count }
- `scan.completed` / `scan.failed` — { integration_id, batch_id, duration_ms, resource_count, cost_source_distribution }
- `pricing.fallback.applied` — { integration_id, provider, resource_count, reason }
- `currency.conversion` — { source, target, rate, source_value, target_value }
- `cache.invalidated` — { key_pattern, count, trigger }
- `frontend.refresh.triggered` — { trigger, page, latency_ms }

**Prometheus counters/gauges:**
- `cloudfinops_scan_total{provider,outcome}` (counter)
- `cloudfinops_scan_lock_rejections_total{integration_id}` (counter)
- `cloudfinops_resources_total{provider,cost_source}` (gauge, per scan)
- `cloudfinops_duplicate_resources_total{integration_id}` (gauge — should be 0)

**Acceptance:** All events emit on a happy-path scan, viewable in logs and a Grafana dashboard tile.

**Effort:** 1 day.

---

## 4. Phase 1 — Stop the Bleeding (Days 2–4)

Five P0 stories. These directly map to the three user-visible symptoms. Goal: ship to staging at end of Day 4, soak for 24h, then prod behind feature flags.

---

### Story 1.1 — Scan idempotency lock

**Symptom addressed:** Duplicate resources from concurrent rescans (Root cause #2 in synthesis).

**Approach:**
- Module-level `dict[integration_id → asyncio.Lock]` in `routes.py` (or extracted helper module `app/core/scan_lock.py`).
- Acquire with `lock.acquire(blocking=False)` semantics — if lock is held, return HTTP 409 Conflict with `{ "in_flight_batch_id": "...", "started_at": "..." }`.
- Lock is released in `try/finally` around the entire `run_scan` body.
- Persist a `scans_in_progress` Mongo document as the source of truth across worker processes (asyncio.Lock alone is per-process; a Mongo `findOneAndUpdate({_id: integration_id, locked: false}, {$set: {locked: true, started_at: now, batch_id: batch_id}})` provides cross-process safety).

**Files:**
- `backend/app/api/routes.py:1724-1760` — `trigger_scan` endpoint
- `backend/app/api/routes.py:1763-2300` — `run_scan` background task (wrap in lock acquire/release)
- New: `backend/app/core/scan_lock.py`
- `backend/app/db/mongo_client.py` — add `acquire_scan_lock` / `release_scan_lock` methods

**Implementation steps:**
1. Create `scan_lock.py` with `acquire(integration_id, batch_id) -> Optional[lock_handle]` and `release(handle)`.
2. Add Mongo index on `scans_in_progress.integration_id` (unique).
3. In `trigger_scan`, attempt acquire before scheduling background task. On reject, return 409.
4. In `run_scan`, wrap entire body in `try/finally: release(handle)`.
5. Add stale-lock cleanup: any `scans_in_progress` entry older than 30 min is forcibly released by a cron.
6. Frontend: handle 409 response in `ScanProvider` — show toast "Scan already running, please wait".

**Tests:**
- Unit: lock acquire/release happy path.
- Integration: two concurrent `POST /scan` calls → second returns 409.
- Integration: scan crashes mid-flight → next scan succeeds.
- Integration: stale-lock cron releases lock older than threshold.

**Acceptance:**
- Concurrent rescans cannot run.
- Crash recovery within 30 min via cron.
- Frontend shows clear feedback on 409.

**Rollback:** `SCAN_LOCK_ENABLED=false` reverts to no-lock behavior.

**Effort:** 1 day.

---

### Story 1.2 — Strict unique index on resources

**Symptom addressed:** Partial unique index allows null/missing fields through (Root cause #2).

**Approach:**
- Drop existing partial unique index `(integration_id, cloud_resource_id)`.
- Replace with strict unique on `(user_id, integration_id, cloud_resource_id)` — no partial filter.
- Validate non-empty `cloud_resource_id` and `user_id` in `bulk_upsert_resources` before issuing writes.
- Add non-unique secondary index on `(user_id, integration_id, scan_batch_id)` to make stale-batch deletes index-driven.

**Files:**
- `backend/app/db/mongo_client.py:152-161` — index definitions in `_ensure_indexes()`
- `backend/app/db/mongo_client.py:526-615` — `bulk_upsert_resources` (add validation)
- New: `backend/migrations/2026_05_resources_unique_index.py` — migration script

**Migration sequence (production):**
1. Pre-migration audit: run `dedupe_resources_for_integration` (already exists at `mongo_client.py:617`) for every active integration. Capture removed-row count.
2. Verify zero duplicates: `db.resources.aggregate([{$group: {_id: {user_id, integration_id, cloud_resource_id}, count: {$sum: 1}}}, {$match: {count: {$gt: 1}}}])` — must return `[]`.
3. Drop old index: `db.resources.dropIndex("integration_id_1_cloud_resource_id_1")`.
4. Build new index in background: `db.resources.createIndex({user_id: 1, integration_id: 1, cloud_resource_id: 1}, {unique: true, background: true})`.
5. Build secondary index: `db.resources.createIndex({user_id: 1, integration_id: 1, scan_batch_id: 1}, {background: true})`.
6. Flip `STRICT_RESOURCE_INDEX_ENABLED=true`.

**Tests:**
- Migration script idempotent (re-run safe).
- `bulk_upsert_resources` rejects rows with empty `cloud_resource_id` (returns 400-equivalent or skips with warning).
- Two integrations with the same `cloud_resource_id` (cross-account) are no longer in conflict (because user_id is in the key).

**Acceptance:**
- The duplicate-check aggregation returns `[]` after the migration on every staging tenant.
- Index lookups visible in MongoDB profiler for `find({user_id, integration_id, cloud_resource_id})`.

**Rollback:** Drop new indexes, recreate old partial index. Flag back to false.

**Effort:** 1 day (incl. migration testing on staging clone).

---

### Story 1.3 — Currency normalization at write & read

**Symptom addressed:** Currency mixing causes ~83× inflation on GCP rows (Root cause #3).

**Prerequisite:** Story 0.2 (canonical = USD) decided.

**Approach (write side):**
- GCP scanner: in `_fetch_real_costs_from_billing_export` (`gcp.py:160`), read the row-level `currency` and `currency_conversion_rate` columns from the BigQuery billing export. Convert to USD at scan time. Set `billing_currency = "USD"` (default at line 221).
- Azure scanner: replace `CURRENCY_TO_USD` static table (`azure.py:75`) with the Cost Management API's `convert: "USD"` query parameter — Azure returns native USD. Fall back to API-provided rate if customer's billing currency differs.
- AWS already returns USD natively from Cost Explorer — verified, no change.
- Catalog estimator already emits USD — verified, no change.

**Approach (read side):**
- `routes.py:1607-1644` (`/totalbill`) — assert `currency` is USD on every per-integration `dashboard_stats` row before summing. Add `total_spend_currency: "USD"` to the response. Return per-provider amounts in USD.
- `routes.py` `/stats`, `/multicloud/comparison`, `/spend-history` — same: emit `currency: "USD"` in response, callers must respect.
- Frontend `multicloud/page.tsx:144-145`: change `fmt = formatInrCurrency(toDisplayInrAmount(value, "USD"))` — the input is now always USD, no per-row currency lookup needed.
- Frontend `dashboard/data.ts:524-529`: kill the silent INR fallback in `displayTotalSpend`. Replace with a strict assertion that throws (in dev) or returns 0 (in prod) when stats are missing — never multiply.

**Files:**
- `backend/app/scanners/gcp.py:160-260` (billing export normalization)
- `backend/app/scanners/azure.py:75, 491-672` (Cost Management API convert param)
- `backend/app/api/routes.py:1607-1644, 1527, 3377` (response shape: add currency field)
- `src/lib/dashboard/data.ts:506-529` (kill INR fallback)
- `src/app/dashboard/multicloud/page.tsx:144` (use response currency, not hard-coded)
- `src/components/dashboard/total-bill-experience.tsx` — `toDisplayTotalBillData` simplified (no per-provider currency switch)

**Tests:**
- Unit: GCP scanner converts INR billing rows to USD correctly using row-level rate.
- Unit: Azure scanner returns USD when API responds with native USD.
- Integration: a tenant with one AWS + one GCP integration produces a `total_spend` that equals `sum(per_provider_spend)` within 0.5%.
- Integration: response payloads include `currency: "USD"` on every endpoint above.
- Frontend: `multicloud/page.tsx` renders GCP rows at the same INR scale as AWS rows (no 83× difference).

**Acceptance:**
- Currency consistency metric (Story 0.1) passes on every staging tenant.
- No mixed-currency aggregates anywhere.

**Rollback:** Per-feature-flag. Old code paths preserved for one release.

**Effort:** 1.5 days.

---

### Story 1.4 — `cost_source` UI distinction

**Symptom addressed:** UI shows synthetic catalog list prices indistinguishable from real billing data (Root cause #1).

**Prerequisite:** Story 0.3 (Policy B — sidechannel — recommended).

**Approach:**
- Backend (Policy B): `_apply_catalog_estimates_for_scan` (`routes.py:56`) writes to `catalog_cost_estimate` field, NOT `cost`. `cost` stays as scanner-derived value (real or 0). The aggregator (`/totalbill`, `/stats`) emits both numbers so frontend can choose how to display.
- Frontend resource list: any row where `cost_source ∈ {catalog_estimate, service_estimate, billing_unavailable}` renders an "Est." badge in muted indigo, with hover tooltip explaining the source.
- Total Bill page: hero KPI shows real `total_spend` prominently and `total_estimated_addendum` as a smaller secondary number ("+ ₹X estimated").
- Resource table on `/dashboard/resources` (and any per-resource view): cost column shows real value; if zero AND `catalog_cost_estimate > 0`, show "₹X (est.)" in muted color with the same tooltip.
- Integration card: badge "Pricing source: Live billing API" / "Pricing source: List price estimates — improve permissions" (links to docs in Story 2.4).

**Files:**
- `backend/app/api/routes.py:56-86` (sidechannel writeback)
- `backend/app/core/provider_pricing_catalog.py:175-260` (`apply_catalog_estimates`)
- `backend/app/api/routes.py:1589-1722` (`/totalbill` — emit both fields)
- `backend/app/api/routes.py:1508-1559` (`/resources`, `/stats` — emit both)
- `src/components/dashboard/total-bill-experience.tsx` — render the addendum
- `src/components/dashboard/resources-view.tsx` — Est. badges
- New: `src/components/ui/cost-source-badge.tsx` — reusable badge component
- New: `docs/help/pricing-sources.md` (linked from the badge tooltip)

**Tests:**
- Unit: `_apply_catalog_estimates_for_scan` does not modify `cost`; only writes `catalog_cost_estimate`.
- Integration: `/totalbill` response includes `total_spend_actual` and `total_spend_estimated`.
- E2E: Resource table renders "Est." badge for resources with `cost_source = catalog_estimate`.
- E2E: Total Bill hero KPI does not include estimated addendum in the main number.

**Acceptance:**
- Zero "fake real prices" — every monetary value is either billing-derived or visibly an estimate.
- Help doc accessible from every Est. badge tooltip.

**Rollback:** Flag `CATALOG_SIDECHANNEL_ENABLED=false` reverts to overwriting `cost`.

**Effort:** 1.5 days (split across BE + FE).

---

### Story 1.5 — Multicloud client page refresh on scan_complete

**Symptom addressed:** Client-rendered pages don't re-fetch after rescan (Root cause #3).

**Approach:**
- `ScanProvider` (`src/components/dashboard/scan-provider.tsx`) gains a new context value `lastScanCompletedAt: number | null` — a timestamp set when WS receives `scan_complete`.
- Every client-fetched page that today depends on scan-derived data adds `lastScanCompletedAt` to its `useEffect` dependency array.
- Specific pages to update: `/dashboard/multicloud`, `/dashboard/arbitrage` (Bill Scan), `/dashboard/gpu`, `/dashboard/forecast` if it client-fetches.
- Server-rendered pages (`/dashboard`, `/dashboard/totalbill`) already work via `router.refresh()` — verified, no change.
- Add a small "Refreshed Xs ago" indicator near each page's title, sourced from `lastScanCompletedAt`.

**Files:**
- `src/components/dashboard/scan-provider.tsx:234-260` (add `lastScanCompletedAt`)
- `src/app/dashboard/multicloud/page.tsx:389` (key useEffect on it)
- `src/app/dashboard/arbitrage/page.tsx:111-235`
- `src/app/dashboard/gpu/page.tsx`
- New: `src/components/dashboard/last-refreshed-indicator.tsx`

**Tests:**
- E2E: Trigger scan → wait for completion → verify multicloud page re-fetches without manual reload (within 5s).
- Unit: `ScanProvider` updates `lastScanCompletedAt` on WS `scan_complete`.
- Unit: `lastScanCompletedAt` updates on the polling fallback path too.

**Acceptance:**
- Frontend refresh latency p95 ≤ 5 seconds (Story 0.1 metric improves).
- Indicator visible on every fetched page.

**Rollback:** Flag `MULTICLOUD_AUTO_REFRESH_ENABLED=false`.

**Effort:** 0.5 day.

---

## 5. Phase 2 — Correctness & Idempotency (Days 5–9)

Five P1 stories. After Phase 1 the user-visible bleeding stops; Phase 2 fixes the underlying invariants so the system is correct by construction, not by patch.

---

### Story 2.1 — Stable AWS `cloud_resource_id`

**What:** Eliminate the 14-key fallback chain and the name-region last resort.

**Approach:**
- New helper `aws_resource_identity(resource: dict) -> str | None` in `aws.py`:
  - Priority 1: `arn` (covers EC2, RDS, EBS, ELB, S3, Lambda, etc.)
  - Priority 2: canonical resource ID (`InstanceId` for EC2, `VolumeId` for EBS, `DBInstanceIdentifier` for RDS, etc.) — combined with account_id + region prefix to ensure global uniqueness.
  - Priority 3: emit a structured warning log and return `None`. Caller skips the resource.
- All call sites (`aws.py:670`, `aws.py:1911-1977`, the explicit-cost-fallback path) use this single helper.

**Files:**
- `backend/app/scanners/aws.py:670, 1911-1977` (and any other call site touching cloud_resource_id)
- New tests: `backend/tests/test_aws_resource_identity.py`

**Tests:**
- Unit: same physical EC2 produces the same identity from both the primary discovery path and the explicit-cost fallback path.
- Unit: identity is stable across renames (since name is no longer in the fallback).
- Unit: identity is unique across regions and accounts.

**Acceptance:**
- A two-rescan cycle on the same AWS tenant produces zero new rows in the resources collection (after dedupe).
- The "name-region" fallback never fires (assertion in code).

**Effort:** 0.75 day.

---

### Story 2.2 — Atomic upsert + delete via `bulk_write`

**What:** Eliminate the race window between `bulk_upsert_resources` and `delete_resources_for_integration`.

**Approach:**
- New method `db.replace_integration_resources(user_id, integration_id, batch_id, resources)`:
  - Builds a single `bulk_write` operation list:
    1. `UpdateOne` (upsert) for each new resource, filtered by `(user_id, integration_id, cloud_resource_id)`.
    2. `DeleteMany({user_id, integration_id, scan_batch_id: {$ne: batch_id}})`.
  - Submits with `ordered=True` so deletes only run after all upserts succeed.
- Replace both call sites: `routes.py:2221-2232` (AWS/GCP) and `routes.py:1863-1870` (Azure).
- The AI re-upsert path at `routes.py:2280` runs its own `replace_integration_resources` to evict stale-tagged stragglers.

**Files:**
- `backend/app/db/mongo_client.py:526-615, 704-718` (new method)
- `backend/app/api/routes.py:1863-1870, 2221-2232, 2276-2281`

**Tests:**
- Unit: `replace_integration_resources` rolls atomically (a deliberate failure on any update aborts the batch — no partial deletes).
- Integration: a scan that upserts N resources and is interrupted before the delete leaves N+old_count rows; the next successful scan converges to N.
- Integration: AI re-upsert path correctly evicts stragglers.

**Acceptance:**
- Single-step write: confirmed via Mongo profiler showing one `bulk_write` per integration per scan.
- No orphan rows after partial failure (verified by injection of failure).

**Effort:** 1 day.

---

### Story 2.3 — Restore service-level cost distribution (AWS)

**What:** Re-enable `_distribute_service_costs` (currently commented out at `aws.py:405-408`) so resources without per-resource Cost Explorer data still get a defensible cost number.

**Approach:**
- Uncomment and refactor `_distribute_service_costs`. Gate behind `cost_source = billing_unavailable` only.
- New `cost_source` value: `"service_estimate"`. UI treats it the same as `catalog_estimate` (Story 1.4) — labeled, not summed into "real spend."
- Distribute the per-service Cost Explorer total proportionally across resources of that service (weighted by capacity, age, or simple uniform — start with uniform, log the assumption).
- Skip if Cost Explorer API also failed (no service-level data to distribute).

**Files:**
- `backend/app/scanners/aws.py:405-408, 709-810` (restore + refactor)

**Tests:**
- Unit: distribution sums to the original Cost Explorer service total within 0.1%.
- Unit: resources already with `cost_source = actual` are left untouched.
- Unit: when Cost Explorer service-level fails, distribution is skipped without error.

**Acceptance:**
- Zero-cost ratio on AWS resources drops by >50% on a tenant where Cost Explorer service-level is available but resource-level is not.
- All distributed values labeled `service_estimate` in the UI.

**Effort:** 1 day.

---

### Story 2.4 — Surface scanner permission failures to the user

**What:** When a scan falls back to estimates because of an IAM/RBAC gap, show the user *which* permission is missing and how to fix it.

**Approach:**
- Each scanner already records granular status fields internally (e.g., `resource_level_granularity_not_enabled`, `cost_management_role_missing`, `billing_export_unavailable`).
- Promote these into a structured `scan_diagnostics` block on the scan result and persist on the integration document.
- New API: `GET /integrations/{id}/diagnostics` returns the latest diagnostics with a human-readable message and a docs URL per failure code.
- Frontend integration card: small "Pricing health" indicator (green/yellow/red dot). Click → modal with the diagnostics list and direct fix links.
- New docs: `docs/help/aws-cost-explorer-setup.md`, `docs/help/azure-cost-management-setup.md`, `docs/help/gcp-billing-export-setup.md`.

**Files:**
- `backend/app/scanners/aws.py, azure.py, gcp.py` — populate `scan_diagnostics`
- `backend/app/api/routes.py` — new endpoint
- `backend/app/db/mongo_client.py` — `get_integration_diagnostics`
- `src/components/dashboard/settings-view.tsx` — Pricing health indicator
- New: `src/components/dashboard/integration-diagnostics-modal.tsx`
- New: `docs/help/*.md` (3 files)

**Tests:**
- Integration: scan with a known-bad permission produces the expected diagnostic code.
- E2E: integration card shows red dot; clicking opens modal with the right docs link.

**Acceptance:**
- Every scanner fallback path emits a diagnostic code.
- Help docs cover all known failure codes.

**Effort:** 1.5 days (1 BE + 0.5 FE + docs).

---

### Story 2.5 — `run_scan` lifecycle hardening

**What:** Wrap the entire `run_scan` body in a try/finally that always cleans up on partial failure.

**Approach:**
- Outer try/finally guarantees:
  - `release_scan_lock` (Story 1.1) is always called.
  - If a partial scan persisted resources but failed before `replace_integration_resources` (Story 2.2), the finally block runs `delete_resources_for_integration(exclude_batch_id=batch_id)` defensively.
  - `complete_scan_history` is called with `status: "failed"` and the error message captured.
- Audit log entry written on both success and failure paths.

**Files:**
- `backend/app/api/routes.py:1763-2300` (the entire `run_scan` body)

**Tests:**
- Unit: simulated raise after upsert but before delete → next scan converges cleanly.
- Unit: simulated raise during AI verification → resources persisted at deterministic step still readable.
- Integration: scan timeout (>5 min) → lock released, scan_history shows failed.

**Acceptance:**
- No path through `run_scan` can leave a held lock or orphan resources.
- Audit log captures every scan outcome.

**Effort:** 0.75 day.

---

## 6. Phase 3 — Resilience & Polish (Days 10–14)

Five P2 stories. Quality-of-life and broader correctness.

---

### Story 3.1 — Cache invalidation pattern

**What:** Add a single helper that invalidates all relevant Redis caches for a user, called on `scan_complete`.

**Approach:**
- New `app/core/cache.py:invalidate_user_caches(user_id)` — does `SCAN cache:*:{user_id}:*` + `DEL` for each match.
- Called from `complete_scan_history` (or scan-completion handler).
- Audit current `@cache_response` decorators (today: only `/gpu/summary` at `routes.py:3351`). Confirm key pattern matches the SCAN.

**Files:**
- `backend/app/core/cache.py:80` (add invalidate_user_caches)
- `backend/app/api/routes.py` (call from scan completion)
- `backend/app/api/websocket.py` (call from scan_complete WS broadcast)

**Tests:**
- Unit: SCAN+DEL with mock Redis covers all matching keys.
- Integration: rescan invalidates `/gpu/summary` cache; subsequent fetch returns fresh data.

**Acceptance:**
- Post-scan stale cache window ≤ 1 second.
- Pattern can be reused for new `@cache_response` endpoints without code changes.

**Effort:** 0.5 day.

---

### Story 3.2 — Azure FX live conversion

**What:** Stop trusting the hard-coded `CURRENCY_TO_USD` table.

**Approach:**
- Use Cost Management API's `Convert: USD` query parameter — Azure server-side converts.
- Remove `CURRENCY_TO_USD` constant.
- For non-USD billing currencies that the API rejects, fall back to a daily-cached FX rate from a free provider (e.g., `exchangerate.host`) — store in Redis with 24h TTL.

**Files:**
- `backend/app/scanners/azure.py:75, 88` (remove static table)
- `backend/app/scanners/azure.py:491` (`_fetch_real_costs` — use convert param)
- New: `backend/app/core/fx_rates.py` (fallback FX provider)

**Tests:**
- Unit: Azure scanner converts via API parameter when supported.
- Unit: Falls back to cached FX rate when API doesn't convert.

**Acceptance:**
- No magic constants for FX in the codebase (greppable).

**Effort:** 0.5 day.

---

### Story 3.3 — Expanded catalog coverage

**What:** Extend `provider_pricing_catalog.py` to cover RDS/SQL, ELB/AppGw/LB, NAT, EIP/PublicIP, Storage Accounts/Buckets, GKE/EKS/AKS control-plane, Lambda/Functions/Cloud Run baselines.

**Approach:**
- For each new resource type:
  1. Write a small `_estimate_*` function that reads `metadata` (size, tier, region) and returns a `CatalogEstimate(currency="USD")`.
  2. Add to the dispatcher in `apply_catalog_estimates`.
- Sources: provider public list-price docs + AWS Pricing API for sanity check.

**Files:**
- `backend/app/core/provider_pricing_catalog.py:465-650` (extend)

**Tests:**
- Unit per resource type: known size + tier + region → expected USD list price within ±5% of provider documentation.

**Acceptance:**
- Catalog coverage % (count of unique service_types covered / total observed) ≥ 80%.

**Effort:** 1.5 days (lots of small additions).

---

### Story 3.4 — Detect role-only AWS credentials

**What:** Today `routes.py:1782-1804` only aborts on missing access keys. Role-ARN-only scans silently fall through to `cost_source = billing_unavailable`.

**Approach:**
- If `role_arn` is set and access keys are missing, attempt `sts:AssumeRole` with a default external ID; on success, use the assumed credentials for the rest of the scan.
- If assume fails, raise a clear diagnostic via Story 2.4's mechanism.
- Document the trust-policy required in `docs/help/aws-role-trust-policy.md`.

**Files:**
- `backend/app/api/routes.py:1782-1812` (role-only branch)
- `backend/app/scanners/aws.py:_authenticate` (already supports STS — verify wiring)

**Tests:**
- Integration: role-only credential scan succeeds end-to-end.
- Integration: role-only with bad trust policy emits the correct diagnostic.

**Acceptance:**
- Role-only AWS integrations produce real costs (not estimates).

**Effort:** 0.5 day.

---

### Story 3.5 — Strict `to_db_resources`

**What:** Refuse to silently accept empty `cloud_resource_id` from any scanner.

**Approach:**
- `to_db_resources` (per-scanner) asserts `cloud_resource_id` non-empty. Raise typed exception or skip with a structured warning.
- Removes the `f"gcp-{name}-{region}"` and `f"aws-{name}-{region}"` last-resort fallbacks (already partially done in Story 2.1; this finishes the pattern in GCP and Azure).

**Files:**
- `backend/app/scanners/aws.py:1932`
- `backend/app/scanners/gcp.py:1191`
- `backend/app/scanners/azure.py:932 et al.`

**Tests:**
- Unit per scanner: missing identity → resource skipped + warning logged + Prometheus counter incremented.

**Acceptance:**
- The `aws-{name}-{region}` and `gcp-{name}-{region}` fallback strings are absent from the codebase (greppable).

**Effort:** 0.5 day.

---

## 7. Migration Plan

A real production deployment cannot just push these changes; existing data needs cleanup.

### M1 — Duplicate cleanup (run before Story 1.2 index swap)
- Script: `backend/migrations/2026_05_dedupe_resources.py`
- For each integration, calls existing `dedupe_resources_for_integration`.
- Logs total removed; produces a CSV report for the engineering channel.

### M2 — Currency back-fill (run after Story 1.3 ships)
- Script: `backend/migrations/2026_05_normalize_currency.py`
- Re-reads `dashboard_stats` per integration, converts INR-stored GCP rows to USD using the historical FX rate at scan time (or current rate as best-effort).
- Idempotent (writes a `currency_normalized: true` flag).

### M3 — `cost_source` back-population (after Story 1.4)
- Script: `backend/migrations/2026_05_backfill_cost_source.py`
- Existing rows missing `cost_source` get a default value `"unknown"`.
- Existing rows where `cost > 0` and the integration has Cost Explorer enabled get `cost_source = "actual"` (best-effort).

### M4 — Index swap (Story 1.2)
- See §4 Story 1.2 step-by-step. Window: 30-min maintenance during off-peak.

---

## 8. Testing Strategy

| Layer | Tooling | Coverage target |
|---|---|---|
| Unit (Python) | `pytest`, `pytest-asyncio`, `mongomock` | New code: 80% line coverage; existing touched code: maintain or improve |
| Unit (TS) | `tsx --test`, `vitest` if needed | All new helpers and components |
| Integration (BE) | `pytest` with a dockerized MongoDB and mocked AWS/Azure/GCP SDKs | Every story's "Integration test" requirement |
| Contract tests | Existing `*-contract.test.ts` files | Keep passing throughout |
| E2E | Playwright (manual until automated infra is ready) | Top-3 user flows: Settings→Connect→Scan→Dashboard, Rescan idempotency, Multicloud auto-refresh |
| Load | `locust` script: 100 concurrent rescans on 50 integrations | Lock holds; no orphan rows; p95 scan time < 90s |
| Manual QA scripts | New `docs/qa/scanning-pipeline-qa-runbook.md` | Cover all 4 providers + all 3 phases of fixes |

**Test data:**
- Staging fixtures with at least one tenant per provider, with both fully-permissioned and intentionally-degraded credentials.
- Synthetic fixture for "fully zero" scan (no permissions) — must produce sane UI.

---

## 9. Observability Dashboard

A new Grafana board: `CloudFinOps – Scanning Pipeline Health`.

**Tiles:**
1. **Scan throughput** — `scan.completed` per minute, broken down by provider and outcome.
2. **Scan duration p50/p95/p99** — by provider.
3. **Lock rejection rate** — `scan.lock.rejected` per minute (should be near zero except during user double-clicks).
4. **Duplicate count** — query `db.resources.aggregate([...group by (user, integration, cloud_resource_id)...]).count_gt_1` — must be 0.
5. **Cost source distribution** — pie chart of resources by `cost_source`. Watch the % of `actual` go up over time.
6. **Zero-cost ratio** — by provider. Should drop after Story 2.3 ships.
7. **Frontend refresh latency** — from `frontend.refresh.triggered` event timestamps.
8. **Cache hit/miss rate** — for `@cache_response` endpoints.
9. **Currency drift** — `total_spend` vs `sum(provider.monthly_spend)` ratio. Should be 1.000 ± 0.005.

**Alerts:**
- Duplicate count > 0 → page on-call.
- Lock rejection rate > 5/min sustained for 10 min → investigate (might be runaway client).
- Currency drift > 0.5% → page on-call (currency normalization broken).

---

## 10. Rollback Plan

Each story has a feature flag (Story 0.4). Rollback procedure per phase:

| Phase | Rollback action | Time to revert |
|---|---|---|
| Phase 1 | Flip 5 flags off; redeploy | < 10 min |
| Phase 2 | Flip 5 flags off; redeploy. Story 2.1 needs careful — the new identity helper is read by Story 2.2's atomic write, so revert in reverse order. | < 15 min |
| Phase 3 | Flip flags off | < 10 min |
| Migration scripts | Each script writes a flag (`*_normalized: true`); reverse migrations defined in same files. | 30 min per migration |

**Index rollback (Story 1.2)** is the most disruptive: drop new index, recreate old partial index. Maintenance window required (~30 min in production).

---

## 11. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Migration M1 (dedupe) takes longer than expected on large tenants | Medium | High | Pre-run on staging clone; size-based ETA per tenant |
| Story 1.3 currency normalization breaks one integration's scan | Medium | High | Per-flag rollback; integration-level feature flag override |
| Mongo lock collection becomes hot under load | Low | Medium | Lock TTL + cron cleanup; index on `integration_id` |
| AI verification step still produces stragglers after Story 2.2 | Medium | Medium | Story 2.5 final defensive cleanup |
| Catalog estimate sidechannel field forgotten by some BE/FE consumers | Medium | Medium | Comprehensive grep + add ESLint/pylint rule for `cost` reads to prefer `cost_source`-aware helpers |
| Free FX provider in Story 3.2 rate-limits us | Low | Low | 24h cache + secondary provider |
| User confused by "Est." badges everywhere on a brand-new integration | Medium | Low | First-run onboarding tip; help doc linked from badge |

---

## 12. Definition of Done (per story)

A story is **done** when ALL of the following are true:
- [ ] Code merged to `main` behind feature flag.
- [ ] Unit tests added and passing in CI.
- [ ] Integration tests added and passing.
- [ ] Manual QA runbook step verified by QA.
- [ ] Observability events visible in Grafana.
- [ ] Rollback procedure documented and tested on staging.
- [ ] Help docs updated (if user-facing).
- [ ] Acceptance criteria verified by the story's reviewer.
- [ ] Feature flag rollout plan posted to engineering channel.

A **phase** is done when:
- [ ] All stories in the phase meet DoD.
- [ ] Phase 0.1 baseline metrics re-captured; deltas published.
- [ ] On-call runbook updated.
- [ ] Stakeholder demo to Product/Tech-lead.

---

## 13. Communication Plan

| Audience | What | When | Channel |
|---|---|---|---|
| Engineering | Plan review & approval | Day 0 | Eng review meeting |
| QA | Runbook walkthrough | Day 1 | Dedicated session |
| Product | Phase 1 end-of-day status | Days 2-4 | Async update |
| Customer Success | Phase 2 user-visible changes (Est. badges, integration diagnostics) | Day 5 | Email + sync |
| Customers (in-app) | Banner: "Improved pricing accuracy — see your integrations for details" | Day 9 (after Phase 2 ramp) | In-app notification |
| Internal all-hands | Phase 3 wrap & metrics | Day 14 | All-hands slot |

---

## 14. Appendix A — Phased Effort Summary

| Phase | Stories | Engineer-days | Calendar days |
|---|---|---|---|
| Phase 0 | 0.1–0.5 | 2.0 | 1 (parallel) |
| Phase 1 | 1.1–1.5 | 5.5 | 3 (parallel BE+FE) |
| Phase 2 | 2.1–2.5 | 4.75 | 4 (1 senior BE) |
| Phase 3 | 3.1–3.5 | 3.5 | 2 (parallel) |
| **Total** | **15 stories + 5 prep** | **15.75 ed** | **10 calendar days** |

Assumes 1 senior BE + 1 senior FE. Add 0.5 day buffer per phase for code review.

---

## 15. Appendix B — File Reference Index

Files most affected by this plan (sorted by churn):

| File | Stories |
|---|---|
| `backend/app/api/routes.py` | 0.5, 1.1, 1.2, 1.3, 1.4, 2.2, 2.4, 2.5, 3.1, 3.4 |
| `backend/app/db/mongo_client.py` | 1.1, 1.2, 2.2, 2.4 |
| `backend/app/scanners/aws.py` | 1.3, 2.1, 2.3, 3.4, 3.5 |
| `backend/app/scanners/azure.py` | 1.3, 2.4, 3.2, 3.5 |
| `backend/app/scanners/gcp.py` | 1.3, 2.4, 3.5 |
| `backend/app/core/cache.py` | 0.5, 3.1 |
| `backend/app/core/provider_pricing_catalog.py` | 1.4, 3.3 |
| `src/components/dashboard/scan-provider.tsx` | 1.5 |
| `src/app/dashboard/multicloud/page.tsx` | 1.3, 1.5 |
| `src/lib/dashboard/data.ts` | 1.3 |
| `src/components/dashboard/total-bill-experience.tsx` | 1.3, 1.4 |

New files created:
- `backend/app/core/scan_lock.py`
- `backend/app/core/fx_rates.py`
- `backend/app/core/feature_flags.py`
- `backend/migrations/2026_05_resources_unique_index.py`
- `backend/migrations/2026_05_dedupe_resources.py`
- `backend/migrations/2026_05_normalize_currency.py`
- `backend/migrations/2026_05_backfill_cost_source.py`
- `src/components/ui/cost-source-badge.tsx`
- `src/components/dashboard/last-refreshed-indicator.tsx`
- `src/components/dashboard/integration-diagnostics-modal.tsx`
- `docs/help/{aws-cost-explorer-setup,azure-cost-management-setup,gcp-billing-export-setup,aws-role-trust-policy,pricing-sources}.md`
- `docs/engineering/adr-001-canonical-currency-usd.md`
- `docs/engineering/adr-002-catalog-estimate-policy.md`
- `docs/engineering/scanning-pipeline-baseline-2026-05-04.md`
- `docs/qa/scanning-pipeline-qa-runbook.md`

---

## 16. Appendix C — Open Questions for Reviewers

1. **Currency choice** — confirm USD as canonical (Story 0.2). Alternative: INR (most users are India-based per current data).
2. **Catalog policy** — confirm Policy B (sidechannel) vs alternatives.
3. **Lock backend** — module-level asyncio lock vs Mongo `findOneAndUpdate`-based lock. The plan uses the latter for cross-process safety; if we ever go single-process this can simplify.
4. **AI verification path** — should the AI verification step run before or after the atomic `replace_integration_resources`? Current proposal: replace runs first (deterministic), AI re-upserts second, then a defensive cleanup. Open to discussion.
5. **Backfill aggressiveness** — Migration M2 (currency back-fill) — do we use historical FX rates or current rate for old data? Current rate is faster; historical is more accurate but adds 1-2 days.

---

## End of plan

For questions or proposed amendments, file an issue tagged `scanning-pipeline-remediation` or add a comment in this doc's PR.
