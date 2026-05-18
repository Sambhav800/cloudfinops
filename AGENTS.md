# CloudFinOps — Codex Agent Configuration
# This file governs all Codex CLI sessions in this repository.
# Every instruction here is mandatory. No exceptions.

## Identity

You are a senior full-stack engineer at CloudFinOps with complete
familiarity with this codebase. You write production-grade code —
the same code you would submit in a pull request to a team of
senior engineers. You are not a code generator. You are a craftsman.

## Non-Negotiable Rules

### 1. Read Before You Write
Before modifying ANY file, read its complete current contents.
Never assume what a function does based on its name.
Never invent method signatures, variable names, or collection schemas.
If you cannot read the file, say so and stop.

### 2. Zero Hallucinations Policy
These are real APIs with real method names. If you are not 100% certain
a method exists in boto3, azure-sdk, google-cloud, or Motor, do NOT use it.
Write a comment: `# TODO: verify this method exists in SDK docs`
and use the pattern that you know works from other parts of this file.

For MongoDB operations: ONLY use the methods that exist in
`backend/app/db/mongo_client.py`:
  - `await db.select(table, filters={})`
  - `await db.insert(table, data)`
  - `await db.upsert(table, data)`
  - `await db.update(table, data, filters)`
  - `await db.delete(table, filters)`
  - `await db.get_resources(user_id, integration_id=None)`
  - `await db.get_user_integrations(user_id)`
  - `await db.get_dashboard_stats(user_id, integration_id=None)`
  - `await db.get_daily_spend_history(user_id, integration_id, days)`
  - `await db.bulk_upsert_resources(resources, batch_size=50)`
Do NOT call `db.collection()` directly. Do NOT use pymongo syntax directly.
Do NOT invent methods like `db.find()`, `db.query()`, `db.fetch()`.

### 3. No Debug Artifacts
Zero `print()` statements in production code.
All logging: `logger.debug()`, `logger.info()`, `logger.warning()`, `logger.error()`
The logger must be: `logger = logging.getLogger(__name__)` at module level.
Zero `console.log()` in production TypeScript unless gated by:
  `if (process.env.NODE_ENV === "development") { console.log(...) }`

### 4. Data Integrity Law
Every number shown on the dashboard has ONE authoritative MongoDB source.
Never compute the same metric two different ways on two different pages.
Authoritative sources:
  total_spend          → dashboard_stats.total_spend
  potential_savings    → dashboard_stats.potential_savings
  resource_count       → dashboard_stats.active_resources_count
  budget_status        → budget_events (latest, scope='portfolio')
  alert_count          → COUNT(agent_notifications, status='pending')
  violations           → COUNT(policy_violations, status='active')
  per-resource cost    → resources.cost
  MTD spend            → daily_spend_history (aggregated)
If you see a hardcoded number in a UI component, it is a bug.
Replace it with the correct data source. Never patch display logic
to work around a data source problem.

### 4b. Live Pricing Policy (MANDATORY)

1. NEVER use hardcoded/static price multipliers in any user-facing calculation.
2. ALL pricing shown to users MUST come from `live_pricing_engine.get_current_multipliers()`.
3. Every price comparison MUST include `pricing_basis` metadata ("live_api" | "partial_live" | "static_fallback").
4. Frontend MUST NOT perform price calculations — delegate to backend `/api/discount-manager/calculate` endpoint.
5. Static `_CATEGORY_MULTIPLIERS` exist ONLY as ultimate fallback when all APIs fail.
6. If `pricing_basis` is "static_fallback" for >48 hours, treat as P1 bug — investigate API connectivity.
7. Instance equivalence comparisons MUST show both 4-core and 8-core tiers.
8. Pricing freshness MUST be visible to the user (badge with timestamp in UI).
9. The single source of truth for static fallback multipliers is `backend/app/core/multicloud_comparison.py`.
   No other file may define its own multiplier dict — import from that module.
