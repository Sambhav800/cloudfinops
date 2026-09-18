---
title: "83% of Kubernetes Costs Are Idle Resources — Why Your Cloud Bill Can't Tell You Which Team Owns It"
slug: "kubernetes-cost-visibility-83-percent-idle"
excerpt: "Container workloads now consume 35% of EC2 compute spend, but 83% of that is idle. The bigger problem: your cloud billing tool sees the node, not the namespace. Here's how to build real Kubernetes cost visibility and recover the waste."
category: "Cloud Cost Optimization"
author:
  name: "Nishant Jain"
  role: "Co-Founder & CTO"
  avatar: "/images/team/nishant.png"
publishedAt: "2026-09-18"
updatedAt: "2026-09-18"
readTime: 17
featured: true
tags: ["kubernetes", "k8s", "cloud-cost-optimization", "finops", "containers", "eks", "aks", "gke", "devops"]
---

## The Kubernetes Billing Blind Spot

Container workloads now consume **35% of all EC2 compute spend** — up from 30% the prior year (Datadog, 2026). For organizations running at scale, the percentage is higher: 25% of AWS customers direct more than three-quarters of their EC2 budget to containers.

That's a lot of money. Here's the problem: **83% of it is idle**.

Datadog's 2026 State of Cloud Costs breaks the waste down precisely:
- **54%** of Kubernetes costs come from overprovisioned cluster infrastructure — nodes sitting larger than workloads actually require
- **29%** come from oversized pod resource requests — containers claiming CPU and memory they never consume

Meaning for every $100 your organization spends running Kubernetes, **$17 is doing useful work**. The other $83 is scheduled, allocated, and billed capacity that your workloads never actually use.

This is not a new insight. Kubernetes has had a resource request/limit model since 2014. What's changed is the scale of the problem and the growing sophistication of the tooling required to address it — because the standard cloud billing tools that you use to manage every other category of cloud spend are architecturally blind to Kubernetes waste.

## Why AWS Cost Explorer Cannot Tell You About Kubernetes Waste

Your AWS bill knows what each EC2 instance costs. It does not know what is running on that instance.

Kubernetes schedules multiple workloads — multiple services, namespaces, and teams — on shared infrastructure. When you query your AWS Cost Explorer, you see the node cost. You do not see that the `payments-service` namespace is consuming 8% of that node, `auth-service` is consuming 3%, and the remaining 89% is empty headroom reserved by pod resource requests that nobody has reviewed since the service was deployed.

This isn't a limitation of AWS's billing system. It's a fundamental architectural reality: cloud providers bill for virtual machines, and Kubernetes abstracts away the virtual machine. The attribution problem lives in the gap between those two layers, and no amount of tagging at the EC2 level closes it.

The practical consequence: when your CFO asks why the cloud bill went up 40% this quarter and the answer is buried in Kubernetes overhead from three different teams across twelve namespaces, the engineering organization literally cannot produce a credible breakdown from standard billing tools. They need a separate instrumentation layer. Most organizations don't have it.

## Understanding Why Waste Accumulates in Kubernetes

To fix Kubernetes cost problems, you need to understand the mechanism that creates them.

### The Request/Actual Gap

Kubernetes schedules pods based on `requests` — the CPU and memory a container declares it needs. The scheduler subtracts declared requests from node allocatable capacity and places pods accordingly.

Here's the critical distinction: the scheduler does not care about actual utilization. It cares about declared requests. A node is "full" when the sum of all pod requests equals its allocatable capacity, regardless of whether any of those pods are consuming their requested resources.

A concrete example:

```yaml
# Typical microservice resource spec set by a developer
resources:
  requests:
    cpu: "500m"      # Developer specified this conservatively
    memory: "512Mi"  # Developer specified this conservatively
  limits:
    cpu: "1000m"
    memory: "1Gi"
```

Actual measured usage for this service over 30 days: 45m CPU, 87Mi memory.

- Declared CPU request: 500m
- Actual CPU usage: 45m
- CPU waste: 91% of reserved capacity
- Declared memory request: 512Mi
- Actual memory usage: 87Mi
- Memory waste: 83% of reserved capacity

This pod is reserving 11x more CPU and 6x more memory than it actually uses. Multiply this pattern across 200 services in a cluster and you have a scheduler that believes the cluster is heavily loaded while the kernel reports it's mostly idle.

