---
title: "Kubernetes Cost Optimization: How to Cut EKS, AKS & GKE Spend by 40% (2026)"
slug: "kubernetes-cost-optimization-guide"
excerpt: "Kubernetes clusters hide waste in over-provisioned node pools, idle namespaces, and CPU requests that never get used. Here's a practical guide to cutting K8s costs across all three clouds."
category: "Cloud Cost Optimization"
author:
  name: "Nishant Jain"
  role: "Co-Founder & CTO"
  avatar: "/images/team/nishant.png"
publishedAt: "2026-08-22"
updatedAt: "2026-08-22"
readTime: 16
featured: true
tags: ["kubernetes", "eks", "aks", "gke", "cost-optimization", "spot-instances", "autoscaling"]
---

## Why Kubernetes Silently Burns Money

Kubernetes was designed for reliability, not cost efficiency. Every default in the system biases toward over-provisioning. Developers set CPU requests high because they got burned by throttling once. Ops teams add buffer nodes because they saw a scheduling failure during a deployment. Cluster autoscaler keeps a spare node "just in case." None of these decisions are wrong from a reliability standpoint, but collectively they create clusters that run at 15-30% actual utilization while billing you for 100% of provisioned capacity.

I have seen teams running $40,000/month EKS clusters where the actual CPU and memory consumption, measured over 30 days, never exceeded $14,000 worth of compute. That is a 65% waste rate hiding behind the abstraction layer that Kubernetes provides between your workloads and the underlying infrastructure.

The root cause is always the same: the gap between what pods request and what they actually use.

Here is a real example. A team deploys a Go microservice with these resource specs:

```yaml
resources:
  requests:
    cpu: "1000m"
    memory: "2Gi"
  limits:
    cpu: "2000m"
    memory: "4Gi"
```

The scheduler reserves 1 full CPU core and 2GB of RAM for this pod. But actual usage, measured via `kubectl top pod` over a week, averages 80m CPU and 256MB memory. That pod is consuming 8% of its requested CPU and 12.5% of its requested memory. Multiply by 200 pods across your cluster, and you are paying for nodes that are 85% idle at the kernel level while Kubernetes reports them as "fully scheduled."

> **Key insight:** Kubernetes scheduling operates on requests, not actual usage. The scheduler considers a node "full" when the sum of all pod requests equals node capacity, regardless of whether those pods are actually consuming those resources. This single architectural decision is the #1 source of Kubernetes cost waste across every cloud provider.

## Understanding Requests vs Limits vs Actual Usage

Before you can optimize anything, you need to internalize how the three-layer resource model works in Kubernetes, because most cost waste stems from misunderstanding these concepts.

**Requests** are what the scheduler uses for placement decisions. When you set `requests.cpu: 500m`, the scheduler subtracts 500 millicores from the node's allocatable capacity. That capacity is reserved even if your pod uses zero CPU. Requests are a scheduling guarantee, not a consumption measure.

**Limits** are the hard ceiling enforced by the Linux kernel's cgroup controller. If a pod exceeds its CPU limit, it gets throttled (not killed). If it exceeds its memory limit, it gets OOMKilled. Limits exist to prevent noisy-neighbor problems, not for cost control.

**Actual usage** is what the pod genuinely consumes at runtime, measured by the metrics-server or Prometheus. This is the only number that reflects real cost. Everything above actual usage and below the request line is pure waste.

The waste formula is straightforward:

```
Waste % = (Requested - Actual) / Requested * 100
```

Run this across your cluster right now:

```bash
# Get per-pod CPU waste (requests vs actual usage)
kubectl top pods --all-namespaces --no-headers | while read ns pod cpu mem; do
  cpu_actual=$(echo $cpu | sed 's/m//')
  cpu_request=$(kubectl get pod $pod -n $ns -o jsonpath='{.spec.containers[0].resources.requests.cpu}' 2>/dev/null | sed 's/m//')
  if [ -n "$cpu_request" ] && [ "$cpu_request" -gt 0 ] 2>/dev/null; then
    waste=$(( (cpu_request - cpu_actual) * 100 / cpu_request ))
    echo "$ns/$pod: ${waste}% CPU waste (requested: ${cpu_request}m, actual: ${cpu_actual}m)"
  fi
done
```

For a quicker cluster-wide snapshot:

```bash
# Cluster-level allocation vs capacity
kubectl describe nodes | grep -A 5 "Allocated resources" | grep -E "cpu|memory"
```

