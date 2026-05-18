# CloudFinOps Release 1 Spec
**Forecasting, Budget Copilot, and Executive Pack**

Status: Draft  
Date: March 15, 2026  
Audience: Product, engineering, design, and GTM

## 1. Summary
Release 1 turns CloudFinOps from a scan-and-report product into a read-only financial decision layer for cloud leadership. The release introduces deterministic forecasting, budget tracking, and finance-ready reporting without asking customers for write access or operational authority over their infrastructure.

Release 1 must be:
- read-only
- deterministic
- compatible with both live cloud integrations and billing-export workflows
- useful to CTO, finance, and engineering leadership on day one

## 2. Why This Release
Current CloudFinOps already has the right foundation:
- dashboard summary metrics
- daily spend history storage
- budget fields on integrations
- report generation UI
- scheduled workers
- Slack, WhatsApp, and email delivery plumbing

What is missing is a trustworthy finance product surface. Today, budget and report data are fragmented across `dashboard_stats`, `daily_spend_history`, AI-generated governance payloads, and notification-shaped report records. Release 1 consolidates those into a clean, read-only finance layer.

## 3. Product Positioning
CloudFinOps Release 1 is:
- a multi-cloud budget and forecast copilot
- an executive reporting layer for cloud spend
- a planning tool for customers that want visibility before they trust automation

CloudFinOps Release 1 is not:
- an auto-remediation product
- a cloud operations agent
- a purchasing agent for commitments
- a write-access control plane

## 4. Goals
- Give every user a trustworthy month-end spend forecast.
- Show budget risk at both portfolio and per-account level.
- Surface simple, explainable "what changed" drivers for spend movement.
- Generate board-ready and finance-ready reports inside the app and on schedule.
- Keep the release usable for low-trust customers who only allow read-only access or bill ingestion.

## 5. Non-Goals
- No delete, stop, resize, or remediation execution.
- No autonomous commitment purchases.
- No chargeback engine.
- No dependency on AI-generated budget or forecast outputs.
- No new customer permission ask beyond existing read-only cloud access, billing exports, and optional delivery channels.

## 6. Target Users
- Founder / CTO: wants forecasted month-end cloud risk and clear top drivers.
- Finance lead / CFO: wants monthly budget status, variance, and board-ready summaries.
- Engineering manager / platform lead: wants provider and account visibility without handing over operational control.

## 7. Customer Inputs Required
- Existing live AWS/Azure/GCP integrations or uploaded / automated billing exports.
- Optional per-account budget limits.
- Optional portfolio budget limit.
- Optional Slack webhook and WhatsApp number for alerts.
- Optional report recipients and cadence.

No write permissions are required.

## 8. Current Foundations To Reuse

### Reuse directly
- `src/app/dashboard/page.tsx`
- `src/components/dashboard/dashboard-sections-client.tsx`
- `src/components/dashboard/reports-view.tsx`
- `src/components/dashboard/settings-view.tsx`
- `backend/app/api/routes.py`
- `backend/app/workers/anomaly_worker.py`
- `backend/app/workers/report_worker.py`
- `backend/app/db/MongoDB.py`

### Reuse with caution
- `src/components/dashboard/governance-view.tsx`
  Reason: visual patterns are reusable, but the current budget values come from AI-shaped governance payloads.
- `backend/app/ai/mcp_server.py:get_ml_cost_forecast(...)`
  Reason: forecasting logic is reusable, but it must be exposed through real product APIs and wrapped in deterministic contracts.

### Do not treat as source of truth
- `getGovernanceAnalysis()` budget values
- `agent_notifications` as the long-term report store
- current `/api/stats` for portfolio-level budget math
- current `/api/spend-history` output when `integration_id` is omitted

## 9. Release 1 Scope

### 9.1 Dashboard overview additions
Keep `/dashboard` as the top-level summary page.

