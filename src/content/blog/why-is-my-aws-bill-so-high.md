---
title: "Why Is My AWS Bill So High? 7 Common Causes and How to Fix Them"
slug: "why-is-my-aws-bill-so-high"
excerpt: "Your AWS bill doubled and you don't know why. Here are the 7 most common reasons your cloud costs spike unexpectedly, with exact steps to find and fix each one."
category: "AWS"
author:
  name: "Nishant Jain"
  role: "Co-Founder & CTO"
  avatar: "/images/team/nishant.png"
publishedAt: "2026-08-10"
updatedAt: "2026-08-10"
readTime: 14
featured: false
tags: ["aws", "cost-optimization", "billing", "cost-spike", "ec2", "data-transfer"]
---

## The Moment You See the Number

You open the AWS console on a Monday morning. The billing dashboard shows a number that makes no sense. Last month you spent $4,200. This month's projection says $7,800. Nobody deployed anything new. Nobody approved a bigger instance. The number just... grew.

This happens to nearly every engineering team running production on AWS. The Flexera 2026 State of the Cloud Report found that 32% of cloud spend is wasted, and the average team doesn't notice cost spikes until 2-3 weeks after they start.

The good news: there are exactly 7 patterns that cause 90% of unexpected AWS bill increases. Each has a specific diagnostic path and a fix you can apply today.

## Cause 1: NAT Gateway Data Processing Charges

This is the single most common surprise on AWS bills. NAT Gateway charges $0.045 per GB of data processed, and if your private subnet instances talk to S3, DynamoDB, ECR, or any AWS service through the NAT Gateway instead of a VPC endpoint, you're paying egress fees for internal traffic.

**How it happens:**

Your VPC has private subnets (good security practice). Instances in those subnets need internet access, so you create a NAT Gateway. But now every API call to S3, every container image pull from ECR, every DynamoDB query routes through the NAT Gateway and incurs data processing charges.

A team pulling 50GB/day of data from S3 through a NAT Gateway pays $67.50/day ($2,025/month) for traffic that should cost $0.

**How to diagnose:**

```bash
# Check NAT Gateway costs in Cost Explorer
aws ce get-cost-and-usage \
  --time-period Start=2026-08-01,End=2026-08-10 \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["EC2 - Other"]}}' \
  --group-by Type=DIMENSION,Key=USAGE_TYPE
```

Look for `NatGateway-Bytes` in the output.

**How to fix:**

Create VPC endpoints for the services your instances talk to most:

```bash
# S3 Gateway Endpoint (FREE, eliminates most NAT traffic)
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-xxx \
  --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids rtb-xxx

# DynamoDB Gateway Endpoint (also FREE)
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-xxx \
  --service-name com.amazonaws.us-east-1.dynamodb \
  --route-table-ids rtb-xxx
```

S3 and DynamoDB gateway endpoints are completely free. Interface endpoints for ECR, SQS, SNS, etc. cost $0.01/hour + $0.01/GB, which is still 78% cheaper than NAT Gateway.

**Expected savings:** 40-80% reduction in "EC2 - Other" costs within 24 hours.

## Cause 2: Forgotten Dev/Test Environments Running 24/7