This shows you how much of each node's capacity has been reserved by requests. Compare that to actual utilization from your monitoring system. The gap is what you are paying for but not using.

| Layer | Controlled By | Impact on Cost | Impact on Performance |
|---|---|---|---|
| Requests | Developer (pod spec) | Directly determines node count needed | Guarantees minimum resources |
| Limits | Developer (pod spec) | Indirect (prevents burst beyond node capacity) | Prevents noisy neighbors |
| Actual Usage | Application behavior | True cost driver | What users actually experience |
| Node Capacity | Ops/Platform (node pool config) | Maximum billing ceiling | Total available resources |

> **Key insight:** Most organizations set requests at 2-10x actual usage because developers optimize for "never get throttled" rather than "use what I need." The fix is not to remove requests (that causes scheduling chaos) but to right-size them based on measured P95 usage plus a 20% buffer.

## Node Pool Rightsizing Across EKS, AKS, and GKE

Node pools are the compute layer beneath your pods. Choosing the wrong instance types or sizes for your node pools creates structural waste that no amount of pod-level optimization can fix.

The most common mistake: using large general-purpose instances (m5.2xlarge, Standard_D8s_v3, e2-standard-8) for workloads that are either memory-heavy or CPU-heavy, never both equally. If your pods are memory-bound, you are paying for CPU cores that will never be utilized. If they are CPU-bound, you are paying for RAM that sits empty.

### How to Identify the Right Instance Family

```bash
# Check actual resource ratios across your pods
kubectl get pods --all-namespaces -o json | jq -r '
  .items[] | select(.spec.containers[0].resources.requests) |
  "\(.metadata.namespace)/\(.metadata.name) cpu:\(.spec.containers[0].resources.requests.cpu // "none") mem:\(.spec.containers[0].resources.requests.memory // "none")"
'
```

If most pods request 250m CPU but 1-2Gi memory, you need memory-optimized nodes (r-series on AWS, E-series on Azure, n2-highmem on GCP). If pods request 2-4 cores but only 512Mi-1Gi memory, use compute-optimized nodes (c-series on AWS, F-series on Azure, c2 on GCP).

### Instance Type Recommendations by Workload Profile

| Workload Type | AWS (EKS) | Azure (AKS) | GCP (GKE) | CPU:Memory Ratio |
|---|---|---|---|---|
| Balanced (web services) | m7i.xlarge | Standard_D4s_v5 | e2-standard-4 | 1:4 |
| Memory-heavy (caching, JVM) | r7i.xlarge | Standard_E4s_v5 | n2-highmem-4 | 1:8 |
| CPU-heavy (compute, encoding) | c7i.xlarge | Standard_F4s_v2 | c2-standard-4 | 1:2 |
| GPU (ML inference) | g5.xlarge | Standard_NC4as_T4_v3 | g2-standard-4 | varies |
| Burstable (dev/staging) | t3.xlarge | Standard_B4ms | e2-medium | varies |

### Node Pool Sizing Strategy

Do not run a single large node pool. Split by workload class:

1. **System pool** (small, on-demand): 2-3 nodes for kube-system, monitoring, ingress controllers. These must be highly available and should not be interrupted.

2. **Workload pool** (right-sized, mixed): Your main application pods. Use a mix of on-demand and spot instances (covered in next section).

3. **Batch pool** (spot/preemptible only): Jobs, CronJobs, CI runners, data pipelines. Anything tolerant of interruption.

```bash
# EKS: Create a memory-optimized node group
eksctl create nodegroup \
  --cluster my-cluster \
  --name mem-optimized \
  --node-type r7i.xlarge \
  --nodes-min 2 \
  --nodes-max 10 \
  --node-labels workload-type=memory-heavy

# AKS: Add a compute-optimized node pool
az aks nodepool add \
  --resource-group myRG \
  --cluster-name myCluster \
  --name cpupool \
  --node-vm-size Standard_F4s_v2 \
  --min-count 2 \
  --max-count 10 \
  --labels workload-type=cpu-heavy

# GKE: Add a memory-optimized node pool
gcloud container node-pools create mem-pool \
  --cluster my-cluster \
  --machine-type n2-highmem-4 \
  --num-nodes 2 \
  --enable-autoscaling \
  --min-nodes 2 \
  --max-nodes 10 \
  --node-labels workload-type=memory-heavy
```

