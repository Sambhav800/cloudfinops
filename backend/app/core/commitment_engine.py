import logging
import asyncio
import boto3
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

from ..db.mongo_client import get_db_client
from ..core.retry import build_aws_retry_config, call_with_backoff, is_aws_retryable, is_gcp_retryable
from ..security.crypto import decrypt_integration_credentials

logger = logging.getLogger(__name__)

class CloudCommitment(BaseModel):
    id: str
    provider: str  # "aws", "azure", "gcp"
    type: str      # "Savings Plan", "Reservation", "CUD"
    name: str
    status: str    # "active", "expired", "pending"
    start_date: str
    end_date: str
    commitment_amount: float
    currency: str = "USD"
    region: Optional[str] = None
    utilization_pct: float = Field(ge=0, le=100)
    savings_amount: float
    coverage_type: str  # "Compute", "Instance", "Database"

class CommitmentEngine:
    """
    Unified engine for managing cloud commitments (AWS Savings Plans, Azure Reservations, GCP CUDs).
    """

    def __init__(self):
        self.executor = None # Use default ThreadPoolExecutor

    @staticmethod
    def _call_with_backoff(operation_name: str, func, is_retryable):
        return call_with_backoff(operation_name, func, is_retryable=is_retryable)

    def _load_demo_commitments(
        self,
        integration: dict,
    ) -> tuple[List[CloudCommitment], bool]:
        metadata = integration.get("metadata")
        if not isinstance(metadata, dict):
            return [], False

        # Only serve demo commitments for explicitly flagged demo integrations
        if metadata.get("environment") != "demo":
            return [], False

        raw_commitments = metadata.get("demo_commitments")
        if not isinstance(raw_commitments, list):
            return [], False

        parsed: List[CloudCommitment] = []
        for raw_commitment in raw_commitments:
            if not isinstance(raw_commitment, dict):
                continue
            try:
                parsed.append(CloudCommitment(**raw_commitment))
            except Exception as error:
                logger.warning(
                    "Skipping invalid demo commitment for integration %s: %s",
                    integration.get("id"),
                    error,
                )

        return parsed, bool(parsed)

    def _get_aws_client(self, service: str, access_key_id: str, secret_access_key: str, region: str = "us-east-1"):
        """Get a boto3 client for a specific service and region."""
        session = boto3.Session()
        return session.client(
            service,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=build_aws_retry_config(region_name=region),
        )

    async def get_aws_commitments(
        self, access_key_id: str, secret_access_key: str, regions: Optional[List[str]] = None
    ) -> List[CloudCommitment]:
        """
        Fetch active Savings Plans and Reserved Instances from AWS.
        Maps raw AWS responses to the CloudCommitment normalized model.
        """
        loop = asyncio.get_event_loop()
        
        # Use a subset of regions if none provided, but we really need to check where RIs might be
        # For SPs and CE, us-east-1 is the standard endpoint
        scan_regions = regions if regions else ["us-east-1", "us-west-2", "eu-west-1"]

        def fetch():
            commitments = []
            sp_map = {} # arn -> commitment
            ri_map = {} # id -> commitment

            # 1. Fetch Savings Plans (Global)
            try:
                sp_client = self._get_aws_client("savingsplans", access_key_id, secret_access_key)
                sp_response = self._call_with_backoff(
                    "AWS savings plans list",
                    lambda: sp_client.describe_savings_plans(states=['active', 'payment-pending']),
                    is_aws_retryable,
                )
                
                for sp in sp_response.get('savingsPlans', []):
                    sp_id = sp['savingsPlanId']
                    sp_arn = sp['savingsPlanArn']
                    sp_type = sp['savingsPlanType'] # Compute, EC2Instance, SageMaker
                    
                    commitment = CloudCommitment(
                        id=sp_id,
                        provider="aws",
                        type="Savings Plan",
                        name=f"{sp_type} Savings Plan",
                        status=sp['status'].lower(),
                        start_date=sp['start'].isoformat() if isinstance(sp['start'], datetime) else str(sp['start']),
                        end_date=sp['end'].isoformat() if isinstance(sp['end'], datetime) else str(sp['end']),
                        commitment_amount=float(sp['commitment']),
                        currency=sp['currencyCode'],
                        region=sp.get('region') or "global",
                        utilization_pct=0.0,
                        savings_amount=0.0,
                        coverage_type="Compute" if "Compute" in sp_type else "Instance"
                    )
                    commitments.append(commitment)
                    sp_map[sp_arn] = commitment
            except Exception as e:
                logger.error(f"AWS SP fetch error: {e}")

            # 2. Fetch Reserved Instances (Regional)
            for region in scan_regions:
                try:
                    ec2_client = self._get_aws_client("ec2", access_key_id, secret_access_key, region=region)
                    ri_response = self._call_with_backoff(
                        f"AWS reserved instances list ({region})",
                        lambda: ec2_client.describe_reserved_instances(
                            Filters=[{'Name': 'state', 'Values': ['active', 'payment-pending']}]
                        ),
                        is_aws_retryable,
                    )
                    
                    for ri in ri_response.get('ReservedInstances', []):
                        ri_id = ri['ReservedInstancesId']
                        
                        commitment = CloudCommitment(
                            id=ri_id,
                            provider="aws",
                            type="Reservation",
                            name=f"{ri['ProductDescription']} RI ({ri['InstanceType']})",
                            status=ri['State'].lower(),
                            start_date=ri['Start'].isoformat() if isinstance(ri['Start'], datetime) else str(ri['Start']),
                            end_date=ri['End'].isoformat() if isinstance(ri['End'], datetime) else str(ri['End']),
                            commitment_amount=float(ri.get('FixedPrice', 0)) / 12.0, # Approximate monthly
                            currency=ri['CurrencyCode'],
                            region=region,
                            utilization_pct=0.0,
                            savings_amount=0.0,
                            coverage_type="Instance"
                        )
                        commitments.append(commitment)
                        ri_map[ri_id] = commitment
                except Exception as e:
                    logger.error(f"AWS RI fetch error in {region}: {e}")

            # 3. Enrich with Utilization & Savings from Cost Explorer
            try:
                ce = self._get_aws_client("ce", access_key_id, secret_access_key)
                
                # Utilization for last 7 days
                end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
                
                # SP Utilization
                if sp_map:
                    sp_util = self._call_with_backoff(
                        "AWS savings plans utilization",
                        lambda: ce.get_savings_plans_utilization_details(
                            TimePeriod={'Start': start_date, 'End': end_date}
                        ),
                        is_aws_retryable,
                    )
                    for detail in sp_util.get('SavingsPlansUtilizationDetails', []):
                        arn = detail.get('SavingsPlanArn')
                        if arn in sp_map:
                            sp_map[arn].utilization_pct = float(detail.get('Utilization', {}).get('UtilizationPercentage', 0))
                            sp_map[arn].savings_amount = float(detail.get('Savings', {}).get('NetSavings', 0))

                # RI Utilization
                if ri_map:
                    ri_util = self._call_with_backoff(
                        "AWS reservation utilization",
                        lambda: ce.get_reservation_utilization(
                            TimePeriod={'Start': start_date, 'End': end_date},
                            GroupBy=[{'Type': 'DIMENSION', 'Key': 'RESERVATION_ID'}]
                        ),
                        is_aws_retryable,
                    )
                    for detail in ri_util.get('UtilizationsByTime', []):
                        for group in detail.get('Groups', []):
                            ri_id = group.get('Attributes', {}).get('reservationId')
                            if ri_id in ri_map:
                                util_data = group.get('Utilization', {})
                                ri_map[ri_id].utilization_pct = float(util_data.get('UtilizationPercentage', 0))
                                ri_map[ri_id].savings_amount = float(util_data.get('NetSavings', 0))
                                
            except Exception as e:
                logger.warning(f"AWS Commitment utilization enrichment error: {e}")

            return commitments

        return await loop.run_in_executor(self.executor, fetch)

    async def get_gcp_commitments(
        self, project_id: str, service_account_email: str, private_key: str, regions: Optional[List[str]] = None
    ) -> List[CloudCommitment]:
        """
        Fetch active Committed Use Discounts (CUDs) from GCP Compute Engine.
        """
        loop = asyncio.get_event_loop()
        
        # Approved regions for scanning if none provided
        scan_regions = regions if regions else ["us-central1", "us-east1", "us-east4", "us-west1", "europe-west1", "asia-east1"]

        def fetch():
            from google.cloud import compute_v1
            from google.oauth2 import service_account
            
            commitments = []
            service_info = {
                "type": "service_account",
                "project_id": project_id,
                "private_key": private_key,
                "client_email": service_account_email,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            credentials = service_account.Credentials.from_service_account_info(
                service_info,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            
            try:
                client = compute_v1.RegionCommitmentsClient(credentials=credentials)
                
                for region in scan_regions:
                    try:
                        request = compute_v1.ListRegionCommitmentsRequest(
                            project=project_id,
                            region=region,
                        )
                        response = self._call_with_backoff(
                            f"GCP commitments list ({region})",
                            lambda: list(client.list(request=request)),
                            is_gcp_retryable,
                        )
                        
                        for item in response:
                            # Map GCP commitment to CloudCommitment normalized model
                            commitment = CloudCommitment(
                                id=str(item.id),
                                provider="gcp",
                                type="CUD",
                                name=item.name,
                                status=item.status.lower() if hasattr(item, "status") else "active",
                                start_date=item.start_timestamp if item.start_timestamp else "",
                                end_date=item.end_timestamp if item.end_timestamp else "",
                                commitment_amount=0.0, # Detailed amount requires resource parsing
                                currency="USD",
                                region=region,
                                utilization_pct=0.0, # Placeholder, enrichment would need Cloud Monitoring
                                savings_amount=0.0,
                                coverage_type="Compute"
                            )
                            commitments.append(commitment)
                    except Exception as e:
                        if "Not Found" not in str(e): # Ignore regions without Compute Engine enabled/accessible
                            logger.error(f"GCP CUD fetch error in {region}: {e}")
            except Exception as e:
                logger.error(f"GCP CUD client error: {e}")
                
            return commitments

        return await loop.run_in_executor(self.executor, fetch)


    async def get_commitments(self, user_id: str) -> List[CloudCommitment]:
        """
        Fetch all commitments across providers for a specific user.
        """
        db = get_db_client()
        integrations = await db.get_user_integrations(user_id)

        all_commitments = []
        tasks = []
        integrations_needing_fallback = []

        for integration in integrations:
            if integration.get("status") != "active":
                continue

            provider = integration.get("provider")
            demo_commitments, handled_by_demo_metadata = self._load_demo_commitments(integration)
            if handled_by_demo_metadata:
                all_commitments.extend(demo_commitments)
                continue

            try:
                credentials = decrypt_integration_credentials(integration)
            except Exception as e:
                logger.error(f"Failed to decrypt credentials for integration {integration.get('id')}: {e}")
                integrations_needing_fallback.append(integration)
                continue

            regions = integration.get("regions", [])

            if provider == "aws":
                access_key = credentials.get("access_key_id")
                secret_key = credentials.get("secret_access_key")
                if access_key and secret_key:
                    tasks.append((integration, self.get_aws_commitments(access_key, secret_key, regions)))
                else:
                    integrations_needing_fallback.append(integration)
            elif provider == "gcp":
                project_id = credentials.get("project_id")
                client_email = credentials.get("service_account_email")
                private_key = credentials.get("private_key")
                if project_id and client_email and private_key:
                    tasks.append((integration, self.get_gcp_commitments(project_id, client_email, private_key, regions)))
                else:
                    integrations_needing_fallback.append(integration)
            else:
                integrations_needing_fallback.append(integration)

        if tasks:
            coros = [task for _, task in tasks]
            results = await asyncio.gather(*coros, return_exceptions=True)
            for (integration, _), res in zip(tasks, results):
                if isinstance(res, list) and len(res) > 0:
                    all_commitments.extend(res)
                else:
                    if isinstance(res, Exception):
                        logger.error(f"Error fetching commitments: {res}")
                    integrations_needing_fallback.append(integration)

        return all_commitments

commitment_engine = CommitmentEngine()
