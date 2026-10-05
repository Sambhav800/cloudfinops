---
title: "Your GPUs Are Running at 23% Utilization — The Real Math on What That Costs (and How to Fix It)"
slug: "gpu-waste-23-percent-utilization"
excerpt: "Average GPU utilization across production teams is 23%. An H100 at 50% utilization effectively costs double per productive GPU-hour compared to 100% utilization. Here's how to find your GPU waste, calculate the actual dollar impact, and implement auto-shutdown policies that save five figures a month."
category: "Cloud Cost Optimization"
author:
  name: "Nishant Jain"
  role: "Co-Founder & CTO"
  avatar: "/images/team/nishant.png"
publishedAt: "2026-09-18"
updatedAt: "2026-09-18"
readTime: 16
featured: false
tags: ["gpu", "ai-costs", "cloud-cost-optimization", "aws", "azure", "gcp", "machine-learning", "finops"]
---

## The Most Expensive Idle Resource in Your Stack

An idle t3.micro costs you $8.50/month. An idle 8x H100 node on AWS (p5.48xlarge) costs you approximately **$98/hour** — $71,760/month if it runs around the clock.

GPU waste is categorically different from any other type of cloud waste. Not because it's harder to find — it's actually straightforward to detect with basic CloudWatch metrics. But because the dollar impact per resource is an order of magnitude larger than anything else in your cloud bill, and because the cultural norms around GPU provisioning haven't caught up with the cost reality.

Here is the number that should be on every engineering leader's weekly dashboard: **the average GPU utilization across production teams is 23%** (Harness, 2025).

Not 23% because teams are careless. 23% because the billing model for GPUs is fundamentally misaligned with how ML workloads actually run. Cloud providers bill by the hour. Training jobs finish. Inference endpoints sit idle between traffic spikes. Development sessions leave instances running overnight. The gap between "allocated" and "used" is structural, and without deliberate operational discipline, it compounds into massive waste.

GPU instances now represent **14% of total EC2 compute costs** on average — up from 10% the prior year (Datadog, 2026). For teams with ML workloads in production, the percentage is higher. At 14% of a $500K/month AWS bill, that's $70K/month on GPUs. At 23% utilization, you are effectively paying $69.56/effective-GPU-hr for a resource that costs $8.00/GPU-hr at full utilization on an H100.

## The Effective Cost Math

Cloud providers bill GPU instances by the hour, regardless of what percentage of the GPU is actually doing work. This creates a nonlinear relationship between utilization and effective cost per unit of compute.

Using AWS p4d.24xlarge (8x A100 40GB) at $32.77/hr as a reference point:

| GPU Utilization | Hourly Charge | Effective Cost/GPU-hr | vs. 100% Utilization |
|---|---|---|---|
| 100% | $32.77/hr | $4.10/GPU-hr | baseline |
| 75% | $32.77/hr | $5.46/GPU-hr | **+33%** |
| 50% | $32.77/hr | $8.19/GPU-hr | **+100%** |
| 23% (industry avg) | $32.77/hr | $17.80/GPU-hr | **+334%** |
| 10% | $32.77/hr | $41.00/GPU-hr | **+900%** |

At the industry average of 23% utilization, you are paying **4.3x more per productive GPU-hour** than a team running their hardware efficiently. For a team spending $100K/month on GPUs at 23% utilization, bringing efficiency to 70% means the same productive workload costs approximately $33K/month — a **$67K/month recovery** from operational discipline alone.

This math gets worse with newer hardware. A p5.48xlarge (8x H100 SXM5) runs approximately $98.32/hr. At 23% utilization:

- Effective cost per productive GPU-hour: $53.44
- Monthly waste vs 70% utilization target: approximately $57,600/month on a single node
- Annualized: $691,000 in waste from one poorly-utilized 8xH100 node

Most companies running serious ML workloads have more than one GPU node. Do the math for your fleet.

## Why GPU Utilization Is Chronically Low

The 23% average is not a random outcome. It is the predictable result of several structural patterns in how ML workloads operate:

### Training Jobs End Without Instance Termination

