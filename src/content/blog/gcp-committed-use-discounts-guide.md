---
title: "GCP Committed Use Discounts Explained: CUDs vs SUDs vs Flex CUDs (2026)"
slug: "gcp-committed-use-discounts-guide"
excerpt: "Google Cloud's commitment pricing is confusing. This guide breaks down CUDs, SUDs, and the new Flex CUDs — when to buy each, how to calculate coverage, and mistakes to avoid."
category: "GCP"
author:
  name: "Nishant Jain"
  role: "Co-Founder & CTO"
  avatar: "/images/team/nishant.png"
publishedAt: "2026-08-20"
updatedAt: "2026-08-20"
readTime: 14
featured: false
tags: ["gcp", "committed-use-discounts", "suds", "cost-optimization", "savings"]
---

## Why GCP Commitment Pricing Confuses Everyone

Google Cloud's discount model is fundamentally different from AWS and Azure. On AWS, you pick a Savings Plan or Reserved Instance and move on. On GCP, three separate discount mechanisms can apply to the same workload simultaneously, they interact with each other in non-obvious ways, and the billing reports don't always make it clear which discount applied where.

Here's what typically happens: a team running $18,000/month in GCP Compute Engine notices they're already getting Sustained Use Discounts automatically. Someone asks "should we also buy CUDs?" The finance team looks at the CUD pricing page, sees "up to 57% off," and signs a 3-year commitment. Three months later, they realize the CUD replaced their SUD rather than stacking on top of it, and the actual incremental savings were far less than expected.

This guide breaks down each discount mechanism, explains exactly how they interact, and gives you a framework for calculating optimal commitment coverage. I've spent the last year building commitment analysis tooling at CloudFinOps, and the patterns I see in real billing data keep repeating across teams of every size.

## Sustained Use Discounts (SUDs): The Automatic Baseline

Sustained Use Discounts are GCP's automatic volume discount. You don't buy anything, don't commit to anything, and don't even need to know they exist. If a VM runs for more than 25% of a month, GCP starts applying incremental discounts.

### How SUDs Calculate

GCP divides each month into four usage tiers:

| Usage in Month | Effective Discount | Cumulative Savings |
|---|---|---|
| 0-25% (first week) | 0% (full price) | 0% |
| 25-50% (second week) | 20% off this increment | ~6% overall |
| 50-75% (third week) | 40% off this increment | ~14% overall |
| 75-100% (fourth week) | 60% off this increment | ~22% overall |
| Full month (730 hours) | Blended rate | **~30% overall** |

A VM running the entire month effectively pays for only 70% of the on-demand rate. This is significant. A team spending $10,000/month on always-on VMs is already saving roughly $3,000/month without doing anything.

### What Qualifies for SUDs

SUDs apply to:
- General-purpose VMs (N1, N2, N2D, N4, E2, C3, C3D)
- Custom machine types
- Sole-tenant node groups (on the node cost, not the VMs inside)

SUDs do NOT apply to:
- Preemptible and Spot VMs (already discounted)
- E2 shared-core instances (f1-micro, g1-small)
- Committed Use Discount covered usage (CUDs replace SUDs)
- A2 and G2 accelerator-optimized families
- Cloud SQL, GKE Autopilot pods (different pricing models)

> **Key insight:** SUDs are calculated per machine family, per region, across your entire project. GCP aggregates all N2 vCPUs in us-central1 into a single usage bucket. You don't need individual VMs to run all month — as long as your combined N2 usage in a region fills the month, you get the full discount.

### The Aggregation Trick

This aggregation behavior is powerful and underappreciated. Say you have three N2 VMs in us-central1:
- VM-A: runs hours 0-8 daily (33% of month)
- VM-B: runs hours 8-16 daily (33% of month)
- VM-C: runs hours 16-24 daily (33% of month)

Individually, each VM barely qualifies for the second SUD tier. But GCP aggregates them: your combined N2 usage in that region equals 100% of one VM running all month. You get the full 30% SUD on the aggregate.

This makes SUDs particularly effective for teams running batch jobs, development environments with staggered schedules, or auto-scaling groups where the total capacity stays relatively constant even as individual instances cycle.

