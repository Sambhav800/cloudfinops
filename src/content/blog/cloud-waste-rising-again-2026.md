---
title: "Cloud Waste Is Rising Again for the First Time in 5 Years — And the Easy Wins Are Gone"
slug: "cloud-waste-rising-again-2026"
excerpt: "Flexera 2026 data shows cloud waste back at 29% — the first increase in five consecutive years. Old-generation instances, gp2 volumes, abandoned commitments, and cross-AZ traffic are the new frontier. Here's what's driving the increase and what actually works now."
category: "FinOps"
author:
  name: "Nishant Jain"
  role: "Co-Founder & CTO"
  avatar: "/images/team/nishant.png"
publishedAt: "2026-09-18"
updatedAt: "2026-09-18"
readTime: 15
featured: false
tags: ["finops", "cloud-cost-optimization", "cloud-waste", "aws", "azure", "gcp", "reserved-instances", "savings-plans"]
---

## The Trend Nobody Expected to Reverse

For five consecutive years, the percentage of cloud spend wasted trended in the right direction. FinOps teams matured. Rightsizing became standard practice. Reserved instances and Savings Plans adoption grew. The narrative was clear: FinOps is working, waste is declining.

Then Flexera's 2026 State of the Cloud Report landed: **cloud waste is back up to 29%.**

The first increase in five years. Against global public cloud spend of approximately $723 billion (2026), that 29% figure represents over $200 billion in annual waste. Moving in the wrong direction.

The immediate question is: why? FinOps programs haven't gotten worse. Most organizations are doing more formal cost management than they did two years ago. Yet waste is rising.

The answer, captured perfectly in a practitioner quote from the FinOps Foundation's 2026 State of FinOps report:

> *"We have hit the 'big rocks' of waste and now face a high volume of smaller opportunities that require more effort to capture."*

The easy wins ran out. What replaced them is harder, more distributed, and requires a fundamentally different operational approach.

## What Changed: The Anatomy of New Waste

The old categories of cloud waste were high-dollar, high-visibility, and relatively easy to fix. An idle dev instance running 24/7. A massively overprovisioned production server from the early cloud era. An RI purchased for a workload that was decommissioned six months ago.

The characteristics these shared: each one was individually significant in dollar terms, could be found with a simple audit, and had a clear owner who could action it.

The new waste landscape is different on all three dimensions. Datadog's 2026 cloud cost analysis documents exactly where the budget is leaking now.

### Old-Generation Instance Types: $170 for Every $1,000 Spent

**83% of organizations still run older-generation EC2 instances.** These instances represent 17% of EC2 spend — not trivial — despite current-generation equivalents being both cheaper and more performant.

The instances in question: m4, c4, r4, t2, and similar. Their current-generation replacements (m6i, c6i, r6i, t3/t4g) typically deliver 10-20% better price/performance. In many cases, the current-generation instance with equivalent specs costs less *and* runs faster.

The reason this persists despite being a known issue: old-generation instances are not broken. They're running the workloads they were originally deployed for, those workloads are still working, and the instance refresh fell off the priority list. Every quarter, it gets pushed below more urgent engineering work. Every quarter, you pay a 15-20% performance/cost premium for the privilege of not doing the migration.

Identifying them:

```bash
# AWS: Find all old-generation instances
aws ec2 describe-instances \
  --filters \
    "Name=instance-state-name,Values=running" \
    "Name=instance-type,Values=m4.*,c4.*,r4.*,t2.*,i2.*,d2.*,m3.*,c3.*" \
  --query 'Reservations[].Instances[].[InstanceId,InstanceType,Tags[?Key==`Name`]|[0].Value]' \
  --output table

# Cost by instance generation (requires Cost Explorer with resource IDs enabled)
aws ce get-cost_and_usage \
  --time-period Start=2026-09-01,End=2026-09-30 \
  --granularity MONTHLY \
  --filter '{"Dimensions":{"Key":"INSTANCE_TYPE","Values":["m4.large","m4.xlarge","c4.large","t2.micro","t2.small","t2.medium","t2.large"]}}' \
  --metrics UnblendedCost \
  --group-by '[{"Type":"DIMENSION","Key":"INSTANCE_TYPE"}]'
```