This is the single largest source of GPU waste for teams that aren't fully managed on SageMaker or Vertex AI. A training job runs for 6 hours, completes at 2 AM, and the instance keeps running until someone SSHs in Monday morning. The instance billed 60+ hours of idle GPU time because no one implemented job completion → termination automation.

The fix is three lines of code in any training script:

```python
import subprocess
import sys

def run_training():
    # ... your training code ...
    pass

if __name__ == "__main__":
    try:
        run_training()
        print("Training complete, terminating instance...")
    finally:
        if not os.getenv("SKIP_TERMINATE"):  # Safety valve for development
            # AWS
            subprocess.run(["aws", "ec2", "terminate-instances", 
                          "--instance-ids", get_instance_id()])
            # GCP
            # subprocess.run(["gcloud", "compute", "instances", "delete", 
            #                get_instance_name(), "--zone", ZONE, "--quiet"])
```

For managed training (SageMaker, Vertex AI, Azure ML), this termination is automatic when the training job completes. If you're running training on raw EC2/GCP Compute instances without this automation, you are almost certainly paying for idle GPU time every week.

### Development and Experimentation Are Low-Utilization by Design

A researcher iterating on model architecture uses 3-8% of an A100's compute while they're writing code, reading papers, and running exploratory queries between training epochs. They need the GPU on standby for quick iteration, but the actual compute demand is minimal.

Paying $98/hr for an interactive development environment is between 15x-30x more expensive than appropriate alternatives, depending on the workload.

The right tooling for development vs production:

| Use Case | Right Instance | Avoid |
|---|---|---|
| Interactive notebook development | T4 (G4dn.xlarge, $0.526/hr) | A100/H100 |
| Exploratory training runs (<2hr) | A10G (G5.2xlarge, $1.21/hr) | H100 |
| Production fine-tuning | A100 (P4d) | H100 unless needed |
| Large model training (70B+) | H100 (P5) | A100 (insufficient VRAM) |
| High-throughput inference | A10G (G5) or inf2 | A100 (over-spec) |
| Low-latency inference (<100ms) | inf2 (AWS Inferentia2) | Any GPU (wrong tool) |

The largest single GPU optimization most teams can make is **separating development infrastructure from training infrastructure**. Dev environments should use T4s with idle-timeout auto-stop policies. Training runs on A100/H100s that terminate when jobs complete. The cost difference is 20-30x.

### Inference Endpoints Provision for Peak, Pay for Trough

A model endpoint deployed to handle peak traffic load incurs that cost 24/7, even when it's serving 5 requests per minute at 2 AM instead of 500 per minute at 2 PM.

Most inference workloads have a traffic ratio of 10:1 to 50:1 between peak and trough hours. Without autoscaling that can scale GPU replicas down (or to zero during overnight periods), you're paying for peak capacity at trough hours for the majority of the day.

AWS, Azure, and GCP all support GPU endpoint autoscaling. The operational complexity is checkpointing model loading time (warm-up latency when scaling from zero) and configuring appropriate scale-in cooldowns to avoid thrashing.

A well-configured inference autoscaling policy for a medium-sized production endpoint typically looks like:

```json
{
  "min_capacity": 1,
  "max_capacity": 10,
  "scale_out_cooldown": 60,
  "scale_in_cooldown": 600,
  "target_metric": "GPUUtilization",
  "target_value": 60,
  "scale_to_zero_after_hours": 22,
  "scale_to_zero_before_hours": 6
}
```

The 10-minute scale-in cooldown prevents premature scale-in during traffic lulls. The scale-to-zero window captures overnight savings. For an endpoint that would otherwise run 2 GPU instances 24/7, this configuration typically recovers 35-40% of cost.

### Multi-Tenant Clusters Have Invisible Waste

When multiple teams share a GPU cluster without per-job resource accounting, overprovisioned jobs crowd out other workloads and force the cluster to maintain larger capacity than aggregate demand requires.

