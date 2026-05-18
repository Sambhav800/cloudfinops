"""
Dynamic exchange rate cache with static fallback.

Fetches rates from ECB (free, no API key) and caches in MongoDB for 24 hours.
Falls back to static rates if the API is unavailable — never fails a scan.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import httpx

from ..db import MongoDBClient

logger = logging.getLogger(__name__)

COLLECTION = "exchange_rate_cache"
CACHE_TTL_HOURS = 24
ECB_API_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D..EUR.SP00.A?lastNObservations=1&format=csvdata"

_STATIC_FALLBACK: Dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "INR": 0.012,
    "JPY": 0.0067,
    "CAD": 0.74,
    "AUD": 0.65,
    "BRL": 0.20,
    "KRW": 0.00074,
    "SGD": 0.75,
    "CHF": 1.13,
    "SEK": 0.096,
    "NOK": 0.093,
    "DKK": 0.145,
    "PLN": 0.25,
    "CZK": 0.043,
    "HUF": 0.0027,
    "TRY": 0.031,
    "ZAR": 0.055,
    "MXN": 0.058,
    "CNY": 0.14,
    "HKD": 0.128,
    "TWD": 0.031,
    "THB": 0.029,
    "MYR": 0.22,
    "IDR": 0.000063,
    "PHP": 0.018,
    "AED": 0.272,
    "SAR": 0.267,
}


async def _fetch_fresh_rates() -> Optional[Dict[str, float]]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://open.er-api.com/v6/latest/USD",
                headers={"Accept": "application/json"},
            )
            if response.status_code != 200:
                return None
            data = response.json()
            rates_raw = data.get("rates")
            if not isinstance(rates_raw, dict):
                return None
            rates: Dict[str, float] = {}
            for currency, rate in rates_raw.items():
                try:
                    usd_per_unit = 1.0 / float(rate) if float(rate) > 0 else 0.0
                    rates[currency.upper()] = round(usd_per_unit, 8)
                except (ValueError, TypeError, ZeroDivisionError):
                    continue
            rates["USD"] = 1.0
            return rates if len(rates) > 5 else None
    except Exception as error:
        logger.debug("Exchange rate fetch failed: %s", error)
        return None


async def get_exchange_rates(db: Optional[MongoDBClient] = None) -> Dict[str, float]:
    if db:
        try:
            cached = await db.select(COLLECTION, filters={"id": "latest_rates"})
            if cached:
                record = cached[0]
                fetched_at = record.get("fetched_at")
                if fetched_at:
                    fetched_dt = datetime.fromisoformat(str(fetched_at))
                    if datetime.now(timezone.utc) - fetched_dt < timedelta(hours=CACHE_TTL_HOURS):
                        rates = record.get("rates")
                        if isinstance(rates, dict) and len(rates) > 5:
                            return rates
        except Exception:
            pass

    fresh = await _fetch_fresh_rates()
    if fresh:
        if db:
            try:
                await db.upsert(COLLECTION, {
                    "id": "latest_rates",
                    "rates": fresh,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "source": "open.er-api.com",
                })
            except Exception:
                pass
        return fresh

    return dict(_STATIC_FALLBACK)


def convert_to_usd(amount: float, currency: str, rates: Dict[str, float]) -> float:
    if not currency or currency.upper() == "USD":
        return amount
    rate = rates.get(currency.upper())
    if rate and rate > 0:
        return round(amount * rate, 4)
    fallback = _STATIC_FALLBACK.get(currency.upper())
    if fallback and fallback > 0:
        return round(amount * fallback, 4)
    return amount