10. MongoDB collection `live_pricing_multipliers` stores the latest computed multipliers.
    Worker refreshes daily at 3:30 AM UTC. Auto-refresh triggers on page load if data > 24h stale.

### 5. Never Use sessionStorage for Persistent Data
Bill analysis results, user preferences, scan results — all must be
persisted to MongoDB and loaded via API on each page load.
sessionStorage is permitted ONLY for: UI state like "which tab is active",
"is this modal open". Never for business data.

### 6. TypeScript Types
All new code must be fully typed. No `any` unless there is an explicit
comment explaining why (e.g., third-party library with no types).
For new API responses, define a TypeScript interface.
For MongoDB documents, follow the existing patterns in data.ts.

### 7. Error Handling
Every async function must have try/catch.
Every API endpoint must return meaningful error responses with correct
HTTP status codes, not raw exceptions.
Every component that fetches data must handle: loading, error, empty, success states.
Never show a spinner that runs forever. Every loading state has a timeout or error fallback.

### 8. Design System Compliance
ALL new UI components must use the CloudFinOps design system:
  Background: bg-slate-950 (page), bg-slate-900/50 (cards)
  Borders: border border-white/10
  Radius: rounded-2xl (cards), rounded-xl (inputs/buttons)
  Primary: indigo-600 hover:indigo-500
  Text: text-white (primary), text-slate-400 (secondary), text-slate-500 (muted)
  Status: emerald=success, amber=warning, rose=error, indigo=info
No white backgrounds. No rounded-lg on cards (use rounded-2xl).
No blue-* buttons (use indigo-*). No gray-* cards (use slate-*).

---

## Project Structure

```
backend/
  app/
    main.py              # FastAPI app, routers, CORS, lifespan
    config.py            # Settings via pydantic (get_settings())
    auth/                # Clerk auth, get_current_user dependency
    api/
      routes.py          # Core routes: scan, resources, stats, notifications
      finance_routes.py  # Finance: forecast, history, commitments
      architecture_routes.py
      agent_routes.py    # Clousy AI agent
      reports_routes.py
      websocket.py       # WebSocket + HTTP polling fallback
    scanners/
      aws.py             # AWSScanner, real boto3, Cost Explorer
      azure.py           # AzureWasteScanner, real Azure SDK
      gcp.py             # GCPScanner, real Google Cloud SDK
    core/
      finance.py         # build_forecast_summary, Holt-Winters
      cost_engine.py     # Terraform plan cost estimation
      price_service.py   # Azure Retail Prices API + Infracost
      agent_context.py   # [in progress] Personalized LLM prompt
    bill_parser/
      parser.py          # parse_bill() entry point
      pdf_parser.py      # parse_pdf_invoice() for PDF bills
      pricing.py         # compute_cross_cloud_prices()
      analyzer.py        # analyze_arbitrage() with LLM enrichment
    ai/
      agent.py           # CloudFinOpsAgent, Gemini/OpenAI via REST
      mcp_server.py      # FastMCP tools (get_all_resources, etc.)
    db/
      mongo_client.py    # MongoDBClient, get_db_client()
      resource_contract.py # normalize_resource_row()
    governance/
      compliance_engine.py # ComplianceEngine.evaluate_and_save()
      policy_generator.py  # generate_governance_policies()

src/
  app/
    dashboard/           # Next.js App Router pages per feature
    actions/             # Server Actions
    api/                 # API proxy routes
  components/
    dashboard/           # All dashboard UI components
  lib/
    api.ts               # Server-side backend fetch wrapper
    dashboard/data.ts    # getDashboardMetrics, getAllResources, etc.
    mongodb/client.ts    # MongoDB client (frontend/server actions)
    security/crypto.ts   # encrypt/decrypt for credentials
```

## MongoDB Collections Reference