Use node affinity and taints/tolerations to direct pods to the appropriate pool:

```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: workload-type
          operator: In
          values:
          - memory-heavy
```

## Spot and Preemptible Node Pools: 60-90% Compute Discounts

Spot instances (AWS/Azure) and preemptible VMs (GCP) offer 60-90% discounts compared to on-demand pricing. The trade-off is that the cloud provider can reclaim these instances with minimal notice (2 minutes on AWS, 30 seconds on GCP). For Kubernetes workloads with proper pod disruption budgets and multiple replicas, this is not a real risk. It is free money.

### Cloud-Specific Spot Implementation

| Feature | EKS (AWS Spot) | AKS (Azure Spot) | GKE (Preemptible/Spot) |
|---|---|---|---|
| Discount | 60-90% | 60-90% | 60-91% |
| Interruption Notice | 2 minutes | 30 seconds | 30 seconds |
| Max Runtime | None | None | 24 hours (preemptible), None (Spot) |
| Availability SLA | None | None | None |
| Graceful Shutdown | SIGTERM + drain | SIGTERM + drain | SIGTERM + drain |
| Best For | Stateless services, batch | Stateless services, batch | Stateless services, batch |

### Setting Up Spot Node Pools

```bash
# EKS: Spot managed node group with diversification
eksctl create nodegroup \
  --cluster my-cluster \
  --name spot-workers \
  --spot \
  --instance-types m7i.xlarge,m6i.xlarge,m5.xlarge,r7i.xlarge \
  --nodes-min 3 \
  --nodes-max 20 \
  --node-labels lifecycle=spot \
  --asg-access

# AKS: Spot node pool with eviction policy
az aks nodepool add \
  --resource-group myRG \
  --cluster-name myCluster \
  --name spotpool \
  --priority Spot \
  --eviction-policy Delete \
  --spot-max-price -1 \
  --node-vm-size Standard_D4s_v5 \
  --min-count 3 \
  --max-count 20 \
  --labels lifecycle=spot

# GKE: Spot VM node pool
gcloud container node-pools create spot-pool \
  --cluster my-cluster \
  --spot \
  --machine-type e2-standard-4 \
  --num-nodes 3 \
  --enable-autoscaling \
  --min-nodes 3 \
  --max-nodes 20 \
  --node-labels lifecycle=spot
```

### Handling Interruptions Gracefully

The key to running on Spot safely is pod disruption budgets (PDBs) combined with multiple replicas spread across availability zones:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: my-app-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: my-app
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  replicas: 4
  template:
    spec:
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
      tolerations:
      - key: "kubernetes.azure.com/scalesetpriority"
        operator: "Equal"
        value: "spot"
        effect: "NoSchedule"
```

> **Key insight:** The safest Spot strategy is instance diversification. On EKS, specify 4-8 instance types in your node group. The Spot fleet will pull from whichever pool has the most capacity, dramatically reducing interruption frequency. Teams running diversified Spot fleets on EKS typically see fewer than 2 interruptions per week per 100 nodes.

## Karpenter vs Cluster Autoscaler: Which Saves More Money

Cluster Autoscaler (CA) has been the default Kubernetes scaling solution since 2016. Karpenter, released by AWS in 2021 and now a CNCF project with multi-cloud support, takes a fundamentally different approach. The cost implications are significant.

### How They Differ

**Cluster Autoscaler** operates at the node group level. It watches for pending pods, determines which node group could satisfy them, and adjusts the desired count of that group's Auto Scaling Group (or VMSS/MIG). It cannot mix instance types within a decision, cannot decommission underutilized nodes proactively (without a separate descheduler), and scales in 2-5 minute increments.

**Karpenter** operates at the pod level. It looks at pending pods, computes the optimal instance type and size that would satisfy them with minimal waste, and provisions that exact instance directly via the cloud provider API. It consolidates underutilized nodes automatically, can mix instance types freely, and provisions in 30-60 seconds.

| Capability | Cluster Autoscaler | Karpenter |
|---|---|---|
| Scaling Speed | 2-5 minutes | 30-60 seconds |
| Instance Selection | Fixed per node group | Dynamic, per scheduling decision |
| Bin-packing | Node group level only | Pod-level optimization |
| Node Consolidation | Requires descheduler addon | Built-in |
| Spot Diversification | Manual (multiple node groups) | Automatic across dozens of types |
| Cloud Support | All clouds | AWS (GA), Azure/GCP (beta via CNCF) |
| Cost Savings vs CA | Baseline | Typically 20-35% additional savings |
| Configuration Complexity | Low | Medium |

### Karpenter NodePool Example (AWS)

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      requirements:
      - key: kubernetes.io/arch
        operator: In
        values: ["amd64"]
      - key: karpenter.sh/capacity-type
        operator: In
        values: ["spot", "on-demand"]
      - key: karpenter.k8s.aws/instance-category
        operator: In
        values: ["m", "c", "r"]
      - key: karpenter.k8s.aws/instance-generation
        operator: Gt
        values: ["5"]
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 60s
  limits:
    cpu: "1000"
    memory: "2000Gi"
```

