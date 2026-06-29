# CloudFinOps — Intern Onboarding Guide

## What Is CloudFinOps?

CloudFinOps is an AI-powered cloud cost optimization platform. Companies connect their AWS, Azure, or GCP accounts (or upload billing invoices), and we:

1. **Scan** their cloud estate to find waste (zombie VMs, idle disks, oversized instances)
2. **Analyze** their bills to find cross-cloud savings (e.g., "this workload is 40% cheaper on GCP")
3. **Generate** safe CLI remediation scripts so engineers can actually fix the waste
4. **Track** budgets, forecasts, and governance compliance

We sell to DevOps/SRE teams at companies spending $50K+/month on cloud.

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | Next.js 16 (App Router) | React, TypeScript, Tailwind CSS |
| UI Components | Lucide icons, Recharts, Framer Motion | Dark theme only |
| Auth | Clerk | JWT-based, handles login/signup |
| Backend | FastAPI (Python 3.11) | Async, REST API |
| Database | MongoDB Atlas | All access via `MongoDBClient` class |
| AI | Google Gemini (Flash) | Bill analysis, recommendations |
| File Storage | Google Cloud Storage (GCS) | Uploaded bills archived here |
| Deployment | GCP Cloud Run | Frontend + Backend as separate services |
| CI/CD | GitHub Actions + Cloud Build | Auto-deploy on push to main |

---

## Project Structure

```
cloudfinops-main/
├── src/                          # Frontend (Next.js)
│   ├── app/                      # Pages (App Router)
│   │   ├── dashboard/            # Authenticated pages
│   │   │   ├── arbitrage/        # Bill Scanner page
│   │   │   ├── pending-actions/  # Recommendations page
│   │   │   ├── resources/        # Resource inventory
│   │   │   └── ...
│   │   ├── api/                  # API proxy routes (forwards to backend)
│   │   └── actions/              # Server actions
│   ├── components/dashboard/     # All dashboard UI components
│   ├── lib/                      # Utilities, API client, types
│   └── middleware.ts             # Auth middleware
├── backend/                      # Backend (FastAPI)
│   ├── app/
│   │   ├── api/routes.py         # Main API routes (big file)
│   │   ├── auth/clerk.py         # JWT authentication
│   │   ├── bill_parser/          # Bill parsing engine
│   │   ├── scanners/             # AWS/Azure/GCP cloud scanners
│   │   ├── ai/                   # AI agent, fix generator
│   │   ├── core/                 # Business logic modules
│   │   └── db/mongo_client.py    # Database access layer
│   ├── requirements.txt
│   └── Dockerfile
├── Dockerfile.frontend
├── next.config.ts
└── CLAUDE.md                     # Project conventions (READ THIS)
```

---

## How to Run Locally

### Prerequisites
- Node.js 20+
- Python 3.11+
- A `.env.local` file (ask Nishant for credentials)

### Frontend
```bash
npm install
npm run dev    # Starts at http://localhost:3000
```

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The frontend proxies all `/api/*` requests to the backend at `localhost:8000`.

---

## Key Conventions (Must Follow)

1. **No `console.log()` in production** — Use only if gated by `process.env.NODE_ENV === "development"`
2. **No `print()` in backend** — Use `logger = logging.getLogger(__name__)`
3. **Dark theme only** — `bg-slate-950` (page), `bg-slate-900/50` (cards), `border-white/10`
4. **All DB access via MongoDBClient** — Never use raw pymongo
5. **All routes need auth** — Backend: `Depends(get_current_user)`, Frontend: Clerk middleware
6. **All MongoDB queries must include `user_id`** — Multi-tenant; never leak data between users

---

## Your Primary Task: Free Bill Scanner Landing Page

### What We're Building

A standalone page at `audit.cloudfinops.solutions` (or `/audit` route) where anyone can:
1. Drag-and-drop a cloud billing PDF/CSV
2. Get an instant waste analysis report
3. **No login required** — this is a lead generation tool

### What Already Exists (Don't Rebuild These)

| Component | Location | What It Does |
|-----------|----------|--------------|
| Upload form | `src/components/dashboard/bill-upload-form.tsx` | File picker + discount inputs |
| Analysis view | `src/components/dashboard/bill-analysis-view.tsx` | Shows savings, categories, opportunities |
| Executive report | `src/components/dashboard/bill-executive-report.tsx` | AI findings with waste grade |
| Backend parser | `backend/app/bill_parser/parser.py` | Normalizes CSV/Excel/PDF |
| AI enrichment | `backend/app/bill_parser/gemini_extractor.py` | Gemini fallback for unreadable bills |
| Arbitrage engine | `backend/app/bill_parser/analyzer.py` | Cross-cloud pricing comparison |
| Upload API | `backend/app/api/routes.py` (line ~2796) | POST `/api/scan/upload-bill` |

