---
title: "BigQuery Cost Optimization: Slots vs On-Demand and 8 Query Patterns That Drain Your Budget"
slug: "bigquery-cost-optimization-slots-vs-on-demand"
excerpt: "BigQuery's on-demand pricing makes it easy to run a $500 query without realizing it. Learn when to switch to slots, which query patterns waste money, and how to set up cost controls."
category: "GCP"
author:
  name: "Sambhav Pal"
  role: "Founder & CEO"
  avatar: "/images/team/founder.png"
publishedAt: "2026-08-19"
updatedAt: "2026-08-19"
readTime: 13
featured: false
tags: ["gcp", "bigquery", "cost-optimization", "slots", "query-optimization"]
---

## The $500 Query Problem

A data analyst runs a query against a 4 TB events table. The query takes 8 seconds. The analyst thinks "that was fast, BigQuery is great." The query cost $25. They run variations of it 20 times during their analysis session. That afternoon's exploration cost $500.

Nobody notices until the monthly bill arrives three weeks later.

This is the fundamental tension of BigQuery's on-demand pricing model. It's frictionless to start, requires no capacity planning, and charges you per byte scanned. That last part is the trap. Unlike a provisioned database where bad queries just run slowly, in BigQuery bad queries run fast AND cost more. There's no natural feedback loop telling you to stop.

Google reports that the median BigQuery customer spends 40-60% of their budget on queries that could be optimized to scan 80% less data. That's not a rounding error. That's the difference between a $3,000/month analytics bill and a $12,000 one.

This guide covers the two levers you have: choosing the right pricing model (on-demand vs slots), and fixing the query patterns that waste the most money regardless of which model you're on.

## On-Demand vs Slots: Understanding BigQuery's Two Pricing Models

BigQuery offers two fundamentally different pricing approaches, and choosing wrong can double your costs.

### On-Demand Pricing

With on-demand, you pay $6.25 per TB of data scanned by your queries (as of 2026). You don't pay for storage separately in this context—storage is $0.02/GB/month for active data and $0.01/GB/month for long-term data regardless of your compute pricing model.

**How it works:** Every query scans some amount of data. A `SELECT *` on a 2 TB table scans 2 TB and costs $12.50. A query that selects two columns from the same partitioned and clustered table might scan 15 GB and cost $0.09.

**Who it's good for:**
- Teams scanning less than ~60 TB/month (roughly $375/month)
- Highly variable workloads—some weeks heavy analysis, some weeks nothing
- Exploration and ad-hoc analysis where usage is unpredictable
- Small teams (fewer than 5 active analysts)

**The risk:** A single poorly-written scheduled query running hourly against an unpartitioned table can cost more per month than a flat-rate slot reservation would.

### Slots (Editions Pricing)

Slots are units of BigQuery compute capacity. Instead of paying per byte scanned, you buy a fixed number of slots and your queries share that capacity. Your queries can scan as much data as they want—you've already paid for the compute.

**How it works:** You purchase slot commitments (100 slots minimum for most editions). Your queries queue for available slots. More slots = more concurrent queries running at full speed. Fewer slots = queries wait longer or run slower.

> **Key insight:** Slots don't make individual queries cheaper by scanning less data. They make your total monthly bill predictable and capped. If your team runs enough queries, the flat cost of slots becomes cheaper per-query than on-demand.

### The Editions Comparison

Google restructured BigQuery pricing into three editions in 2023. Here's how they compare:

| Feature | On-Demand | Standard Edition | Enterprise Edition | Enterprise Plus |
|---|---|---|---|---|
| Pricing model | $6.25/TB scanned | $0.04/slot-hour | $0.06/slot-hour | $0.10/slot-hour |
| Minimum commitment | None | 100 slots (autoscale) | 100 slots (autoscale) | 100 slots (autoscale) |
| Commitment options | None | None (pay-as-you-go) | 1-year, 3-year | 1-year, 3-year |
| Autoscaling | N/A | Up to 1600 slots | Up to 2400 slots | Up to 4800 slots |
| Baseline discount (1yr) | N/A | N/A | ~30% off pay-as-you-go | ~30% off pay-as-you-go |
| Baseline discount (3yr) | N/A | N/A | ~50% off pay-as-you-go | ~50% off pay-as-you-go |
| BI Engine | Not included | Not included | Included | Included |
| Materialized views auto-refresh | Manual | Manual | Auto | Auto with zero-cost |
| Row-level security | Yes | Yes | Yes | Advanced policies |
| Multi-region failover | No | No | No | Yes |