The developer who set these requests was not being irresponsible. They set them conservatively to avoid throttling (CPU limit exceeded) or OOMKills (memory limit exceeded) in production. There was no feedback loop telling them their conservative estimate was wasting 90% of the reservation.

### Why Requests Don't Get Updated

Resource requests are set at deploy time, typically copied from a template or estimated from brief load tests. Once set, they almost never get reviewed because:

- There's no alert that fires when actual usage is 10% of request
- The person who set the request may have moved to another team
- Changing resource requests requires a rolling deploy and testing
- The consequences of setting them too low (OOMKill in production) are visible; the consequences of setting them too high (paying for idle capacity) are not

This is the same structural problem that creates every other type of cloud waste: costs are invisible, feedback loops are missing, and the default behavior is to overprovision.

### The Cluster Sizing Problem

Even with perfectly specified pod requests, clusters accumulate waste through overprovisioned node groups. Common causes:

**Buffer nodes for availability.** Cluster autoscaler keeps N spare nodes for fast pod scheduling. If N is set to 3 for a 10-node cluster, you're paying 30% more than necessary as a scheduling buffer.

**Wrong node type for workload mix.** A node group with 16 vCPU, 64GB nodes serving workloads that individually need 0.5 vCPU and 1GB each. The CPU-to-memory ratio of the node doesn't match workload requirements, and you can never fully pack the nodes in either dimension.

**Multiple clusters for environment isolation.** Development and staging clusters sized to match production "just in case." Dev clusters that run 24/7 at production scale burn significant budget for workloads that could run on much smaller instances and only during working hours.

**Reserved minimum capacity.** Cluster autoscaler minimum node count set high enough that the cluster never scales below a given floor, even during off-hours when demand drops.

## Measuring Your Kubernetes Waste

Before optimizing, you need to quantify the problem in your specific environment. Here are the commands to do it.

### Cluster-Level Allocation vs. Utilization

```bash
# Shows how much of each node's capacity is reserved by requests (vs actual usage)
kubectl describe nodes | grep -A 10 "Allocated resources"

# Better: Compare allocation across all nodes
kubectl get nodes --no-headers | awk '{print $1}' | while read node; do
  echo "=== $node ==="
  kubectl describe node $node | grep -A 5 "Allocated resources:"
done
```

The output shows `cpu  X/Y (Z%)` and `memory  X/Y (Z%)` — requests as a fraction of allocatable capacity. In a healthy cluster, this should be 70-80% to leave room for burst scheduling without wasteful empty space. If you see numbers below 50%, your nodes are oversized for the workload.

### Pod-Level Waste Analysis

```bash
# Requires metrics-server installed
# Shows pods where actual CPU is significantly below requested

kubectl top pods --all-namespaces --no-headers 2>/dev/null | \
  while read namespace pod cpu_actual memory_actual; do
    cpu_req=$(kubectl get pod $pod -n $namespace \
      -o jsonpath='{.spec.containers[0].resources.requests.cpu}' 2>/dev/null)
    
    # Convert millicores to integer
    cpu_req_m=$(echo $cpu_req | sed 's/m//' | sed 's/\([0-9]*\)\b/\1/')
    cpu_actual_m=$(echo $cpu_actual | sed 's/m//')
    
    if [ -n "$cpu_req_m" ] && [ "$cpu_req_m" -gt 0 ] 2>/dev/null; then
      waste=$(( (cpu_req_m - cpu_actual_m) * 100 / cpu_req_m ))
      if [ $waste -gt 70 ]; then
        echo "$namespace/$pod: ${waste}% CPU waste (req: ${cpu_req_m}m, actual: ${cpu_actual_m}m)"
      fi
    fi
  done
```

This surfaces pods where actual CPU utilization is more than 70% below declared requests — your highest-priority rightsizing candidates.

### Namespace Cost Approximation

Without a dedicated cost allocation tool, you can approximate namespace cost share by comparing resource requests to total cluster cost:

```bash
# Total cluster CPU requests by namespace
kubectl get pods --all-namespaces --no-headers \
  -o custom-columns='NS:.metadata.namespace,CPU:.spec.containers[0].resources.requests.cpu' \
  | awk -F' ' '{gsub(/m/,"",$2); ns[$1]+=$2} END {for(n in ns) print n"\t"ns[n]"m"}' \
  | sort -k2 -rn

# Total cluster memory requests by namespace  
kubectl get pods --all-namespaces --no-headers \
  -o custom-columns='NS:.metadata.namespace,MEM:.spec.containers[0].resources.requests.memory' \
  | awk -F' ' '{
    mem=$2
    if(mem~/Mi/) {gsub(/Mi/,"",mem); ns[$1]+=mem}
    else if(mem~/Gi/) {gsub(/Gi/,"",mem); ns[$1]+=mem*1024}
  } END {for(n in ns) print n"\t"ns[n]"Mi"
  }' | sort -k2 -rn
```

