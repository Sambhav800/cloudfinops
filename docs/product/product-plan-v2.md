# CloudFinOps — Product Plan (Revised 2026-03-16)

## Core Philosophy

**CloudFinOps is a read-only intelligence platform.** We never execute changes, delete resources, move data, or modify infrastructure on behalf of customers. Every recommendation ends at **guidance, scripts, and handoff** — the human always clicks the button in their own cloud console, CI/CD pipeline, or IaC workflow. This eliminates the catastrophic risk surface that comes with write-access automation while still delivering 90% of the value.

---

## Features To Build Next (Priority Order)

### 1. Shift-Left Cost Estimation for Terraform, Helm, and PRs
**What it does:** Before any deployment, CloudFinOps analyzes Terraform plans, Helm charts, or PR diffs and shows the projected cost delta.

### 2. Multi-Cloud Commitment Copilot
**What it does:** Unified view of AWS Savings Plans/RIs, Azure savings plans/reservations, and GCP CUDs showing gaps and utilization.

### 3. Remediation Guidance and Handoff Workflows
**What it does:** Packages AI recommendations into structured tickets with approval tracking and realized-savings verification.

### 4. AI and LLM Spend Tracking
**What it does:** Tracks and allocates spend on AI/LLM services by team, feature, and model.

### 5. FOCUS-Aligned Billing Lake with Owner Inference
**What it does:** Normalizes all billing data into a FOCUS-aligned schema and probabilistic resource ownership.

---

## Credit Usage Strategy
- **GCP ($2,000):** Primary Platform (Cloud Run, Cloud Build, BigQuery).
- **Azure ($300):** Narrow Testing/Webhooks.
- **MongoDB ($500):** Primary Application Data Layer.