Fixing them requires a coordinated migration (stop → resize → start or snapshot → new instance launch), which can be done with zero downtime using a rolling approach. For most EC2 workloads, the migration from m4 to m6i or c4 to c6i involves no application changes — it's an infrastructure-only change that takes 15-30 minutes per instance.

The question to ask your infrastructure team: do we have a tracked inventory of every instance generation we're running, and do we have a migration timeline for anything pre-generation-5?

### gp2 EBS Volumes: The 20% Premium Nobody Fixed

**58% of average EBS spend still goes to gp2 volumes**, despite gp3 being available since December 2020 and costing approximately 20% less with better baseline performance (Datadog, 2026).

gp3 provides:
- Baseline: 3,000 IOPS and 125 MB/s throughput (same as gp2 at max free IOPS)
- Cost: $0.08/GB-month vs gp2's $0.10/GB-month
- Additional IOPS: Purchasable separately, only if needed
- Additional throughput: Purchasable separately, only if needed

For the majority of database and application workloads that don't need more than 3,000 baseline IOPS, gp3 is strictly better than gp2 — lower cost, same performance. For workloads that were purchasing provisioned IOPS on gp2 to get above 3,000 IOPS, gp3 is dramatically cheaper because the baseline IOPS are included.

gp2 volumes can be converted to gp3 in-place, online, with no downtime. This is a 5-minute operation per volume.

```bash
# Find all gp2 volumes in a region
aws ec2 describe-volumes \
  --filters Name=volume-type,Values=gp2 \
  --query 'Volumes[].[VolumeId,Size,State,Attachments[0].InstanceId]' \
  --output table

# Convert a single gp2 to gp3 (no downtime)
aws ec2 modify-volume \
  --volume-id vol-0123456789abcdef0 \
  --volume-type gp3

# Bulk convert all gp2 volumes to gp3 (careful — review first)
aws ec2 describe-volumes \
  --filters Name=volume-type,Values=gp2 \
  --query 'Volumes[].VolumeId' \
  --output text | xargs -I {} aws ec2 modify-volume --volume-id {} --volume-type gp3
```

For a team with 500 gp2 volumes averaging 200GB each, the savings from a complete gp2→gp3 migration: **$10,000/month**. This is a half-day of work.

The reason this persists six years after gp3 launched: no one told the teams managing those volumes that they were paying a 20% premium. The volumes kept working. Without active cost visibility, there's no signal to trigger the optimization.

### Cross-Availability Zone Data Transfer: The Hidden $200K Bill

**98% of organizations incur cross-AZ data transfer charges.** This cost category is nearly half of all data transfer costs (Datadog, 2026) — yet it's almost never discussed in cost reviews because it's buried in the "Data Transfer" line item and doesn't have resource-level attribution in standard billing reports.

AWS charges $0.01/GB for data transferred between availability zones within the same region. That sounds trivial. It isn't.

A microservices architecture where Service A in us-east-1a calls Service B in us-east-1b for every request, generating 100GB of cross-AZ transfer per day, costs $30/day → **$900/month from one service pair**. Scale this across a typical production microservices environment with dozens of service-to-service calls, and cross-AZ transfer costs routinely reach $50K-$200K/month.

How it happens: Kubernetes, ECS, and other container orchestrators distribute pods across AZs for availability. When a pod in AZ-a calls a pod in AZ-b, cross-AZ charges accrue. The application developer never sees these charges — they're at the infrastructure layer, invisible to application-level monitoring.

Finding your cross-AZ traffic:

```bash
# Enable VPC Flow Logs if not already enabled
aws ec2 create-flow-logs \
  --resource-type VPC \
  --resource-ids $VPC_ID \
  --traffic-type ALL \
  --log-destination-type cloud-watch-logs \
  --log-group-name /aws/vpc/flowlogs

# Query cross-AZ traffic in CloudWatch Logs Insights
# (after flow logs are enabled and collecting data)
# Fields: srcaddr, dstaddr, bytes, action
# Filter: look for traffic where src and dst are in different AZ subnets
```

A faster signal: use AWS Cost Explorer to look at "Data Transfer - Inter AZ" under the EC2 data transfer breakdown. Sort by region. The top entries are your cross-AZ cost centers.

The fix for high cross-AZ traffic between specific service pairs: **AZ affinity in Kubernetes scheduling.**