Divide each namespace's total requests by the cluster's total requests to get its approximate cost share. Multiply by your monthly EC2 cost for those nodes. This is not exact attribution, but it's a usable proxy until you install proper cost allocation tooling.

## Building Real Cost Attribution

The commands above give you a snapshot. For ongoing cost attribution, you need a persistent layer between cluster metrics and billing data.

### Option 1: OpenCost (Free, CNCF)

OpenCost is an open-source Kubernetes cost monitoring tool, graduated to CNCF sandbox status. It allocates cloud provider costs to Kubernetes workloads in real time using actual resource utilization, not just requests.

Installation on EKS:

```bash
# Add the OpenCost Helm repository
helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm repo update

# Install in its own namespace
helm install opencost opencost/opencost \
  --namespace opencost \
  --create-namespace \
  --set opencost.exporter.cloudProviderApiKey=$AWS_ACCESS_KEY_ID \
  --set opencost.exporter.aws.accessKeyID=$AWS_ACCESS_KEY_ID \
  --set opencost.exporter.aws.secretAccessKey=$AWS_SECRET_ACCESS_KEY
```

Access the UI:
```bash
kubectl port-forward --namespace opencost service/opencost 9090:9090
```

Within 24 hours, OpenCost gives you namespace-level, deployment-level, and label-level cost breakdowns that update in real time. This is the data your engineering team needs to act on the 29% pod-level waste.

### Option 2: Cloud Provider Native Tools

**AWS:** Cost Allocation Tags + Container Insights. Requires EKS with Container Insights enabled and consistent namespace-to-cost-center tag mapping. Less granular than OpenCost but zero additional tooling to manage.

```bash
# Enable Container Insights on EKS
aws eks update-addon --cluster-name $CLUSTER_NAME \
  --addon-name amazon-cloudwatch-observability \
  --addon-version latest
```

**GCP:** GKE Cost Allocation (built-in). Enable in the GKE cluster settings to see per-namespace and per-label cost data directly in the Google Cloud Console Billing section.

**Azure:** Azure Monitor Container Insights with Cost Analysis integration. Requires the Container Insights add-on and workspace linking.

### Option 3: Dedicated Cost Allocation Platform

For organizations managing multiple clusters across multiple cloud providers, purpose-built tools (Kubecost, CloudZero Kubernetes, or CloudFinOps) provide cross-cluster aggregation, team-level showback, and automated rightsizing recommendations without the operational overhead of managing OpenCost instances per cluster.

## Fixing the 54%: Cluster-Level Waste

Cluster-level waste (the larger of the two categories) requires addressing node group sizing and autoscaler configuration.

### Right-Size Node Groups for Workload Profile

Identify whether your current node types match your workload CPU-to-memory ratio:

```bash
# What ratio does your current workload need?
kubectl get pods --all-namespaces \
  -o jsonpath='{range .items[*]}{.spec.containers[0].resources.requests.cpu}{"\t"}{.spec.containers[0].resources.requests.memory}{"\n"}{end}' \
  | awk '{
    if($1~/m/) {cpu+=substr($1,1,length($1)-1)/1000} else {cpu+=$1}
    if($2~/Mi/) {mem+=substr($2,1,length($2)-2)/1024} else if($2~/Gi/) {mem+=substr($2,1,length($2)-2)}
  } END {print "Total CPU cores:", cpu; print "Total Memory GB:", mem; print "Ratio (GB/vCPU):", mem/cpu}'
```

Compare the output ratio to your node type's ratio:

| Node Type | vCPUs | Memory | Ratio (GB/vCPU) | Best For |
|---|---|---|---|---|
| m6i.4xlarge | 16 | 64GB | 4:1 | General purpose |
| r6i.4xlarge | 16 | 128GB | 8:1 | Memory-heavy (databases, caches) |
| c6i.4xlarge | 16 | 32GB | 2:1 | CPU-heavy (computation, build systems) |
| t3.xlarge | 4 | 16GB | 4:1 | Dev/test workloads |

