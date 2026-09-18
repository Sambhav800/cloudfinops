---
title: "Cloud Waste Is Rising Again for the First Time in 5 Years — And the Easy Wins Are Gone"
slug: "cloud-waste-rising-again-2026"
excerpt: "Flexera 2026 data shows cloud waste back up to 29% — the first increase in five consecutive years. The easy optimizations have been found. What's left requires a fundamentally different approach."
category: "FinOps"
author:
  name: "Nishant Jain"
  role: "Co-Founder & CTO"
  avatar: "/images/team/nishant.png"
publishedAt: "2026-09-18"
readTime: 9
featured: false
tags: ["finops", "cloud-cost-optimization", "cloud-waste", "aws", "azure", "gcp", "reserved-instances"]
---

## The Trend Nobody Expected

For five consecutive years, the percentage of cloud spend wasted trended down. FinOps programs matured, teams got better at rightsizing, commitment discount adoption improved. The trajectory was clear and encouraging.

Then 2026 happened.

**Cloud waste is back up to 29%** (Flexera 2026). The first increase in five years. Against a total public cloud spend of $723 billion, that's over $200 billion in annual waste — and it's moving in the wrong direction.

This isn't a story about teams getting lazier or FinOps losing momentum. It's a story about what happens when the obvious wins run out.

## Why Waste Is Rising Despite More FinOps Programs

The FinOps Foundation's 2026 State of FinOps report captured it precisely in a practitioner quote that should be read by every cloud leader:

> *"We have hit the 'big rocks' of waste and now face a high volume of smaller opportunities that require more effort to capture."*

The big rocks were the easy ones. Forgotten dev instances running 24/7. Massively overprovisioned production servers from the early cloud era. Reserved instances purchased for workloads that had been migrated or decommissioned. Unattached EBS volumes and elastic IPs that accrued because nobody cleaned up after deploys.

Those have been found. The teams that were going to find them have found them. The remaining waste is:
- Smaller per-resource dollar amounts
- Spread across hundreds or thousands of resources
- Requires cross-team coordination to fix
- Has legitimate business justifications that make automated deletion risky

And simultaneously, the cloud footprint is growing with new workload types — containers, serverless, AI infrastructure — that generate waste in new ways that existing FinOps tooling wasn't designed to detect.

## The Specific Waste That's Growing

Datadog's 2026 cloud cost analysis reveals exactly where the new waste is accumulating:

**Old-generation instance types.** 83% of organizations still run older-generation EC2 instances, and these instances represent 17% of EC2 spend. Moving from m4 to m6i or m7i typically delivers 10-20% better price/performance with zero workload changes. This is a known optimization that somehow persists across the majority of enterprises.

**gp2 volumes instead of gp3.** 58% of average EBS spend still goes to gp2 volumes, despite gp3 costing approximately 20% less and delivering better baseline performance. Amazon has been recommending this migration since 2020. Six years later, the majority of EBS spend hasn't moved.

**Cross-AZ data transfer.** 98% of organizations incur cross-availability-zone data transfer charges. This cost is nearly half of all data transfer costs. It's created by architectural decisions — services in different AZs calling each other — that are rarely reviewed after initial deployment.

**Commitment discount underuse.** Only 67% of organizations use commitment-based discounts (RIs, Savings Plans, CUDs) — down from 72% the prior year. Among those that do, only 29% cover more than half their eligible spend. The organizations that should be capturing 30-50% discounts on predictable workloads are paying full on-demand rates instead.

These four categories share a common characteristic: they're all technically known issues that haven't been fixed because fixing them requires sustained operational work rather than a one-time audit.

## Why Commitment Adoption Dropped

The drop in commitment discount usage from 72% to 67% is particularly telling.

Commitments require confidence in future usage. If you're not sure a workload will still be running at its current scale in 12 months — because you're evaluating AI alternatives, running a migration, considering a consolidation — you'll avoid the commitment rather than risk paying for capacity you won't use.