The `consolidationPolicy: WhenEmptyOrUnderutilized` setting is where the cost savings come from. Karpenter continuously evaluates whether pods on underutilized nodes could be rescheduled onto fewer nodes, then cordons, drains, and terminates the excess nodes. This happens automatically, without human intervention, every 60 seconds.

### When to Use Which

Use **Cluster Autoscaler** when:
- You are on Azure or GCP and need production-grade stability (Karpenter multi-cloud is still maturing)
- Your workloads are predictable and you have pre-configured node groups that match well
- You need the simplest possible setup with minimal operational overhead

Use **Karpenter** when:
- You are on AWS (or can tolerate beta status on other clouds)
- Your workloads are heterogeneous (varying CPU/memory ratios across pods)
- You want automatic node consolidation without running a separate descheduler
- You want to maximize Spot instance diversification without managing dozens of node groups
- Scaling speed matters (30-second provisioning vs 2-5 minutes)

## VPA for Pod Rightsizing: Automating the Request/Limit Problem

The Vertical Pod Autoscaler (VPA) solves the fundamental problem of developers setting resource requests too high. It observes actual pod resource consumption over time and either recommends or automatically applies updated requests and limits.

### VPA Modes

| Mode | Behavior | Risk Level | Best For |
|---|---|---|---|
| Off | Recommendations only (no action) | Zero | Initial analysis, understanding waste |
| Initial | Sets resources only at pod creation | Low | New deployments |
| Auto | Evicts and recreates pods with new resources | Medium | Stateless services with 3+ replicas |
| Recreate | Same as Auto (legacy name) | Medium | Same as Auto |

### Deploying VPA in Recommendation Mode

Start with recommendation mode to understand the gap before making changes:

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: my-app-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  updatePolicy:
    updateMode: "Off"
  resourcePolicy:
    containerPolicies:
    - containerName: '*'
      minAllowed:
        cpu: 50m
        memory: 64Mi
      maxAllowed:
        cpu: 4000m
        memory: 8Gi
```

After a week of data collection, check recommendations:

```bash
# View VPA recommendations for all deployments
kubectl get vpa --all-namespaces -o json | jq -r '
  .items[] | 
  "\(.metadata.namespace)/\(.metadata.name): " +
  "target cpu=\(.status.recommendation.containerRecommendations[0].target.cpu // "N/A") " +
  "target mem=\(.status.recommendation.containerRecommendations[0].target.memory // "N/A") " +
  "upper cpu=\(.status.recommendation.containerRecommendations[0].upperBound.cpu // "N/A") " +
  "upper mem=\(.status.recommendation.containerRecommendations[0].upperBound.memory // "N/A")"
