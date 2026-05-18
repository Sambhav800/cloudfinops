from types import SimpleNamespace
from pathlib import Path

import pytest

from app.core import cache as cache_module


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.keys = []

    async def get(self, key):
        self.keys.append(("get", key))
        return self.values.get(key)

    async def setex(self, name, time, value):
        self.keys.append(("setex", name))
        self.values[name] = value


@pytest.mark.asyncio
async def test_cache_response_key_includes_query_arguments(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(cache_module, "redis_client", fake_redis)
    calls = []

    @cache_module.cache_response(expire_seconds=60)
    async def endpoint(integration_id=None, days=30, user=None, db=None):
        calls.append((integration_id, days))
        return {"integration_id": integration_id, "days": days}

    user = SimpleNamespace(id="user-1")

    first = await endpoint(integration_id="aws-1", days=30, user=user, db=object())
    second = await endpoint(integration_id="gcp-1", days=30, user=user, db=object())
    cached_first = await endpoint(integration_id="aws-1", days=30, user=user, db=object())

    assert first == {"integration_id": "aws-1", "days": 30}
    assert second == {"integration_id": "gcp-1", "days": 30}
    assert cached_first == first
    assert calls == [("aws-1", 30), ("gcp-1", 30)]
    set_keys = [key for action, key in fake_redis.keys if action == "setex"]
    assert len(set_keys) == 2
    assert set_keys[0] != set_keys[1]


def test_dashboard_root_read_routes_are_not_response_cached():
    routes_source = Path(__file__).resolve().parents[1].joinpath("app/api/routes.py").read_text()

    for endpoint_name in ("get_resources", "get_stats", "get_spend_history", "get_multicloud_comparison"):
        start_token = f"async def {endpoint_name}"
        start_index = routes_source.index(start_token)
        decorator_window = routes_source[max(0, start_index - 160):start_index]
        assert "@cache_response" not in decorator_window


def test_scan_dashboard_confidence_does_not_default_to_fake_ai_score():
    routes_source = Path(__file__).resolve().parents[1].joinpath("app/api/routes.py").read_text()

    assert 'ai_stats.get("ai_confidence_score", 75)' not in routes_source
    assert 'ai_stats.get("ai_confidence_score", 0)' in routes_source