```yaml
# Kubernetes service topology: prefer same-AZ routing
apiVersion: v1
kind: Service
metadata:
  name: backend-service
spec:
  selector:
    app: backend
  ports:
  - port: 80
  # Route to same-AZ pods first, other AZs as fallback
  topologyKeys:
    - "topology.kubernetes.io/zone"
    - "*"
```

For service pairs with very high cross-AZ transfer, co-locate them in the same AZ entirely. This requires availability trade-offs (you lose multi-AZ redundancy for this service pair), but for stateless services that can be horizontally scaled within a single AZ, it's often the right call.

### Commitment Discount Coverage: A Step Backward

**Commitment discount usage dropped from 72% to 67%** of organizations (Datadog, 2026). Among those using them, **only 29% cover more than half their eligible spend.**

This is particularly concerning because commitment discounts (AWS Savings Plans and RIs, Azure RIs, GCP CUDs) are arguably the highest-ROI optimization available for stable workloads — 20-40% savings with zero engineering effort beyond the purchase decision.

Why did adoption drop?

The primary cause: uncertainty about future usage. Teams evaluating AI alternatives, planning migrations, or running cost optimization programs that might change their instance mix are reluctant to commit 12 months of usage. The risk of paying for capacity you no longer need outweighs the savings.

The secondary cause: the tooling gap. Identifying the right commitment type, size, and payment option requires analysis most teams do manually — if at all. A commitment that saves $3,000/month but takes 20 hours of analysis work to size correctly gets deprioritized against operational work with more immediate impact.

The third cause: coverage analysis complexity. Organizations with multiple AWS accounts, multiple regions, and mixed instance families need to understand how Savings Plan coverage aggregates across their portfolio before sizing a purchase. Without proper tooling, this analysis is error-prone enough that teams avoid it.

The practical impact: organizations with $500K/month of eligible EC2 spend and 40% commitment coverage are paying $100K+/month in avoidable on-demand charges — costs they could lock in at 25-40% discount with a straightforward coverage analysis.

**Finding your commitment coverage gap:**

```bash
# AWS Savings Plans coverage (shows what % of eligible spend is covered)
aws ce get-savings-plans-coverage \
  --time-period Start=2026-08-01,End=2026-09-01 \
  --granularity MONTHLY \
  --group-by '[{"Type":"DIMENSION","Key":"INSTANCE_FAMILY"}]'

# Reserved Instance coverage by instance type
aws ce get-reservation-coverage \
  --time-period Start=2026-08-01,End=2026-09-01 \
  --granularity MONTHLY \
  --group-by '[{"Type":"DIMENSION","Key":"INSTANCE_TYPE"}]'
```

The output shows `OnDemandHours` and `TotalHours` per instance family. Any family with a significant gap — `OnDemandHours` representing more than 40% of `TotalHours` on stable, predictable workloads — is a candidate for incremental commitment purchases.

The right approach for most teams: **start with Compute Savings Plans** (most flexible — applies across instance families, regions, and services) and **size conservatively** (cover your P25 baseline usage, not your average). You can always buy more coverage later. Over-committing is painful.

```bash
# Get Savings Plans recommendations from AWS
aws ce get-savings-plans-purchase-recommendation \
  --savings-plans-type COMPUTE_SP \
  --term-in-years ONE_YEAR \
  --payment-option NO_UPFRONT \
  --lookback-period-in-days SIXTY_DAYS

# This returns the recommended hourly commitment amount and projected savings
```

## The Structural Problem: Cost Feedback Loops Are Broken

All of the waste categories above share a root cause: the person making the cost-creating decision has no visibility into the cost impact of that decision.

A developer deploying a new service on a t2.medium instance (old generation) doesn't know it costs 15% more than a t3.medium. There's no prompt at deploy time. There's no monthly report to their team. There's no cost review process where someone would notice.

An SRE provisioning 2TB of gp2 EBS for a new database doesn't know it costs $200/month more than gp3. The default was gp2 when they learned Terraform. Nobody updated the module. The configuration persists unchanged across hundreds of resources.

The State of FinOps 2026 identifies **pre-deployment architecture costing** as the second most-requested missing capability in FinOps tooling — behind only AI cost attribution. The industry knows the problem. Building the solution is still in progress at most organizations.

One practitioner in the report had reached 97% optimization in their Cost Optimization Hub. The remaining 3% was intentionally left alone for legitimate business reasons. They got there not primarily through better tooling — but by making cost-visible infrastructure decisions the default behavior for every engineer deploying to production.