### What You Need to Build

#### Frontend (New Page)

Create a new public page (no auth required) with:
- Clean, single-purpose landing design
- Drag-and-drop upload area (large, centered)
- Supported formats badge: PDF, CSV, XLSX
- Privacy assurance text ("Your bill is analyzed in-memory and not stored")
- Loading state with progress (parsing takes 10-30 seconds)
- Results display: waste grade, total savings, top 3 findings
- CTA: "Get full breakdown — Sign up free" (links to /login)

**Key difference from existing bill scanner:**
- The existing one is behind auth (`/dashboard/arbitrage`)
- The new one is public, shows a **limited** report (teaser)
- Full details (resource IDs, scripts, all findings) require signup

#### Backend (New Unauthenticated Route)

A new endpoint that:
- Does NOT require `Depends(get_current_user)`
- Accepts file upload (same validation: PDF/CSV/XLSX, max 20MB for free tier)
- Runs the parser + basic analysis
- Returns a **redacted** response (top-level metrics only, no resource IDs)
- Does NOT store the file to GCS (privacy: process and delete)
- Rate-limited by IP (max 5 scans/hour)

### Files You Should Study First

Read these in this order:
1. `CLAUDE.md` — Project conventions (5 min read)
2. `src/components/dashboard/bill-upload-form.tsx` — See how upload works
3. `src/components/dashboard/bill-analysis-view.tsx` — See how results display
4. `backend/app/bill_parser/parser.py` — Understand parsing logic
5. `backend/app/api/routes.py` (search for `upload-bill`) — See the full upload flow

### Design Reference

Follow the existing design system:
- Background: `bg-slate-950`
- Cards: `bg-slate-900/50 border border-white/10 rounded-2xl`
- Primary button: `bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl`
- Text: `text-white` (headings), `text-slate-400` (body)
- Accents: emerald for savings, rose for waste, amber for warnings

---

## Secondary Tasks

### QA / Break Testing (Ongoing)

Your job: Try to break the bill parser. Find edge cases.

**How:**
1. Search online for sample AWS/Azure/GCP invoices and billing exports
2. Download various formats: CSV with weird encoding, multi-page PDFs, Excel with merged cells
3. Upload through the existing bill scanner at `/dashboard/arbitrage`
4. Log any failures in a spreadsheet: filename, format, error message, expected behavior
5. Check: Does it detect the correct provider? Are amounts parsed correctly? Does Gemini fallback work?

**Where to find test bills:**
- AWS: Settings > Billing > Export as CSV
- Azure: Cost Management > Download
- GCP: Billing > Export
- Also try: multi-currency bills, bills with enterprise discounts, bills with $0 line items

### Frontend Bug Fixes

If assigned a UI bug:
1. Run `npm run dev` to start the frontend
2. Make your fix
3. Run `npm run typecheck` before pushing (must pass)
4. Run `npm run lint` (fix any errors)

### Content Formatting (When Assigned)

Nishant will share raw technical bullet points. Your job:
- Format into a clean LinkedIn post or Reddit post
- Add proper code formatting (use triple backticks for code blocks)
- Make diagrams using Mermaid or Excalidraw if architecture is involved
- Never publish — always send back for review first

---

## Git Workflow

```bash
git checkout -b feature/your-feature-name   # Create branch
# ... make changes ...
git add <specific files>                     # Stage changes
git commit -m "feat(scope): description"     # Commit
git push -u origin feature/your-feature-name # Push
# Then open a Pull Request on GitHub
```

**Commit format:** `feat(bill-parser): add drag-drop upload page`

**Scopes:** `bill-parser`, `dashboard`, `ui`, `auth`, `scanner`

**Rules:**
- Never push directly to `main`
- Always open a PR
- Run `npm run typecheck` before pushing

---

## Who to Ask

- **Nishant (CTO)** — Architecture decisions, backend logic, deployment
- **Sambhav** — Product direction, business context, design feedback

---

## Day 1 Checklist

- [ ] Clone the repo
- [ ] Get `.env.local` from Nishant
- [ ] Run frontend + backend locally
- [ ] Read `CLAUDE.md`
- [ ] Navigate to `/dashboard/arbitrage` and upload a sample bill
- [ ] Read `bill-upload-form.tsx` to understand the existing upload flow
- [ ] Read `bill-analysis-view.tsx` to understand how results are displayed