Add:
- forecasted month-end spend card
- budget status card
- overrun risk badge
- top provider variance snippet

Do not turn the overview page into the full finance workspace. It should remain the summary layer.

### 9.2 New finance page
Add a new route:
- `src/app/dashboard/forecast/page.tsx`

This page is the main Budget Copilot surface.

Sections:
- forecast summary cards
- actual MTD vs forecasted EOM chart
- portfolio budget status
- per-provider / per-account budget table
- top spend-change drivers
- empty state for insufficient history

Future panels such as scenarios and commitment planning are explicitly out of scope for Release 1.

### 9.3 Reports center upgrade
Keep `/dashboard/reports`, but reposition it as the Executive / Finance Pack.

Release 1 report templates:
- Monthly Executive Summary
- Budget Variance Report
- Provider Spend Summary
- Board Pack

Reports must be:
- viewable in-app
- persistently listed
- downloadable
- optionally deliverable by email

### 9.4 Settings extension
Keep `/dashboard/settings` and extend the current cloud account settings.

Release 1 additions:
- portfolio budget limit
- default report recipients
- report cadence
- alert thresholds

Do not hide Release 1 in the current placeholder settings tabs.

## 10. User Flows

### Flow A: First budget setup
1. User connects one or more accounts or billing exports.
2. User opens Settings.
3. User sets per-account budget limits.
4. User optionally sets a portfolio budget.
5. User optionally configures Slack, WhatsApp, and report recipients.
6. User lands on Forecast and immediately sees current MTD, forecasted EOM, and risk status.

### Flow B: Ongoing finance review
1. User opens `/dashboard/forecast`.
2. User sees actual MTD spend, projected EOM spend, and budget variance.
3. User inspects top drivers by provider, service, or account.
4. User exports a report or sends it to stakeholders.

### Flow C: Scheduled executive reporting
1. User enables weekly or monthly report delivery.
2. Backend generates a persisted report record.
3. Email is sent through Resend.
4. The same report remains available in-app for later viewing and download.

## 11. Functional Requirements

### 11.1 Forecasting
- Forecast must be deterministic.
- Forecast must work from `daily_spend_history`.
- If at least 14 days of history exist, use Holt-Winters style smoothing.
- If less than 14 days but at least 5 days exist, use a simpler moving-average style fallback.
- If fewer than 5 days exist, return a clear insufficient-history response.
- Forecast must support:
  - portfolio scope
  - integration scope
  - provider/account breakdown

### 11.2 Budget Copilot
- Compare forecasted EOM spend against configured budget limits.
- Support both:
  - per-integration budgets
  - one optional portfolio budget
- If no portfolio budget is set, portfolio status falls back to the sum of active integration budgets.
- Persist budget events when state changes:
  - approaching budget
  - forecasted over budget
  - over budget
  - recovered

### 11.3 Executive Pack
- Manual report generation from the UI.
- Scheduled report generation via worker.
- In-app report history.
- Report metadata persistence.
- Download and email delivery.

### 11.4 Explainability
- Every forecast response must include:
  - method used
  - as-of timestamp
  - days of history used
  - trend direction
- Every budget response must include:
  - budget source
  - current actual MTD
  - projected EOM
  - variance amount
  - variance percent

## 12. Backend API Spec

### 12.1 `GET /api/finance/forecast`
Purpose: return deterministic forecast and budget summary.

Query params:
- `scope=portfolio|integration`
- `integration_id` when `scope=integration`
- `days` default `30`

Response:

```json
{
  "scope": "portfolio",
  "as_of": "2026-03-15T10:00:00Z",
  "currency": "USD",
  "history_days_used": 30,
  "forecast_method": "holt_winters",
  "forecast_stable": true,
  "actual_mtd_spend": 12450.12,
  "forecast_eom_spend": 18780.55,
  "budget_limit": 17000.00,
  "variance_amount": 1780.55,
  "variance_pct": 10.47,
  "status": "forecasted_over_budget",
  "trend": "increasing",
  "drivers": [
    {
      "dimension": "provider",
      "key": "AWS",
      "delta_amount": 920.14
    }
  ]
}
```