**The breakeven calculation:** At on-demand rates of $6.25/TB, if your team scans more than ~60 TB/month consistently, Standard Edition's 100 slots at $0.04/slot-hour ($2,880/month) starts becoming cheaper. At 150+ TB/month, Enterprise Edition with a 1-year commitment is almost certainly cheaper.

### How to Calculate Your Breakeven

Run this query against your project's INFORMATION_SCHEMA to get your monthly scan volume:

```sql
SELECT
  TIMESTAMP_TRUNC(creation_time, MONTH) AS month,
  SUM(total_bytes_processed) / POW(1024, 4) AS tb_scanned,
  SUM(total_bytes_processed) / POW(1024, 4) * 6.25 AS estimated_on_demand_cost
FROM
  `region-us`.INFORMATION_SCHEMA.JOBS
WHERE
  creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 6 MONTH)
  AND job_type = 'QUERY'
  AND state = 'DONE'
GROUP BY month
ORDER BY month DESC;
```

If your monthly scan consistently exceeds 60 TB and the trend is stable or growing, it's time to evaluate slots.

## The 8 Query Patterns That Drain Your Budget

Regardless of whether you're on on-demand or slots, these patterns waste resources. On on-demand, they directly inflate your bill. On slots, they consume capacity that could serve other queries, creating bottlenecks that force you to buy more slots.

### Pattern 1: SELECT * (The Silent Budget Killer)

BigQuery is columnar. It stores each column separately. When you select only the columns you need, BigQuery only reads those columns from storage. When you use `SELECT *`, it reads every column.

**Expensive:**
```sql
-- Scans ALL columns from a 3 TB table = $18.75
SELECT *
FROM `project.dataset.events`
WHERE event_date = '2026-08-01'
LIMIT 100;
```

**Optimized:**
```sql
-- Scans only 3 columns, maybe 45 GB = $0.28
SELECT event_id, user_id, event_name
FROM `project.dataset.events`
WHERE event_date = '2026-08-01'
LIMIT 100;
```

The `LIMIT` clause doesn't help with cost. BigQuery still scans the full data matching your `WHERE` clause before applying the limit. The savings come entirely from selecting fewer columns.

### Pattern 2: No Partitioning

An unpartitioned table forces BigQuery to scan the entire table for every query, even if you only need yesterday's data.

**Expensive:**
```sql
-- Scans entire 2 TB table even though you only want one day
SELECT user_id, event_name, timestamp
FROM `project.dataset.events_unpartitioned`
WHERE DATE(timestamp) = '2026-08-01';
```

**Optimized:**
```sql
-- With a date-partitioned table, only scans the single partition (~7 GB)
SELECT user_id, event_name, timestamp
FROM `project.dataset.events_partitioned`
WHERE event_date = '2026-08-01';  -- partition filter
```

Create partitioned tables at design time:
```sql
CREATE TABLE `project.dataset.events_partitioned`
PARTITION BY event_date
CLUSTER BY user_id
AS SELECT * FROM `project.dataset.events_unpartitioned`;
```

> **Key insight:** Require partition filters on all production tables. Set `require_partition_filter = true` in table options so that queries without a partition predicate are rejected outright rather than scanning the whole table by accident.

### Pattern 3: Cross-Joins and Cartesian Products

Cross-joins multiply rows. A 10M row table crossed with a 1M row table produces 10 trillion row combinations. Even if BigQuery can handle it, you're paying for that explosion.

