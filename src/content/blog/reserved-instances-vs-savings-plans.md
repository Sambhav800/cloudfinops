---
title: "Reserved Instances vs Savings Plans: Which One Actually Saves More (and When to Buy Neither)"
slug: "reserved-instances-vs-savings-plans"
excerpt: "The most expensive FinOps mistake isn't wasted compute. It's buying a 3-year reservation for a resource you should have deleted. Here's how to decide between RIs, Savings Plans, and staying on-demand."
category: "Cloud Cost Optimization"
author:
  name: "Nishant Jain"
  role: "Co-Founder & CTO"
  avatar: "/images/team/nishant.png"
publishedAt: "2026-08-14"
updatedAt: "2026-08-14"
readTime: 13
featured: false
tags: ["reserved-instances", "savings-plans", "aws", "azure", "commitment-discounts", "finops"]
---

## The Commitment Trap

A team spends $12,000/month on EC2. Someone reads that Reserved Instances save 40%. They buy a 3-year All Upfront RI for their largest instance. Three months later, the application migrates to containers. The instance gets terminated. The reservation keeps charging for 33 more months.

That reservation just cost them $20,000 more than on-demand would have.

This happens constantly. AWS doesn't publish how much money companies waste on unused reservations, but internal FinOps teams at large companies estimate 8-15% of their total commitment spend goes to reservations that outlive the workloads they were bought for.

The question isn't "should I buy commitments?" (yes, for stable workloads). The question is "how do I know which workloads are stable enough to commit to?"

## How Commitment Discounts Work (All Three Clouds)

Every major cloud provider offers the same basic trade: commit to spending a certain amount or using a certain resource for 1-3 years, and they'll give you 20-72% off.

| Provider | Commitment Type | Discount Range | Flexibility |
|---|---|---|---|
| AWS | Compute Savings Plans | 20-30% (1yr), 40-54% (3yr) | Any instance family, size, OS, region |
| AWS | EC2 Instance Savings Plans | 30-40% (1yr), 55-62% (3yr) | Any size within a specific family + region |
| AWS | Reserved Instances (Standard) | 30-40% (1yr), 55-72% (3yr) | Locked to specific instance type + region |
| AWS | Reserved Instances (Convertible) | 20-30% (1yr), 40-54% (3yr) | Exchangeable for different types |
| Azure | Reservations | 30-72% (1yr/3yr) | Locked to VM series + region |
| Azure | Savings Plans | 20-35% (1yr/3yr) | Flexible across VM families |
| GCP | Committed Use Discounts (CUDs) | 20-57% (1yr/3yr) | Locked to machine family + region |
| GCP | Sustained Use Discounts | Up to 30% | Automatic (no commitment required) |

## The Decision Framework: When to Commit vs. Stay On-Demand

Buying a commitment is an investment decision. Like any investment, you need to understand: what's the upfront cost, what's the payback period, and what's the risk of the underlying asset becoming worthless?

### The 90-Day Rule

**Never buy a commitment for any workload that hasn't run continuously for at least 90 days.**

Here's why: workloads that have been stable for 90 days have proven they're not experiments, demos, or temporary migrations. They've survived at least one architecture review, one quarter-end resource audit, and multiple deployment cycles. The probability of them running for another 12 months is high.

Workloads running for less than 90 days have a much higher chance of being modified, migrated, or terminated.

### The Stability Score

Before buying any commitment, check these signals:

| Signal | Stable (Buy) | Unstable (Don't Buy) |
|---|---|---|
| Instance type changed in last 90 days? | No | Yes |
| Running 24/7 without stops? | Yes | Intermittent |
| CPU utilization consistent (CV < 30%)? | Yes | Highly variable |
| Tagged as production? | Yes | Dev/staging/experiment |
| Application roadmap mentions migration? | No migration planned | Container/serverless migration coming |
| Team size and growth rate | Stable team | Rapidly hiring (architecture will change) |

Score each signal. If you get 5/6 or 6/6 "Stable" answers, commit. If you get 4/6, consider a 1-year plan with flexibility. Below 4/6, stay on-demand.

## Savings Plans vs Reserved Instances: The Real Comparison

### Savings Plans (Recommended for Most Teams)

Savings Plans commit you to a **dollar amount per hour** of compute usage. If you commit to $10/hour, AWS gives you a discount on the first $10/hour of eligible compute, regardless of which instances are running.

**Pros:**
- Instance family, size, OS, and region can all change without breaking the commitment
- Automatically applies to the cheapest combination of running instances
- Works across EC2, Fargate, and Lambda
- Lower risk than RIs because your architecture can evolve

**Cons:**
- Slightly lower discount than Standard RIs (about 5-10% less savings)
- Still requires a 1-year or 3-year term
- Underutilized if your total compute spend drops below the committed amount

**Best for:** Teams whose workloads are stable in total spend but might change instance types, teams migrating to containers, teams that don't want to manage individual RI lifecycles.

### Reserved Instances (Higher Savings, Higher Risk)

RIs commit you to a **specific instance type** in a **specific region** for 1-3 years.

**Pros:**
- Maximum discount (up to 72% for 3-year all-upfront Standard RI)
- Capacity reservation option (guaranteed instance availability)
- Can be sold on the AWS Marketplace if you no longer need them

**Cons:**
- Locked to a specific instance type (m5.xlarge RI doesn't cover m6i.xlarge)
- Region-locked (us-east-1 RI doesn't cover eu-west-1)
- No refunds if workload changes
- Management overhead: tracking which RIs cover which instances

**Best for:** Databases (rarely change instance type), long-running production workloads with zero chance of migration, teams that want maximum savings and are confident in stability.

### The Hybrid Approach (What Smart Teams Do)

1. **Compute Savings Plans** for 60% of your stable baseline (flexible, lower risk)
2. **EC2 Instance Savings Plans** for 20% of your baseline (known instance families, moderate discount)
3. **On-demand** for the remaining 20% (handles variability and new workloads)

Never commit more than 80% of your baseline. The 20% buffer protects you from paying for commitments that outlive workloads.

## How to Calculate Your Stable Baseline

Your "stable baseline" is the minimum compute spend that runs every hour of every day. Here's how to find it:

```bash
# AWS: Get hourly compute cost for the last 90 days
aws ce get-cost-and-usage \
  --time-period Start=2026-05-10,End=2026-08-10 \
  --granularity HOURLY \
  --metrics "UnblendedCost" \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Elastic Compute Cloud - Compute"]}}' \
  --output json > hourly_compute.json
```

From this data:
- **P10 (10th percentile)** of hourly spend = your rock-solid baseline (commit at this level with 1-year plans)
- **P50 (median)** of hourly spend = your typical baseline (commit up to 60% of this with 1-year plans)
- **P90** = your peak (never commit above this; use on-demand/spot for peaks)

**Example:**
- Hourly compute costs range from $8/hour (night minimum) to $25/hour (peak)
- P10 = $9.50/hour, P50 = $14/hour, P90 = $22/hour
- Commit: $9.50/hour in Compute Savings Plans (covers the absolute minimum)
- Optionally: another $3/hour in EC2 Savings Plans (up to 60% of P50 = $8.40 total)
- Result: $12.50/hour committed, saving 30-40% on that portion, on-demand for peaks

## The Break-Even Math

Before any commitment purchase, calculate the break-even point:

**For No-Upfront 1-Year RI (30% discount):**
- Monthly RI cost: $100 (discounted from $143 on-demand)
- Monthly savings: $43
- Break-even: Immediate (you save from day 1)
- Risk: If you terminate after 6 months, you still save $258 over that period

**For All-Upfront 3-Year RI (60% discount):**
- Upfront cost: $2,500
- Equivalent on-demand over 3 years: $6,200
- Monthly savings: $103
- Break-even: Month 24 (you need to run for 2 years just to recoup the upfront payment)
- Risk: If workload ends after 18 months, you've lost $650

**The rule of thumb:** No-upfront 1-year commitments have nearly zero risk. All-upfront 3-year commitments only make sense for databases and core infrastructure that genuinely won't change for 3 years.

## Azure Reservations: Key Differences

Azure Reservations work similarly to AWS RIs but with a few important differences:

1. **Cancellation is possible** (unlike AWS). You can cancel an Azure Reservation with a 12% early termination fee after 60 days. This dramatically reduces the risk.

2. **Instance size flexibility** within a VM family. A Standard_D4s_v3 reservation covers any D-series v3 in the same region (proportional coverage).

3. **Exchange policy.** You can exchange a reservation for a different VM series without canceling. The remaining value transfers.

4. **Scope options:** Single subscription, shared across subscriptions in a billing account, or specific resource group.

**When to use Azure Reservations over Savings Plans:**
- You want the cancellation safety net (12% fee is acceptable vs. AWS's zero flexibility)
- Your VMs stay within the same family (D-series, E-series) but might change size
- You need capacity reservation (guaranteed VM availability in the region)

## GCP Committed Use Discounts: Key Differences

GCP CUDs are the simplest form:

1. **No upfront payment.** You commit to using X vCPUs and Y GB memory in a region for 1 or 3 years. GCP bills you the discounted rate monthly.

2. **Resource-based, not dollar-based.** You commit to "16 vCPUs + 64GB memory in us-central1" rather than "$X/hour of compute."

3. **Sustained Use Discounts (SUDs) are automatic.** If you run an instance for 25%+ of the month, GCP automatically gives you 10-30% off. No commitment needed. CUDs stack on top of SUDs.

4. **Spend-based CUDs** (newer option) work like AWS Compute Savings Plans. Commit to $/hour across all compute.

**GCP recommendation:** Start with SUDs (automatic, zero risk). Add spend-based CUDs after 90 days of stable spend data.

## Common Mistakes That Cost Real Money

### Mistake 1: Buying RIs for over-provisioned instances

You have an m5.2xlarge running at 15% CPU. You buy a 3-year RI for it. You've now locked yourself into 3 years of paying for an over-provisioned instance. You should have rightsized to m5.large FIRST, then committed.

**Rule: Always rightsize before committing. Never commit to waste.**

### Mistake 2: Committing to more than 80% of baseline

Your baseline is $10/hour. You commit $10/hour in savings plans. Your team optimizes and reduces to $7/hour. Now you're paying for $3/hour of unused commitment. Or your baseline drops during a slow quarter.

**Rule: Commit to 60-70% of your P10 baseline. Leave buffer for optimization and variability.**

### Mistake 3: Ignoring the 3-year discount because "things change"

Things change, but some things don't. Your production PostgreSQL RDS instance has been the same db.r5.2xlarge for 18 months. It will still be that for another 3 years. Not buying a 3-year RI for that database is leaving 60% savings on the table.

**Rule: For databases and core infrastructure that hasn't changed in 6+ months, 3-year commitments are almost always correct.**

### Mistake 4: Not tracking commitment utilization

You bought RIs 8 months ago. Are they actually being used? If an instance was terminated and the RI is unused, you need to either (a) launch a new instance of that type, (b) sell the RI on the marketplace (AWS), or (c) exchange it (Azure).

**Rule: Check RI/SP utilization monthly. Target >95% utilization. Below 80% means you over-committed.**

## The Right Order of Operations

Most teams get this backwards. They hear "RIs save 40%" and immediately buy commitments. The correct order:

1. **Eliminate waste first** (terminate zombies, delete orphaned resources)
2. **Rightsize what remains** (reduce over-provisioned instances to right-fit)
3. **Schedule non-production** (stop dev/test outside business hours)
4. **Measure the new baseline** (wait 30-60 days to see stable spend)
5. **Then commit** (Savings Plans for flexibility, RIs for max savings on stable workloads)

If you commit before steps 1-3, you're locking in waste. You're paying 60% less for a resource you shouldn't be running at all. That's not a savings. That's a smaller version of the same problem.

## FAQ

### Can I sell unused AWS Reserved Instances?

Yes. AWS allows you to list Standard RIs (not Convertible) on the Reserved Instance Marketplace. You set the price, and other AWS customers can buy your remaining term. Typically sells at 5-15% below the equivalent AWS direct price. It takes a few days to a few weeks to find a buyer depending on the instance type and remaining term.

### What happens if my usage exceeds my Savings Plan commitment?

You get the discounted rate up to your commitment amount. Usage above the commitment is charged at normal on-demand rates. You don't pay penalties. This is why Savings Plans are lower risk than RIs: you never pay more than on-demand, you just stop getting the discount above your committed amount.

### Should a startup with 6 months of runway buy reserved instances?

Probably not. A 1-year commitment when you have 6 months of runway means you're betting on raising your next round before the commitment expires. If fundraising takes longer than expected, you're stuck paying for cloud resources with money you don't have. Wait until you have 18+ months of runway before making 1-year commitments.

### How do I know if my savings plan is being utilized properly?

AWS provides a "Savings Plans Utilization" report in Cost Explorer. Target >95%. If utilization drops below 80% for more than 2 weeks, you either over-committed or your workload pattern changed. Azure provides similar reporting under "Reservations" in the Azure portal.

### Is it better to buy many small commitments or one large one?

Many small commitments. If you need 100 vCPUs of committed capacity, buy 10 separate 10-vCPU reservations expiring on different months. This way, if your needs change, you only lose one small reservation instead of one large one. It also gives you monthly opportunities to adjust your commitment level up or down.