If your workloads have a 6:1 memory-to-CPU ratio but you're running m6i instances (4:1), you'll always have leftover CPU before memory fills up — or vice versa. The cluster can never reach high overall utilization because one dimension fills first.

### Tune Cluster Autoscaler for Faster Scale-In

Cluster autoscaler's default settings are conservative (biased toward keeping nodes alive) because AWS charges for partial hours either way. In practice, aggressive scale-in saves significantly more than the occasional sub-optimal node usage:

```yaml
# cluster-autoscaler deployment args
- --scale-down-delay-after-add=3m        # Wait 3m after adding node before scaling down (default: 10m)
- --scale-down-unneeded-time=3m          # Node must be unneeded for 3m to scale down (default: 10m)
- --scale-down-utilization-threshold=0.5  # Scale down when node at <50% utilization (default: 0.5)
- --skip-nodes-with-system-pods=false    # Allow scaling down nodes with system pods if evictable
- --balance-similar-node-groups=true     # Spread load across similar node groups
```

The default configuration keeps nodes alive for 10+ minutes after workloads are removed. For bursty workloads, this creates persistent over-provisioning. The 3-minute configuration above recovers capacity significantly faster.

### Scale Non-Production Clusters to Zero After Hours

The highest-ROI Kubernetes optimization most teams haven't done: non-production clusters should not run at production scale overnight and on weekends.

Using KEDA (Kubernetes Event-Driven Autoscaling) with a cron scaler:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: dev-cluster-schedule
spec:
  scaleTargetRef:
    name: cluster-autoscaler
  triggers:
  - type: cron
    metadata:
      timezone: "Asia/Kolkata"
      start: "0 8 * * 1-5"   # Scale up: 8 AM weekdays
      end: "0 20 * * 1-5"    # Scale down: 8 PM weekdays
      desiredReplicas: "5"    # Working hours capacity
```

Combined with a minimum node count of 1 for essential system pods, this scales the cluster down to minimal capacity for 16 hours/day on weekdays plus full weekends — 128 hours/week of near-zero-cost operation for your development cluster.

For a cluster running $15,000/month at full scale, capturing 60% of off-hours saves approximately **$9,000/month**.

## Fixing the 29%: Pod-Level Rightsizing

Pod resource request rightsizing is the harder problem because it's distributed across every deployment manifest in your codebase.

### Vertical Pod Autoscaler in Recommendation Mode

VPA analyzes actual pod utilization over time and suggests appropriate resource requests. Running in recommendation mode (it observes without modifying), it gives you a prioritized list of oversized pods:

```bash
# Install VPA
kubectl apply -f https://github.com/kubernetes/autoscaler/releases/latest/download/vertical-pod-autoscaler.yaml

# Create a VPA object for your deployment in "Off" mode (recommendation only)
cat <<EOF | kubectl apply -f -
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: my-service-vpa
  namespace: production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-service
  updatePolicy:
    updateMode: "Off"   # Recommendation only — no automatic changes
  resourcePolicy:
    containerPolicies:
    - containerName: my-service
      minAllowed:
        cpu: 50m
        memory: 64Mi
      maxAllowed:
        cpu: 2
        memory: 2Gi
EOF

# View recommendations after 24+ hours of data
kubectl describe vpa my-service-vpa -n production
```

The output includes `Lower Bound`, `Target`, and `Upper Bound` recommendations for both CPU and memory. The `Target` recommendation is typically the P90 utilization value — appropriate for most workloads with a small built-in buffer.

### Implementing Recommendations Without Downtime

VPA recommendations require a pod restart to take effect. For zero-downtime application, use a rolling update:

```bash
# Apply VPA recommendation to deployment (after validating the recommendation)
kubectl set resources deployment my-service \
  --requests=cpu=90m,memory=128Mi \
  --limits=cpu=500m,memory=512Mi \
  -n production

# Monitor the rolling update
kubectl rollout status deployment/my-service -n production
```

For teams with many services to rightsize, building a GitOps workflow that creates PRs with VPA-recommended resource values (reviewed and merged by the service owner) scales better than manual updates:

```python
# vpa_to_pr.py — creates GitHub PRs for VPA recommendations
import subprocess
import yaml
import json