Every team has them. A staging environment someone spun up for a demo three months ago. A load testing cluster that ran for two days and nobody shut down. A personal dev instance that costs $0.50/hour (sounds cheap until you realize that's $365/month).

**How it happens:**

Developers create resources for testing with no shutdown schedule. There's no automated cleanup policy. The instances don't show up in anyone's daily workflow, so they run indefinitely. AWS doesn't remind you that something is running. The meter just ticks.

**How to diagnose:**

```bash
# Find all running EC2 instances with their launch time
aws ec2 describe-instances \
  --filters "Name=instance-state-name,Values=running" \
  --query "Reservations[].Instances[].{ID:InstanceId, Type:InstanceType, Launch:LaunchTime, Name:Tags[?Key=='Name']|[0].Value}" \
  --output table
```

Sort by LaunchTime. Anything running for 30+ days without the `Environment: production` tag is suspect.

**How to fix:**

1. Tag everything at creation time (enforce with Service Control Policies)
2. Set up AWS Instance Scheduler to stop dev/test instances outside business hours
3. Create a Lambda function that terminates untagged instances after 7 days

```bash
# Immediate: stop all instances tagged Environment=dev that have run 30+ days
aws ec2 describe-instances \
  --filters "Name=tag:Environment,Values=dev,staging,test" \
             "Name=instance-state-name,Values=running" \
  --query "Reservations[].Instances[?LaunchTime<='2026-07-10'].InstanceId" \
  --output text | xargs -n 1 aws ec2 stop-instances --instance-ids
```

**Expected savings:** 20-40% of your EC2 bill if you're a team of 5+ developers.

## Cause 3: EBS Volumes Attached to Stopped Instances (or Orphaned Entirely)

When you stop an EC2 instance, the compute charges stop. But the EBS volumes stay attached and keep charging you. When you terminate an instance, EBS volumes persist by default unless you explicitly set `DeleteOnTermination: true`.

**How it happens:**

The default EBS behavior on termination is to persist the root volume. Most teams don't change this. Over time, you accumulate dozens of orphaned volumes from terminated instances, plus all the volumes still attached to stopped instances that nobody will start again.

A single 1TB gp3 volume costs $80/month whether it's attached to a running instance or sitting completely unused.

**How to diagnose:**

```bash
# Find all unattached EBS volumes
aws ec2 describe-volumes \
  --filters "Name=status,Values=available" \
  --query "Volumes[].{ID:VolumeId, Size:Size, Type:VolumeType, Created:CreateTime}" \
  --output table

# Find total cost of orphaned volumes
aws ec2 describe-volumes \
  --filters "Name=status,Values=available" \
  --query "sum(Volumes[].Size)" \
  --output text
```

Multiply the total GB by $0.08 (gp3) or $0.10 (gp2) for your monthly waste.

**How to fix:**

1. Snapshot the volume first (if you might need the data):
```bash
aws ec2 create-snapshot --volume-id vol-xxx --description "Backup before cleanup"
```

2. Delete the orphaned volume:
```bash
aws ec2 delete-volume --volume-id vol-xxx
```

3. Prevent future orphans by setting `DeleteOnTermination` on all new instances.

**Expected savings:** $50-500/month depending on how many volumes you've accumulated.

## Cause 4: Data Transfer Between Availability Zones

This is the silent killer that doesn't show up as a separate line item until you dig into Cost Explorer. Inter-AZ data transfer costs $0.01/GB in each direction ($0.02 round trip). If your application architecture has services in different AZs talking to each other frequently, this adds up fast.

**How it happens:**

You deploy an application across multiple AZs for high availability (correct practice). But your services make thousands of API calls per second to each other across AZ boundaries. A microservice making 10,000 requests/second with 5KB payloads transfers 4.3TB/month across AZs, costing $86/month per service pair.

With 10 services, that's potentially $860/month just in inter-AZ chatter.

**How to diagnose:**

Look at your VPC Flow Logs or check Cost Explorer for data transfer line items:

```bash
aws ce get-cost-and-usage \
  --time-period Start=2026-08-01,End=2026-08-10 \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --filter '{"Dimensions":{"Key":"USAGE_TYPE","Values":["USE2-DataTransfer-Regional-Bytes"]}}' \
  --output table
```

**How to fix:**

- Use AZ-aware service discovery (prefer same-AZ replicas)
- Enable client-side caching for frequently requested data
- Consider running latency-sensitive services in a single AZ with failover rather than active-active across AZs
- Use ElastiCache or DynamoDB DAX to reduce cross-AZ database calls

**Expected savings:** 30-60% of data transfer costs, depending on architecture.

## Cause 5: CloudWatch Logs Ingestion and Storage

CloudWatch charges $0.50/GB for log ingestion and $0.03/GB/month for storage. If your application logs at DEBUG level in production, or your containers emit verbose health check logs, the costs compound quickly.

**How it happens:**

A developer enables debug logging to troubleshoot an issue and forgets to turn it off. A Kubernetes cluster with 50 pods, each logging 100MB/day, ingests 5GB/day ($2.50/day = $75/month) just for health checks and routine operations that nobody ever reads.

**How to diagnose:**

```bash
# Find your top log groups by stored bytes
aws logs describe-log-groups \
  --query "logGroups[?storedBytes > \`1000000000\`].{Name:logGroupName, StoredGB:storedBytes}" \
  --output table
```

**How to fix:**

1. Set retention policies on all log groups (7 days for dev, 30 days for prod, 90 days for compliance):
```bash
aws logs put-retention-policy \
  --log-group-name /aws/lambda/my-function \
  --retention-in-days 30
```

2. Filter verbose logs at the application level before they reach CloudWatch
3. For long-term storage, export to S3 ($0.023/GB vs $0.03/GB)
4. Use CloudWatch Logs Insights instead of storing everything "just in case"

**Expected savings:** 40-70% of CloudWatch costs.

## Cause 6: Idle or Over-Provisioned RDS Instances

RDS is often the second-largest line item on AWS bills, and it's the most commonly over-provisioned service. Teams provision for peak load, but peak might be 2 hours per day. The other 22 hours, you're paying for capacity you don't use.

**How it happens:**

During initial deployment, the team picks db.r5.xlarge because "we might need it." The application runs fine on 10% of that capacity. Nobody checks CloudWatch RDS metrics because "the database is working." Meanwhile, you're paying $550/month for a database that could run on db.t3.medium ($65/month).

**How to diagnose:**

```bash
# Check CPU utilization for your RDS instances (last 14 days)
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBInstanceIdentifier,Value=my-database \
  --start-time 2026-07-25T00:00:00Z \
  --end-time 2026-08-10T00:00:00Z \
  --period 3600 \
  --statistics Average Maximum \
  --output table
```

If the average is below 20% and the maximum is below 60%, you're over-provisioned.

**How to fix:**

1. Enable Performance Insights (free for 7 days retention) to understand actual workload
2. Downgrade by one instance class and monitor for 1 week
3. For dev/test databases: use Aurora Serverless v2 (scales to zero when idle)
4. For production: consider reserved instances after you've rightsized (30-60% savings)

**Expected savings:** 40-80% per database instance that's over-provisioned.

## Cause 7: Elastic IPs, Load Balancers, and Idle Network Resources

AWS charges for Elastic IPs that aren't attached to running instances ($3.65/month each since Feb 2024). It also charges for idle Application Load Balancers ($16.20/month minimum even with zero traffic). These are small individually but accumulate.

**How it happens:**

An engineer creates an ALB for a service that gets decommissioned. The ALB stays because "someone might need it." Elastic IPs get allocated for instances that are later terminated. Nobody audits these because each one costs less than a coffee per month. But 20 idle EIPs + 5 idle ALBs = $154/month of pure waste.

**How to diagnose:**

```bash
# Find unattached Elastic IPs
aws ec2 describe-addresses \
  --query "Addresses[?AssociationId==null].{IP:PublicIp, AllocationId:AllocationId}" \
  --output table

# Find ALBs with zero target groups or zero healthy targets
aws elbv2 describe-load-balancers \
  --query "LoadBalancers[].{Name:LoadBalancerName, ARN:LoadBalancerArn, State:State.Code}" \
  --output table
```

**How to fix:**

Release unused Elastic IPs:
```bash
aws ec2 release-address --allocation-id eipalloc-xxx
```

Delete idle load balancers (after confirming no DNS points to them):
```bash
aws elbv2 delete-load-balancer --load-balancer-arn arn:aws:elasticloadbalancing:...
```

**Expected savings:** $50-200/month depending on accumulation.

## The Diagnostic Playbook: Find Your Spike in 10 Minutes

If your bill just spiked and you need to find the cause fast:

1. Open AWS Cost Explorer
2. Group by "Service" with daily granularity for the last 30 days
3. Find which service line jumped
4. Within that service, group by "Usage Type" to see what kind of usage drove it
5. Map to the 7 causes above

| Service Line That Grew | Most Likely Cause | Fix Priority |
|---|---|---|
| EC2 - Other | NAT Gateway (Cause 1) or Data Transfer (Cause 4) | High |
| Amazon EC2 | Forgotten instances (Cause 2) or EBS (Cause 3) | High |
| Amazon RDS | Over-provisioned database (Cause 6) | Medium |
| CloudWatch | Log ingestion (Cause 5) | Medium |
| Elastic Load Balancing | Idle ALBs (Cause 7) | Low |

## Prevention: Stop Spikes Before They Happen

1. **AWS Budgets with alerts** at 80% and 100% of your expected monthly spend
2. **Tagging policy enforced via SCPs** so every resource has an owner and environment tag
3. **Weekly cost review** (15 minutes, every Monday) comparing this week vs last week by service
4. **Automated cleanup** for resources older than 30 days without a production tag
5. **Cost anomaly detection** (AWS Cost Anomaly Detection is free and catches spikes within 24 hours)

## FAQ

### How quickly can I reduce my AWS bill after identifying waste?

Most of the fixes above take effect immediately. Stopping an instance, deleting an orphaned volume, or creating a VPC endpoint reduces your bill starting from the next billing hour. The exception is reserved instances and savings plans, which require a commitment decision and have a longer payback period.

### Should I use AWS Cost Optimization Hub or a third-party tool?

AWS Cost Optimization Hub is free and consolidates recommendations across your accounts. It's a good starting point. Third-party tools like CloudFinOps add workload pattern analysis (detecting diurnal usage for autoscaling recommendations), cross-cloud comparison, and continuous monitoring with alerting. Use the native tool first, then add a third-party layer when you need deeper automation.

### What's a good target for cloud waste percentage?

Industry average is 25-32% waste (Flexera 2026). Well-optimized teams run at 10-15% waste. Getting to 5% waste requires aggressive commitment coverage, autoscaling everywhere, and spot instances for fault-tolerant workloads. For most teams, getting from 30% to 15% is the realistic first milestone.

### How do I prevent developers from accidentally running up costs?

Three layers: (1) AWS Budgets with SNS alerts so someone gets paged at 80% of budget, (2) Service Control Policies that prevent launching expensive instance types (p4d, p5) without approval, (3) Tag-or-terminate automation that cleans up untagged resources after 7 days. Culture matters too: share the bill with the team monthly.

### Is it worth optimizing if we spend less than $5,000/month?

Yes, but focus on the high-leverage items: NAT Gateway VPC endpoints (Cause 1) and stopping unused dev instances (Cause 2) typically save 20-30% with 30 minutes of work. Don't spend a week optimizing CloudWatch log retention if it saves you $15/month. Prioritize by absolute dollar impact.
