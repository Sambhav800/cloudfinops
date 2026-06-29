"""
GPU Metrics Store — time-series storage using MongoDB bucket pattern.
One document per resource per day, with 5-minute sample intervals (max 288/day).
TTL: 90 days via MongoDB index.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION_NAME = "gpu_metrics"
MAX_SAMPLES_PER_DAY = 288  # 24h * 60min / 5min interval


class GpuMetricsStore:
    """Manages GPU metrics time-series data in MongoDB with bucket pattern."""

    def __init__(self, db_client):
        self._db = db_client

    async def record_sample(
        self,
        resource_id: str,
        user_id: str,
        provider: str,
        sm_pct: float | None = None,
        mem_pct: float | None = None,
        power_w: float | None = None,
        temp_c: float | None = None,
    ) -> None:
        """
        Record a single GPU metrics sample.
        Appends to the current day's bucket document.
        """
        now = datetime.now(timezone.utc)
        bucket_date = now.strftime("%Y-%m-%d")

        sample = {"ts": now.isoformat()}
        if sm_pct is not None:
            sample["sm_pct"] = round(sm_pct, 2)
        if mem_pct is not None:
            sample["mem_pct"] = round(mem_pct, 2)
        if power_w is not None:
            sample["power_w"] = round(power_w, 1)
        if temp_c is not None:
            sample["temp_c"] = round(temp_c, 1)

        filters = {
            "resource_id": resource_id,
            "bucket_date": bucket_date,
        }

        existing = await self._db.select(COLLECTION_NAME, filters=filters)

        if existing:
            doc = existing[0]
            samples = doc.get("samples", [])
            if len(samples) >= MAX_SAMPLES_PER_DAY:
                samples = samples[-(MAX_SAMPLES_PER_DAY - 1):]
            samples.append(sample)

            daily_avg = self._compute_daily_avg(samples)
            await self._db.update(
                COLLECTION_NAME,
                data={"samples": samples, "daily_avg": daily_avg, "sample_count": len(samples)},
                filters=filters,
            )
        else:
            doc = {
                "resource_id": resource_id,
                "user_id": user_id,
                "provider": provider,
                "bucket_date": bucket_date,
                "samples": [sample],
                "daily_avg": sample,
                "sample_count": 1,
                "created_at": now.isoformat(),
            }
            await self._db.insert(COLLECTION_NAME, doc)

    async def get_latest_metrics(self, resource_id: str) -> dict[str, Any] | None:
        """Get the most recent metrics sample for a resource."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        docs = await self._db.select(COLLECTION_NAME, filters={
            "resource_id": resource_id,
            "bucket_date": today,
        })
        if not docs:
            return None
        samples = docs[0].get("samples", [])
        if not samples:
            return None
        return samples[-1]

    async def get_history(
        self,
        resource_id: str,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """
        Get aggregated daily metrics for a resource over N days.
        Returns list of {date, sm_pct, mem_pct, power_w, temp_c} averages.
        """
        docs = await self._db.select(COLLECTION_NAME, filters={
            "resource_id": resource_id,
        })

        if not docs:
            return []

        docs.sort(key=lambda d: d.get("bucket_date", ""), reverse=True)
        recent = docs[:days]

        result = []
        for doc in reversed(recent):
            avg = doc.get("daily_avg", {})
            result.append({
                "date": doc.get("bucket_date"),
                "sm_pct": avg.get("sm_pct"),
                "mem_pct": avg.get("mem_pct"),
                "power_w": avg.get("power_w"),
                "temp_c": avg.get("temp_c"),
                "sample_count": doc.get("sample_count", 0),
            })

        return result

    async def get_all_live_metrics(self, user_id: str) -> list[dict[str, Any]]:
        """Get latest metrics for all GPU resources owned by a user."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        docs = await self._db.select(COLLECTION_NAME, filters={
            "user_id": user_id,
            "bucket_date": today,
        })

        results = []
        for doc in docs:
            samples = doc.get("samples", [])
            if not samples:
                continue
            latest = samples[-1]
            results.append({
                "resource_id": doc.get("resource_id"),
                "provider": doc.get("provider"),
                "latest": latest,
                "daily_avg": doc.get("daily_avg"),
                "sample_count": doc.get("sample_count", 0),
            })

        return results

    def _compute_daily_avg(self, samples: list[dict]) -> dict[str, float | None]:
        """Compute average metrics across all samples in a bucket."""
        fields = ["sm_pct", "mem_pct", "power_w", "temp_c"]
        avg: dict[str, float | None] = {}

        for field in fields:
            values = [s[field] for s in samples if field in s and s[field] is not None]
            if values:
                avg[field] = round(sum(values) / len(values), 2)
            else:
                avg[field] = None

        return avg