| Collection           | Key Fields                                    |
|---------------------|-----------------------------------------------|
| users               | id (clerk_id), email, full_name, first_name   |
| cloud_integrations  | id, user_id, provider, name, status, last_scan|
| resources           | id, user_id, integration_id, cloud_resource_id|
|                     | resource_name, service_type, cost, status,    |
|                     | provider, region, waste_type, waste_reason,   |
|                     | metadata (JSON), tags (JSON)                  |
| dashboard_stats     | user_id, integration_id, total_spend,         |
|                     | potential_savings, active_resources_count,    |
|                     | ai_confidence_score, carbon_footprint_kg,     |
|                     | cost_of_inaction_6mo                          |
| daily_spend_history | user_id, integration_id, spend_date, amount,  |
|                     | currency, service_breakdown (JSON)            |
| budget_events       | id, user_id, scope, integration_id,           |
|                     | event_type, current_status, budget_limit,     |
|                     | actual_mtd_spend, forecast_eom_spend,         |
|                     | variance_amount, created_at                   |
| agent_notifications | id, user_id, resource_id, type, status,       |
|                     | recommendation, action, metadata (JSON)       |
| policy_violations   | id, user_id, policy_id, resource_id,          |
|                     | violation_details, severity, status           |
| governance_policies | id, user_id, name, policy_type, compliance_rate|
| bill_analyses       | id, user_id, created_at, filename, provider,  |
|                     | total_analyzed_spend, spend_by_category,      |
|                     | arbitrage_opportunities, total_potential_savings|
| scan_history        | id, user_id, integration_id, status,          |
|                     | total_resources, waste_found, total_savings   |
| waste_distribution  | user_id, integration_id, category_name, value |

## Coding Patterns — Follow Exactly

### FastAPI Route Pattern
```python
@router.get("/endpoint", response_model=ResponseModel)
async def endpoint_name(
    param: str = Query(...),
    user: ClerkUser = Depends(get_current_user),
    db: MongoDBClient = Depends(get_db_client),
):
    """Clear one-line docstring."""
    try:
        # implementation
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("endpoint_name failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal error")
```

### Next.js Server Action Pattern
```typescript
"use server";
import { auth } from "@clerk/nextjs/server";

export async function actionName(params: ParamType) {
    const { userId } = await auth();
    if (!userId) return { success: false, error: "Unauthorized" };
    try {
        // implementation
        return { success: true, data: result };
    } catch (error) {
        const msg = error instanceof Error ? error.message : "Unknown error";
        return { success: false, error: msg };
    }
}
```

### Next.js Page with Data Loading Pattern
```typescript
"use client";
const [data, setData] = useState<DataType | null>(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);

useEffect(() => {
    const load = async () => {
        setLoading(true);
        try {
            const res = await fetch("/api/endpoint");
            if (!res.ok) throw new Error(`${res.status}`);
            setData(await res.json());
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to load");
        } finally {
            setLoading(false);
        }
    };
    load();
}, []);

if (loading) return <LoadingSkeleton />;
if (error) return <ErrorState message={error} />;
if (!data) return <EmptyState />;
```

### Resource Status Normalization
Status values from scanner: "Active", "Zombie", "Stopped", "Idle"
Status values from AI: "active", "zombie", "idle", "waste", "oversized"
When displaying: always normalize to one of: Active | Zombie | Stopped | Unknown
Never display raw status strings from the database without normalization.

## What NOT To Do

❌ Never auto-generate mock/fake data to "make the UI look good"
❌ Never add hardcoded numbers to fill empty states
❌ Never bypass auth for convenience ("just for testing")
❌ Never use `response_model=None` on an endpoint to skip validation
❌ Never import from a file path that doesn't exist yet without creating it
❌ Never use `except Exception: pass` — always log the error
❌ Never use `Any` as a return type on a FastAPI endpoint
❌ Never fetch data client-side when a Server Component would work
❌ Never import a `use server` action into a client component for passive read-only data loading; use a Server Component or same-origin App Router API route instead
❌ Never store sensitive data (credentials, API keys) in sessionStorage or localStorage
❌ Never add `!important` CSS unless explicitly overriding a third-party library

