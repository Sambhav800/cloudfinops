import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from app.core.commitment_engine import CommitmentEngine, CloudCommitment

@pytest.mark.asyncio
async def test_get_aws_commitments_mapping():
    engine = CommitmentEngine()
    
    # Mock boto3 session and clients
    mock_session = MagicMock()
    mock_sp_client = MagicMock()
    mock_ec2_client = MagicMock()
    mock_ce_client = MagicMock()
    
    def mock_get_client(service, *args, **kwargs):
        if service == "savingsplans":
            return mock_sp_client
        elif service == "ec2":
            return mock_ec2_client
        elif service == "ce":
            return mock_ce_client
        return MagicMock()

    # Setup mock responses
    mock_sp_client.describe_savings_plans.return_value = {
        'savingsPlans': [
            {
                'savingsPlanId': 'sp-123',
                'savingsPlanArn': 'arn:aws:savingsplans::123456789012:savingsplan/sp-123',
                'savingsPlanType': 'Compute',
                'status': 'active',
                'start': datetime(2023, 1, 1, tzinfo=timezone.utc),
                'end': datetime(2024, 1, 1, tzinfo=timezone.utc),
                'commitment': '0.50',
                'currencyCode': 'USD'
            }
        ]
    }
    
    mock_ec2_client.describe_reserved_instances.return_value = {
        'ReservedInstances': [
            {
                'ReservedInstancesId': 'ri-456',
                'ProductDescription': 'Linux/UNIX',
                'InstanceType': 'm5.large',
                'State': 'active',
                'Start': datetime(2023, 1, 1, tzinfo=timezone.utc),
                'End': datetime(2024, 1, 1, tzinfo=timezone.utc),
                'FixedPrice': 1200.0,
                'CurrencyCode': 'USD'
            }
        ]
    }
    
    mock_ce_client.get_savings_plans_utilization_details.return_value = {
        'SavingsPlansUtilizationDetails': [
            {
                'SavingsPlanArn': 'arn:aws:savingsplans::123456789012:savingsplan/sp-123',
                'Utilization': {'UtilizationPercentage': '95.5'},
                'Savings': {'NetSavings': '10.0'}
            }
        ]
    }
    
    mock_ce_client.get_reservation_utilization.return_value = {
        'UtilizationsByTime': [
            {
                'Groups': [
                    {
                        'Attributes': {'reservationId': 'ri-456'},
                        'Utilization': {
                            'UtilizationPercentage': '80.0',
                            'NetSavings': '5.0'
                        }
                    }
                ]
            }
        ]
    }

    with patch.object(engine, '_get_aws_client', side_effect=mock_get_client):
        commitments = await engine.get_aws_commitments(
            access_key_id="fake",
            secret_access_key="fake",
            regions=["us-east-1"]
        )
        
        assert len(commitments) == 2
        
        # Verify SP
        sp = next(c for c in commitments if c.type == "Savings Plan")
        assert sp.id == "sp-123"
        assert sp.utilization_pct == 95.5
        assert sp.savings_amount == 10.0
        assert sp.coverage_type == "Compute"
        
        # Verify RI
        ri = next(c for c in commitments if c.type == "Reservation")
        assert ri.id == "ri-456"
        assert ri.utilization_pct == 80.0
        assert ri.savings_amount == 5.0
        assert ri.coverage_type == "Instance"
