---
pdf_options:
  margin: 25mm
  format: A4
  headerTemplate: '<div style="width:100%;font-size:8px;color:#6366f1;text-align:right;padding-right:25mm;">CloudFinOps Solutions Pvt. Ltd. | Confidential</div>'
  footerTemplate: '<div style="width:100%;font-size:8px;color:#999;text-align:center;">Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>'
  displayHeaderFooter: true
stylesheet: https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown.min.css
body_class: markdown-body
---

<div style="text-align:center;padding:60px 0 40px 0;">
<img src="../public/logo-main.png" width="220" />
<h1 style="margin-top:30px;font-size:32px;color:#1e293b;">PROOF OF CONCEPT PROPOSAL</h1>
<h2 style="color:#6366f1;font-weight:500;margin-top:10px;">CloudFinOps × IFFCO Kisan Finance</h2>
<p style="font-size:16px;color:#64748b;margin-top:20px;">Autonomous Cloud Cost Intelligence Platform</p>
<br/><br/>
<table style="margin:0 auto;text-align:left;font-size:14px;border:none;">
<tr><td style="color:#64748b;padding:4px 20px;">Prepared for:</td><td><strong>IFFCO Kisan Finance</strong> Cloud Infrastructure Team</td></tr>
<tr><td style="color:#64748b;padding:4px 20px;">Prepared by:</td><td><strong>CloudFinOps Solutions Pvt. Ltd.</strong></td></tr>
<tr><td style="color:#64748b;padding:4px 20px;">Date:</td><td>June 2026</td></tr>
<tr><td style="color:#64748b;padding:4px 20px;">Version:</td><td>1.0</td></tr>
<tr><td style="color:#64748b;padding:4px 20px;">Classification:</td><td style="color:#dc2626;">Confidential</td></tr>
</table>
</div>

<div style="page-break-after: always;"></div>

## 1. DEMONSTRATE NEED

### Problem Statement

IFFCO Kisan Finance operates critical workloads on Microsoft Azure that face four interconnected challenges:

**1. Lack of Unified Visibility**

There is no single pane of glass showing all Azure resources, their real time utilization, cost attribution, and waste classification. The team relies on Azure Advisor's limited rule based checks, which miss 60 to 70% of optimization opportunities.

**2. Seasonal Workload Misclassification**

Resources supporting month end batch processing (financial closing, reporting, reconciliation) are idle 80 to 90% of the month but critical during peak windows. Current monitoring either flags them as waste (false positives) or ignores them entirely. Neither approach optimizes cost.

**3. Underutilization Without Actionable Resolution**

Resources running at 10 to 25% utilization are identified, but the team lacks clarity on: (a) whether the provider offers a smaller SKU, (b) whether the workload can safely downscale, and (c) what the auto scaling options are for their specific Azure VM families.

**4. Manual Optimization Process**

The cloud operations team spends 15 to 20+ hours per month manually reviewing resources, cross referencing metrics, and generating remediation tickets. This time could be redirected to strategic infrastructure work.

### Market Validation

- Indian enterprises waste 25 to 30% of cloud spend (Nasscom FinOps Report 2025)
- Azure Advisor catches only rule based waste; misses workload pattern based optimization entirely
- No existing tool provides seasonal workload detection + provider aware rightsizing + autonomous remediation in a single platform

<div style="page-break-after: always;"></div>

## 2. ENVISION SOLUTIONS

### Proposed Solution: CloudFinOps Platform

An AI powered autonomous cloud optimization platform that connects to IFFCO's Azure environment via read only credentials and delivers:

| Capability | How It Works | IFFCO Value |
|-----------|-------------|-------------|
| **AI Resource Classification** | Gemini Flash verifies every resource as Active, Zombie, Idle, Oversized, or Waste with confidence scores | Eliminates false positives; trusted recommendations |
| **Seasonal Workload Detection** | 30 day rolling analysis with peak burst pattern recognition. High peak + low average = "periodic batch", never zombie | Month end servers correctly classified; no false alarms |
| **Provider Aware Rightsizing** | Full Azure SKU catalog with family hierarchies. Only recommends sizes that actually exist. Knows minimums per family | Actionable recommendations, not theoretical |
| **Autonomous Remediation** | Generates `az` CLI commands with rollback instructions, validated by Safety Critic before surfacing | One click execution, zero risk of breaking production |
| **Proactive Scheduling Alerts** | Historical pattern learning; alerts team before known peak windows; suggests downscale after peak ends | Optimal cost without manual calendar tracking |
| **Governance & Compliance** | Tagging policy enforcement, region compliance, security posture scoring | Audit ready compliance reporting |

### Constraints Addressed

- **Security:** Read only Service Principal with zero write access to IFFCO's environment
- **Compliance:** No data leaves IFFCO's network; all processing is on premise
- **Integration:** No agents installed on VMs; purely API based scanning via Azure Resource Manager
- **Cost:** Platform cost is less than 4% of current monthly cloud spend (guaranteed positive ROI)

<div style="page-break-after: always;"></div>

## 3. DEFINE POC GOALS

### Primary Goals

1. **Connect** IFFCO's Azure subscription via read only Service Principal within 30 minutes of kickoff
2. **Scan** all Azure resources (VMs, Disks, IPs, SQL, Storage, Network) and classify utilization state
3. **Identify** minimum 10 actionable optimization findings worth 15% or more of current monthly spend
4. **Demonstrate** seasonal workload detection by correctly classifying batch processing VMs as "periodic" (not zombie)
5. **Generate** safe, executable `az` CLI remediation scripts for each finding with rollback commands
6. **Produce** a CTO grade executive report with total savings potential, governance score, and prioritized action plan

### Secondary Goals

- Validate GPU Intelligence module (if IFFCO has any NC/ND/NV series VMs)
- Demonstrate multi cloud comparison: "What would your Azure workloads cost on AWS or GCP?"
- Show governance scoring: tagging compliance, region policy, security posture
- Demonstrate the AI agent's conversational capability (ask natural language questions about your infrastructure)

<div style="page-break-after: always;"></div>

## 4. SPECIFY MEASURABLE SUCCESS CRITERIA

| # | Success Metric | Target | How Measured |
|---|---------------|--------|-------------|
| 1 | Resources scanned | 100% of subscription | Count vs. Azure Resource Graph total |
| 2 | False positive rate | Less than 5% | Manual validation of zombie classifications |
| 3 | Seasonal workload accuracy | 100% correct | Batch VMs classified as "periodic", not zombie |
| 4 | Savings identified | 15% or more of monthly spend | Sum of all remediation opportunities |
| 5 | Time to first insight | Under 15 minutes | Clock from credential entry to dashboard |
| 6 | Remediation safety | Zero production breaking scripts | Safety Critic validation pass rate |
| 7 | Actionable findings | 10 or more specific recommendations | Each with CLI command + rollback |
| 8 | Governance score | Baseline established | Tagging, region, security compliance % |

### Acceptance Criteria for Full Deployment

If the POC achieves 6 of 8 or more metrics above, IFFCO proceeds to:
- Full subscription onboarding (all resource groups)
- Scheduled automated scanning (daily)
- Team onboarding and access provisioning

<div style="page-break-after: always;"></div>

## 5. IDENTIFY TEAM

### CloudFinOps Team

| Name | Role | Responsibility |
|------|------|---------------|
| Nishant Jain | CTO & Co Founder | Technical implementation, platform configuration, Azure integration, demo delivery |
| Sambhav Pal | CEO & Co Founder | Stakeholder communication, success criteria alignment, executive reporting |

### IFFCO Team (Requested)

| Role | Responsibility |
|------|---------------|
| Cloud Head / VP Infrastructure | POC sponsor, success criteria approval, access provisioning |
| Azure Admin | Service Principal creation, credential handoff |
| Cloud Ops Engineer | Validation of findings, seasonal workload confirmation |
| Finance/Procurement (Optional) | Cost data validation, savings verification |

### Access Requirements from IFFCO

1. **Azure Service Principal** with `Reader` role on target subscription(s)
2. **Cost Management Reader** role (for actual billing data, not estimated)
3. **30 minute kickoff call** to align on tagged resources, known batch workloads, and any excluded resource groups