## Committed Use Discounts (CUDs): The Long-Term Play

CUDs are GCP's version of Reserved Instances. You commit to using a minimum amount of resources (vCPUs and memory) in a specific region for 1 or 3 years. In exchange, you get substantial discounts on those resources.

### CUD Pricing by Term

| Resource | 1-Year CUD Discount | 3-Year CUD Discount |
|---|---|---|
| vCPUs (most families) | 20% | 57% |
| Memory (most families) | 20% | 57% |
| GPUs (A100, H100, L4) | 15% | 35% |
| Local SSD | 20% | 57% |

The 57% discount on a 3-year commitment is the headline number GCP uses in marketing. It's real, but it comes with serious constraints.

### How CUDs Actually Work

CUDs are resource-based, not spend-based. You commit to a specific number of vCPUs and GB of memory in a region. For example: "28 vCPUs and 112 GB memory in us-central1 for 3 years."

This means:
1. You pay for the committed resources whether you use them or not
2. The commitment is locked to a region (no cross-region flexibility)
3. CUDs apply to the machine family you specify (N2 CUDs cover N2 usage only)
4. The discount replaces SUDs — it doesn't stack on top of them

That last point is critical. If a resource already gets a 30% SUD and you buy a 1-year CUD at 20% off, you've actually lost money. The CUD's 20% discount replaces your free 30% SUD. This is the single most common mistake teams make with GCP commitments.

> **Key insight:** A 1-year CUD (20% off) is WORSE than the free SUD (30% off) for resources running full-time. Only 3-year CUDs (57% off) provide meaningful savings beyond what SUDs already give you for always-on workloads.

### Spend-Based CUDs

GCP also offers spend-based CUDs for certain services (Cloud SQL, Cloud Run, VMware Engine). These work more like AWS Savings Plans — you commit to a dollar amount per hour rather than specific resources.

| Service | 1-Year Spend CUD | 3-Year Spend CUD |
|---|---|---|
| Cloud SQL | 25% | 52% |
| Cloud Run | 17% | 40% |
| VMware Engine | 15% | 35% |

Spend-based CUDs are generally simpler to manage because they apply automatically to eligible usage regardless of machine configuration changes.

## Flex CUDs: The Middle Ground (2025+)

Google introduced Flex CUDs to address the massive gap between "no commitment" and "1-3 year lock-in." Flex CUDs let you commit for shorter periods with proportionally smaller discounts.

### How Flex CUDs Work

| Flex CUD Term | Discount | Minimum Commitment |
|---|---|---|
| 3 months | 8-12% | Per-family, per-region |
| 6 months | 14-18% | Per-family, per-region |
| 9 months | 17-22% | Per-family, per-region |

