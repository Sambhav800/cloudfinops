# Workload Pattern Analyzer — Design Document

## Problem Statement

Current scanner takes a 7-day daily average of CPU/memory and classifies resources with simple thresholds:
- CPU avg < 2% → Zombie
- Utilization < 25% → Underutilized (rightsize)
- avg < 20%, max > 50% → "Bursty" (but no action)

This misclassifies resources with **diurnal patterns** (high during business hours, low at night) as underutilized because the 24h average looks low. A web server doing 80% CPU during 9am-6pm and 5% at night averages ~35% — the scanner says "moderate" but the real recommendation should be **autoscaling** with min=1 max=4.

## Solution: Time-Series Workload Pattern Classifier

### Architecture

```
Azure Monitor / CloudWatch
       │
       ▼ (30 days × hourly = 720 data points)
┌──────────────────────────┐
│  Workload Pattern Engine │
│                          │
│  1. Fetch hourly metrics │
│  2. Classify pattern     │
│  3. Compute thresholds   │
│  4. Generate rec         │
└──────────────────────────┘
       │
       ▼
 Recommendation: AUTOSCALE / RIGHTSIZE / SCHEDULE / SPOT
```

### Pattern Classification

| Pattern | Detection Logic | Recommendation |
|---------|----------------|----------------|
| **Diurnal** | Std dev of hourly-of-day averages > 15% of mean; peak/trough ratio > 3:1 | Autoscale with computed min/max |
| **Weekly** | Weekday avg > 2× weekend avg | Schedule (stop weekends) + Autoscale weekdays |
| **Steady-State** | Coefficient of variation < 0.3 | Rightsize to P95 + buffer |
| **Burst/Sporadic** | P99 > 5× P50; most hours near zero | Spot instances or serverless |
| **Growing** | Linear regression slope > 2% per week | Right-size up; warn about capacity |

### Metric Collection (30-day PT1H)

**Azure Monitor API:**
```python
timespan = "P30D"  # or ISO 8601 range
interval = "PT1H"  # hourly granularity
metrics = "Percentage CPU,Available Memory Bytes,Network In Total"
aggregation = "Average,Maximum,Minimum"
```

**AWS CloudWatch:**
```python
Period = 3600  # 1 hour
StartTime = now - 30 days
Statistics = ['Average', 'Maximum', 'Minimum']
MetricName = 'CPUUtilization'  # + NetworkIn, MemoryUtilization (via agent)
```

### Autoscaling Threshold Calculation

For diurnal patterns:
```
min_threshold = P10 of hourly averages (trough floor)
max_threshold = P90 of hourly averages (peak ceiling)
scale_out_cpu = P75 of peak-hour averages (when to add capacity)
scale_in_cpu  = P25 of trough-hour averages (when to remove capacity)

Recommended min instances = ceil(peak_demand / max_single_instance_capacity)
Recommended max instances = ceil(P99_demand / comfortable_single_capacity)
```

### Decision Matrix

```
IF pattern == DIURNAL and peak_trough_ratio > 2.5:
    → AUTOSCALE
    → min_instances based on trough demand
    → max_instances based on peak demand + 20% buffer
    → scale_out_threshold = 70% (industry standard)
    → scale_in_threshold = 30%

ELIF pattern == STEADY_STATE and avg_utilization < 30%:
    → RIGHTSIZE
    → target_size = smallest SKU that handles P95 load + 30% buffer

ELIF pattern == WEEKLY and weekend_avg < 10%:
    → SCHEDULE
    → stop_times: Sat 00:00 - Mon 06:00
    → savings: (weekend_hours / total_hours) × monthly_cost

ELIF pattern == BURST and idle_hours_pct > 80%:
    → SPOT/SERVERLESS
    → "This workload is idle 80%+ of the time with rare bursts. 
       Consider Azure Functions or Spot VMs with checkpointing."
```

### Confidence Scoring

```
confidence = base_confidence × data_quality_factor × pattern_clarity_factor

data_quality_factor:
  - 30 days data: 1.0
  - 14-29 days: 0.85
  - 7-13 days: 0.7
  - < 7 days: 0.5

pattern_clarity_factor:
  - peak/trough ratio > 5:1: 1.0 (crystal clear diurnal)
  - ratio 3:1 - 5:1: 0.9
  - ratio 2:1 - 3:1: 0.75
  - ratio < 2:1: 0.6 (ambiguous)
```

### Implementation Plan

**Phase 1: Metric Collection Upgrade**
- New method `_get_vm_metrics_hourly(resource_id)` → 30 days × PT1H
- Returns 720 data points per metric (CPU, memory, network)
- Cache raw metrics in resource metadata for dashboard charts

**Phase 2: Pattern Classifier**
- New module `backend/app/core/workload_patterns.py`
- Functions: `classify_pattern()`, `compute_autoscale_thresholds()`, `compute_schedule()`
- Uses numpy-free math (mean, std, percentiles via statistics module)

**Phase 3: Recommendation Engine Overhaul**
- Replace "underutilized → rightsize" with pattern-aware decisions
- New recommendation types: `autoscale`, `schedule`, `spot_candidate`, `rightsize`
- Each recommendation includes: action, thresholds, estimated savings, evidence chart data

**Phase 4: AI Integration**
- Feed pattern classification + raw hourly data to Gemini for:
  - Validating the pattern detection
  - Generating natural-language explanation
  - Correlating with cost data to estimate savings
  - Suggesting specific Azure VMSS / AWS ASG configurations

### Recommendation Schema

```python
{
    "type": "autoscale",
    "resource_id": "...",
    "resource_name": "demo-web-server",
    "pattern_detected": "diurnal",
    "evidence": {
        "observation_days": 30,
        "peak_hours": ["09:00-18:00 IST"],
        "trough_hours": ["22:00-06:00 IST"],
        "peak_avg_cpu": 72.4,
        "trough_avg_cpu": 8.2,
        "peak_trough_ratio": 8.8,
        "data_points": 720
    },
    "recommendation": {
        "action": "Enable Azure Virtual Machine Scale Sets (VMSS) autoscaling",
        "min_instances": 1,
        "max_instances": 4,
        "scale_out_threshold_cpu": 70,
        "scale_in_threshold_cpu": 30,
        "cooldown_minutes": 5,
        "explanation": "This VM shows a strong diurnal pattern — 72% CPU during business hours, 8% at night. Instead of paying for peak capacity 24/7, autoscaling with 1-4 instances saves ~40% by scaling down during low-traffic hours."
    },
    "estimated_savings_pct": 40,
    "estimated_savings_monthly_usd": 56.0,
    "confidence": 0.92,
    "severity": "high"
}
```

### References

- Google Active Assist: Uses 8 days of 5-min data for recommendations
- AWS Compute Optimizer: Uses 14 days of CloudWatch metrics (5-min intervals)
- Azure Advisor: Uses 7-14 days of daily aggregates (our current approach — weakest)
- Spot.io: Uses 30+ days with ML-based pattern detection
- Research: "Workload Characterization and Prediction in the Cloud" (Reiss et al., Google, 2012)
- Research: "Auto-scaling Web Applications in Clouds" (Lorido-Botran et al., 2014)
- Industry: FinOps Foundation "Right Sizing" domain (recommends P95 + buffer approach)