'
```

### VPA Best Practices for Cost Savings

1. **Never use VPA in Auto mode for single-replica deployments.** VPA evicts pods to apply new resource values. With one replica, that means downtime.

2. **Set `minAllowed` based on application startup requirements.** Many Java/JVM applications need more memory during startup than steady state. If VPA sets memory too low based on running averages, pods will OOMKill during rollouts.

3. **Pair VPA with HPA carefully.** VPA and HPA should not both target CPU. Let HPA scale horizontally on CPU, and VPA adjust memory requests vertically. Or use the Multidimensional Pod Autoscaler (MPA) if your platform supports it.

4. **Run VPA in Off mode for 2 weeks before switching to Auto.** This gives the recommendation engine enough data points to avoid noisy adjustments from short-term load spikes.

```bash
# Quick check: which pods have the largest request-vs-actual gap?
kubectl top pods --all-namespaces --sort-by=cpu --no-headers | head -20
```

> **Key insight:** In my experience, VPA in recommendation mode consistently identifies 30-50% over-provisioning across production clusters. The average Kubernetes deployment requests 3-5x more CPU than it uses at P95. Even applying VPA recommendations conservatively (using the upperBound instead of target) yields 25-35% cost reduction in node spend.

## Namespace Cost Allocation and Showback

You cannot optimize what you cannot measure. One of Kubernetes' biggest cost management gaps is the lack of built-in cost attribution. A cluster bills as one line item on your cloud invoice. Which team is responsible for what portion of that cost? Without namespace-level cost allocation, nobody owns the waste.

### Implementing Cost Allocation

Every namespace should map to a team, service, or cost center. Label everything:

```bash
# Label namespaces with cost-center metadata
kubectl label namespace payments team=payments cost-center=CC-1234
kubectl label namespace analytics team=data-eng cost-center=CC-5678
kubectl label namespace staging env=non-prod cost-center=CC-0001
```

### Calculating Namespace Cost

The formula for namespace cost is:

```
Namespace Cost = Sum of (pod_cpu_request * node_cpu_cost_per_core_hour) + 
                 Sum of (pod_memory_request * node_mem_cost_per_gb_hour) +
                 Proportional share of shared resources (ingress, monitoring, etc.)
```

Use resource quotas to enforce per-namespace budgets:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-budget
  namespace: payments
spec:
  hard:
    requests.cpu: "20"
    requests.memory: "40Gi"
    limits.cpu: "40"
    limits.memory: "80Gi"
    pods: "100"
```

### Cost Allocation Tools Comparison

| Tool | Open Source | Multi-Cloud | Real-Time | Accuracy |
|---|---|---|---|---|
| Kubecost | Community edition yes | Yes | Yes | High (node-level billing) |
| OpenCost | Yes (CNCF) | Yes | Yes | High |
| AWS Split Cost Allocation (EKS) | No (native) | EKS only | Near real-time | Very high (CUR-based) |
| GKE Cost Allocation | No (native) | GKE only | Yes | Very high |
| AKS Cost Analysis | No (native) | AKS only | Yes | High |
| CloudFinOps | SaaS | Yes | Yes | High (scans pod-level metrics) |

CloudFinOps can detect over-provisioned pods by comparing actual resource consumption against requests at the namespace level, flagging individual deployments where the waste gap exceeds configurable thresholds. This is particularly useful when you need to identify the top offenders before running VPA across the entire cluster.

### Showback Reports That Drive Action

Cost allocation data is useless unless it changes behavior. Set up weekly automated reports per team:

```bash
# Generate per-namespace resource consumption summary
for ns in $(kubectl get ns -o jsonpath='{.items[*].metadata.name}'); do
  cpu=$(kubectl describe quota -n $ns 2>/dev/null | grep "requests.cpu" | awk '{print $2}')
  mem=$(kubectl describe quota -n $ns 2>/dev/null | grep "requests.memory" | awk '{print $2}')
  if [ -n "$cpu" ]; then
    echo "Namespace: $ns | CPU Quota Used: $cpu | Memory Quota Used: $mem"
  fi
done
```

Attach a dollar amount. When an engineering manager sees "your team's namespace costs $8,400/month and 62% is unused capacity," they will prioritize rightsizing. When the report just says "CPU utilization: 38%," nothing happens.

## Bin-Packing Efficiency: Getting More Pods Per Node

Bin-packing is the art of scheduling pods onto nodes such that minimal allocatable capacity goes unused. Poor bin-packing means you are paying for nodes that are 70% scheduled but have 30% of capacity in fragments too small for any pending pod to use.

### Why Fragmentation Happens

Consider a node with 4 CPU cores and 16Gi memory. Three pods are scheduled:
- Pod A: requests 1.5 CPU, 6Gi memory
- Pod B: requests 1.5 CPU, 4Gi memory  
- Pod C: requests 0.5 CPU, 4Gi memory

Total allocated: 3.5 CPU (87.5%), 14Gi memory (87.5%). Remaining: 0.5 CPU, 2Gi memory. If the next pending pod needs 1 CPU, it cannot fit. The node is effectively "full" despite having resources free. The cluster autoscaler provisions a new node for that single pod.

### Improving Bin-Packing

**1. Standardize pod sizes.** If all your pods use multiples of a base unit (e.g., 250m CPU / 512Mi memory), they tessellate into nodes much more efficiently than random sizes.

**2. Use pod topology spread constraints** to distribute evenly:

```yaml
topologySpreadConstraints:
- maxSkew: 1
  topologyKey: kubernetes.io/hostname
  whenUnsatisfiable: ScheduleAnyway
  labelSelector:
    matchLabels:
      app: my-app
```

**3. Enable the MostAllocated scoring strategy** in kube-scheduler (or use Karpenter's built-in bin-packing). The default scheduler uses LeastAllocated, which spreads pods across nodes for reliability but wastes capacity:

```yaml
# Scheduler profile for better bin-packing
apiVersion: kubescheduler.config.k8s.io/v1
kind: KubeSchedulerConfiguration
profiles:
- schedulerName: default-scheduler
  plugins:
    score:
      enabled:
      - name: NodeResourcesFit
        weight: 1
  pluginConfig:
  - name: NodeResourcesFit
    args:
      scoringStrategy:
        type: MostAllocated
        resources:
        - name: cpu
          weight: 1
        - name: memory
          weight: 1
```

**4. Use the descheduler** to rebalance pods from underutilized nodes:

```bash
# Install descheduler via Helm
helm install descheduler descheduler/descheduler \
  --namespace kube-system \
  --set schedule="*/5 * * * *" \
  --set deschedulerPolicy.strategies.LowNodeUtilization.enabled=true \
  --set deschedulerPolicy.strategies.LowNodeUtilization.params.nodeResourceUtilizationThresholds.thresholds.cpu=20 \
  --set deschedulerPolicy.strategies.LowNodeUtilization.params.nodeResourceUtilizationThresholds.thresholds.memory=20
```

### Measuring Bin-Packing Efficiency

```bash
# Per-node allocatable vs allocated (bin-packing score)
kubectl get nodes -o json | jq -r '
  .items[] | 
  "\(.metadata.name): allocatable_cpu=\(.status.allocatable.cpu) allocatable_mem=\(.status.allocatable.memory)"
'

# Compare with actual scheduled requests
kubectl describe nodes | grep -A 3 "Allocated resources" | grep -E "cpu|memory"
```

A well-packed cluster should show 75-85% of allocatable resources consumed by pod requests on each node. Below 60% indicates significant bin-packing inefficiency. Above 90% leaves too little headroom for burst and system processes.

## Commitment Discounts for Kubernetes Workloads

Spot instances handle the variable portion of your cluster. But the baseline, the minimum number of nodes your cluster always needs, should be covered by commitment discounts (Reserved Instances, Savings Plans, or Committed Use Discounts).

### Identifying Your Committed Baseline

```bash
# Find your cluster's minimum node count over the last 30 days
# (requires Prometheus/metrics history)
# Look at the minimum number of Ready nodes at any point:
kubectl get nodes --no-headers | wc -l  # Current count
```

Check your cloud provider's metrics for the minimum node count over 30 days. That floor is your commitment target.

### Cloud-Specific K8s Commitment Strategies

| Strategy | AWS (EKS) | Azure (AKS) | GCP (GKE) |
|---|---|---|---|
| Best commitment type | Compute Savings Plans | Azure Savings Plans | CUDs (resource-based) |
| Why | Covers any instance type/size Karpenter picks | Covers any VM series | Covers any machine type in family |
| Flexibility with autoscaling | High (dollar-based, instance-agnostic) | High (dollar-based) | Medium (locked to machine family) |
| Discount (1yr) | 20-30% | 15-25% | 20-28% |
| Discount (3yr) | 40-54% | 35-50% | 46-57% |
| Combines with Spot | Yes (SP covers on-demand portion only) | Yes | Yes |

### The Layered Commitment Model for K8s

The optimal Kubernetes cost structure uses three layers:

1. **Commitment layer (40-60% of nodes):** Cover your steady-state minimum with 1-year Compute Savings Plans (AWS), Azure Savings Plans, or GCP CUDs. This is compute that is always running regardless of traffic.

2. **On-demand layer (10-20% of nodes):** A small buffer of on-demand instances for the system node pool, critical stateful workloads, and the delta between committed baseline and Spot availability.

3. **Spot layer (30-50% of nodes):** All stateless, interruptible workloads. Batch jobs, CI/CD runners, and replicated services with PDBs.

This layered approach yields effective discounts of 50-65% compared to running everything on-demand:

```
Effective discount = (0.50 * 40% SP discount) + (0.15 * 0% on-demand) + (0.35 * 70% Spot discount)
                   = 20% + 0% + 24.5%
                   = 44.5% (conservative estimate)
```

In practice, teams that implement all three layers plus VPA-driven rightsizing consistently achieve 40-60% total cost reduction.

### GKE-Specific: Sustained Use Discounts

GKE offers automatic Sustained Use Discounts (SUDs) that apply without any commitment. If a VM runs for more than 25% of the month, Google starts applying incremental discounts up to 30%. These stack with CUDs for the baseline, meaning your committed GKE nodes can see 57% CUD discount plus SUD benefits on the remaining on-demand portion.

```bash
# GKE: Check current CUD utilization
gcloud compute commitments list --format="table(name,status,plan,resources)"
```

> **Key insight:** For Kubernetes clusters using Karpenter or similar dynamic provisioners, Compute Savings Plans (AWS) or dollar-based Savings Plans (Azure) are strictly better than Reserved Instances. RIs lock you to a specific instance type, but Karpenter changes instance types constantly based on pending pod requirements. Dollar-based plans apply regardless of which instance the provisioner selects.

## Frequently Asked Questions

### What is a good target utilization for a Kubernetes cluster?

Aim for 65-75% average CPU utilization and 70-80% memory utilization at the node level. Below 50% indicates severe over-provisioning. Above 85% leaves insufficient headroom for traffic spikes and pod scheduling. These targets apply to actual usage, not request-based allocation. A cluster can show 95% allocated (requests consuming capacity) while actual utilization sits at 30%, which means you are paying for 3x the compute you need.

### Should I set CPU limits on my pods?

This is genuinely debated. The argument against CPU limits: limits cause throttling even when the node has idle capacity, hurting latency without saving money. The argument for: without limits, a single misbehaving pod can consume an entire node's CPU, degrading co-located workloads. My recommendation: set memory limits always (OOMKill is better than node-level memory pressure), but consider removing CPU limits for well-behaved services in clusters where you have monitoring to catch runaway processes. Use LimitRange defaults as a safety net rather than per-pod limits.

### How much can I realistically save with Spot instances on Kubernetes?

For stateless workloads with 3+ replicas and proper PDBs, you can safely run 60-80% of your compute on Spot. With Spot discounts averaging 65-75% off on-demand, that translates to 40-55% savings on compute costs for those workloads. The catch: Spot availability varies by region and instance type. Diversify across 6-10 instance types and 3 availability zones to maintain consistent capacity. If you are running single-replica stateful services, those must stay on-demand.

### Is Karpenter worth switching to from Cluster Autoscaler?

If you are on AWS with heterogeneous workloads and clusters above 50 nodes, yes. Karpenter typically delivers 20-35% additional cost savings over Cluster Autoscaler through better bin-packing, automatic consolidation, and broader Spot diversification. The migration effort is moderate (replace node groups with NodePools, update pod scheduling constraints). For clusters under 20 nodes with homogeneous workloads, the savings may not justify the migration effort. On Azure and GCP, wait for the CNCF Karpenter provider to reach GA before switching production clusters.

### How do I prevent developers from requesting too many resources?

Implement a three-part strategy: (1) Deploy VPA in recommendation mode and surface the waste gap in PR reviews and team dashboards. (2) Set LimitRange defaults at the namespace level so pods without explicit requests get reasonable values instead of unlimited access. (3) Use admission webhooks (Gatekeeper/Kyverno) to reject pod specs where requests exceed 2x the VPA recommendation for that deployment. The cultural fix matters more than the technical one: make resource efficiency a visible metric in team scorecards, not a DevOps afterthought.

```yaml
# LimitRange: enforce sensible defaults
apiVersion: v1
kind: LimitRange
metadata:
  name: default-resources
  namespace: my-team
spec:
  limits:
  - default:
      cpu: 500m
      memory: 512Mi
    defaultRequest:
      cpu: 100m
      memory: 128Mi
    type: Container
```

---

Kubernetes cost optimization is not a one-time project. It is an ongoing practice of measuring actual consumption, closing the gap between requests and reality, leveraging Spot capacity for interruptible workloads, and committing to stable baselines. The clusters I have seen achieve 40%+ savings all share one trait: they measure waste weekly, assign ownership per namespace, and treat resource requests as a tunable parameter rather than a set-and-forget value. Start with visibility (VPA recommendations + namespace cost allocation), then layer in Spot, then commit once your baseline stabilizes. That sequence, in that order, reliably cuts Kubernetes spend by 35-50% within 90 days.
