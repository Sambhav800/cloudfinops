import pytest

from app.core import commitment_engine as commitment_engine_module


class FakeCommitmentDB:
    def __init__(self, integrations):
        self.integrations = integrations

    async def get_user_integrations(self, user_id):
        return self.integrations


def _valid_demo_commitment():
    return {
        "id": "commitment-1",
        "provider": "aws",
        "type": "Savings Plan",
        "name": "Demo Savings Plan",
        "status": "active",
        "start_date": "2026-01-01T00:00:00+00:00",
        "end_date": "2027-01-01T00:00:00+00:00",
        "commitment_amount": 4200.0,
        "currency": "USD",
        "region": "global",
        "utilization_pct": 93.4,
        "savings_amount": 610.0,
        "coverage_type": "Compute",
    }


@pytest.mark.asyncio
async def test_get_commitments_prefers_persisted_demo_commitments(monkeypatch):
    engine = commitment_engine_module.CommitmentEngine()
    db = FakeCommitmentDB(
        [
            {
                "id": "integration-aws-demo",
                "status": "active",
                "provider": "aws",
                "metadata": {
                    "demo_commitments": [_valid_demo_commitment()],
                },
            }
        ]
    )

    monkeypatch.setattr(commitment_engine_module, "get_db_client", lambda: db)

    def _unexpected_decrypt(_integration):
        raise AssertionError("decrypt_integration_credentials should not run for demo commitments")

    monkeypatch.setattr(
        commitment_engine_module,
        "decrypt_integration_credentials",
        _unexpected_decrypt,
    )

    commitments = await engine.get_commitments("user-demo")

    assert len(commitments) == 1
    assert commitments[0].name == "Demo Savings Plan"
    assert commitments[0].provider == "aws"
    assert commitments[0].utilization_pct == 93.4


@pytest.mark.asyncio
async def test_get_commitments_skips_invalid_demo_rows(monkeypatch):
    engine = commitment_engine_module.CommitmentEngine()
    db = FakeCommitmentDB(
        [
            {
                "id": "integration-aws-demo",
                "status": "active",
                "provider": "aws",
                "metadata": {
                    "demo_commitments": [
                        {"id": "broken-row"},
                        _valid_demo_commitment(),
                    ],
                },
            }
        ]
    )

    monkeypatch.setattr(commitment_engine_module, "get_db_client", lambda: db)
    monkeypatch.setattr(
        commitment_engine_module,
        "decrypt_integration_credentials",
        lambda _integration: {},
    )

    commitments = await engine.get_commitments("user-demo")

    assert len(commitments) == 1
    assert commitments[0].id == "commitment-1"