This is rational behavior at the individual decision level. But aggregated across an organization, it means paying full on-demand rates for workloads that are actually stable, because the team managing them doesn't have enough visibility into the broader portfolio to feel confident making a commitment.

The irony: the organizations with the least cost visibility are also the ones least likely to capture commitment discounts — which means they pay more, which makes the cost problem worse, which reduces the appetite for investing in the visibility tooling that would enable better commitment decisions.

## What Advanced Teams Are Doing Instead

The practitioners at the frontier of FinOps have shifted their focus from finding waste to preventing it from being created in the first place.

**One advanced practitioner quoted in the State of FinOps report had reached 97% optimization in their Cost Optimization Hub.** The remaining 3% was intentionally left alone for legitimate business reasons. They got there not by running better audits — by making cost-conscious infrastructure decisions the default behavior for every engineer deploying to production.

The specific mechanisms:
- **Pre-deploy cost estimates** integrated into CI/CD pipelines (flagged as the #2 most-needed missing tooling capability by practitioners)
- **Instance-type selection guardrails** that default to current-generation instances and require justification for older types
- **Automated commitment management** that continuously analyzes eligible spend and purchases savings plans without requiring manual decision-making
- **Tagging enforcement** at deploy time rather than retroactive tagging campaigns

The common thread is shifting the work upstream. Retroactive optimization is expensive — it requires identifying resources, getting ownership, coordinating changes, sometimes requiring application modifications. Preventive optimization is cheap — it's a configuration change that makes the right behavior the default.

## The Organizational Shift That's Required

There's a cultural component to the rising waste trend that tooling alone won't fix.

Cloud cost optimization delivered obvious wins for years. Teams could spend a day on rightsizing and find five-figure monthly savings. That created organizational habits: periodic audits, reactive optimization, end-of-quarter reviews.

The 2026 problem requires continuous, distributed attention across engineering. Every team managing infrastructure needs to own their costs with the same diligence they apply to performance and reliability metrics. That's a fundamentally different operating model from "the FinOps team runs a quarterly audit."

The organizations that will reverse the rising waste trend are the ones that build cost visibility into their normal engineering workflow — not as a separate FinOps function, but as a native part of how they build and operate software.

## Five Things That Are Still Easy Wins in 2026

Despite the "easy wins are gone" narrative, there are still some straightforward optimizations that many organizations haven't touched:

1. **gp2 → gp3 migration.** Run `aws ec2 describe-volumes --filters Name=volume-type,Values=gp2` in each region. Everything that comes back is a candidate for an in-place type change with no downtime.

2. **gp3 → gp3 right-sizing.** gp3 volumes are often over-provisioned on IOPS and throughput beyond what workloads use. Baseline IOPS (3000) and throughput (125 MB/s) cover the majority of database and application workloads. Provisioned additions above baseline cost extra and are frequently unnecessary.

3. **Old-generation EC2 instance swap.** Filter your EC2 inventory for m4, c4, r4, t2 instance types. These are all more expensive and slower than their current-generation equivalents. The swap is usually zero-risk and takes 10 minutes per instance.

4. **Savings Plan coverage analysis.** In AWS Cost Explorer → Savings Plans → Coverage. The "Uncovered" column shows you on-demand spend eligible for commitment discounts. If coverage is below 70% on any instance family with consistent usage, you're leaving 20-40% on the table.

5. **Cross-AZ traffic audit.** Enable VPC Flow Logs and filter for inter-AZ traffic. The top talkers are your cross-AZ optimization candidates. Deploying application components in the same AZ as the services they call most frequently eliminates the transfer cost with no behavioral change.

None of these require new tooling. They require 2-3 hours of focused attention.

The bigger question is why they haven't been done already — and that answer usually comes back to the same thing: no visibility, no ownership, no feedback loop. Fix the visibility and the optimizations follow.

---

*CloudFinOps automatically identifies old-generation instances, gp2 volumes, commitment coverage gaps, and cross-AZ traffic patterns across your entire cloud footprint — and assigns ownership so the right team can act. [Scan your cloud bill free](/bill-scan) to see your waste breakdown in 30 seconds.*