<div style="page-break-after: always;"></div>

## 6. CREATE A TIMELINE

### Phase 1: Setup & Discovery (Week 1)

| Day | Activity | Owner | Deliverable |
|-----|----------|-------|------------|
| 1 | Kickoff call: align on scope, identify workloads, define seasonal patterns | Both teams | Scope document |
| 2 | Create Service Principal, provision read only access | IFFCO Azure Admin | Credentials handed off |
| 3 | Connect Azure subscription to CloudFinOps platform | Nishant | Successful connection verified |
| 4 to 5 | Initial full scan + AI verification + baseline metrics collection | CloudFinOps (automated) | Raw scan results + baseline |

### Phase 2: Deep Analysis & Validation (Week 2 to 3)

| Week | Activity | Owner | Deliverable |
|------|----------|-------|------------|
| Week 2 | Full resource classification + waste detection across all resource groups | Platform | Dashboard populated with findings |
| Week 2 | Seasonal workload identification and pattern calibration | IFFCO Cloud Ops + CloudFinOps | Batch VMs tagged and validated |
| Week 3 | Multi cycle observation (capture at least one monthly peak if timing allows) | Platform | Confidence in periodic classification |
| Week 3 | Rightsizing recommendations generated with SKU aware constraints | Platform | Actionable downsize suggestions |

### Phase 3: Remediation & Governance (Week 4)

| Activity | Owner | Deliverable |
|----------|-------|------------|
| Remediation scripts generated and safety validated | Platform | CLI commands with rollback for each finding |
| Governance score calculated (tagging, region, security) | Platform | Compliance report |
| Scheduling recommendations for periodic workloads | Platform | Peak/off peak scaling plan |
| Internal QA review of all findings for accuracy | CloudFinOps | Zero false positive verification |

### Phase 4: Executive Presentation & Decision (Week 5 to 6)

| Activity | Owner | Deliverable |
|----------|-------|------------|
| Executive presentation to IFFCO leadership with full POC results | Both teams | POC Results Deck |
| Walkthrough of savings, governance score, and remediation plan | CloudFinOps | Live dashboard demo |
| Success criteria evaluation against agreed metrics | Both teams | Scorecard (pass/fail per metric) |
| Commercial discussion and deployment timeline for production | Both teams | Go/No Go decision |

**Total POC Duration: 5 to 6 weeks**

<div style="page-break-after: always;"></div>

## 7. DEPLOYMENT MODEL

### On Premise (Dockerized) within IFFCO Network

CloudFinOps will be deployed **entirely within IFFCO's network perimeter**. No data leaves the premises.

<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin:20px 0;">

**Architecture Overview**

The platform runs as three Docker containers on a single host (or Kubernetes cluster):

| Container | Role | Port |
|-----------|------|------|
| Frontend (Next.js) | Web dashboard for IFFCO users | 3000 |
| Backend (FastAPI) | Scanning engine, AI verification, intelligence | 8000 |
| MongoDB | Data persistence (resources, metrics, credentials) | 27017 (internal only) |

**Network flow:** Only outbound HTTPS (port 443) to Azure management APIs. Zero inbound connections from the internet.

**Outbound whitelist (5 domains only):**
- `login.microsoftonline.com` (Azure AD auth)
- `management.azure.com` (Resource Manager)
- `monitor.azure.com` (Metrics)
- `prices.azure.com` (Pricing API)
- `management.core.windows.net` (Cost Management)

**Security guarantees:**
- Rootless containers with read only filesystem
- All credentials AES 256 encrypted at rest
- Service Principal has zero write permissions
- No application data (database content, VM files) is ever accessed

</div>

<div style="page-break-after: always;"></div>

## 8. COMMERCIAL PROPOSAL

### Pricing for IFFCO Kisan Finance

Based on IFFCO's current Azure spend of approximately **₹30,00,000 per month** (₹3.6 Crore per year):

<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:24px;margin:20px 0;">