**Expensive:**
```sql
-- Accidental cross-join via comma syntax: 10M x 500K = 5 trillion combinations
SELECT a.user_id, b.product_name
FROM `project.dataset.users` a, `project.dataset.products` b
WHERE a.preferred_category = b.category;
```

**Optimized:**
```sql
-- Explicit JOIN scans only matching rows
SELECT a.user_id, b.product_name
FROM `project.dataset.users` a
INNER JOIN `project.dataset.products` b
  ON a.preferred_category = b.category;
```

Always use explicit `JOIN` syntax. Never use comma-separated table lists in `FROM` clauses. The query optimizer usually catches this, but not always—especially with complex multi-table queries.

### Pattern 4: Repeated CTEs That Re-Scan Data

BigQuery doesn't materialize CTEs. Every time a CTE is referenced, the underlying query executes again. If you reference the same CTE three times, that data gets scanned three times.

**Expensive:**
```sql
-- CTE scans 800 GB. Referenced 3 times = 2.4 TB scanned
WITH user_metrics AS (
  SELECT user_id, SUM(revenue) as total_rev, COUNT(*) as events
  FROM `project.dataset.events`
  WHERE event_date BETWEEN '2026-01-01' AND '2026-08-01'
  GROUP BY user_id
)
SELECT 'high_value' as segment, COUNT(*) FROM user_metrics WHERE total_rev > 1000
UNION ALL
SELECT 'medium_value', COUNT(*) FROM user_metrics WHERE total_rev BETWEEN 100 AND 1000
UNION ALL
SELECT 'low_value', COUNT(*) FROM user_metrics WHERE total_rev < 100;
```

**Optimized:**
```sql
-- Single scan with conditional aggregation
SELECT
  COUNTIF(total_rev > 1000) AS high_value,
  COUNTIF(total_rev BETWEEN 100 AND 1000) AS medium_value,
  COUNTIF(total_rev < 100) AS low_value
FROM (
  SELECT user_id, SUM(revenue) as total_rev
  FROM `project.dataset.events`
  WHERE event_date BETWEEN '2026-01-01' AND '2026-08-01'
  GROUP BY user_id
);
```

Alternatively, materialize the CTE into a temporary table if you need to reference it multiple times in a complex pipeline:
```sql
CREATE TEMP TABLE user_metrics AS
SELECT user_id, SUM(revenue) as total_rev, COUNT(*) as events
FROM `project.dataset.events`
WHERE event_date BETWEEN '2026-01-01' AND '2026-08-01'
GROUP BY user_id;
```

### Pattern 5: No Clustering

Partitioning restricts which partitions BigQuery reads. Clustering determines the sort order within those partitions, allowing BigQuery to skip blocks of data that don't match your filter.

**Expensive:**
```sql
-- Table is partitioned by date but not clustered
-- Scans the entire day's partition (50 GB) to find one country
SELECT user_id, event_name
FROM `project.dataset.events`
WHERE event_date = '2026-08-01'
  AND country = 'US';
```

**Optimized:**
```sql
-- Same query on a table clustered by country
-- BigQuery skips blocks where country != 'US', scans maybe 8 GB
SELECT user_id, event_name
FROM `project.dataset.events_clustered`
WHERE event_date = '2026-08-01'
  AND country = 'US';
```

Cluster by columns that appear frequently in your `WHERE` and `GROUP BY` clauses. You can specify up to four clustering columns. Put the most-filtered column first.

```sql
CREATE TABLE `project.dataset.events_optimized`
PARTITION BY event_date
CLUSTER BY country, user_id, event_name
AS SELECT * FROM `project.dataset.events`;
```

### Pattern 6: Scanning Full Tables for Aggregates

Running daily dashboards that re-aggregate raw data from scratch each time wastes enormous amounts of scan.

**Expensive:**
```sql
-- Dashboard query runs every hour, re-scans 3 months of data each time
SELECT
  DATE(timestamp) AS day,
  COUNT(DISTINCT user_id) AS dau,
  SUM(revenue) AS daily_revenue
FROM `project.dataset.events`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
GROUP BY day;
```