### 12.2 `GET /api/finance/forecast-history`
Purpose: return actual daily spend and stored forecast snapshots for charting and variance review.

Query params:
- `scope=portfolio|integration`
- `integration_id` when needed
- `days` default `90`

### 12.3 `GET /api/finance/budget-events`
Purpose: return durable budget risk and status events for UI and reporting.

Query params:
- `status=open|closed|all`
- `scope=portfolio|integration|all`

### 12.4 `GET /api/finance/settings`
Purpose: return portfolio-level finance preferences.

### 12.5 `PUT /api/finance/settings`
Purpose: update portfolio-level budget and reporting preferences.

Request:

```json
{
  "portfolio_budget_limit": 17000,
  "report_recipients": ["finance@company.com", "cto@company.com"],
  "report_cadence": "weekly",
  "alert_thresholds": {
    "warning_pct": 80,
    "critical_pct": 100,
    "forecast_pct": 95
  }
}
```

### 12.6 Existing route retained
- `PUT /api/integrations/{integration_id}/settings`

Release 1 keeps this route for per-integration budget and delivery fields, but audit logging must redact webhook UTenant Isolation and phone numbers before persistence.

### 12.7 Reports API
Add a real reports API instead of storing report records in `agent_notifications`.

Endpoints:
- `GET /api/reports`
- `POST /api/reports`
- `GET /api/reports/{report_id}`
- `POST /api/reports/{report_id}/send`

## 13. Data Model

### 13.1 Reuse existing collections
- `cloud_integrations`
- `dashboard_stats`
- `daily_spend_history`

### 13.2 Add `finance_settings`
Purpose: user-level finance preferences.

Fields:
- `id`
- `user_id`
- `portfolio_budget_limit`
- `currency`
- `report_recipients`
- `report_cadence`
- `alert_thresholds`
- `created_at`
- `updated_at`

### 13.3 Add `forecast_snapshots`
Purpose: persist daily forecast outputs for variance analysis and reporting.

Fields:
- `id`
- `user_id`
- `scope_type` (`portfolio` or `integration`)
- `integration_id` nullable
- `period_month` (`YYYY-MM`)
- `as_of`
- `currency`
- `history_days_used`
- `forecast_method`
- `forecast_stable`
- `actual_mtd_spend`
- `forecast_eom_spend`
- `budget_limit`
- `variance_amount`
- `variance_pct`
- `status`
- `trend`
- `drivers`
- `created_at`

Indexes:
- `(user_id, scope_type, period_month, as_of desc)`
- `(integration_id, period_month, as_of desc)` sparse

### 13.4 Add `budget_events`
Purpose: durable, user-visible budget state changes.

Fields:
- `id`
- `user_id`
- `scope_type`
- `integration_id` nullable
- `event_type`
- `status`
- `severity`
- `currency`
- `actual_mtd_spend`
- `forecast_eom_spend`
- `budget_limit`
- `variance_amount`
- `variance_pct`
- `message`
- `metadata`
- `first_seen_at`
- `last_seen_at`
- `acknowledged_at` nullable
- `created_at`

### 13.5 Add `reports`
Purpose: durable in-app report records.

Fields:
- `id`
- `user_id`
- `report_type`
- `title`
- `status`
- `period_start`
- `period_end`
- `generated_at`
- `delivery_mode`
- `recipients`
- `summary`
- `data`
- `artifact_path` nullable
- `created_at`

## 14. Data Contract Rules
- Forecast and budget outputs must be deterministic.
- `total_spend` cannot be reused as a universal finance field without normalization.
- Release 1 must introduce explicit semantics:
  - `actual_mtd_spend`
  - `forecast_eom_spend`
  - `budget_limit`
  - `variance_amount`
  - `variance_pct`
  - `currency`
  - `as_of`
