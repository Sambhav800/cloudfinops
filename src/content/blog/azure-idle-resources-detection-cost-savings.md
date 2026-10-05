---
title: "Azure Idle Resources: How to Find and Eliminate Wasted VMs, Disks & IPs (2026)"
slug: "azure-idle-resources-detection-cost-savings"
excerpt: "Your Azure subscription is likely running idle VMs, orphaned managed disks, and unattached public IPs right now. Here's how to find them using Azure Advisor, CLI, and automation."
category: "Azure"
author:
  name: "Nishant Jain"
  role: "Co-Founder & CTO"
  avatar: "/images/team/nishant.png"
publishedAt: "2026-07-10"
updatedAt: "2026-07-25"
readTime: 13
featured: false
tags: ["azure", "idle-resources", "cost-optimization", "azure-advisor", "virtual-machines"]
---

## The Azure Waste Problem

Azure makes it incredibly easy to provision resources — and equally easy to forget about them. A developer spins up a D4s_v3 VM for a quick test, forgets to deallocate it, and you're paying $140/month for a machine doing nothing.

According to Microsoft's own data, the average Azure subscription has 15-25% waste in idle or over-provisioned resources. For a team spending ₹20L/month on Azure, that's ₹3-5L/month burning away.

> Unlike AWS where "stopping" an instance stops billing for compute (but not EBS), Azure's "Stopped" state is different from "Stopped (deallocated)." A VM in "Stopped" state still incurs compute charges. Only "Stopped (deallocated)" stops the billing clock. This distinction alone accounts for thousands in unnecessary Azure spend.

## The Five Types of Azure Waste

| Resource Type | How It Becomes Waste | Monthly Cost Example |
|---------------|---------------------|---------------------|
| **Idle VMs** | Test/dev machines left running 24/7 | D4s_v3: ~$140/month |
| **Orphaned Managed Disks** | VM deleted but disk retained | P30 (1TB): ~$122/month |
| **Unattached Public IPs** | Reserved but not assigned to running resources | ~$3.65/month each (adds up) |
| **Idle App Service Plans** | Plan running but no apps deployed | S1: ~$73/month |
| **Over-provisioned databases** | Azure SQL provisioned for peak, idle 90% of time | S3 (100 DTUs): ~$150/month |

## Step 1: Use Azure Advisor for Quick Wins

Azure Advisor is your free first line of defense. It analyzes your resource configuration and telemetry to give personalized recommendations.

### Accessing Cost Recommendations

```bash
# List all cost recommendations via Azure CLI
az advisor recommendation list --category Cost --output table

# Filter for high-impact items
az advisor recommendation list --category Cost \
  --query "[?impact=='High']" --output table
```

Azure Advisor specifically flags:
- **Idle VMs:** CPU average <5% over 14 days
- **Rightsizing opportunities:** VMs that could use a smaller SKU
- **Reserved Instance recommendations:** Stable workloads that would benefit from commitments
- **Unused Public IPs:** IPs not attached to any NIC

### Limitations of Azure Advisor