def get_vpa_recommendations(namespace: str):
    result = subprocess.run(
        ['kubectl', 'get', 'vpa', '-n', namespace, '-o', 'json'],
        capture_output=True, text=True
    )
    vpas = json.loads(result.stdout)
    
    recommendations = []
    for vpa in vpas.get('items', []):
        target = vpa.get('status', {}).get('recommendation', {}).get('containerRecommendations', [])
        for rec in target:
            recommendations.append({
                'service': vpa['spec']['targetRef']['name'],
                'namespace': namespace,
                'container': rec['containerName'],
                'cpu_target': rec['target']['cpu'],
                'memory_target': rec['target']['memory'],
                'cpu_lower': rec['lowerBound']['cpu'],
                'cpu_upper': rec['upperBound']['cpu'],
            })
    return recommendations

# Get recommendations and calculate savings potential
for rec in get_vpa_recommendations('production'):
    print(f"{rec['namespace']}/{rec['service']}: CPU {rec['cpu_target']} (bounds: {rec['cpu_lower']}-{rec['cpu_upper']}), Memory {rec['memory_target']}")
```

## Enforcing Tag Compliance for Attribution

All the cost allocation tooling in the world produces meaningless output without consistent labeling. Kubernetes cost attribution requires every namespace, deployment, and pod to carry a consistent set of labels.

Minimum label set for attribution:

```yaml
# Required labels on every Namespace
labels:
  team: "platform"           # Which team owns this namespace
  cost-center: "engineering" # Budget owner
  environment: "production"  # prod | staging | dev | test

# Required labels on every Deployment
labels:
  app: "payments-service"
  team: "payments"
  service-tier: "critical"   # critical | standard | background
```

Enforce this with an admission webhook or OPA Gatekeeper policy:

```yaml
# OPA Gatekeeper constraint — reject deployments missing required labels
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-team-label
spec:
  match:
    kinds:
      - apiGroups: ["apps"]
        kinds: ["Deployment"]
  parameters:
    labels:
      - key: team
      - key: cost-center
      - key: environment
```

With consistent labeling in place, any cost allocation tool (OpenCost, Kubecost, cloud provider native) can produce accurate per-team, per-service attribution.

## The Attribution-to-Accountability Loop

The technical fixes above address the symptoms. The underlying cause of 83% idle Kubernetes costs is a missing feedback loop: developers make resource decisions without cost context, and those decisions persist indefinitely without review.

Building the feedback loop requires:

**Visibility:** Per-namespace cost data in a dashboard that teams actively monitor — not just in the FinOps team's tooling but in the dashboards engineering teams check daily.

**Ownership:** Every namespace has a named owner who receives a weekly cost summary. Not a list of resources — a dollar number with a trend line.

**Feedback at deploy time:** CI/CD integration that calculates estimated monthly cost for a deployment change before it merges. A pod that increases its memory request from 256Mi to 1Gi should generate a PR comment: "This change increases estimated monthly cost for this service by $340."

**Review cadence:** Quarterly review of VPA recommendations across the fleet, with the service owner responsible for applying recommendations or documenting why the current requests are justified.

Teams that implement this loop reliably reduce their Kubernetes costs by 40-60% within two quarters — not because they found a clever optimization, but because developers finally have the context to make cost-conscious resource decisions.

## Quick Wins This Week

1. **Run `kubectl top nodes`** right now. Compare to cluster capacity. Anything below 40% allocation is a cluster-sizing opportunity.

2. **Install OpenCost** in your largest cluster. 30 minutes. Immediate namespace-level cost breakdown.

3. **Deploy VPA in "Off" mode** for your top 5 most expensive namespaces. Come back in 48 hours and read the recommendations.

4. **Check your dev/staging cluster schedule.** Does it run 24/7? Implement a scheduled scale-down for nights and weekends this week.

5. **Audit your label compliance.** Run `kubectl get namespaces --show-labels`. Any namespace without a `team` label is invisible to cost attribution.

The 83% idle figure is structural — it exists because Kubernetes defaults to overprovisioning and feedback loops are missing. But it's entirely solvable. The teams that have addressed it systematically are running Kubernetes at 65-75% resource utilization with the same reliability guarantees as before. The difference is $83 out of every $100 being used for productive work instead of $17.

---

*CloudFinOps connects to your Kubernetes clusters and surfaces namespace-level cost allocation, VPA-equivalent rightsizing recommendations, and cluster utilization analysis across EKS, AKS, and GKE — without requiring you to install and maintain OpenCost in each cluster. [Scan your cloud bill free](/bill-scan) to see your Kubernetes cost breakdown.*