A common pattern: Team A requests 4 GPUs for a job that needs 2. Team B requests 8 GPUs for a job that needs 5. The cluster scheduler satisfies both requests, but 5 GPUs across those two jobs are doing nothing. Without per-job utilization monitoring, this waste is invisible — the cluster appears "at capacity" even though half its GPUs are idle.

The solution is resource quotas with actual utilization enforcement:

```yaml
# Kubernetes resource quotas with GPU enforcement
apiVersion: v1
kind: ResourceQuota
metadata:
  name: ml-team-quota
  namespace: ml-team
spec:
  hard:
    requests.nvidia.com/gpu: "8"   # Max reserved GPUs
    limits.nvidia.com/gpu: "16"    # Hard maximum
```

Combined with a weekly utilization review process where teams report actual vs requested GPU usage, this drives self-correction on overprovisioned job specs.

## Finding Your GPU Waste: A Practical Audit

Here's the exact process to quantify your GPU waste in under two hours.

### Step 1: List Running GPU Instances

**AWS:**
```bash
aws ec2 describe-instances \
  --filters "Name=instance-type,Values=p3.*,p4d.*,p4de.*,p5.*,g4dn.*,g5.*" \
  --query 'Reservations[].Instances[].{ID:InstanceId,Type:InstanceType,State:State.Name,Launch:LaunchTime}' \
  --output table
```

**GCP:**
```bash
gcloud compute instances list \
  --filter="(machineType:n1-highmem OR machineType:a2 OR machineType:a3)" \
  --format="table(name,machineType,status,creationTimestamp)"
```

**Azure:**
```bash
az vm list --output table \
  --query "[?contains(hardwareProfile.vmSize, 'NC') || contains(hardwareProfile.vmSize, 'ND') || contains(hardwareProfile.vmSize, 'NV')]"
```

### Step 2: Pull GPU Utilization for Each Instance

**AWS CloudWatch (7-day average):**
```bash
# For each instance_id from step 1
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name GPUUtilization \
  --dimensions Name=InstanceId,Value=$INSTANCE_ID \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 86400 \
  --statistics Average \
  --query 'Datapoints[].Average' \
  --output text | awk '{sum+=$1; n++} END {print "7-day avg GPU util:", sum/n "%"}'
```

Note: `GPUUtilization` metric is only available for instances with the CloudWatch agent installed and GPU metrics configured. For instances without it, use nvidia-smi output forwarded to CloudWatch or your monitoring platform.

### Step 3: Calculate Waste Cost

For each instance, the monthly waste cost vs a 70% utilization target:

```python
# GPU waste calculator
HOURLY_RATES = {
    "p3.8xlarge": 12.24,    # 4x V100
    "p3.16xlarge": 24.48,   # 8x V100
    "p4d.24xlarge": 32.77,  # 8x A100 40GB
    "p4de.24xlarge": 40.97, # 8x A100 80GB
    "p5.48xlarge": 98.32,   # 8x H100 SXM5
    "g4dn.xlarge": 0.526,   # 1x T4
    "g4dn.12xlarge": 3.912, # 4x T4
    "g5.xlarge": 1.006,     # 1x A10G
    "g5.48xlarge": 16.29,   # 8x A10G
}

def calculate_monthly_gpu_waste(instance_type: str, actual_util_pct: float, hours_per_month: float = 730):
    hourly_rate = HOURLY_RATES.get(instance_type, 0)
    if not hourly_rate:
        return 0
    
    target_util = 0.70  # 70% target utilization
    actual_util = actual_util_pct / 100
    
    # Cost at actual utilization vs target utilization (same total compute output)
    # If actual is lower than target, you're paying for unused capacity
    if actual_util >= target_util:
        return 0  # No waste
    
    waste_fraction = (target_util - actual_util) / target_util
    monthly_cost = hourly_rate * hours_per_month
    monthly_waste = monthly_cost * waste_fraction
    
    return {
        "instance": instance_type,
        "monthly_cost": round(monthly_cost, 2),
        "utilization": f"{actual_util_pct:.1f}%",
        "waste_fraction": f"{waste_fraction*100:.1f}%",
        "monthly_waste": round(monthly_waste, 2),
        "annual_waste": round(monthly_waste * 12, 2),
    }

# Example calculation
result = calculate_monthly_gpu_waste("p4d.24xlarge", actual_util_pct=23.0)
print(result)
# {'instance': 'p4d.24xlarge', 'monthly_cost': 23922.1, 'utilization': '23.0%',
#  'waste_fraction': '67.1%', 'monthly_waste': 16052.0, 'annual_waste': 192624.5}
```