| Component | Amount |
|-----------|--------|
| **Annual Platform License** | **₹12,00,000 per year** |
| GST (18%) | ₹2,16,000 |
| **Total Annual Cost** | **₹14,16,000 per year** |

</div>

### What This Includes

- Unlimited scanning across all Azure subscriptions
- Daily automated scans with real time WebSocket alerts
- Full AI verification (Gemini Flash powered classification)
- GPU Intelligence module
- Seasonal workload detection and scheduling alerts
- Autonomous remediation with Safety Critic validation
- Governance and compliance scoring
- Conversational AI assistant (Clousy) for natural language queries
- On premise Docker deployment (no data leaves IFFCO network)
- Dedicated support with 4 hour response time (business hours IST)
- Monthly executive FinOps reports
- Quarterly business reviews

### ROI Projection

| Metric | Value |
|--------|-------|
| Current monthly Azure spend | ₹30,00,000 |
| Expected savings (conservative 15%) | ₹4,50,000 per month |
| Annual savings projection | ₹54,00,000 per year |
| Platform cost | ₹14,16,000 per year |
| **Net annual benefit** | **₹39,84,000 per year** |
| **ROI** | **3.8x return on investment** |

### POC Terms

- **POC is free** (no cost to IFFCO during the 5 to 6 week evaluation period)
- Full production deployment begins only after POC success criteria are met
- Month to month billing available for the first 3 months (no annual lock in required upfront)
- 30 day exit clause: cancel anytime with 30 days notice

<div style="page-break-after: always;"></div>

## 9. PLAN NEXT STEPS

### If POC is Successful (6 of 8 or more criteria met):

**Week 7 to 8: Full Onboarding**
- Connect all Azure subscriptions (prod, staging, dev)
- Configure scheduled daily scans
- Set up WebSocket based real time alerts
- Onboard IFFCO cloud team (dashboard access, Clousy AI assistant)

**Month 3: Autonomous Operations**
- Enable confidence gated autonomous execution for high confidence patterns
- Set up governance policies (tagging enforcement, region compliance)
- Monthly executive FinOps reports automated
- Integrate with IFFCO's ticketing system (ServiceNow/Jira) for remediation workflow

**Month 4 onwards: Continuous Optimization**
- Reserved Instance and Savings Plan optimization recommendations
- Commitment lifecycle management (expiry alerts, renewal guidance)
- Custom policy engine for IFFCO specific compliance requirements
- Quarterly business reviews with measurable savings tracking

<div style="page-break-after: always;"></div>

## APPENDIX: Sample Findings (Illustrative)

These are example findings the platform would surface during the POC:

| # | Resource | Finding | Monthly Waste | Remediation |
|---|----------|---------|--------------|-------------|
| 1 | stopped-vm-01 (Standard_D4s_v5) | VM stopped but disk still incurring charges | ₹8,400/mo | `az vm delete` or detach disk |
| 2 | oversized-vm-02 (Standard_D8s_v5) | 8 vCPUs allocated, average usage 1.2 vCPU | ₹12,600/mo savings | `az vm resize` to Standard_D2s_v5 |
| 3 | orphan-disk-03 (Premium P30 1TB) | Unattached managed disk with no VM association | ₹7,200/mo | `az disk delete` after backup verification |
| 4 | batch-server-04 (Standard_D4s_v5) | Correctly classified as PERIODIC (not zombie) | ₹0 (no action) | Schedule based resize recommended |
| 5 | unused-pip-05 | Static public IP with no NIC association | ₹350/mo | `az network public-ip delete` |
| 6 | dev-sql-06 (GP_Gen5_8) | Dev SQL with 2% avg DTU; prod SKU pricing | ₹15,000/mo savings | Downgrade to Basic or Serverless tier |

---

<div style="text-align:center;margin-top:40px;padding:20px;">
<img src="../public/logo-main.png" width="140" />
<p style="color:#64748b;margin-top:15px;font-size:13px;">
CloudFinOps Solutions Pvt. Ltd.<br/>
Sambhav Pal (CEO) · Nishant Jain (CTO)<br/>
https://cloudfinops.solutions
</p>
</div>
