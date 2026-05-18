# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CloudFinOps is an AI-powered cloud waste & governance manager. It has a Next.js 16 frontend (App Router) and a FastAPI Python backend, both backed by MongoDB. It supports multi-cloud scanning (AWS, Azure, GCP) for waste detection, cost tracking, bill analysis, and AI-driven governance.

## Commands

### Frontend (Next.js)
```bash
npm install                  # Install dependencies
npm run dev                  # Dev server (webpack mode) at localhost:3000
npm run build                # Production build
npm run lint                 # ESLint
npm run typecheck            # TypeScript type checking (tsc --noEmit)
```

### Backend (FastAPI)
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # Dev server at 127.0.0.1:8000
```

### Tests
```bash
cd backend && python -m pytest tests/ -v           # All backend tests
cd backend && python -m pytest tests/test_foo.py -v  # Single test file
cd backend && python -m pytest tests/test_foo.py::test_bar -v  # Single test
```

### Verification
```bash
npm run verify:resource-contract   # Verify frontend/backend resource contract alignment
```

## Architecture

**Frontend** (`src/`): Next.js 16 App Router with Clerk auth. Pages live under `src/app/dashboard/` for authenticated routes and `src/app/` for public marketing pages. Server actions in `src/app/actions/`. API proxy routes in `src/app/api/` forward to the Python backend. Data fetching layer in `src/lib/dashboard/data.ts` calls backend via `src/lib/api.ts`.

**Backend** (`backend/app/`): FastAPI with Clerk JWT auth (`app/auth/`). Cloud scanners in `app/scanners/{aws,azure,gcp}.py`. AI agent (Gemini/OpenAI) in `app/ai/agent.py`. Bill parsing in `app/bill_parser/`. Governance/compliance in `app/governance/`. All DB access goes through `app/db/mongo_client.py` — never use raw pymongo/Motor directly.

**Frontend→Backend proxy**: `next.config.ts` rewrites `/api/*` and `/ws/*` to the Python backend (defaults to `http://127.0.0.1:8000`). Set `NEXT_PUBLIC_BACKEND_URL` to override.

**Deployment**: Frontend on Netlify (or GCP Cloud Run via `Dockerfile.frontend`). Backend on GCP Cloud Run. CI via GitHub Actions + Cloud Build.

## Key Conventions

### MongoDB Access (Backend)
Only use methods from `MongoDBClient` in `backend/app/db/mongo_client.py`:
- `await db.select(table, filters={})`, `await db.insert(table, data)`, `await db.upsert(table, data)`
- `await db.update(table, data, filters)`, `await db.delete(table, filters)`
- `await db.get_resources(user_id, integration_id=None)`
- `await db.get_dashboard_stats(user_id, integration_id=None)`
- `await db.get_daily_spend_history(user_id, integration_id, days)`
- `await db.bulk_upsert_resources(resources, batch_size=50)`

Never call `db.collection()` directly or invent methods like `db.find()`.

### Data Integrity
Every metric has ONE authoritative MongoDB source (see AGENTS.md §4 for full mapping). Never compute the same metric two ways. Never hardcode numbers in UI.

### Design System
Dark theme only: `bg-slate-950` (page), `bg-slate-900/50` (cards), `border-white/10`, `rounded-2xl` (cards), `indigo-600` (primary). Status colors: emerald=success, amber=warning, rose=error.

### Resource Status Normalization
Scanner returns: "Active", "Zombie", "Stopped", "Idle". Always normalize to: Active | Zombie | Stopped | Unknown before display.

### Auth Pattern
All backend routes use `user: ClerkUser = Depends(get_current_user)`. All MongoDB queries MUST include `user_id` scoping. Frontend server actions call `await auth()` from `@clerk/nextjs/server`.

### Required Environment Variables (Backend)
`CLERK_SECRET_KEY`, `MONGODB_URI`, `ENCRYPTION_KEY` (minimum). Optional: `GEMINI_API_KEY`, `NVIDIA_API_KEY`, `INFRACOST_API_KEY`, `GCP_BILLING_CATALOG_API_KEY`, `REDIS_URL`.

### Live Pricing Engine
The discount manager uses real-time cloud pricing from multiple sources:
- Primary: Infracost GraphQL API (`INFRACOST_API_KEY` — free tier at infracost.io)
- Secondary: Azure Retail Prices API (public, no key needed)
- Fallback: Static multipliers from `multicloud_comparison.py` (last resort only)

Pricing syncs daily at 3:30 AM UTC via APScheduler worker (`pricing_sync_worker.py`).
MongoDB collection: `live_pricing_multipliers`. Redis cache: `live_pricing:current` (TTL 15 min).

**Rules:**
- NEVER hardcode pricing multipliers in frontend code.
- ALL price calculations MUST go through the backend `/api/discount-manager/calculate` endpoint.
- Every price shown to users MUST include `pricing_basis` metadata (live_api | cached | static_fallback).
- The canonical multiplier source is `backend/app/core/multicloud_comparison.py` — no duplicates elsewhere.

### MCP Servers (Development)
- `cloud-cost-mcp`: Multi-cloud pricing comparison (2700+ instances, no key needed) — `npx cloud-cost-mcp`
- `infracost-mcp`: IaC cost estimation — `npx infracost-mcp`
- `aws-finops-mcp-server`: AWS Cost Explorer + waste audit

### Logging
Backend: `logger = logging.getLogger(__name__)` — no `print()`. Frontend: no `console.log()` unless gated by `process.env.NODE_ENV === "development"`.

### sessionStorage
Only for ephemeral UI state (active tab, modal open). Business data must be persisted to MongoDB and loaded via API.

## Commit Message Format

```
feat(scope): description
fix(scope): description
refactor(scope): description
test(scope): description
```

Scopes: pdf-parser, bill-analysis, dashboard, agent, ui, auth, scanner, governance, finance