### Step 4: Identify Which Pattern Applies

For each underutilized instance, determine which waste pattern explains it:

| Pattern | Signal | Fix |
|---|---|---|
| Completed training job | Instance running, no GPU process active | Auto-termination on job completion |
| Idle dev environment | Low but present utilization (<10%), SSH sessions active | Scheduled stop/start or idle-timeout policy |
| Oversized for workload | Utilization 30-50%, always-on process | Rightsize to smaller GPU instance |
| Oversized inference | Utilization varies, spikes to 60%+, troughs to <5% | GPU endpoint autoscaling |
| Multi-tenant cluster inefficiency | Cluster "busy" per scheduler, low actual utilization | Per-job resource quotas |

## The Five GPU Waste Patterns and Their Fixes

### Pattern 1: The Forgotten Training Run

**Symptoms:** Instance running, GPU memory allocated to a CUDA process, but no active training job. `nvidia-smi` shows a process but utilization is <2%. SSH session ended hours ago.

**Why it happens:** Training completed, but no termination automation was implemented. The instance is waiting for a human to notice.

**Fix (AWS):**
```python
# training_wrapper.py
import boto3
import subprocess
import signal
import sys
import os

def get_instance_id():
    """Get EC2 instance ID from metadata service."""
    import urllib.request
    token = urllib.request.urlopen(
        urllib.request.Request(
            'http://169.254.169.254/latest/api/token',
            headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'},
            method='PUT'
        )
    ).read().decode()
    return urllib.request.urlopen(
        urllib.request.Request(
            'http://169.254.169.254/latest/meta-data/instance-id',
            headers={'X-aws-ec2-metadata-token': token}
        )
    ).read().decode()

def terminate_on_complete():
    instance_id = get_instance_id()
    ec2 = boto3.client('ec2', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
    print(f"Training complete. Terminating instance {instance_id}...")
    ec2.terminate_instances(InstanceIds=[instance_id])

if __name__ == "__main__":
    try:
        # Import and run your actual training here
        from train import main
        main()
    except Exception as e:
        print(f"Training failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if os.environ.get("AUTO_TERMINATE", "true").lower() == "true":
            terminate_on_complete()
```

Set `AUTO_TERMINATE=false` in your `.env.local` during development to avoid accidentally terminating dev instances.

### Pattern 2: Idle Development Environments

**Symptoms:** Instance running with <15% GPU utilization, intermittent spikes when notebooks execute cells, continuous low baseline charge.

**Why it happens:** Researchers need GPU-accelerated environments for quick iteration but spend majority of time reading, writing, or waiting for results.

**Fix (AWS idle-timeout via CloudWatch):**
```bash
# Create CloudWatch alarm that stops instance after 30 min of <5% GPU utilization
aws cloudwatch put-metric-alarm \
  --alarm-name "gpu-idle-stop-$INSTANCE_ID" \
  --metric-name GPUUtilization \
  --namespace AWS/EC2 \
  --dimensions Name=InstanceId,Value=$INSTANCE_ID \
  --statistic Average \
  --period 1800 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator LessThanOrEqualToThreshold \
  --alarm-actions "arn:aws:swf:us-east-1:$ACCOUNT_ID:action/actions/AWS_EC2.InstanceId.Stop/1.0" \
  --ok-actions "" \
  --treat-missing-data notBreaching
```

Alternatively, use AWS Instance Scheduler or a Lambda function on a cron schedule to stop/start dev instances:

```python
# lambda_gpu_scheduler.py — runs on EventBridge schedule
import boto3

def handler(event, context):
    ec2 = boto3.client('ec2')
    action = event.get('action')  # 'start' or 'stop'
    
    # Get all dev GPU instances by tag
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:Environment', 'Values': ['development']},
            {'Name': 'tag:GpuScheduled', 'Values': ['true']},
            {'Name': 'instance-state-name', 'Values': ['running' if action == 'stop' else 'stopped']}
        ]
    )
    
    instance_ids = [
        i['InstanceId'] 
        for r in response['Reservations'] 
        for i in r['Instances']
    ]
    
    if instance_ids:
        if action == 'stop':
            ec2.stop_instances(InstanceIds=instance_ids)
            print(f"Stopped {len(instance_ids)} dev GPU instances")
        else:
            ec2.start_instances(InstanceIds=instance_ids)
            print(f"Started {len(instance_ids)} dev GPU instances")
```

Schedule stop at 8 PM, start at 8 AM weekdays. For a $32.77/hr p4d instance, this recovers 16 off-hours × 5 days + 48 weekend hours = 128 hours/week → **$4,194/week** from one node.

### Pattern 3: Wrong Instance Type for Workload

**Symptoms:** A100 or H100 instances running inference workloads that have consistent, moderate throughput with GPU utilization around 30-45%.

**Why it happens:** Infrastructure provisioned for training was repurposed for inference without resizing. Or the team "future-proofed" by over-specifying initial inference infrastructure.

**Fix:** Match GPU type to workload requirements.

The GPU selection decision tree:
- Model parameters > 70B, or training at scale → H100 SXM5 (p5)
- Model parameters 7B-70B training, or large-batch inference → A100 (p4d)
- Model parameters up to 13B inference, real-time serving → A10G (g5)
- CV inference, embedding generation, small model inference → T4 (g4dn)
- CPU-viable inference, cost-critical → Inferentia2 (inf2) — 40-70% cheaper than GPU for compatible models

For an inference workload running on a p4d.24xlarge that actually fits on two g5.48xlarges, the cost difference:
- p4d.24xlarge: $32.77/hr
- 2x g5.48xlarge: 2 × $16.29 = $32.58/hr

Nearly identical cost, but the g5 instances are purpose-built for inference workloads and will often deliver better throughput-per-dollar for the specific operations involved.

### Pattern 4: Overprovisioned Inference Endpoints

**Symptoms:** Inference endpoint with traffic that varies 10:1 or more between peak and trough. GPU utilization spikes to 70%+ for 4-6 hours, then drops to <10% for 18+ hours.

**Fix:** Enable GPU autoscaling with appropriate warmup configuration.

For SageMaker:
```python
import boto3

client = boto3.client('application-autoscaling')

# Register the endpoint variant as a scalable target
client.register_scalable_target(
    ServiceNamespace='sagemaker',
    ResourceId=f'endpoint/{endpoint_name}/variant/{variant_name}',
    ScalableDimension='sagemaker:variant:DesiredInstanceCount',
    MinCapacity=1,
    MaxCapacity=10
)

# Scale out aggressively (2 min evaluation), scale in conservatively (10 min cooldown)
client.put_scaling_policy(
    PolicyName=f'{endpoint_name}-gpu-scaling',
    ServiceNamespace='sagemaker',
    ResourceId=f'endpoint/{endpoint_name}/variant/{variant_name}',
    ScalableDimension='sagemaker:variant:DesiredInstanceCount',
    PolicyType='TargetTrackingScaling',
    TargetTrackingScalingPolicyConfiguration={
        'TargetValue': 60.0,  # Target 60% GPU utilization
        'CustomizedMetricSpecification': {
            'MetricName': 'GPUUtilization',
            'Namespace': '/aws/sagemaker/Endpoints',
            'Dimensions': [
                {'Name': 'EndpointName', 'Value': endpoint_name},
                {'Name': 'VariantName', 'Value': variant_name}
            ],
            'Statistic': 'Average'
        },
        'ScaleInCooldown': 600,   # 10 minutes — don't scale in too fast
        'ScaleOutCooldown': 120,  # 2 minutes — scale out quickly on traffic spikes
    }
)
```