Flex CUDs share most properties with standard CUDs:
- Resource-based (vCPUs + memory)
- Region-locked
- Machine-family specific
- Replace SUDs (don't stack)

The crucial difference: they auto-expire. No 3-year albatross if your workload changes.

### When Flex CUDs Make Sense

Flex CUDs solve a specific problem: workloads that are too stable for on-demand pricing but too uncertain for multi-year commitments. Common scenarios:

- **Project-based work**: A 6-month ML training pipeline that needs consistent GPU capacity
- **Seasonal patterns**: Retail workloads that spike for 3-4 months annually
- **Migration bridges**: Workloads running on GCP for 6-9 months before moving to a different architecture
- **Startup validation**: You know you'll need these resources for the next two quarters but can't predict year two

> **Key insight:** Flex CUDs are only worthwhile when the discount exceeds your SUD rate. For always-on workloads, a 3-month Flex CUD at 8-12% is worse than the free 30% SUD. Flex CUDs shine for workloads with 40-70% monthly utilization where SUDs only partially apply.

### The Complete Comparison Table

| Feature | SUD | Standard CUD (1yr) | Standard CUD (3yr) | Flex CUD |
|---|---|---|---|---|
| Discount | Up to 30% | 20% | 57% | 8-22% |
| Commitment required | None | 1 year | 3 years | 3-9 months |
| Applies automatically | Yes | No (must purchase) | No (must purchase) | No (must purchase) |
| Cancellable | N/A | No | No | No (but short-term) |
| Cross-region | No | No | No | No |
| Cross-family | No | No | No | No |
| Stacks with SUDs | N/A | No (replaces) | No (replaces) | No (replaces) |
| Upfront payment | None | None | None | None |
| GPU support | No | Yes | Yes | Limited |
| Best for | Always-on VMs | Never (use 3yr instead) | Stable 3yr+ workloads | 3-9 month projects |

## How to Calculate Optimal CUD Coverage

The math for optimal CUD coverage is more nuanced than most guides suggest. You can't just look at average monthly spend and commit to that amount. You need to account for SUD interactions, utilization variability, and growth patterns.

### Step 1: Establish Your Baseline Usage

Pull 90 days of usage data from Cloud Billing exports (BigQuery). For each machine family and region combination, calculate:

```
min_daily_vcpus = lowest vCPU count running in any 24-hour period
avg_daily_vcpus = average vCPU count across all days
p10_daily_vcpus = 10th percentile daily vCPU count
```

Your safe CUD commitment level is `p10_daily_vcpus` — the amount of compute that ran even on your quietest days.

### Step 2: Calculate Incremental Savings Over SUDs

For always-on workloads already getting the full 30% SUD, the incremental savings from a 3-year CUD are:

```
On-demand rate: $1.00/hour (example)
With SUD (30% off): $0.70/hour
With 3yr CUD (57% off): $0.43/hour

Incremental savings: $0.70 - $0.43 = $0.27/hour
Incremental discount vs SUD price: 38.6% additional savings
```

For a workload running 730 hours/month at $1.00/hour on-demand:
- Without any discount: $730/month
- With SUD only: $511/month (saving $219)
- With 3yr CUD: $314/month (saving $416)
- Incremental CUD benefit over SUD: $197/month

Over 3 years, that one vCPU saves an additional $7,092 compared to relying on SUDs alone.

### Step 3: Size Your Commitment Correctly

Here's a practical example. A team with the following N2 usage in us-central1:

| Day Type | vCPUs Running | Memory (GB) |
|---|---|---|
| Weekday (production + dev) | 96 vCPUs, 384 GB | Peak hours |
| Weekend (production only) | 48 vCPUs, 192 GB | Baseline |
| Minimum observed (3 months) | 44 vCPUs, 176 GB | Holiday weekend |

Safe CUD commitment: **44 vCPUs, 176 GB memory** (the minimum observed over 90 days).

Monthly cost impact:
- On-demand for 44 N2 vCPUs + 176 GB (us-central1): ~$2,188/month
- With SUD (full month): ~$1,532/month
- With 3yr CUD: ~$941/month
- Monthly savings vs SUD: **$591/month**
- Annual savings: **$7,092**
- 3-year total savings vs SUD: **$21,276**

The remaining 4-52 vCPUs of variable usage continues to get SUDs automatically. You're not leaving money on the table — you're avoiding over-commitment.

### Step 4: Account for Growth and Decay

If your usage is growing 10% monthly, your minimum today will be your average in 3 months. You might commit more aggressively. If your usage is declining or you're planning a migration to GKE Autopilot or Cloud Run, commit less (or not at all).

A useful heuristic:

| Growth Rate | Commitment Strategy |
|---|---|
| > 15% monthly growth | Commit to current P10, re-evaluate quarterly |
| 5-15% monthly growth | Commit to current P25, re-evaluate every 6 months |
| Stable (< 5% change) | Commit to current P50 safely |
| Declining usage | Don't commit (or use Flex CUDs only) |
| Migration planned in < 2 years | Flex CUDs or no commitment |

## When NOT to Buy CUDs

Not every workload deserves a commitment. Here are the situations where staying on-demand (with free SUDs) is the right call:

### 1. You're Considering a 1-Year CUD for Always-On Workloads

The math simply doesn't work. A 1-year CUD gives 20% off. A full-month SUD gives 30% off. You'd literally pay more with the CUD. The only scenario where a 1-year CUD makes sense is for workloads with very low monthly utilization (below 50%) where SUDs don't fully kick in — but in that case, you should question why you're running always-allocated VMs in the first place.

### 2. Your Architecture Is in Flux

If any of these are true in the next 12 months, don't commit:
- Migrating from VMs to GKE or Cloud Run
- Evaluating a move from N2 to C3/C3D for better price-performance
- Considering a region change for latency or compliance reasons
- Expecting a major refactor that changes resource requirements by more than 30%

### 3. Your Usage Is Highly Variable

If your minimum-to-maximum usage ratio is below 0.3 (your quietest day uses less than 30% of your busiest day), your safe commitment zone is tiny. The overhead of managing a small CUD may not be worth the savings.

### 4. You Don't Have 90 Days of Data

Never commit based on projected usage. Projections are wrong. Wait until you have 90 days of actual billing data showing consistent resource consumption.

### 5. You're Running Spot/Preemptible VMs

Spot VMs already get 60-91% discounts. CUDs don't apply to them and shouldn't — the workloads running on Spot are by definition interruptible and shouldn't receive long-term commitments.

> **Key insight:** The most expensive CUD mistake isn't under-committing. It's over-committing. An unused CUD charges you 100% of the committed rate for resources sitting idle. Under-committing just means some usage stays on SUD pricing, which is still 30% off. The asymmetry of risk strongly favors conservative commitments.

## Common CUD Mistakes (and How to Avoid Them)

### Mistake 1: Buying 1-Year CUDs for Stable Workloads

As discussed above, 1-year CUDs provide less savings than free SUDs for always-on workloads. If you're committing, commit for 3 years or don't commit at all. The middle ground is Flex CUDs for shorter-term certainty.

**Fix:** Audit existing 1-year CUDs. If the covered workloads are running 24/7, you're overpaying compared to just relying on SUDs. Let the CUD expire and either upgrade to 3-year or stay on SUDs.

### Mistake 2: Not Accounting for SUD Replacement

Teams see "57% off" and calculate savings against on-demand pricing. But for always-on workloads, the baseline isn't on-demand — it's the SUD-discounted rate. The real savings are 57% vs 30%, not 57% vs 0%.

**Fix:** Always calculate incremental savings over your current effective rate. For workloads already getting full SUDs, the incremental 3-year CUD benefit is ~38.6% beyond what you're already saving.

### Mistake 3: Committing Across Too Many Families

GCP CUDs are locked to machine families. If you commit 20 vCPUs each to N2, C3, and E2, you can't shift between them. If you later consolidate onto C3 for better performance, your N2 and E2 CUDs go to waste.

**Fix:** Standardize on 1-2 machine families before committing. Run a cost-performance analysis to determine which family gives the best value for your workload profile, migrate everything to it, stabilize for 90 days, then commit.

### Mistake 4: Ignoring Regional Lock-in

CUDs are region-specific. A commitment in us-central1 provides zero benefit if you move workloads to europe-west1. With GCP's growing region count and evolving latency requirements, regional shifts are more common than teams expect.

**Fix:** Only commit in regions where you have compliance or latency requirements that prevent relocation. For workloads that could theoretically move regions, keep them on SUDs unless you have strong confidence in regional stability.

### Mistake 5: Setting and Forgetting

CUDs don't auto-adjust. If you committed to 64 vCPUs eighteen months ago and now only run 40, you're paying for 24 idle vCPUs at committed rates. Many teams buy CUDs and never review them until renewal.

**Fix:** Set a calendar reminder for monthly CUD utilization reviews. At CloudFinOps, our commitment analysis engine flags under-utilized CUDs automatically, but even a manual monthly check of your CUD utilization report in Cloud Billing prevents waste from creeping in unnoticed.

### Mistake 6: Not Using CUD Sharing Across Projects

By default, CUDs apply to the project where they're purchased. But GCP allows CUD sharing across projects within a billing account. If you have 5 projects each running N2 instances in us-central1, you can buy one larger CUD that covers aggregate usage across all projects.

**Fix:** Enable CUD sharing in your billing account settings. Consolidate commitments at the billing-account level rather than buying per-project CUDs. The aggregated baseline is always higher and more stable than individual project baselines.

### The Decision Flowchart

Here's the flowchart I use when advising teams on GCP commitment strategy:

**Step 1: Is the workload running on preemptible/Spot VMs?**
- Yes: No CUD needed. Spot pricing is already deeply discounted.
- No: Continue.

**Step 2: Has the workload been stable for 90+ days?**
- No: Wait. Let SUDs cover you in the meantime (up to 30% free savings).
- Yes: Continue.

**Step 3: Is the workload likely to persist for 3+ years in its current form?**
- Yes: Buy a 3-year CUD for your P10 usage baseline.
- No, but likely 6-12 months: Consider Flex CUDs if utilization is below 60% monthly.
- No, but likely 6-12 months with high utilization: Stay on SUDs (30% is hard to beat short-term).
- Uncertain: Stay on SUDs.

**Step 4: Is the workload running full-time (730 hours/month)?**
- Yes: Only 3-year CUDs make sense (1-year CUDs are worse than SUDs).
- No (40-70% utilization): Flex CUDs might beat partial SUDs.
- No (below 40% utilization): Consider auto-scaling or scheduling instead of commitments.

**Step 5: How much to commit?**
- Start with P10 baseline (minimum observed over 90 days).
- Scale up to P25-P50 only if usage is stable or growing.
- Never commit to more than 80% of average usage.
- Re-evaluate every quarter.

## FAQ

### Do CUDs and SUDs stack? Can I get both discounts?

No. CUDs replace SUDs — they don't add on top. When you purchase a CUD, the committed resources receive the CUD discount rate, and the SUD no longer applies to those resources. Only your non-committed usage (above the CUD amount) continues to receive SUDs. This is why 1-year CUDs (20% off) are actually worse than SUDs (30% off) for always-on workloads.

### Can I cancel or modify a CUD after purchasing?

No. Standard CUDs (1-year and 3-year) are non-cancellable and non-modifiable. Once purchased, you pay for the committed resources for the full term regardless of whether you use them. Flex CUDs are also non-cancellable, but their shorter terms (3-9 months) limit the exposure window. This is why conservative sizing is critical — you can always buy additional CUDs later, but you cannot reduce existing ones.

### How do CUDs work with GKE and Kubernetes?

CUDs apply to the underlying Compute Engine VMs that make up your GKE node pools. If you run a GKE Standard cluster with N2 node pools in us-central1, an N2 CUD in that region covers those nodes. For GKE Autopilot, the pricing model is different — Google manages the infrastructure, and CUDs don't directly apply. If you're planning a migration from GKE Standard to Autopilot, factor that into your commitment decision. Additionally, CUD sharing across projects means your GKE project can benefit from CUDs purchased elsewhere in the same billing account.

### What happens if I use more resources than my CUD covers?

Usage above your committed amount simply runs at normal pricing with SUDs applied. There's no penalty for exceeding your commitment — you just don't get the CUD rate on the excess. This is actually the ideal scenario: you've optimally sized your CUD to cover your baseline, and variable usage above that gets the automatic 30% SUD. Think of CUDs as covering your floor, with SUDs catching everything above.

### Should I buy separate CUDs for vCPUs and memory, or always bundle them?

GCP CUDs commit to vCPUs and memory independently. You can buy 32 vCPUs and 64 GB memory, or 32 vCPUs and 256 GB memory, depending on your workload profile. The key is to match your commitment ratio to your actual machine type ratio. If you run n2-standard-8 instances (8 vCPUs, 32 GB memory = 1:4 ratio), commit at a 1:4 ratio. If you commit to 32 vCPUs but only 64 GB memory while running standard instances that need 128 GB, you'll get the CUD rate on CPUs but pay SUD rates on the unmatched memory. Always check your actual vCPU-to-memory ratio before purchasing.

---

GCP's discount landscape rewards teams that understand the interactions between these three mechanisms. The optimal strategy for most organizations is straightforward: let SUDs handle your variable workloads for free, buy 3-year CUDs sized conservatively for your rock-solid baseline, and use Flex CUDs for medium-term projects where you want savings without long-term risk. Skip 1-year CUDs entirely for always-on workloads — they're a trap that costs more than doing nothing.

The biggest savings don't come from picking the perfect commitment level. They come from knowing which workloads should be committed at all versus which should be rightsized, rescheduled, or eliminated entirely. Start with waste removal, stabilize your usage, then commit to what remains.