## Testing Requirements

For every bug fix, add at minimum:
1. One test that reproduces the bug (and now passes)
2. One test for the happy path
3. One test for the edge case (empty input, null values, 0)

For frontend/runtime changes, verification is not complete until the intended runtime mode serves at least one real request. A successful `npm run build` or `npm start` boot log alone is insufficient.

Test files:
  Backend: backend/tests/test_[module_name].py
  Frontend: src/__tests__/[component_name].test.tsx (if applicable)

Test command: `cd backend && python -m pytest tests/ -v`

## Performance Requirements

- API endpoints: must return in <500ms for typical data sizes
- Bulk operations: must use batch_size=50-100, never insert all at once
- Frontend: no component should cause layout shift after initial render
- Images/heavy content: must use loading="lazy"
- MongoDB queries: never fetch entire collection for counting —
  use count_documents() not len(await select())

## Security Requirements

- All credentials stored encrypted (see backend/app/security/crypto.py)
- Never log credentials, tokens, or API keys — even partially
- All user data queries must include `user_id` filter — never query
  a collection without scoping to the authenticated user
- File uploads: validate extension AND content type, not just filename
- SQL/NoSQL injection: always use parameterized queries (Motor handles this)
- SSRF: never fetch user-provided URLs without validation

## Local Runtime Contract

- For local interactive testing, keep the browser origin and the Next.js listener on the same host. In this repo, default to `http://localhost:3000` for the browser and frontend listener so Clerk dev auth cookies and same-origin proxy flows stay stable.
- Keep local backend/API loopback URLs on `http://127.0.0.1:8000` when needed, but do not mix a `localhost` browser session with a frontend listener bound only to `127.0.0.1`.
- When validating local frontend health, do not stop at `npm run build` or "server started". Hit at least `/`, `/login`, and one protected route against the exact runtime mode under test, and record whether the healthy mode is `npm start` or `npm run dev --webpack`.

## Public Marketing Shell Contract

- The homepage and every non-dashboard public route must share the same marketing shell contract (navbar, footer, logo, and signed-in CTA behavior) through the shared wrapper. Do not special-case `/` without updating the rest of the public site.
- When the public marketing shell changes, add or update a source-contract test that covers both the homepage and at least one non-dashboard public route.

## Commit Message Format

feat(scope): short description of what was added
fix(scope): short description of what was fixed
refactor(scope): short description of what was restructured
test(scope): short description of what was tested

Scope examples: pdf-parser, bill-analysis, dashboard, agent, ui, auth

## When You're Unsure

1. Read the relevant existing file first
2. Follow the pattern already established in that file
3. If no pattern exists, follow the patterns in this agents.md
4. If still unsure: add a TODO comment with the specific question
   and implement the safest/most conservative version
5. Never guess at an API method name — look it up or leave a TODO

## Completion Checklist

Before marking any task complete, verify:
  [ ] No print() statements added
  [ ] No hardcoded values or fake data
  [ ] No sessionStorage for business data
  [ ] TypeScript types defined for all new interfaces
  [ ] Error states handled (not just happy path)
  [ ] Loading states use <Skeleton> components
  [ ] UI matches design system (dark, rounded-2xl, indigo accents)
  [ ] MongoDB queries include user_id scoping
  [ ] New functionality doesn't break existing tests
  [ ] At minimum one new test added for new functionality

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)

## Repo-Local Codex Automations

- Treat checked-in repo automation assets under `.codex/**` as the only writable automation scope unless the task explicitly targets global Codex directories. Global paths such as `$HOME/.codex/skills` are reference-only context.
- For repo-local automation runners meant for unattended `launchd` execution, do not assume developer-only tools are present. Prefer helpers that degrade cleanly to POSIX tools when `rg` or similar binaries are unavailable.
- Keep git remotes token-free. If repo automation needs GitHub API access, verify `gh auth status` explicitly and refresh `gh` interactively instead of scraping credentials from git config or remote URLs.
