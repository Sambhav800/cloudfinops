import pytest

from app.core.simulation_store import (
    get_simulation_history,
    get_simulation_run,
    save_simulation_run,
)


class FakeSimulationDb:
    def __init__(self):
        self.rows = []

    async def insert(self, table, data):
        assert table == "simulation_runs"
        self.rows.append(dict(data))
        return [dict(data)]

    async def select(self, table, columns="*", filters=None):
        assert table == "simulation_runs"
        filters = filters or {}
        return [
            dict(row)
            for row in self.rows
            if all(row.get(key) == value for key, value in filters.items())
        ]


@pytest.mark.asyncio
async def test_save_simulation_run_stores_summary_without_raw_plan():
    db = FakeSimulationDb()

    run_id = await save_simulation_run(
        db=db,
        user_id="user-1",
        source_type="terraform_plan",
        source_hash="abc123",
        filename="plan.json",
        monthly={"before": 0.0, "after": 10.0, "delta": 10.0},
        annual={"before": 0.0, "after": 120.0, "delta": 120.0},
        summary={"total_resources": 1, "priced_resources": 1},
        resources=[{"resource_address": "aws_instance.web"}],
        unestimated_resources=[],
        findings=[],
        policy={"status": "pass"},
    )

    assert run_id
    assert db.rows[0]["id"] == run_id
    assert db.rows[0]["user_id"] == "user-1"
    assert "plan" not in db.rows[0]


@pytest.mark.asyncio
async def test_get_simulation_history_filters_by_user_id_and_hides_heavy_arrays():
    db = FakeSimulationDb()
    first_id = await save_simulation_run(
        db,
        "user-1",
        "terraform_plan",
        "hash-1",
        None,
        {"delta": 1.0},
        {"delta": 12.0},
        {"total_resources": 1},
        [{"resource_address": "aws_instance.one"}],
        [{"resource_address": "aws_unknown.one"}],
        [{"finding_id": "one"}],
        {"status": "warn"},
    )
    await save_simulation_run(
        db,
        "user-2",
        "terraform_plan",
        "hash-2",
        None,
        {"delta": 2.0},
        {"delta": 24.0},
        {"total_resources": 1},
        [{"resource_address": "aws_instance.two"}],
        [],
        [],
        {"status": "pass"},
    )

    history = await get_simulation_history(db, "user-1")

    assert len(history) == 1
    assert history[0]["id"] == first_id
    assert history[0]["_id"] == first_id
    assert "resources" not in history[0]
    assert "unestimated_resources" not in history[0]


@pytest.mark.asyncio
async def test_get_simulation_run_enforces_user_isolation():
    db = FakeSimulationDb()
    run_id = await save_simulation_run(
        db,
        "user-1",
        "terraform_plan",
        "hash-1",
        "plan.json",
        {"delta": 1.0},
        {"delta": 12.0},
        {"total_resources": 1},
        [{"resource_address": "aws_instance.web"}],
        [],
        [],
        {"status": "pass"},
    )

    assert await get_simulation_run(db, "user-2", run_id) is None
    run = await get_simulation_run(db, "user-1", run_id)
    assert run is not None
    assert run["id"] == run_id
    assert run["resources"][0]["resource_address"] == "aws_instance.web"