Advisor is a starting point, not a complete solution:
- It uses 14-day lookback — misses weekly patterns (a VM idle on weekends isn't truly idle)
- It doesn't detect orphaned disks directly
- It doesn't consider the relationship between resources (a "idle" VM might be a standby for failover)
- Recommendations are generic — no CLI commands to execute fixes

## Step 2: Find Idle Virtual Machines

### Define Your Idle Threshold

A VM is "idle" when it meets ALL of these criteria over a 30-day window:

| Metric | Idle Threshold | Azure Monitor Metric Name |
|--------|---------------|---------------------------|
| CPU | Average <5% | Percentage CPU |
| Network In | <1 MB/day | Network In Total |
| Network Out | <1 MB/day | Network Out Total |
| Disk Read Ops | <100/day | Disk Read Operations/Sec |
| Disk Write Ops | <100/day | Disk Write Operations/Sec |

### Azure CLI: Find Low-CPU VMs

```bash
# Get all running VMs in a subscription
az vm list --query "[?powerState=='VM running']" \
  -d --output table

# Check CPU metrics for a specific VM (last 30 days)
az monitor metrics list \
  --resource "/subscriptions/{sub-id}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{vm-name}" \
  --metric "Percentage CPU" \
  --interval PT1H \
  --start-time $(date -u -d "30 days ago" +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --aggregation Average \
  --output table
```

### Azure Resource Graph: Bulk Query for Idle VMs

For subscriptions with hundreds of VMs, use Resource Graph:

```bash
# Find all running VMs with their size and resource group
az graph query -q "
  Resources
  | where type == 'microsoft.compute/virtualmachines'
  | where properties.extended.instanceView.powerState.code == 'PowerState/running'
  | project name, resourceGroup, location,
    vmSize = properties.hardwareProfile.vmSize,
    subscriptionId
  | order by vmSize desc
"
```

Cross-reference this with Azure Monitor metrics to identify the idle subset.

## Step 3: Find Orphaned Managed Disks

When you delete a VM, Azure doesn't automatically delete its managed disks. These "orphaned" disks sit in your subscription accumulating charges.

```bash
# Find all managed disks NOT attached to any VM
az disk list --query "[?managedBy==null]" \
  --output table \
  --query "[].{Name:name, ResourceGroup:resourceGroup, Size:diskSizeGb, SKU:sku.name, State:diskState}"
```

**Expected output:** A list of disks with `diskState: Unattached`. Each of these is costing you money for storage that nothing is using.

**Cost impact by disk tier:**

| Disk SKU | Size | Monthly Cost (Unattached) |
|----------|------|---------------------------|
| Standard HDD (S10) | 128 GB | ~$5.89 |
| Standard SSD (E10) | 128 GB | ~$9.60 |
| Premium SSD (P30) | 1 TB | ~$122.88 |
| Premium SSD (P50) | 4 TB | ~$491.52 |

> A common pattern: a team creates 10 VMs for load testing, each with a 1TB Premium SSD. They delete the VMs but not the disks. That's $1,228/month in orphaned storage — $14,740/year — for zero value.

### Safe Cleanup Process

1. **Snapshot first** (if the data might be needed):
```bash
az snapshot create --resource-group {rg} \
  --name {disk-name}-snapshot \
  --source {disk-id}
```

2. **Verify no dependency** (check if any recovery is pending):
```bash
az disk show --ids {disk-id} --query "diskState"
# Should return "Unattached" — not "ReadyToUpload" or "ActiveSAS"
```

3. **Delete the orphaned disk:**
```bash
az disk delete --ids {disk-id} --yes
```

## Step 4: Find Unattached Public IP Addresses

Public IPs in Azure cost money whether they're attached to a resource or not (for Standard SKU). Basic SKU IPs are free when attached but cost money when not.

```bash
# Find all Public IPs not attached to anything
az network public-ip list \
  --query "[?ipConfiguration==null]" \
  --output table \
  --query "[].{Name:name, ResourceGroup:resourceGroup, SKU:sku.name, Address:ipAddress, Location:location}"
```

Each unattached Standard Public IP costs approximately $3.65/month. A subscription with 50 unattached IPs is wasting $182/month — not catastrophic individually, but this waste pattern signals broader hygiene issues.

## Step 5: Detect Over-Provisioned Azure SQL Databases

Azure SQL databases provisioned in the DTU model often sit at 5-10% utilization:

```bash
# Get DTU usage percentage for the last 14 days
az monitor metrics list \
  --resource "/subscriptions/{sub-id}/resourceGroups/{rg}/providers/Microsoft.Sql/servers/{server}/databases/{db}" \
  --metric "dtu_consumption_percent" \
  --interval PT1H \
  --start-time $(date -u -d "14 days ago" +%Y-%m-%dT%H:%M:%SZ) \
  --aggregation Average Maximum \
  --output table
```

**Decision framework:**

| Average DTU Usage | Peak DTU Usage | Action |
|-------------------|----------------|--------|
| <10% | <30% | Downgrade by 2 tiers |
| <10% | 30-60% | Downgrade by 1 tier |
| 10-40% | <60% | Downgrade by 1 tier |
| 10-40% | >60% | Keep current tier |
| >40% | >80% | Consider upgrading |

## Step 6: Automate Detection with Azure Automation

Set up a recurring runbook that identifies waste automatically:

### Create an Automation Account Runbook

```python
# Azure Automation Runbook (Python)
# Runs weekly, reports idle resources to a Teams webhook

import automationassets
from azure.identity import ManagedIdentityCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.monitor import MonitorManagementClient
import requests
import json
from datetime import datetime, timedelta

credential = ManagedIdentityCredential()
subscription_id = automationassets.get_automation_variable("SubscriptionId")
webhook_url = automationassets.get_automation_variable("TeamsWebhookUrl")

compute_client = ComputeManagementClient(credential, subscription_id)
monitor_client = MonitorManagementClient(credential, subscription_id)

idle_vms = []
end_time = datetime.utcnow()
start_time = end_time - timedelta(days=14)

for vm in compute_client.virtual_machines.list_all():
    if vm.instance_view and "running" in str(vm.instance_view):
        # Check CPU metrics
        metrics = monitor_client.metrics.list(
            vm.id,
            timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
            metricnames="Percentage CPU",
            aggregation="Average"
        )
        for metric in metrics.value:
            for ts in metric.timeseries:
                avg_cpu = sum(d.average for d in ts.data if d.average) / len(ts.data)
                if avg_cpu < 5:
                    idle_vms.append({
                        "name": vm.name,
                        "rg": vm.id.split("/")[4],
                        "size": vm.hardware_profile.vm_size,
                        "avg_cpu": round(avg_cpu, 1)
                    })

# Post to Teams
if idle_vms:
    message = {
        "text": f"⚠️ Found {len(idle_vms)} idle VMs (CPU < 5% over 14 days):\n" +
                "\n".join(f"• {vm['name']} ({vm['size']}) in {vm['rg']} — {vm['avg_cpu']}% avg CPU"
                         for vm in idle_vms)
    }
    requests.post(webhook_url, json=message)
```

Schedule this runbook to run weekly. It gives you a proactive Slack/Teams notification of waste without requiring anyone to log into the portal.

## Step 7: Implement Continuous Governance

### Azure Policy for Prevention

Prevent waste from accumulating in the first place:

```json
{
  "if": {
    "allOf": [
      { "field": "type", "equals": "Microsoft.Compute/virtualMachines" },
      { "field": "tags['team']", "exists": "false" }
    ]
  },
  "then": { "effect": "deny" }
}
```

This denies VM creation without a `team` tag — ensuring every resource has an accountable owner from day one.

### Auto-Shutdown for Dev/Test

Azure has a built-in auto-shutdown feature for VMs:

```bash
# Enable auto-shutdown at 8 PM IST for a dev VM
az vm auto-shutdown \
  --resource-group dev-rg \
  --name dev-vm-01 \
  --time 2030 \
  --timezone "India Standard Time"
```

For entire environments, use Azure DevTest Labs or simply schedule Start/Stop VMs during off-hours (a pre-built Azure Automation solution).

## Tools for Azure Idle Resource Detection

| Tool | Cost | What It Detects | Automation |
|------|------|-----------------|------------|
| Azure Advisor | Free | Idle VMs, rightsizing, RI recommendations | Manual action |
| Azure Cost Management | Free | Budget alerts, cost trends | Alert-based |
| CloudFinOps | Free audit | Idle VMs, orphaned disks, governance gaps | AI recommendations with CLI commands |
| Azure Automation | ~$2/500 minutes | Custom detection logic | Fully automated |
| Azure Resource Graph | Free | Resource inventory queries | Query-based |

## FAQ

### How is "Stopped" different from "Stopped (deallocated)" in Azure?

"Stopped" means the OS shut down but Azure still reserves the compute capacity — you're still billed for the VM. "Stopped (deallocated)" releases the compute capacity back to Azure — billing stops for compute (but continues for attached disks and IPs). Always use `az vm deallocate` instead of just `az vm stop` to actually save money.

### Will deleting an orphaned disk lose my data permanently?

Yes, unless you create a snapshot first. Snapshots cost much less than managed disks (incremental storage only) and can be used to recreate the disk later. Always snapshot before deleting if there's any chance the data is needed.

### How much can I realistically save by cleaning up idle Azure resources?

Most teams find 15-25% savings in their first cleanup. For a ₹20L/month Azure subscription, that's ₹3-5L/month in immediate savings. The recurring savings depend on how well you prevent future waste through governance policies and automation.

### Should I use Azure Reserved Instances or Savings Plans?

For predictable, stable workloads that won't change VM series: use Reserved Instances (higher savings, less flexibility). For workloads that might change size or series: use Azure Savings Plans (slightly lower savings, more flexibility). Most teams benefit from a mix: RIs for databases and production VMs, Savings Plans for variable compute.

### How often should I run idle resource detection?

Weekly is the sweet spot. Daily creates alert fatigue (short-term spikes look like anomalies). Monthly is too slow — by the time you detect a forgotten VM, you've already paid for 4 weeks of waste. Weekly gives you a clean signal-to-noise ratio with fast enough response time.