- Portfolio queries must aggregate across integrations by date, not return raw rows.
- AI-generated governance data must never be the source of truth for Release 1 budget or forecast screens.

## 15. Backend Implementation Notes

### 15.1 Required normalization work
- Fix multi-integration aggregation for `dashboard_stats`.
- Fix multi-integration aggregation for `daily_spend_history`.
- Persist daily spend history for AWS, GCP, and automated billing sync, not just Azure.
- Normalize provider semantics so budget comparisons are based on comparable MTD or forecast values.

### 15.2 Required security hardening
- Redact Slack webhook UTenant Isolation and phone numbers from audit metadata in integration settings updates.
- Keep all finance routes ownership-checked server-side.
- Keep protected data access through backend APIs and existing authenticated server helpers only.

### 15.3 Report generation rules
- Scheduled reports should create a `reports` record before email dispatch.
- Email delivery failures must not delete the report record.
- In-app reports must be retrievable even if email fails.

## 16. Frontend Implementation Notes

### 16.1 New route
- `src/app/dashboard/forecast/page.tsx`

### 16.2 New components
- `src/components/dashboard/forecast-summary-cards.tsx`
- `src/components/dashboard/forecast-trend-chart.tsx`
- `src/components/dashboard/budget-status-table.tsx`
- `src/components/dashboard/variance-driver-list.tsx`
- `src/components/dashboard/forecast-empty-state.tsx`

### 16.3 Existing components to extend
- dashboard overview KPI surface
- reports view and report generation modal
- settings view for budget and report preferences
- sidebar to add `Forecast`

### 16.4 UX rules
- Forecast page must explain when data is insufficient.
- Reports page must feel finance-oriented, not remediation-oriented.
- Budget status must distinguish:
  - no budget configured
  - under budget
  - approaching budget
  - forecasted over budget
  - over budget

## 17. Rollout Plan

### Phase 1: backend normalization and contracts
- normalize spend semantics
- aggregate spend history correctly
- expose public forecast APIs
- add `finance_settings`, `forecast_snapshots`, `budget_events`, and `reports`
- harden settings audit logging

### Phase 2: Forecast page and dashboard summary
- add `/dashboard/forecast`
- add overview forecast cards
- wire finance settings
- implement empty states and provider/account tables

### Phase 3: Executive Pack
- replace notification-backed report storage with `reports`
- add finance report templates
- persist manual and scheduled reports
- upgrade email delivery to use persisted report records

## 18. Success Criteria
- A user with multiple integrations sees one correct portfolio-level forecast.
- A user with only bill-ingestion data can still use Release 1.
- Forecast outputs do not require AI availability.
- Budget alerts are visible in-app and optionally delivered externally.
- Reports persist in-app and remain downloadable after email delivery.
- Sensitive delivery config is not written into audit logs.

## 19. Manual Verification
1. Connect two integrations with different providers and confirm portfolio forecast aggregates both correctly.
2. Configure one per-account budget and one portfolio budget; verify status precedence and math.
3. Verify insufficient-history state with fewer than 5 days of spend history.
4. Generate each Release 1 report type manually and confirm it appears in-app.
5. Trigger scheduled report generation and confirm both email delivery and persisted in-app record.
6. Confirm Slack webhook UTenant Isolation and phone numbers are redacted in audit logs.
7. Confirm no Release 1 page depends on AI-generated governance data.

## 20. Recommended Build Order
1. Normalize spend semantics and aggregated history.
2. Ship the forecast API and persisted forecast snapshots.
3. Add finance settings and budget events.
4. Build `/dashboard/forecast` and dashboard summary cards.
5. Replace the current report storage contract with a real `reports` model.
6. Upgrade scheduled executive reporting.

This is the smallest Release 1 slice that is commercially useful, technically coherent, and consistent with a low-trust customer relationship.