**Optimized:** Pre-aggregate into a summary table updated incrementally:
```sql
-- Scheduled query runs once daily, appends only new data
INSERT INTO `project.dataset.daily_metrics` (day, dau, daily_revenue)
SELECT
  DATE(timestamp) AS day,
  COUNT(DISTINCT user_id) AS dau,
  SUM(revenue) AS daily_revenue
FROM `project.dataset.events`
WHERE DATE(timestamp) = CURRENT_DATE() - 1
GROUP BY day;
```

Your dashboard then queries the small summary table (a few KB) instead of scanning terabytes of raw events.

### Pattern 7: Streaming Inserts Abuse

BigQuery streaming inserts (`tabledata.insertAll`) cost $0.05 per GB inserted. For high-volume event streams, this adds up fast. A system pushing 100 GB/day of events via streaming inserts pays $5/day ($150/month) just for ingestion—on top of storage and query costs.

**Expensive pattern:** Using streaming inserts for batch data that arrives in files (Cloud Storage, GCS buckets), data that doesn't need to be queryable within seconds, or re-streaming data during backfills.

**Optimized:** Use free batch loading for anything that can tolerate a few minutes of latency:
```sql
-- Free batch load from GCS (no per-byte charge)
LOAD DATA INTO `project.dataset.events`
FROM FILES (
  format = 'PARQUET',
  uris = ['gs://bucket/events/2026-08-01/*.parquet']
);
```

Reserve streaming inserts only for data that genuinely must be queryable within seconds (real-time dashboards, alerting pipelines). Everything else should land in Cloud Storage first and batch-load for free.

### Pattern 8: Materialized View Gaps

BigQuery materialized views pre-compute aggregations and automatically maintain them as base data changes. Queries that match a materialized view's pattern are served from the pre-computed result at near-zero cost. Not creating them for your most common query patterns means re-scanning raw data every time.

**Without materialized view (scans 500 GB per execution):**
```sql
SELECT
  country,
  device_type,
  DATE(timestamp) AS day,
  COUNT(*) AS event_count,
  COUNT(DISTINCT user_id) AS unique_users
FROM `project.dataset.events`
WHERE event_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY country, device_type, day;
```

**With materialized view (scans ~0 bytes, reads from cache):**
```sql
CREATE MATERIALIZED VIEW `project.dataset.mv_daily_country_device`
PARTITION BY day
CLUSTER BY country
AS
SELECT
  country,
  device_type,
  event_date AS day,
  COUNT(*) AS event_count,
  COUNT(DISTINCT user_id) AS unique_users
FROM `project.dataset.events`
GROUP BY country, device_type, event_date;
```

Once created, any query whose pattern matches (even partially) gets automatically routed to the materialized view. On Enterprise Edition, these views auto-refresh at no additional cost.

> **Key insight:** Audit your top 20 most-expensive queries (see the INFORMATION_SCHEMA query below). If three or more share a similar aggregation pattern, that's a materialized view waiting to be created. A single materialized view can eliminate hundreds of dollars in monthly scan costs.

## Setting Up Cost Controls

BigQuery doesn't stop you from running a $500 query. You have to build your own guardrails.

### Custom Cost Quotas

Set project-level and user-level quotas to cap daily spending:

```sql
-- Set a project-wide daily limit of 10 TB scanned
-- (configured in GCP Console > BigQuery > Quotas, or via API)
-- Equivalent to ~$62.50/day on-demand cap
```

In the GCP Console, navigate to **IAM & Admin > Quotas**, filter for "BigQuery", and set:
- **Query usage per day per project**: limits total TB scanned across all users
- **Query usage per day per user**: limits individual users from running away with the budget

When a quota is hit, subsequent queries are rejected until the next day. This is a blunt instrument but effective at preventing bill shock.

### Find Your Most Expensive Queries

Use INFORMATION_SCHEMA to identify which queries, users, and scheduled jobs consume the most:

```sql
SELECT
  user_email,
  job_id,
  query,
  total_bytes_processed / POW(1024, 3) AS gb_scanned,
  total_bytes_processed / POW(1024, 4) * 6.25 AS estimated_cost_usd,
  total_slot_ms / 1000 AS slot_seconds,
  creation_time
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND error_result IS NULL
ORDER BY total_bytes_processed DESC
LIMIT 50;
```

This gives you the top 50 most expensive queries in the last 30 days. Look for patterns: is one scheduled query dominating? Is one user running exploratory `SELECT *` queries? Are there repeated queries that should be materialized views?

### Identify Repeated Expensive Queries

```sql
SELECT
  FARM_FINGERPRINT(query) AS query_hash,
  ANY_VALUE(query) AS sample_query,
  COUNT(*) AS execution_count,
  SUM(total_bytes_processed) / POW(1024, 4) AS total_tb_scanned,
  SUM(total_bytes_processed) / POW(1024, 4) * 6.25 AS total_cost_usd,
  AVG(total_bytes_processed) / POW(1024, 3) AS avg_gb_per_run
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND job_type = 'QUERY'
  AND state = 'DONE'
GROUP BY query_hash
HAVING COUNT(*) > 5
ORDER BY total_tb_scanned DESC
LIMIT 20;
```

Queries that run more than 5 times and scan large volumes are prime candidates for materialized views, pre-aggregation tables, or caching layers.

### Dry-Run Queries Before Execution

BigQuery supports dry-run mode that estimates bytes scanned without executing:

```sql
-- In bq CLI:
bq query --dry_run --use_legacy_sql=false \
  'SELECT * FROM `project.dataset.big_table` WHERE date = "2026-08-01"'

-- Returns: Query successfully validated. Assuming the tables are not modified,
-- running this query will process 847.3 GB of data.
```

Build this into your workflow. Before running any ad-hoc query against large tables, dry-run it first. If the estimate exceeds your comfort threshold (say, 100 GB), refine the query before executing.

### Slot Reservations with Autoscaling Caps

If you're on editions pricing, set autoscaling maximums to prevent cost spikes:

```sql
-- Create a reservation with autoscaling capped at 400 slots
-- Base: 100 slots ($0.04/slot-hour = $4/hour)
-- Max autoscale: 400 slots ($16/hour during peak)
CREATE RESERVATION `project.region-us.analytics_team`
OPTIONS (
  slot_capacity = 100,
  edition = 'ENTERPRISE',
  autoscale_max_slots = 400
);
```

This gives your team burst capacity for heavy workloads while capping the maximum hourly cost.

## When to Switch to Editions (Slots)

The decision to move from on-demand to slots depends on three factors: volume, predictability, and team size.

**Switch to Standard Edition when:**
- Monthly scan consistently exceeds 50-60 TB
- Most of that volume comes from scheduled queries and dashboards (predictable)
- You want cost predictability over optimization
- You don't need enterprise features like BI Engine or auto-refresh materialized views

**Switch to Enterprise Edition when:**
- Monthly scan exceeds 100 TB
- You have a mix of scheduled pipelines AND ad-hoc analysis
- You need BI Engine for Looker/connected sheets performance
- Your team is large enough (10+ analysts) that you need workload management
- Auto-refreshing materialized views would save significant engineering time

**Switch to Enterprise Plus when:**
- You have multi-region requirements
- Compliance needs advanced row-level security
- You need guaranteed capacity with no autoscaling delays
- Your workloads are mission-critical with strict SLAs

**Stay on on-demand when:**
- Monthly scan is below 40 TB and not growing
- Usage is highly unpredictable (some months 5 TB, some months 50 TB)
- You're a small team still figuring out your data architecture
- You'd rather optimize queries than manage slot reservations

### The Hybrid Approach

Many teams use both. Keep on-demand for ad-hoc exploration (data scientists, analysts doing one-off investigations) and use slot reservations for production pipelines (scheduled queries, ETL, dashboards). BigQuery lets you assign different projects to different reservations, so your production pipeline gets guaranteed capacity while ad-hoc work stays pay-per-query.