The mechanisms they used:
- Infrastructure module defaults updated to current-generation instances and gp3 volumes (passive — no decision required)
- PR cost estimates for infrastructure changes (active — costs visible at review time)
- Weekly team-level cost emails with 4-week trends (passive — creates awareness without action required)
- Quarterly rightsizing review with VPA/AWS Compute Optimizer recommendations (active — structured review cadence)

## What Advanced FinOps Teams Are Doing Differently

The organizations ahead of the curve on 2026-era cloud waste have made a specific strategic shift: they've moved from reactive optimization (find waste, fix it) to preventive optimization (make waste the exception rather than the default).

This shift looks different operationally:

**Infrastructure modules that default to current-generation.** Your internal Terraform modules default to m6i, not m4. Your EBS module defaults to gp3, not gp2. Your EKS node group module defaults to current-generation instance types. New deployments are cost-optimal by default without requiring engineering teams to actively choose the right option.

**Commitment automation that removes the analysis burden.** AWS Cost Explorer recommendations plus a monthly 15-minute review process. GCP CUD recommendations are built into the Cloud Console. Azure Advisor surfaces RI recommendations. The analytical work has largely been automated — the bottleneck is acting on it, not knowing what to buy.

**Cross-AZ traffic detection in the CI/CD pipeline.** Architecture review bots that flag service-to-service calls where services are configured for multi-AZ deployment without AZ affinity — the architectural decision that generates cross-AZ charges.

**Tagging enforcement at deploy time.** Not retroactive tagging campaigns — admission webhooks that reject resources without required tags. No tag, no deploy. This sounds harsh until you consider that it's the only approach that achieves >95% tagging compliance.

## The Five Things That Are Still Easy Wins

Despite the "easy wins are gone" narrative, there are still straightforward optimizations that many organizations haven't addressed.

**1. gp2 → gp3 migration.** Check your current gp2 volume count and total storage. Multiply storage by $0.02/GB-month (the price difference). That's your monthly savings from a zero-risk, in-place, online volume type conversion.

**2. Old-generation instance refresh.** Filter your EC2 inventory for pre-gen-5 instances. These are all more expensive and slower than current-generation equivalents. The migration is zero-risk for stateless services.

**3. Savings Plan coverage analysis.** Pull the savings plans coverage report. Any instance family with >50% uncovered hours and stable, predictable usage is a commitment candidate. Start with a conservative purchase (P25 baseline) and expand coverage over subsequent months.

**4. Non-production cluster scheduling.** If your development and staging clusters run 24/7, implement scheduled scale-down for nights and weekends. This is purely operational — no code changes, no application impact.

**5. Data transfer breakdown review.** In AWS Cost Explorer, go to Service > EC2 > Data Transfer. Look for "Data Transfer - Inter AZ". If it's more than $1,000/month, investigate which service pairs are generating it.

None of these require new tooling. Each takes 2-4 hours of focused attention. Together, they typically recover 15-25% of current cloud spend.

The harder question is why they haven't been done already. The answer is almost always the same: costs are invisible to the people who can fix them, there's no review process that would surface them, and the consequences of doing nothing are invisible until the bill arrives.

Fix the visibility. The optimizations follow.

## Avoiding the Next 5-Year Reversal

The history of cloud cost management shows a consistent pattern: organizations optimize what they can see, waste accumulates in new categories they can't see, eventually the new categories become visible and get optimized. Then new waste categories emerge.

The 29% number today reflects waste in categories (AI, containers, cross-AZ transfer, old-generation instances) that weren't major cost centers five years ago. The 29% number five years from now will reflect waste in categories we can't fully anticipate yet — but will include whatever new infrastructure paradigm is standard by then.

The only sustainable defense is not periodic optimization campaigns but continuous cost visibility across every category. Not a quarterly FinOps review but weekly team-level cost awareness. Not an annual commitment analysis but an automated commitment management process.

The organizations that build those feedback loops now will not face a reversal when the next new infrastructure category generates its first surprise bill. They'll already be watching.

---

*CloudFinOps automatically identifies old-generation instances, gp2 volumes, commitment coverage gaps, and cross-AZ traffic patterns across your entire cloud footprint — and surfaces them to the team responsible, not just the FinOps dashboard. [Scan your cloud bill free](/bill-scan) to see your waste breakdown in under 60 seconds.*