### Pattern 5: Spot Instance Opportunity for Training

The most underutilized cost reduction available to any team doing ML training: **spot instances**.

AWS spot GPU pricing vs on-demand (approximate, varies by availability):

| Instance | On-Demand | Spot (typical) | Savings |
|---|---|---|---|
| p3.8xlarge | $12.24/hr | $3.67/hr | 70% |
| p3.16xlarge | $24.48/hr | $7.34/hr | 70% |
| g5.48xlarge | $16.29/hr | $4.89/hr | 70% |
| g4dn.12xlarge | $3.912/hr | $1.17/hr | 70% |

The only operational cost: implementing checkpointing so a spot interruption (which gives you a 2-minute warning) doesn't lose hours of training progress. Any training run over 30 minutes should implement periodic checkpointing regardless — it's good practice for fault tolerance independent of the cost savings.

```python
# Checkpoint wrapper for spot-safe training
import torch
import os
import json
from pathlib import Path

class SpotSafeTrainer:
    def __init__(self, checkpoint_dir: str, checkpoint_every_n_steps: int = 100):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_every_n = checkpoint_every_n_steps
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
    def save_checkpoint(self, model, optimizer, step: int, epoch: int, loss: float):
        checkpoint = {
            'step': step,
            'epoch': epoch,
            'loss': loss,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
        }
        path = self.checkpoint_dir / f'checkpoint_step_{step}.pt'
        torch.save(checkpoint, path)
        
        # Keep only last 3 checkpoints
        checkpoints = sorted(self.checkpoint_dir.glob('checkpoint_step_*.pt'))
        for old_ckpt in checkpoints[:-3]:
            old_ckpt.unlink()
    
    def load_latest_checkpoint(self, model, optimizer):
        checkpoints = sorted(self.checkpoint_dir.glob('checkpoint_step_*.pt'))
        if not checkpoints:
            return 0, 0, None
        
        ckpt = torch.load(checkpoints[-1])
        model.load_state_dict(ckpt['model_state_dict'])
        optimizer.load_state_dict(ckpt['optimizer_state_dict'])
        return ckpt['step'], ckpt['epoch'], ckpt['loss']
```

## Building a GPU Cost Dashboard

You can't manage what you can't see. The minimum viable GPU cost dashboard has five metrics:

1. **GPU utilization by instance, 7-day trailing average** — your primary waste signal
2. **Cost per GPU-hour of actual compute** — the effective cost metric
3. **Instances idle >1 hour** (utilization <5%) — your immediate action list
4. **Training job completion → termination time** — identifies missed terminations
5. **Monthly GPU spend vs budget** — the executive summary

If you're on AWS, these metrics are all available in CloudWatch. The gap is aggregation and visualization. A Grafana dashboard pulling from CloudWatch with appropriate alert thresholds handles the visibility layer.

For teams preferring a managed solution, CloudFinOps ingests these metrics across AWS, Azure, and GCP, surfaces the idle instances with one-click investigation, and calculates the savings from each fix — removing the manual aggregation work.

## The Business Case

Gartner projects that **50%+ of GenAI projects will overrun budgets through 2028**. GPU waste is the primary mechanical cause of those overruns. Training runs that should cost $2,000 cost $8,000 because nobody implemented auto-termination. Inference endpoints that should cost $3,000/month cost $12,000/month because autoscaling wasn't configured.

These are not complex engineering problems. They are operational discipline problems with straightforward technical solutions. The teams that build the discipline now — auto-termination, right instance type selection, autoscaling inference, spot training — will run AI infrastructure at 60-70% utilization. The teams that don't will continue paying 4x more per productive GPU-hour than necessary.

At scale, that difference is the gap between AI being a competitive advantage and AI being a budget crisis.

---

*CloudFinOps detects idle and underutilized GPU instances across AWS, Azure, and GCP, and surfaces specific auto-termination, rightsizing, and autoscaling recommendations with projected monthly savings. [Scan your cloud bill free](/bill-scan) to see your GPU waste estimate in under 60 seconds.*