## Putting It All Together: A Cost Optimization Workflow

Here's a systematic approach to reducing BigQuery spend:

**Week 1: Measure**
- Run the INFORMATION_SCHEMA queries above to identify your top 20 most expensive queries
- Calculate your monthly scan volume and compare to slot pricing breakeven
- Identify which queries are scheduled vs ad-hoc

**Week 2: Quick Wins**
- Add partition filters to all queries hitting large tables
- Replace `SELECT *` with explicit column lists in scheduled queries
- Create materialized views for the top 3-5 repeated query patterns
- Enable `require_partition_filter` on large production tables

**Week 3: Architecture**
- Add clustering to tables based on common filter patterns
- Convert repeated CTEs to temp tables or pre-aggregation tables
- Switch batch ingestion from streaming inserts to free batch loads
- Set up daily/per-user quotas as guardrails

**Week 4: Pricing Model**
- If monthly scan exceeds breakeven, trial Standard Edition
- Set up separate reservations for production vs exploration workloads
- Configure autoscaling caps

If you're managing BigQuery costs alongside other cloud resources, CloudFinOps can ingest your GCP billing exports and surface BigQuery-specific spend patterns, identifying which datasets, tables, and scheduled queries contribute most to your bill without requiring you to manually run INFORMATION_SCHEMA queries.

## Frequently Asked Questions

**Does LIMIT reduce the amount of data scanned?**

No. BigQuery scans all data matching your `WHERE` and `FROM` clauses, then applies `LIMIT` to the results. A `SELECT * FROM big_table LIMIT 10` scans the entire table. The only way to reduce scan is to: select fewer columns, use partition filters, or query tables with clustering that matches your filters.

**Can I mix on-demand and slot-based pricing in the same organization?**

Yes. You can have some projects on on-demand and others assigned to slot reservations. This is the recommended hybrid approach: put production pipelines on reserved slots for predictability, and keep ad-hoc projects on on-demand. Assign projects to reservations using BigQuery's workload management features.

**How do I know if my queries are using partitions and clusters effectively?**

Check the query execution details in the BigQuery console or query the job metadata. Look at `total_bytes_processed` vs `total_bytes_billed`. Also check `INFORMATION_SCHEMA.JOBS` for the `total_partitions_processed` field. If a query on a partitioned table shows it processed all partitions, your filter isn't being recognized as a partition predicate. The filter must reference the partition column directly (not wrapped in a function like `DATE(timestamp)` when the partition is on `timestamp`).

**What happens if I exceed my slot capacity?**

Queries queue. They don't fail—they wait for available slots. On autoscaling reservations, BigQuery will scale up to your configured maximum. Beyond that, queries queue until slots free up. This means during peak hours, query latency increases but costs stay capped. If you're seeing consistent queuing, either optimize your queries to use fewer slot-seconds or increase your baseline/autoscale cap.

**Are there hidden costs beyond query scan and slots?**

Yes. Watch for: streaming insert costs ($0.05/GB), storage costs (active vs long-term), BigQuery Storage Read API costs if using external tools like Spark or Dataflow to read from BigQuery, Data Transfer Service costs for cross-region copies, and BigQuery ML model training costs (charged at on-demand rates even if you're on editions for regular queries). Also note that failed queries still incur costs on on-demand pricing if they scanned data before failing.

## Summary

BigQuery cost optimization comes down to two things: scanning less data per query, and choosing the pricing model that matches your usage pattern. Fix the 8 query patterns first—partitioning, clustering, explicit column selection, and materialized views can cut scan volumes by 70-90% without any pricing changes. Then evaluate whether your volume justifies the predictability of slot-based editions pricing.

The most expensive BigQuery deployment isn't the one running complex ML models on petabytes of data. It's the one where 15 analysts run `SELECT *` against unpartitioned tables all day because nobody told them it costs $6.25 per terabyte scanned. Education and guardrails prevent more waste than any pricing optimization ever will.
