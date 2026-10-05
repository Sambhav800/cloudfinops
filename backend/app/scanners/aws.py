"""
AWS Resource Scanner for CloudFinOps.
Scans EC2, EBS, Elastic IPs, VPCs, Subnets, Security Groups, IAM, 
Route Tables, Internet Gateways, Key Pairs, and fetches cost data.
"""

import boto3
import collections
from botocore.exceptions import ClientError
from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import math

from ..core.retry import build_aws_retry_config, call_with_backoff, is_aws_retryable
from ..core.workload_patterns import (
    MetricTimeSeries,
    classify_pattern,
    generate_recommendation,
    WorkloadPattern,
    RecommendationType,
)

logger = logging.getLogger(__name__)

ALL_AWS_REGIONS = [
    'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
    'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1', 'eu-north-1',
    'ap-south-1', 'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
    'ap-southeast-1', 'ap-southeast-2',
    'sa-east-1', 'ca-central-1'
]

APPROVED_REGIONS = ['us-east-1', 'us-west-2', 'eu-west-1']
COST_SOURCE_ACTUAL = "actual"
COST_SOURCE_BILLING_UNAVAILABLE = "billing_unavailable"


@dataclass
class ScannedResource:
    """Represents a scanned cloud resource."""
    resource_name: str
    service_type: str
    cost: float
    status: str
    region: str
    region_compliance: str
    created_by: Optional[str] = None
    metadata: Optional[Dict] = None
    cloud_resource_id: Optional[str] = None


@dataclass
class ScanResult:
    """Result of a complete AWS scan."""
    resources: List[ScannedResource]
    total_spend: float
    potential_savings: float
    active_resources_count: int
    carbon_footprint_kg: float
    waste_distribution: List[Dict[str, Any]]
    regions_scanned: int
    access_denied_services: List[str] = None
    daily_totals: Optional[List[Dict[str, Any]]] = None
    service_breakdown: Optional[Dict[str, float]] = None
    currency: str = "USD"


class AWSScanner:
    """
    Scans AWS resources across multiple regions.
    Identifies zombie resources and calculates potential savings.
    """
    
    def __init__(
        self,
        access_key_id: str = "",
        secret_access_key: str = "",
        regions: Optional[List[str]] = None,
        role_arn: str = "",
        external_id: str = "",
    ):
        self.regions = regions if regions else ALL_AWS_REGIONS
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.access_denied_services = set()
        self.resource_cost_status = "not_checked"
        self.resource_cost_message = ""

        # If role_arn provided, assume it to get temporary credentials
        if role_arn:
            assumed = self._assume_role(access_key_id, secret_access_key, role_arn, external_id)
            self.access_key_id = assumed["AccessKeyId"]
            self.secret_access_key = assumed["SecretAccessKey"]
            self._session_token = assumed["SessionToken"]
        else:
            self.access_key_id = access_key_id
            self.secret_access_key = secret_access_key
            self._session_token = None

    @staticmethod
    def _assume_role(
        access_key_id: str,
        secret_access_key: str,
        role_arn: str,
        external_id: str = "",
    ) -> Dict[str, str]:
        """Assume an IAM role via STS and return temporary credentials."""
        sts_kwargs: Dict[str, Any] = {}
        if access_key_id and secret_access_key:
            sts_kwargs["aws_access_key_id"] = access_key_id
            sts_kwargs["aws_secret_access_key"] = secret_access_key

        sts = boto3.client("sts", **sts_kwargs)
        assume_kwargs: Dict[str, Any] = {
            "RoleArn": role_arn,
            "RoleSessionName": "CloudFinOps-Scanner",
            "DurationSeconds": 3600,
        }
        if external_id:
            assume_kwargs["ExternalId"] = external_id
        else:
            logger.warning("AssumeRole without ExternalId for %s — confused-deputy risk", role_arn)

        response = sts.assume_role(**assume_kwargs)
        return response["Credentials"]

    def _get_client(self, service: str, region: str):
        """Get a boto3 client for a specific service and region with adaptive retries."""
        session = boto3.Session()
        kwargs: Dict[str, Any] = {
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
            "config": build_aws_retry_config(
                region_name=region,
                connect_timeout=3,
                read_timeout=5,
            ),
        }
        if self._session_token:
            kwargs["aws_session_token"] = self._session_token
        return session.client(service, **kwargs)

    def _handle_scan_error(self, service: str, error: Exception, region: str = None):
        err_str = str(error)
        if 'AccessDenied' in err_str or 'UnauthorizedOperation' in err_str:
            self.access_denied_services.add(service)
        if region:
            logger.warning("%s scan error in %s: %s", service, region, error)
        else:
            logger.warning("%s scan error: %s", service, error)

    @staticmethod
    def _normalize_cost_key(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip().lower()

    def _add_cost_key(self, cost_map: Dict[str, float], key: Any, amount: float) -> None:
        normalized = self._normalize_cost_key(key)
        if not normalized or amount <= 0:
            return
        cost_map[normalized] = cost_map.get(normalized, 0.0) + amount

        # If ARN-like, also index by terminal resource token for easier matches.
        if normalized.startswith("arn:"):
            token = normalized.split(":")[-1]
            bare = token.split("/")[-1].split(":")[-1]
            if bare:
                cost_map[bare] = cost_map.get(bare, 0.0) + amount

    def _identity_variants(self, value: Any) -> Set[str]:
        if value is None:
            return set()

        text = str(value).strip()
        if not text:
            return set()

        variants = {text, text.lower()}
        tail = text.rstrip("/").split("/")[-1].split(":")[-1]
        if tail:
            variants.add(tail)
            variants.add(tail.lower())

        return {variant for variant in variants if variant}

    def _resource_identity_candidates(self, resource: ScannedResource) -> Set[str]:
        metadata = resource.metadata or {}
        candidates: Set[str] = set()
        for raw_value in (
            resource.cloud_resource_id,
            resource.resource_name,
            metadata.get("instance_id"),
            metadata.get("volume_id"),
            metadata.get("allocation_id"),
            metadata.get("vpc_id"),
            metadata.get("subnet_id"),
            metadata.get("group_id"),
            metadata.get("route_table_id"),
            metadata.get("igw_id"),
            metadata.get("nacl_id"),
            metadata.get("dhcp_options_id"),
            metadata.get("key_pair_id"),
            metadata.get("user_id"),
            metadata.get("role_id"),
            metadata.get("resource_id"),
            metadata.get("arn"),
            metadata.get("public_ip"),
            metadata.get("bucket_name"),
            metadata.get("url"),
        ):
            candidates.update(self._identity_variants(raw_value))
        return candidates

    def _remember_resource_identity(self, existing_ids: Set[str], resource: ScannedResource) -> None:
        existing_ids.update(self._resource_identity_candidates(resource))

    def _identity_seen(self, existing_ids: Set[str], *values: Any) -> bool:
        return any(
            variant in existing_ids
            for value in values
            for variant in self._identity_variants(value)
        )

    def _lookup_real_cost(self, cost_map: Optional[Dict[str, float]], *values: Any) -> float:
        if not cost_map:
            return 0.0

        for value in values:
            for variant in self._identity_variants(value):
                key = self._normalize_cost_key(variant)
                if key in cost_map:
                    return round(float(cost_map[key]), 2)
        return 0.0

    def _resource_cost_lookup_candidates(self, resource: ScannedResource) -> List[str]:
        candidates: List[str] = []
        metadata = resource.metadata or {}
        for raw_key in (
            resource.cloud_resource_id,
            resource.resource_name,
            metadata.get("instance_id"),
            metadata.get("volume_id"),
            metadata.get("allocation_id"),
            metadata.get("resource_id"),
            metadata.get("arn"),
            metadata.get("public_ip"),
            metadata.get("bucket_name"),
        ):
            key = self._normalize_cost_key(raw_key)
            if key:
                candidates.append(key)
                if key.startswith("arn:"):
                    token = key.split(":")[-1]
                    bare = token.split("/")[-1].split(":")[-1]
                    if bare:
                        candidates.append(bare)

        seen = set()
        ordered: List[str] = []
        for key in candidates:
            if key not in seen:
                seen.add(key)
                ordered.append(key)
        return ordered

    def _apply_real_costs(self, resources: List[ScannedResource], cost_map: Dict[str, float]) -> int:
        if not cost_map:
            return 0
        updated = 0
        for resource in resources:
            candidates = self._resource_cost_lookup_candidates(resource)
            matched_key = None
            for key in candidates:
                if key in cost_map:
                    matched_key = key
                    break
            if not matched_key:
                continue
            real_cost = round(float(cost_map[matched_key]), 2)
            if real_cost <= 0:
                continue
            if abs(resource.cost - real_cost) < 0.01:
                continue
            resource.cost = real_cost
            resource.metadata = resource.metadata or {}
            resource.metadata["cost_source"] = COST_SOURCE_ACTUAL
            resource.metadata["cost_lookup_key"] = matched_key
            updated += 1
        return updated
    
    async def scan(self, progress_callback: Optional[callable] = None) -> ScanResult:
        """Perform an AWS scan using detailed service scanners plus broad inventory fallbacks."""
        specific_resources: List[ScannedResource] = []
        waste_list: List[Dict[str, Any]] = []
        total_spend = 0.0
        potential_savings = 0.0
        active_resources_count = 0
        carbon_footprint = 0.0
        
        # Step 1: Cost data
        if progress_callback:
            await progress_callback(5, "Fetching cost data...")
        total_spend = await self._get_monthly_cost()

        if progress_callback:
            await progress_callback(6, "Fetching daily billing history...")
        daily_totals, service_breakdown = await self._fetch_daily_cost_history()
        
        # Step 1.5: Granular Resource Costs (Cost Explorer)
        if progress_callback:
            await progress_callback(7, "Fetching real resource-level costs...")
        cost_map = await self._fetch_daily_resource_costs()

        # Step 1.7: Explicit IAM auth validation for clearer credential errors
        if progress_callback:
            await progress_callback(8, "Validating IAM credentials...")
        try:
            sts = self._get_client('sts', 'us-east-1')
            call_with_backoff(
                "AWS STS get caller identity",
                sts.get_caller_identity,
                is_retryable=is_aws_retryable,
            )
        except ClientError as error:
            code = error.response.get('Error', {}).get('Code', '')
            if code in {'InvalidClientTokenId', 'SignatureDoesNotMatch', 'UnrecognizedClientException'}:
                raise Exception(
                    "Authentication failed: AWS Access Key ID or Secret Access Key is invalid."
                )
            if code == 'AccessDenied':
                raise Exception(
                    "Access denied: attach read-only IAM permissions (e.g. ViewOnlyAccess) to the scanner principal."
                )
            raise Exception(f"AWS credential validation failed: {str(error)}")
        
        # Step 2: Global IAM resources
        if progress_callback:
            await progress_callback(8, "Scanning IAM resources...")
        iam_resources = await self._scan_iam()
        specific_resources.extend(iam_resources)
        
        # Step 3: Specific Regional Scans
        total_regions = len(self.regions)
        for idx, region in enumerate(self.regions):
            percent = 10 + int((idx / total_regions) * 60)
            
            if progress_callback:
                await progress_callback(percent, f"Scanning {region}...")
            
            # Run specific scanners
            tasks = [
                self._scan_ec2(region),
                self._scan_ebs(region),
                self._scan_elastic_ips(region),
                self._scan_vpcs(region),
                self._scan_subnets(region),
                self._scan_security_groups(region),
                self._scan_route_tables(region),
                self._scan_internet_gateways(region),
                self._scan_network_acls(region),
                self._scan_dhcp_options(region),
                self._scan_key_pairs(region),
                self._scan_rds(region),
                self._scan_lambda(region),
                self._scan_api_gateway(region),
            ]
            if idx == 0:
                tasks.append(self._scan_s3())
                
            results = await asyncio.gather(*tasks)
            
            # EC2
            ec2_res, ec2_waste, ec2_sav, ec2_act, ec2_carb = results[0]
            specific_resources.extend(ec2_res)
            waste_list.extend(ec2_waste)
            potential_savings += ec2_sav
            carbon_footprint += ec2_carb
            
            # EBS
            ebs_res, ebs_waste, ebs_sav = results[1]
            specific_resources.extend(ebs_res)
            waste_list.extend(ebs_waste)
            potential_savings += ebs_sav
            
            # EIP
            eip_res, eip_waste, eip_sav = results[2]
            specific_resources.extend(eip_res)
            waste_list.extend(eip_waste)
            potential_savings += eip_sav
            
            # Network Resources
            specific_resources.extend(results[3]) # VPCs
            specific_resources.extend(results[4]) # Subnets
            specific_resources.extend(results[5]) # SGs
            specific_resources.extend(results[6]) # Route Tables
            specific_resources.extend(results[7]) # IGWs
            specific_resources.extend(results[8]) # NACLs
            specific_resources.extend(results[9]) # DHCP
            specific_resources.extend(results[10]) # Keypairs
            
            # Data & Compute
            rds_res, rds_waste, rds_sav = results[11]
            specific_resources.extend(rds_res)
            waste_list.extend(rds_waste)
            potential_savings += rds_sav
            
            lambda_res, lambda_waste, lambda_sav = results[12]
            specific_resources.extend(lambda_res)
            waste_list.extend(lambda_waste)
            potential_savings += lambda_sav

            apigw_res, apigw_waste, apigw_sav = results[13]
            specific_resources.extend(apigw_res)
            waste_list.extend(apigw_waste)
            potential_savings += apigw_sav

            # Global
            if idx == 0:
                s3_res, s3_waste, s3_sav = results[14]
                specific_resources.extend(s3_res)
                waste_list.extend(s3_waste)
                potential_savings += s3_sav
        
        # Step 4: Universal Inventory Scan (Fill gaps)
        if progress_callback:
            await progress_callback(80, "Running Universal Inventory Scan...")
        
        # Get set of IDs we already found to avoid duplicates
        found_ids = set()
        for r in specific_resources:
            self._remember_resource_identity(found_ids, r)
        
        # Scan generic resources in primary region (Resource Explorer is cross-region capable)
        # But if using Tagging API we might need to iterate.
        # We'll scan generic resources in ALL regions to be safe with Tagging API fallback.
        generic_resources = []
        
        # Only scan generic in us-east-1 for Resource Explorer (it aggregates there usually)
        # OR iterate all for Tagging API.
        # To be safe and thorough, we iterate all regions for generic scan too.
        
        generic_results = []
        for idx, region in enumerate(self.regions):
             # We assume Resource Explorer is global or replicated, BUT
             # Tagging API is strictly regional.
             # So safely iterating all regions is best.
             res = await self._scan_generic_resources(region, found_ids, cost_map)
             generic_results.extend(res)
             
             if progress_callback and idx % 3 == 0:
                 percent = 80 + int((idx / total_regions) * 15)
                 await progress_callback(percent, f"Universal Scan: {region}...")

        # Merge results
        final_resources = specific_resources + generic_results
        
        # Apply resource-level real costs first.
        real_cost_overrides = self._apply_real_costs(final_resources, cost_map)

        # Do not allocate service-level billing buckets across individual resources.
        # Those totals are real at the service level, but per-resource averaging is
        # not exact and made dashboard resource rows look like real priced assets.

        # DO NOT recalculate totals after cost distribution
        # The sum of resources will never equal the full AWS bill because of abstract costs
        # (Data Transfer, Tax, Support, etc.) We keep the original Cost Explorer `total_spend`.
        # total_spend = sum(r.cost for r in final_resources)
        potential_savings = round(
            sum(r.cost for r in final_resources if str(r.status).lower() in ("zombie", "stopped", "idle")),
            2
        )
        
        active_resources_count = len(final_resources)

        if progress_callback:
            await progress_callback(95, "Finalizing scan results...")
        
        logger.info(
            f"AWS scan complete: {len(final_resources)} resources found "
            f"({len(generic_results)} generic, {real_cost_overrides} real-cost overrides). "
            f"Total Spend: ${total_spend}"
        )
        
        return ScanResult(
            resources=final_resources,
            total_spend=total_spend,
            potential_savings=potential_savings,
            active_resources_count=active_resources_count,
            carbon_footprint_kg=carbon_footprint,
            waste_distribution=waste_list,
            regions_scanned=len(self.regions),
            access_denied_services=list(self.access_denied_services),
            daily_totals=daily_totals,
            service_breakdown=service_breakdown,
        )
    
    # -------------------------------------------------------------------
    # UNIVERSAL SCANNER
    # -------------------------------------------------------------------
    
    async def _scan_generic_resources(self, region: str, existing_ids: Set[str], cost_map: Dict[str, float] = None) -> List[ScannedResource]:
        """
        Scan broad AWS inventory using Resource Explorer, Tagging API, and explicit service fallbacks.
        Returns resources that are NOT in existing_ids.
        """
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            try:
                # Try Resource Explorer first, then continue with other inventory sources.
                try:
                    client = self._get_client('resource-explorer-2', region)
                    # Search for everything in this region
                    # Note: Resource Explorer View is required. If execution fails, we fallback.
                    # We try to use default view.
                    paginator = client.get_paginator('search')
                    for page in paginator.paginate(QueryString=f'region:{region}'):
                         for item in page['Resources']:
                             arn = item['Arn']
                             # Parse resource ID from ARN (last part)
                             resource_id = arn.split(':')[-1].split('/')[-1]
                             
                             if self._identity_seen(existing_ids, resource_id, arn):
                                 continue
                             
                             # Extract service name
                             service = item['Service']
                             resource_type = item['ResourceType']
                             
                             # Determine name
                             name = resource_id
                             # Tags are not always in Search result, sometimes in Properties
                             # Resource Explorer returns limited properties.
                             
                             real_cost = self._lookup_real_cost(cost_map, arn, resource_id, name)
                             resource = ScannedResource(
                                 resource_name=name,
                                 service_type=f"AWS {service} {resource_type}",
                                 cost=real_cost,
                                 status='Active',
                                 region=region,
                                 region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                                 created_by='Unknown',
                                 metadata={
                                     'arn': arn,
                                     'resource_id': resource_id,
                                     'discovery_method': 'resource-explorer-2',
                                     'cost_source': COST_SOURCE_ACTUAL if real_cost > 0 else COST_SOURCE_BILLING_UNAVAILABLE,
                                 }
                             )
                             resources.append(resource)
                             self._remember_resource_identity(existing_ids, resource)
                except Exception as e:
                    # Fallback to Resource Groups Tagging API
                    # This finds any tagged resource, and many untagged ones too
                    # logger.debug(f"Resource Explorer failed in {region}, falling back to Tagging API: {e}")
                    pass
                
                # Fallback: Resource Groups Tagging API
                rg_client = self._get_client('resourcegroupstaggingapi', region)
                paginator = rg_client.get_paginator('get_resources')
                
                for page in paginator.paginate():
                    for item in page['ResourceTagMappingList']:
                        arn = item['ResourceARN']
                        resource_id = arn.split(':')[-1].split('/')[-1]
                        
                        if self._identity_seen(existing_ids, resource_id, arn):
                            continue
                        
                        # Parse service from ARN: arn:aws:service:region:account:type/id
                        parts = arn.split(':')
                        if len(parts) > 2:
                            service = parts[2]
                        else:
                            service = 'unknown'
                            
                        # Extract tags
                        tags = {t['Key']: t['Value'] for t in item.get('Tags', [])}
                        name = tags.get('Name', resource_id)
                        owner = tags.get('Owner', tags.get('CreatedBy', 'Unknown'))
                        
                        real_cost = self._lookup_real_cost(cost_map, arn, resource_id, name)
                        
                        resource = ScannedResource(
                            resource_name=name,
                            service_type=f"AWS {service}",
                            cost=real_cost,
                            status='Active',
                            region=region,
                            region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                            created_by=owner,
                            metadata={
                                'arn': arn,
                                'resource_id': resource_id,
                                'discovery_method': 'resourcegroupstaggingapi',
                                'cost_source': COST_SOURCE_ACTUAL if real_cost > 0 else COST_SOURCE_BILLING_UNAVAILABLE,
                                **tags
                            }
                        )
                        resources.append(resource)
                        self._remember_resource_identity(existing_ids, resource)
                
                
            except Exception as e:
                # Fallback to explicit service scanning for major services
                # This ensures we catch untagged resources even if Resource Explorer is off
                logger.debug("Generic scan error/fallback in %s: %s", region, e)
                pass
            
                
            def add_explicit_resource(name: str, service_type: str, id_or_arn: str, resource_region: str, metadata: Dict[str, Any]) -> None:
                if self._identity_seen(existing_ids, name, id_or_arn, metadata.get("arn"), metadata.get("resource_id"), metadata.get("url")):
                    return
                resource = self._create_generic_resource(name, service_type, id_or_arn, resource_region, cost_map, metadata)
                resources.append(resource)
                self._remember_resource_identity(existing_ids, resource)

            # Explicit Service Fallback (Lambda, RDS, S3, DynamoDB, SQS, SNS, CloudFront)
            try:
                # Lambda
                lambda_client = self._get_client('lambda', region)
                paginator = lambda_client.get_paginator('list_functions')
                for page in paginator.paginate():
                    for func in page['Functions']:
                        name = func['FunctionName']
                        arn = func['FunctionArn']
                        add_explicit_resource(name, 'AWS Lambda Function', arn, region, func)
            except Exception as e:
                logger.debug("Explicit Lambda inventory error in %s: %s", region, e)

            try:
                # RDS
                rds_client = self._get_client('rds', region)
                paginator = rds_client.get_paginator('describe_db_instances')
                for page in paginator.paginate():
                     for db in page['DBInstances']:
                         name = db['DBInstanceIdentifier']
                         arn = db['DBInstanceArn']
                         add_explicit_resource(name, 'AWS RDS DBInstance', arn, region, db)
            except Exception as e:
                logger.debug("Explicit RDS inventory error in %s: %s", region, e)

            try:
                # DynamoDB
                ddb_client = self._get_client('dynamodb', region)
                paginator = ddb_client.get_paginator('list_tables')
                for page in paginator.paginate():
                    for table_name in page['TableNames']:
                        add_explicit_resource(table_name, 'AWS DynamoDB Table', table_name, region, {})
            except Exception as e:
                logger.debug("Explicit DynamoDB inventory error in %s: %s", region, e)

            try:
                # S3 (Global)
                if region == 'us-east-1':
                     s3_client = self._get_client('s3', region)
                     for bucket in s3_client.list_buckets().get('Buckets', []):
                         name = bucket['Name']
                         add_explicit_resource(name, 'AWS S3 Bucket', name, 'global', {})
            except Exception as e:
                logger.debug("Explicit S3 inventory error in %s: %s", region, e)

            try:
                # SQS
                sqs_client = self._get_client('sqs', region)
                # list_queues does not paginate, returns up to 1000.
                queues = sqs_client.list_queues().get('QueueUrls', [])
                for q_url in queues:
                    # Construct ARN? Name?
                    # URL: https://sqs.us-east-1.amazonaws.com/12345/MyQueue
                    name = q_url.split('/')[-1]
                    add_explicit_resource(name, 'AWS SQS Queue', q_url, region, {'url': q_url})
            except Exception as e:
                logger.debug("Explicit SQS inventory error in %s: %s", region, e)

            try:
                # SNS
                sns_client = self._get_client('sns', region)
                paginator = sns_client.get_paginator('list_topics')
                for page in paginator.paginate():
                    for topic in page['Topics']:
                        arn = topic['TopicArn']
                        name = arn.split(':')[-1]
                        add_explicit_resource(name, 'AWS SNS Topic', arn, region, {})
            except Exception as e:
                logger.debug("Explicit SNS inventory error in %s: %s", region, e)

            try:
                # CloudFront (Global)
                if region == 'us-east-1':
                    cf_client = self._get_client('cloudfront', region)
                    paginator = cf_client.get_paginator('list_distributions')
                    for page in paginator.paginate():
                        for dist in page.get('DistributionList', {}).get('Items', []):
                            arn = dist['ARN']
                            domain = dist['DomainName']
                            add_explicit_resource(domain, 'AWS CloudFront Distribution', arn, 'global', dist)
            except Exception as e:
                logger.debug("Explicit CloudFront inventory error in %s: %s", region, e)

            return resources
        
        return await loop.run_in_executor(self.executor, scan)

    def _create_generic_resource(self, name, service_type, id_or_arn, region, cost_map, metadata):
        real_cost = self._lookup_real_cost(cost_map, id_or_arn, name, (metadata or {}).get("resource_id"))
        
        return ScannedResource(
            resource_name=name,
            service_type=service_type,
            cost=real_cost,
            status='Active',
            region=region,
            region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
            created_by='Unknown',
            metadata={
                'arn': id_or_arn,
                'discovery_method': 'explicit-fallback',
                'cost_source': COST_SOURCE_ACTUAL if real_cost > 0 else COST_SOURCE_BILLING_UNAVAILABLE,
                **metadata
            },
            cloud_resource_id=id_or_arn,
        )

    # -------------------------------------------------------------------
    # Cost Distribution Logic
    # -------------------------------------------------------------------
    async def _fetch_service_costs(self) -> Dict[str, float]:
        """Fetch cost per service for last 30 days."""
        loop = asyncio.get_event_loop()
        def fetch():
            service_map = {}
            try:
                client = self._get_client('ce', 'us-east-1')
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)
                
                response = client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='MONTHLY',
                    Metrics=['UnblendedCost'],
                    Filter=self._gross_usage_cost_filter(),
                    GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
                )
                
                for time_period in response.get('ResultsByTime', []):
                    for group in time_period.get('Groups', []):
                        service_name = group['Keys'][0]
                        cost = float(group['Metrics']['UnblendedCost']['Amount'])
                        if cost > 0:
                            service_map[service_name] = service_map.get(service_name, 0.0) + cost
                return service_map
            except Exception as e:
                logger.warning(f"Failed to fetch service costs: {e}")
                return {}
        return await loop.run_in_executor(self.executor, fetch)

    def _distribute_service_costs(self, findings: List[ScannedResource], service_costs: Dict[str, float]) -> None:
        """Distribute service-level costs to resources that have 0 cost."""
        # Simple mapping from Scan Service Type to AWS CE Service Name
        mapping = {
            'lambda': 'AWS Lambda',
            'rds': 'Amazon Relational Database Service',
            'dynamodb': 'Amazon DynamoDB',
            's3': 'Amazon Simple Storage Service',
            'ec2': 'Amazon Elastic Compute Cloud - Compute',
            'ebs': 'Amazon Elastic Compute Cloud - Compute',
            'elastic ip': 'Amazon Elastic Compute Cloud - Compute',
            'vpc': 'Amazon Virtual Private Cloud',
            'subnet': 'Amazon Virtual Private Cloud',
            'security group': 'Amazon Virtual Private Cloud',
            'nat gateway': 'Amazon Virtual Private Cloud',
            'cloudfront': 'Amazon CloudFront',
            'sns': 'Amazon Simple Notification Service',
            'sqs': 'Amazon Simple Queue Service',
            'eks': 'Amazon Elastic Container Service for Kubernetes',
            'ecs': 'Amazon Elastic Container Service',
            'kms': 'AWS Key Management Service'
        }
        
        # Group findings by mapped service
        grouped = collections.defaultdict(list)
        for r in findings:
            sl = r.service_type.lower()
            # Find matching service key
            matched_key = None
            for key, val in mapping.items():
                if key in sl:
                    matched_key = val
                    break
            
            if matched_key:
                grouped[matched_key].append(r)
        
        # Distribute
        for ce_service, resources in grouped.items():
            if ce_service in service_costs and service_costs[ce_service] > 0:
                # Calculate total cost already assigned (if any)
                assigned = sum(r.cost for r in resources)
                remaining = max(0, service_costs[ce_service] - assigned)
                
                if remaining > 0:
                    # Count how many have 0 cost (or effectively 0)
                    zero_cost_resources = [r for r in resources if r.cost == 0]
                    if zero_cost_resources:
                        avg = remaining / len(zero_cost_resources)
                        for r in zero_cost_resources:
                            r.cost = avg

    # -------------------------------------------------------------------
    # Cost Explorer
    # -------------------------------------------------------------------

    @staticmethod
    def _parse_cost_metric_amount(metrics: Dict[str, Any], metric_name: str) -> Optional[float]:
        metric = metrics.get(metric_name)
        if not isinstance(metric, dict):
            return None
        try:
            return float(metric.get("Amount") or 0.0)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _extract_cost_metric(cls, metrics: Dict[str, Any]) -> float:
        parsed_amounts: List[float] = []
        for metric_name in ("NetAmortizedCost", "AmortizedCost", "UnblendedCost"):
            amount = cls._parse_cost_metric_amount(metrics, metric_name)
            if amount is None:
                continue
            parsed_amounts.append(amount)
            if amount > 0:
                return amount
        return parsed_amounts[0] if parsed_amounts else 0.0

    @staticmethod
    def _gross_usage_cost_filter() -> Dict[str, Any]:
        return {
            "Not": {
                "Dimensions": {
                    "Key": "RECORD_TYPE",
                    "Values": ["Credit", "Refund"],
                }
            }
        }

    @staticmethod
    def _is_resource_granularity_opt_in_error(error: Exception) -> bool:
        error_text = str(error)
        if isinstance(error, ClientError):
            error_payload = error.response.get("Error", {})
            error_text = f"{error_payload.get('Code', '')} {error_payload.get('Message', '')} {error_text}"
        return (
            "GetCostAndUsageWithResources" in error_text
            and "Resource-level data granularity" in error_text
        )

    
    async def _get_monthly_cost(self) -> float:
        """Fetch current month-to-date actual cost from Cost Explorer."""
        loop = asyncio.get_event_loop()
        
        def fetch():
            try:
                client = self._get_client('ce', 'us-east-1')
                now = datetime.now()
                mtd_start = now.replace(day=1).strftime('%Y-%m-%d')
                # Cost Explorer's End date is exclusive. Using tomorrow includes
                # all provider-published current-month actuals without mixing in
                # forecast or rolling-window estimates.
                mtd_end = (now + timedelta(days=1)).strftime('%Y-%m-%d')
                response = client.get_cost_and_usage(
                    TimePeriod={
                        'Start': mtd_start,
                        'End': mtd_end,
                    },
                    Granularity='MONTHLY',
                    Metrics=['NetAmortizedCost', 'AmortizedCost', 'UnblendedCost'],
                    Filter=self._gross_usage_cost_filter(),
                )
                
                if response.get('ResultsByTime'):
                    total = 0.0
                    for res in response['ResultsByTime']:
                        total += self._extract_cost_metric(res.get('Total', {}))
                    logger.debug("AWS COST: Month-to-date actual total: %.4f", total)
                    return round(total, 6)
                return 0.0
            except ClientError as e:
                logger.warning("Cost Explorer error: %s", e)
                return 0.0
            except Exception as e:
                logger.warning("Cost Explorer MTD cost fetch failed: %s", e)
                return 0.0
        
        return await loop.run_in_executor(self.executor, fetch)

    async def _fetch_daily_cost_history(self, lookback_days: int = 60) -> tuple[List[Dict[str, Any]], Dict[str, float]]:
        """Fetch real daily AWS billing totals from Cost Explorer."""
        loop = asyncio.get_event_loop()

        def fetch():
            daily_by_date: Dict[str, float] = {}
            service_breakdown: Dict[str, float] = {}
            try:
                client = self._get_client('ce', 'us-east-1')
                end_date = datetime.now()
                start_date = end_date - timedelta(days=max(int(lookback_days), 1))
                token = None

                while True:
                    kwargs = {
                        'TimePeriod': {
                            'Start': start_date.strftime('%Y-%m-%d'),
                            'End': end_date.strftime('%Y-%m-%d')
                        },
                        'Granularity': 'DAILY',
                        'Metrics': ['NetAmortizedCost', 'AmortizedCost', 'UnblendedCost'],
                        'Filter': self._gross_usage_cost_filter(),
                        'GroupBy': [{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
                    }
                    if token:
                        kwargs['NextPageToken'] = token

                    response = client.get_cost_and_usage(**kwargs)
                    for time_period in response.get('ResultsByTime', []):
                        date_key = str(time_period.get('TimePeriod', {}).get('Start') or '').strip()
                        if not date_key:
                            continue

                        day_total = 0.0
                        groups = time_period.get('Groups', [])
                        if groups:
                            for group in groups:
                                service_name = str((group.get('Keys') or ['Unknown'])[0] or 'Unknown')
                                amount = self._extract_cost_metric(group.get('Metrics', {}))
                                day_total += amount
                                if amount:
                                    service_breakdown[service_name] = round(
                                        service_breakdown.get(service_name, 0.0) + amount,
                                        4,
                                    )
                        else:
                            day_total = self._extract_cost_metric(time_period.get('Total', {}))

                        daily_by_date[date_key] = round(
                            daily_by_date.get(date_key, 0.0) + day_total,
                            4,
                        )

                    token = response.get('NextPageToken')
                    if not token:
                        break

                daily_totals = [
                    {"date": day, "amount": round(amount, 4)}
                    for day, amount in sorted(daily_by_date.items())
                ]
                return daily_totals, service_breakdown
            except Exception as e:
                logger.warning("Failed to fetch AWS daily billing history: %s", e)
                return [], {}

        return await loop.run_in_executor(self.executor, fetch)
    
    async def _fetch_daily_resource_costs(self, lookback_days: int = 14) -> Dict[str, float]:
        """
        Fetch recent cost per resource from Cost Explorer.
        Returns a map of {ResourceID: Cost}.
        Requires 'Resource Level Data' to be enabled in Cost Explorer.
        """
        loop = asyncio.get_event_loop()
        
        def fetch():
            cost_map = {}
            client = self._get_client('ce', 'us-east-1') # Global endpoint
            end_date = datetime.now()
            # AWS resource-level Cost Explorer rejects older hourly-backed
            # RESOURCE_ID windows, so keep this bounded to the supported range.
            resource_lookback_days = max(1, min(int(lookback_days), 14))
            start_date = end_date - timedelta(days=resource_lookback_days)
            
            # 1) Primary path: resource-level costs by RESOURCE_ID (DAILY granularity)
            self.resource_cost_status = "checking_resource_id_costs"
            try:
                token = None
                while True:
                    kwargs = {
                        'TimePeriod': {
                            'Start': start_date.strftime('%Y-%m-%d'),
                            'End': end_date.strftime('%Y-%m-%d')
                        },
                        'Granularity': 'DAILY',
                        'Filter': {
                            'Dimensions': {
                                'Key': 'SERVICE',
                                'Values': ['Amazon Elastic Compute Cloud - Compute'],
                            }
                        },
                        'Metrics': ['UnblendedCost'],
                        'GroupBy': [{'Type': 'DIMENSION', 'Key': 'RESOURCE_ID'}]
                    }
                    if token:
                        kwargs['NextPageToken'] = token
                        
                    response = client.get_cost_and_usage_with_resources(**kwargs)
                
                    for time_period in response.get('ResultsByTime', []):
                        for group in time_period.get('Groups', []):
                            resource_key = group['Keys'][0]
                            cost = float(group['Metrics']['UnblendedCost']['Amount'])

                            if self._normalize_cost_key(resource_key) in {'noresourceid', 'unknown', ''}:
                                continue
                            self._add_cost_key(cost_map, resource_key, cost)

                    token = response.get('NextPageToken')
                    if not token:
                        break
                self.resource_cost_status = "resource_id_costs_available"
                self.resource_cost_message = ""

            except Exception as e:
                if self._is_resource_granularity_opt_in_error(e):
                    self.resource_cost_status = "resource_level_granularity_not_enabled"
                    self.resource_cost_message = (
                        "Exact AWS per-resource costs require Cost Explorer resource-level "
                        "data granularity to be enabled from the payer account. Standard "
                        "account and service billing totals can still be imported."
                    )
                    logger.warning("%s: %s", self.resource_cost_message, e)
                else:
                    self.resource_cost_status = "resource_id_costs_unavailable"
                    self.resource_cost_message = "Exact AWS per-resource costs are unavailable from Cost Explorer."
                    logger.warning(f"Failed to fetch AWS RESOURCE_ID costs: {e}")

            # 2) Supplemental path: Name tag costs as fallback for resources
            # where provider doesn't emit RESOURCE_ID cleanly.
            try:
                token = None
                while True:
                    kwargs = {
                        'TimePeriod': {
                            'Start': start_date.strftime('%Y-%m-%d'),
                            'End': end_date.strftime('%Y-%m-%d')
                        },
                        'Granularity': 'DAILY',
                        'Metrics': ['UnblendedCost'],
                        'GroupBy': [{'Type': 'TAG', 'Key': 'Name'}]
                    }
                    if token:
                        kwargs['NextPageToken'] = token
                        
                    response = client.get_cost_and_usage(**kwargs)
                
                    for time_period in response.get('ResultsByTime', []):
                        for group in time_period.get('Groups', []):
                            name_key = group['Keys'][0]
                            cost = float(group['Metrics']['UnblendedCost']['Amount'])
                            
                            if cost <= 0:
                                continue
                            name_val = name_key
                            if '$' in name_key:
                                name_val = name_key.split('$', 1)[1]
                            self._add_cost_key(cost_map, name_val, cost)

                    token = response.get('NextPageToken')
                    if not token:
                        break

            except Exception as e:
                logger.warning(f"Failed to fetch cost by Name tag: {e}")
                
            logger.info(f"Fetched AWS cost lookup data for {len(cost_map)} keys")
            return cost_map
        
        return await loop.run_in_executor(self.executor, fetch)
    
    # -------------------------------------------------------------------
    # CloudWatch Hourly Metrics (for workload pattern analysis)
    # -------------------------------------------------------------------

    def _get_ec2_metrics_hourly(self, cw_client, instance_id: str, lookback_days: int = 30) -> Optional[List[float]]:
        """
        Fetch hourly CPU metrics from CloudWatch for workload pattern analysis.

        Returns a chronologically-ordered list of hourly CPU averages
        (up to 720 points for 30 days), or None if insufficient data.
        """
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            response = cw_client.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average'],
            )

            datapoints = response.get('Datapoints', [])
            if len(datapoints) < 48:
                return None

            sorted_dps = sorted(datapoints, key=lambda dp: dp['Timestamp'])
            return [dp['Average'] for dp in sorted_dps]
        except Exception as e:
            logger.debug("Hourly metrics fetch failed for %s: %s", instance_id, e)
            return None

    # -------------------------------------------------------------------
    # EC2 Instances
    # -------------------------------------------------------------------

    async def _scan_ec2(self, region: str) -> tuple:
        """Scan EC2 instances in a region with FULL metadata for AI verification."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            waste = []
            savings = 0.0
            active_count = 0
            carbon = 0.0
            
            try:
                client = self._get_client('ec2', region)
                response = client.describe_instances()
                
                # Try to get CloudWatch metrics for CPU utilization
                cw_client = None
                try:
                    cw_client = self._get_client('cloudwatch', region)
                except Exception:
                    pass
                
                for reservation in response.get('Reservations', []):
                    for instance in reservation.get('Instances', []):
                        instance_id = instance['InstanceId']
                        name = next(
                            (t['Value'] for t in instance.get('Tags', []) if t['Key'] == 'Name'),
                            instance_id
                        )
                        
                        state_name = instance['State']['Name']
                        is_stopped = state_name == 'stopped'
                        all_tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}
                        owner = all_tags.get('Owner', all_tags.get('CreatedBy', 'Unknown'))
                        is_shadow_it = region not in APPROVED_REGIONS
                        
                        if not is_stopped:
                            from ..core.carbon_model import estimate_monthly_carbon_kg
                            carbon += estimate_monthly_carbon_kg("aws", instance.get('InstanceType', ''), region)
                        
                        monthly_cost = 0.0
                        
                        if not is_stopped:
                            active_count += 1
                        
                        # Collect rich metadata for AI verification
                        launch_time = instance.get('LaunchTime')
                        meta = {
                            'instance_id': instance_id,
                            'instance_type': instance.get('InstanceType'),
                            'state': state_name,
                            'state_reason': instance.get('StateTransitionReason', ''),
                            'launch_time': str(launch_time) if launch_time else None,
                            'platform': instance.get('PlatformDetails', instance.get('Platform', 'Linux/UNIX')),
                            'architecture': instance.get('Architecture', ''),
                            'vpc_id': instance.get('VpcId', ''),
                            'subnet_id': instance.get('SubnetId', ''),
                            'private_ip': instance.get('PrivateIpAddress', ''),
                            'public_ip': instance.get('PublicIpAddress', ''),
                            'ebs_optimized': instance.get('EbsOptimized', False),
                            'attached_volumes': len(instance.get('BlockDeviceMappings', [])),
                            'security_groups': [sg['GroupId'] for sg in instance.get('SecurityGroups', [])],
                            'tags': all_tags,
                            'cost_source': COST_SOURCE_BILLING_UNAVAILABLE,
                            'pricing_note': 'Exact per-resource cost requires AWS Cost Explorer RESOURCE_ID billing data.',
                        }
                        
                        # Fetch 7-day summary + 30-day hourly metrics from CloudWatch
                        ec2_status = 'Active'
                        ec2_waste_type = None

                        if cw_client and not is_stopped:
                            end_time = datetime.now()
                            start_time_7d = end_time - timedelta(days=7)

                            # 7-day daily summary for quick stats
                            try:
                                cw_resp = cw_client.get_metric_statistics(
                                    Namespace='AWS/EC2',
                                    MetricName='CPUUtilization',
                                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                                    StartTime=start_time_7d,
                                    EndTime=end_time,
                                    Period=86400,
                                    Statistics=['Average']
                                )
                                datapoints = cw_resp.get('Datapoints', [])
                                if datapoints:
                                    avg_cpu = sum(dp['Average'] for dp in datapoints) / len(datapoints)
                                    meta['avg_cpu_7d'] = round(avg_cpu, 2)
                                    meta['cpu_datapoints'] = len(datapoints)
                                else:
                                    meta['avg_cpu_7d'] = None
                                    meta['cpu_datapoints'] = 0
                            except Exception:
                                meta['avg_cpu_7d'] = None

                            # Network In/Out (bytes -> MB)
                            try:
                                for metric_name, meta_key in [
                                    ('NetworkIn', 'network_in_mb'),
                                    ('NetworkOut', 'network_out_mb'),
                                ]:
                                    cw_net = cw_client.get_metric_statistics(
                                        Namespace='AWS/EC2',
                                        MetricName=metric_name,
                                        Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                                        StartTime=start_time_7d,
                                        EndTime=end_time,
                                        Period=86400,
                                        Statistics=['Sum']
                                    )
                                    net_dps = cw_net.get('Datapoints', [])
                                    if net_dps:
                                        total_bytes = sum(dp['Sum'] for dp in net_dps)
                                        meta[meta_key] = round(total_bytes / (1024 * 1024), 2)
                            except Exception:
                                pass

                            # Disk Read/Write Ops
                            try:
                                for metric_name, meta_key in [
                                    ('DiskReadOps', 'disk_read_ops'),
                                    ('DiskWriteOps', 'disk_write_ops'),
                                ]:
                                    cw_disk = cw_client.get_metric_statistics(
                                        Namespace='AWS/EC2',
                                        MetricName=metric_name,
                                        Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                                        StartTime=start_time_7d,
                                        EndTime=end_time,
                                        Period=86400,
                                        Statistics=['Sum']
                                    )
                                    disk_dps = cw_disk.get('Datapoints', [])
                                    if disk_dps:
                                        total_ops = sum(dp['Sum'] for dp in disk_dps)
                                        avg_daily_ops = total_ops / len(disk_dps)
                                        meta[meta_key] = round(avg_daily_ops, 2)
                            except Exception:
                                pass

                            # --- Idle detection: running but CPU < 2%, network < 1 MB ---
                            avg_cpu_7d = meta.get('avg_cpu_7d')
                            net_in = meta.get('network_in_mb', 0)
                            net_out = meta.get('network_out_mb', 0)
                            if avg_cpu_7d is not None and avg_cpu_7d < 2.0 and (net_in + net_out) < 1.0:
                                ec2_status = 'Zombie'
                                ec2_waste_type = 'idle'
                                meta['waste_reason'] = (
                                    f"IDLE: avg CPU {avg_cpu_7d:.1f}%, network {net_in + net_out:.1f} MB "
                                    f"over 7 days. Running but processing no workload."
                                )
                            else:
                                # --- 30-day workload pattern analysis ---
                                try:
                                    hourly_data = self._get_ec2_metrics_hourly(cw_client, instance_id, lookback_days=30)
                                    if hourly_data and len(hourly_data) >= 48:
                                        series = MetricTimeSeries(hourly_values=hourly_data, metric_name="cpu")
                                        analysis = classify_pattern(series)

                                        instance_type_str = instance.get('InstanceType', '')
                                        vcpu_guess = 2
                                        try:
                                            size_part = instance_type_str.split('.')[1] if '.' in instance_type_str else ''
                                            vcpu_map = {'nano': 1, 'micro': 1, 'small': 1, 'medium': 1,
                                                        'large': 2, 'xlarge': 4, '2xlarge': 8, '4xlarge': 16,
                                                        '8xlarge': 32, '12xlarge': 48, '16xlarge': 64, '24xlarge': 96}
                                            vcpu_guess = vcpu_map.get(size_part, 2)
                                        except Exception:
                                            pass

                                        rec = generate_recommendation(
                                            analysis,
                                            current_vm_size=instance_type_str,
                                            current_monthly_cost=monthly_cost,
                                            current_vm_vcpus=max(vcpu_guess, 1),
                                        )

                                        meta['workload_pattern'] = analysis.pattern.value
                                        meta['peak_trough_ratio'] = analysis.peak_trough_ratio
                                        meta['peak_avg_cpu'] = analysis.peak_avg
                                        meta['trough_avg_cpu'] = analysis.trough_avg
                                        meta['p90_cpu'] = analysis.p90
                                        meta['p95_cpu'] = analysis.p95
                                        meta['observation_days'] = analysis.observation_days
                                        meta['recommendation_type'] = rec.type.value
                                        meta['recommendation_explanation'] = rec.explanation
                                        meta['estimated_savings_pct'] = rec.estimated_savings_pct
                                        meta['pattern_confidence'] = rec.confidence

                                        if rec.autoscale:
                                            meta['autoscale_min_instances'] = rec.autoscale.min_instances
                                            meta['autoscale_max_instances'] = rec.autoscale.max_instances
                                            meta['autoscale_scale_out_cpu'] = rec.autoscale.scale_out_cpu_pct
                                            meta['autoscale_scale_in_cpu'] = rec.autoscale.scale_in_cpu_pct
                                            meta['autoscale_cooldown_min'] = rec.autoscale.cooldown_minutes

                                        if rec.schedule:
                                            meta['schedule_stop_days'] = rec.schedule.stop_days
                                            meta['schedule_savings_pct'] = rec.schedule.estimated_savings_pct

                                        if rec.type in (RecommendationType.AUTOSCALE, RecommendationType.SCHEDULE,
                                                        RecommendationType.RIGHTSIZE, RecommendationType.SPOT_CANDIDATE):
                                            ec2_status = 'Idle'
                                            ec2_waste_type = rec.type.value
                                        else:
                                            ec2_status = 'Active'
                                    else:
                                        meta['workload_pattern'] = 'unknown'
                                except Exception as e:
                                    logger.debug("Workload pattern analysis failed for %s: %s", instance_id, e)
                                    meta['workload_pattern'] = 'unknown'

                        instance_type_lower = str(instance.get('InstanceType', '')).lower()
                        # Expanded GPU detection: P-series (V100/A100/H100), G-series (T4/A10G),
                        # Trainium (trn1), Inferentia (inf1/inf2), Gaudi (dl1), G3 (M60)
                        GPU_PREFIXES = ('p3', 'p4', 'p5', 'g3', 'g4', 'g5', 'trn1', 'inf1', 'inf2', 'dl1')
                        is_gpu_instance = any(instance_type_lower.startswith(prefix) for prefix in GPU_PREFIXES)
                        if is_gpu_instance:
                            meta['is_gpu_instance'] = True
                            meta['instance_type'] = instance.get('InstanceType', '')
                            # MIG-capable (A100/H100 — P4/P5 series)
                            if any(instance_type_lower.startswith(p) for p in ('p4', 'p5')):
                                meta['gpu_optimization_insight'] = (
                                    "MIG-capable GPU (A100/H100) detected. If utilization is low, "
                                    "enable NVIDIA MIG to partition into up to 7 logical GPUs at the same cost."
                                )
                            # Standard training GPU (P3 — V100)
                            elif instance_type_lower.startswith('p3'):
                                meta['gpu_optimization_insight'] = (
                                    "V100 GPU detected. Consider upgrading to A10G (G5) for inference "
                                    "or switch to specialized clouds (Lambda Labs/CoreWeave) to cut costs 40-55%."
                                )
                            # Inference accelerators
                            elif any(instance_type_lower.startswith(p) for p in ('inf1', 'inf2')):
                                meta['gpu_optimization_insight'] = (
                                    "AWS Inferentia chip detected. Verify inference throughput vs. "
                                    "comparable G5 (A10G) or G4dn (T4) instances for cost-effectiveness."
                                )
                            # AWS Trainium
                            elif instance_type_lower.startswith('trn1'):
                                meta['gpu_optimization_insight'] = (
                                    "AWS Trainium detected. Monitor training job completion — "
                                    "idle Trainium hosts cost ~$21.50/hr. Terminate immediately after job finishes."
                                )
                            # G-series (T4/A10G — inference/graphics)
                            else:
                                meta['gpu_optimization_insight'] = (
                                    "GPU inference instance detected. Compare cost vs. "
                                    "JarvisLabs or RunPod for equivalent T4/A10G throughput at 30-40% lower cost."
                                )
                        
                        final_status = 'Stopped' if is_stopped else ec2_status
                        if is_stopped and monthly_cost > 0:
                            ec2_waste_type = 'stopped'

                        if ec2_waste_type and monthly_cost > 0:
                            savings += monthly_cost
                            waste.append({'category_name': f'EC2 {ec2_waste_type}', 'value': monthly_cost})

                        resources.append(ScannedResource(
                            resource_name=name,
                            service_type='AWS EC2 Instance',
                            cost=monthly_cost,
                            status=final_status,
                            region=region,
                            region_compliance='shadow_it' if is_shadow_it else 'compliant',
                            created_by=owner,
                            metadata=meta
                        ))
                        
            except ClientError as e:
                logger.warning(f"EC2 scan error in {region}: {e}")
            
            return resources, waste, savings, active_count, carbon
        
        return await loop.run_in_executor(self.executor, scan)
    
    # -------------------------------------------------------------------
    # EBS Volumes
    # -------------------------------------------------------------------
    
    async def _scan_ebs(self, region: str) -> tuple:
        """Scan EBS volumes in a region."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            waste = []
            savings = 0.0
            
            try:
                client = self._get_client('ec2', region)
                response = client.describe_volumes()
                
                for volume in response.get('Volumes', []):
                    volume_id = volume['VolumeId']
                    name = next(
                        (t['Value'] for t in volume.get('Tags', []) if t['Key'] == 'Name'),
                        volume_id
                    )
                    
                    vol_state = volume['State']
                    is_unattached = vol_state == 'available'
                    all_tags = {t['Key']: t['Value'] for t in volume.get('Tags', [])}
                    owner = all_tags.get('Owner', 'Unknown')
                    is_shadow_it = region not in APPROVED_REGIONS
                    
                    size_gb = volume.get('Size', 0)
                    monthly_cost = 0.0
                    
                    if is_unattached:
                        if monthly_cost > 0:
                            savings += monthly_cost
                            waste.append({'category_name': 'Orphaned EBS', 'value': monthly_cost})
                    
                    # Rich metadata for AI
                    attachments = volume.get('Attachments', [])
                    create_time = volume.get('CreateTime')
                    meta = {
                        'volume_id': volume_id,
                        'size_gb': size_gb,
                        'volume_type': volume.get('VolumeType'),
                        'state': vol_state,
                        'iops': volume.get('Iops'),
                        'throughput': volume.get('Throughput'),
                        'encrypted': volume.get('Encrypted', False),
                        'snapshot_id': volume.get('SnapshotId', ''),
                        'create_time': str(create_time) if create_time else None,
                        'attachment_count': len(attachments),
                        'attached_to': attachments[0].get('InstanceId') if attachments else None,
                        'attachment_state': attachments[0].get('State') if attachments else None,
                        'tags': all_tags,
                        'cost_source': COST_SOURCE_BILLING_UNAVAILABLE,
                        'pricing_note': 'Exact per-volume cost requires AWS Cost Explorer RESOURCE_ID billing data.',
                    }
                    
                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type='AWS EBS Volume',
                        cost=monthly_cost,
                        status='Zombie' if is_unattached else 'Active',
                        region=region,
                        region_compliance='shadow_it' if is_shadow_it else 'compliant',
                        created_by=owner,
                        metadata=meta
                    ))
                    
            except ClientError as e:
                logger.warning(f"EBS scan error in {region}: {e}")
            
            return resources, waste, savings
        
        return await loop.run_in_executor(self.executor, scan)
    
    # -------------------------------------------------------------------
    # Elastic IPs
    # -------------------------------------------------------------------
    
    async def _scan_elastic_ips(self, region: str) -> tuple:
        """Scan Elastic IPs in a region."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            waste = []
            savings = 0.0
            
            try:
                client = self._get_client('ec2', region)
                response = client.describe_addresses()
                
                for address in response.get('Addresses', []):
                    name = next(
                        (t['Value'] for t in address.get('Tags', []) if t['Key'] == 'Name'),
                        address.get('PublicIp', 'Unknown EIP')
                    )
                    
                    is_unassociated = not address.get('AssociationId')
                    all_tags = {t['Key']: t['Value'] for t in address.get('Tags', [])}
                    owner = all_tags.get('Owner', 'Unknown')
                    is_shadow_it = region not in APPROVED_REGIONS
                    monthly_cost = 0.0
                    
                    if is_unassociated:
                        if monthly_cost > 0:
                            savings += monthly_cost
                            waste.append({'category_name': 'Unused Elastic IP', 'value': monthly_cost})
                    
                    meta = {
                        'public_ip': address.get('PublicIp'),
                        'allocation_id': address.get('AllocationId'),
                        'association_id': address.get('AssociationId'),
                        'instance_id': address.get('InstanceId'),
                        'network_interface_id': address.get('NetworkInterfaceId'),
                        'domain': address.get('Domain', 'vpc'),
                        'tags': all_tags,
                        'cost_source': COST_SOURCE_BILLING_UNAVAILABLE,
                        'pricing_note': 'Exact Elastic IP cost requires AWS Cost Explorer RESOURCE_ID billing data.',
                    }
                    
                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type='AWS Elastic IP',
                        cost=monthly_cost,
                        status='Zombie' if is_unassociated else 'Active',
                        region=region,
                        region_compliance='shadow_it' if is_shadow_it else 'compliant',
                        created_by=owner,
                        metadata=meta
                    ))
                    
            except ClientError as e:
                logger.warning(f"Elastic IP scan error in {region}: {e}")
            
            return resources, waste, savings
        
        return await loop.run_in_executor(self.executor, scan)
    
    # -------------------------------------------------------------------
    # VPCs
    # -------------------------------------------------------------------
    
    async def _scan_vpcs(self, region: str) -> List[ScannedResource]:
        """Scan VPCs in a region."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            try:
                client = self._get_client('ec2', region)
                response = client.describe_vpcs()
                
                for vpc in response.get('Vpcs', []):
                    name = next(
                        (t['Value'] for t in vpc.get('Tags', []) if t['Key'] == 'Name'),
                        vpc['VpcId']
                    )
                    is_default = vpc.get('IsDefault', False)
                    
                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type='AWS VPC',
                        cost=0.0,
                        status='Active',
                        region=region,
                        region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                        metadata={
                            'vpc_id': vpc['VpcId'],
                            'cidr_block': vpc.get('CidrBlock'),
                            'is_default': is_default,
                            'state': vpc.get('State')
                        }
                    ))
            except ClientError as e:
                logger.warning(f"VPC scan error in {region}: {e}")
            return resources
        
        return await loop.run_in_executor(self.executor, scan)
    
    # -------------------------------------------------------------------
    # Subnets
    # -------------------------------------------------------------------
    
    async def _scan_subnets(self, region: str) -> List[ScannedResource]:
        """Scan Subnets in a region."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            try:
                client = self._get_client('ec2', region)
                response = client.describe_subnets()
                
                for subnet in response.get('Subnets', []):
                    name = next(
                        (t['Value'] for t in subnet.get('Tags', []) if t['Key'] == 'Name'),
                        subnet['SubnetId']
                    )
                    
                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type='AWS Subnet',
                        cost=0.0,
                        status='Active',
                        region=region,
                        region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                        metadata={
                            'subnet_id': subnet['SubnetId'],
                            'vpc_id': subnet.get('VpcId'),
                            'cidr_block': subnet.get('CidrBlock'),
                            'availability_zone': subnet.get('AvailabilityZone'),
                            'available_ips': subnet.get('AvailableIpAddressCount')
                        }
                    ))
            except ClientError as e:
                logger.warning(f"Subnet scan error in {region}: {e}")
            return resources
        
        return await loop.run_in_executor(self.executor, scan)
    
    # -------------------------------------------------------------------
    # Security Groups
    # -------------------------------------------------------------------
    
    async def _scan_security_groups(self, region: str) -> List[ScannedResource]:
        """Scan Security Groups in a region."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            try:
                client = self._get_client('ec2', region)
                response = client.describe_security_groups()
                
                for sg in response.get('SecurityGroups', []):
                    name = sg.get('GroupName', sg['GroupId'])
                    
                    # Count inbound/outbound rules
                    inbound_rules = len(sg.get('IpPermissions', []))
                    outbound_rules = len(sg.get('IpPermissionsEgress', []))
                    
                    # Flag overly permissive SGs (0.0.0.0/0 on non-80/443)
                    is_risky = False
                    for rule in sg.get('IpPermissions', []):
                        for ip_range in rule.get('IpRanges', []):
                            if ip_range.get('CidrIp') == '0.0.0.0/0':
                                port = rule.get('FromPort', 0)
                                if port not in [80, 443]:
                                    is_risky = True
                    
                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type='AWS Security Group',
                        cost=0.0,
                        status='Active',
                        region=region,
                        region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                        metadata={
                            'group_id': sg['GroupId'],
                            'vpc_id': sg.get('VpcId'),
                            'description': sg.get('Description'),
                            'inbound_rules': inbound_rules,
                            'outbound_rules': outbound_rules,
                            'is_overly_permissive': is_risky
                        }
                    ))
            except ClientError as e:
                logger.warning(f"Security Group scan error in {region}: {e}")
            return resources
        
        return await loop.run_in_executor(self.executor, scan)
    
    # -------------------------------------------------------------------
    # Route Tables
    # -------------------------------------------------------------------
    
    async def _scan_route_tables(self, region: str) -> List[ScannedResource]:
        """Scan Route Tables in a region."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            try:
                client = self._get_client('ec2', region)
                response = client.describe_route_tables()
                
                for rt in response.get('RouteTables', []):
                    name = next(
                        (t['Value'] for t in rt.get('Tags', []) if t['Key'] == 'Name'),
                        rt['RouteTableId']
                    )
                    
                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type='AWS Route Table',
                        cost=0.0,
                        status='Active',
                        region=region,
                        region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                        metadata={
                            'route_table_id': rt['RouteTableId'],
                            'vpc_id': rt.get('VpcId'),
                            'routes_count': len(rt.get('Routes', [])),
                            'associations': len(rt.get('Associations', []))
                        }
                    ))
            except ClientError as e:
                logger.warning(f"Route Table scan error in {region}: {e}")
            return resources
        
        return await loop.run_in_executor(self.executor, scan)
    
    # -------------------------------------------------------------------
    # Internet Gateways
    # -------------------------------------------------------------------
    
    async def _scan_internet_gateways(self, region: str) -> List[ScannedResource]:
        """Scan Internet Gateways in a region."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            try:
                client = self._get_client('ec2', region)
                response = client.describe_internet_gateways()
                
                for igw in response.get('InternetGateways', []):
                    name = next(
                        (t['Value'] for t in igw.get('Tags', []) if t['Key'] == 'Name'),
                        igw['InternetGatewayId']
                    )
                    
                    attachments = igw.get('Attachments', [])
                    is_detached = len(attachments) == 0
                    
                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type='AWS Internet Gateway',
                        cost=0.0,
                        status='Zombie' if is_detached else 'Active',
                        region=region,
                        region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                        metadata={
                            'igw_id': igw['InternetGatewayId'],
                            'attached_vpcs': [a.get('VpcId') for a in attachments]
                        }
                    ))
            except ClientError as e:
                logger.warning(f"Internet Gateway scan error in {region}: {e}")
            return resources
        
        return await loop.run_in_executor(self.executor, scan)
    
    # -------------------------------------------------------------------
    # Network ACLs
    # -------------------------------------------------------------------
    
    async def _scan_network_acls(self, region: str) -> List[ScannedResource]:
        """Scan Network ACLs in a region."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            try:
                client = self._get_client('ec2', region)
                response = client.describe_network_acls()
                
                for nacl in response.get('NetworkAcls', []):
                    name = next(
                        (t['Value'] for t in nacl.get('Tags', []) if t['Key'] == 'Name'),
                        nacl['NetworkAclId']
                    )
                    
                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type='AWS Network ACL',
                        cost=0.0,
                        status='Active',
                        region=region,
                        region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                        metadata={
                            'nacl_id': nacl['NetworkAclId'],
                            'vpc_id': nacl.get('VpcId'),
                            'is_default': nacl.get('IsDefault', False)
                        }
                    ))
            except ClientError as e:
                logger.warning(f"Network ACL scan error in {region}: {e}")
            return resources
        
        return await loop.run_in_executor(self.executor, scan)
    
    # -------------------------------------------------------------------
    # DHCP Options
    # -------------------------------------------------------------------
    
    async def _scan_dhcp_options(self, region: str) -> List[ScannedResource]:
        """Scan DHCP Option Sets in a region."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            try:
                client = self._get_client('ec2', region)
                response = client.describe_dhcp_options()
                
                for dhcp in response.get('DhcpOptions', []):
                    name = next(
                        (t['Value'] for t in dhcp.get('Tags', []) if t['Key'] == 'Name'),
                        dhcp['DhcpOptionsId']
                    )
                    
                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type='AWS DHCP Options',
                        cost=0.0,
                        status='Active',
                        region=region,
                        region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                        metadata={'dhcp_options_id': dhcp['DhcpOptionsId']}
                    ))
            except ClientError as e:
                logger.warning(f"DHCP Options scan error in {region}: {e}")
            return resources
        
        return await loop.run_in_executor(self.executor, scan)
    
    # -------------------------------------------------------------------
    # Key Pairs
    # -------------------------------------------------------------------
    
    async def _scan_key_pairs(self, region: str) -> List[ScannedResource]:
        """Scan Key Pairs in a region."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            try:
                client = self._get_client('ec2', region)
                response = client.describe_key_pairs()
                
                for kp in response.get('KeyPairs', []):
                    name = kp.get('KeyName', kp.get('KeyPairId', 'Unknown'))
                    
                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type='AWS Key Pair',
                        cost=0.0,
                        status='Active',
                        region=region,
                        region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                        metadata={
                            'key_pair_id': kp.get('KeyPairId'),
                            'key_type': kp.get('KeyType'),
                            'fingerprint': kp.get('KeyFingerprint')
                        }
                    ))
            except ClientError as e:
                logger.warning(f"Key Pair scan error in {region}: {e}")
            return resources
        
        return await loop.run_in_executor(self.executor, scan)
    
    # -------------------------------------------------------------------
    # NEW SPECIFIC SCANNERS
    # -------------------------------------------------------------------

    async def _scan_s3(self) -> tuple:
        """Scan S3 buckets (Global)."""
        loop = asyncio.get_event_loop()
        
        def scan():
            logger.debug("S3: started scan_s3 inner function")
            resources = []
            waste = []
            savings = 0.0
            
            try:
                # S3 is global so we use us-east-1
                client = self._get_client('s3', 'us-east-1')
                logger.debug("S3: got client")
                response = client.list_buckets()
                buckets = response.get('Buckets', [])
                logger.debug("S3: list_buckets returned %s buckets", len(buckets))
                
                for bucket in buckets:
                    name = bucket['Name']
                    logger.debug("S3: processing bucket %s", name)
                    created_at = bucket.get('CreationDate')
                    
                    # We can try to get location constraint to get region
                    region = 'us-east-1'
                    try:
                        loc = client.get_bucket_location(Bucket=name)
                        region = loc.get('LocationConstraint') or 'us-east-1'
                        logger.debug("S3: bucket %s location: %s", name, region)
                    except Exception as e:
                        logger.debug("S3: bucket %s loc error: %s", name, e)
                        pass
                        
                    # Try to get tags
                    tags = {}
                    try:
                        tag_resp = client.get_bucket_tagging(Bucket=name)
                        tags = {t['Key']: t['Value'] for t in tag_resp.get('TagSet', [])}
                        logger.debug("S3: bucket %s tags fetched", name)
                    except Exception as e:
                        logger.debug("S3: bucket %s tag error: %s", name, e)
                        pass
                        
                    is_shadow_it = region not in APPROVED_REGIONS
                    
                    meta = {
                        'resource_id': name,
                        'creation_date': str(created_at) if created_at else None,
                        'tags': tags
                    }
                    
                    resources.append(ScannedResource(
                        resource_name=name,
                        service_type='AWS S3 Bucket',
                        cost=0.0, # Will be filled by generic cost distributor if available
                        status='Active',
                        region=region,
                        region_compliance='compliant' if not is_shadow_it else 'shadow_it',
                        created_by=tags.get('Owner', tags.get('CreatedBy', 'Unknown')),
                        metadata=meta,
                        cloud_resource_id=name
                    ))
            except Exception as e:
                self._handle_scan_error("S3", e, None)
                
            return resources, waste, savings
            
        return await loop.run_in_executor(self.executor, scan)

    async def _scan_rds(self, region: str) -> tuple:
        """Scan RDS instances."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            waste = []
            savings = 0.0
            
            try:
                client = self._get_client('rds', region)
                paginator = client.get_paginator('describe_db_instances')
                for page in paginator.paginate():
                    for db in page.get('DBInstances', []):
                        name = db.get('DBInstanceIdentifier')
                        arn = db.get('DBInstanceArn')
                        status = db.get('DBInstanceStatus')
                        
                        tags = {}
                        try:
                            tag_resp = client.list_tags_for_resource(ResourceName=arn)
                            tags = {t['Key']: t['Value'] for t in tag_resp.get('TagList', [])}
                        except Exception:
                            pass
                            
                        is_stopped = status in ('stopped', 'stopping')
                            
                        meta = {
                            'resource_id': name,
                            'arn': arn,
                            'engine': db.get('Engine'),
                            'engine_version': db.get('EngineVersion'),
                            'instance_class': db.get('DBInstanceClass'),
                            'status': status,
                            'publicly_accessible': db.get('PubliclyAccessible'),
                            'multi_az': db.get('MultiAZ'),
                            'tags': tags,
                            'cost_source': COST_SOURCE_BILLING_UNAVAILABLE,
                            'pricing_note': 'Exact RDS resource cost requires AWS Cost Explorer RESOURCE_ID billing data.',
                        }
                        
                        resources.append(ScannedResource(
                            resource_name=tags.get('Name', name),
                            service_type='AWS RDS Instance',
                            cost=0.0,
                            status='Zombie' if is_stopped else 'Active',
                            region=region,
                            region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                            created_by=tags.get('Owner', tags.get('CreatedBy', 'Unknown')),
                            metadata=meta,
                            cloud_resource_id=name
                        ))
            except Exception as e:
                self._handle_scan_error("RDS", e, region)
                
            return resources, waste, savings
            
        return await loop.run_in_executor(self.executor, scan)

    async def _scan_lambda(self, region: str) -> tuple:
        """Scan Lambda functions."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            waste = []
            savings = 0.0
            
            try:
                client = self._get_client('lambda', region)
                paginator = client.get_paginator('list_functions')
                for page in paginator.paginate():
                    for func in page.get('Functions', []):
                        name = func.get('FunctionName')
                        arn = func.get('FunctionArn')
                        
                        tags = {}
                        try:
                            # tags usually included? no, need get_function or list_tags API
                            tag_resp = client.list_tags(Resource=arn)
                            tags = tag_resp.get('Tags', {})
                        except Exception:
                            pass
                            
                        meta = {
                            'resource_id': name,
                            'arn': arn,
                            'runtime': func.get('Runtime'),
                            'memory_size': func.get('MemorySize'),
                            'timeout': func.get('Timeout'),
                            'last_modified': func.get('LastModified'),
                            'tags': tags
                        }
                        
                        resources.append(ScannedResource(
                            resource_name=tags.get('Name', name),
                            service_type='AWS Lambda Function',
                            cost=0.0,
                            status='Active',
                            region=region,
                            region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                            created_by=tags.get('Owner', tags.get('CreatedBy', 'Unknown')),
                            metadata=meta,
                            cloud_resource_id=name
                        ))
            except Exception as e:
                self._handle_scan_error("Lambda", e, region)
                
            return resources, waste, savings
            
        return await loop.run_in_executor(self.executor, scan)

    async def _scan_api_gateway(self, region: str) -> tuple:
        """Scan API Gateway REST and HTTP APIs for idle/ghost detection."""
        loop = asyncio.get_event_loop()

        def scan():
            resources = []
            waste = []
            savings = 0.0

            # --- REST APIs (apigateway) ---
            try:
                client = self._get_client('apigateway', region)
                paginator = client.get_paginator('get_rest_apis')
                cw_client = self._get_client('cloudwatch', region)

                for page in paginator.paginate():
                    for api in page.get('items', []):
                        api_id = api.get('id', '')
                        api_name = api.get('name', api_id)
                        endpoint_type = (api.get('endpointConfiguration', {}).get('types', ['REGIONAL']) or ['REGIONAL'])[0]
                        created_date = str(api.get('createdDate', ''))

                        try:
                            stages_resp = client.get_stages(restApiId=api_id)
                            stages = stages_resp.get('item', [])
                        except Exception:
                            stages = []

                        if not stages:
                            # API with no stages — likely orphaned
                            arn = f"arn:aws:apigateway:{region}::/restapis/{api_id}"
                            resources.append(ScannedResource(
                                resource_name=api_name,
                                service_type='AWS API Gateway',
                                cost=0.0,
                                status='Zombie',
                                region=region,
                                region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                                created_by='Unknown',
                                metadata={
                                    'api_id': api_id,
                                    'api_name': api_name,
                                    'api_type': 'REST',
                                    'stage_name': '',
                                    'endpoint_type': endpoint_type,
                                    'invocations_7d': 0,
                                    'created_date': created_date,
                                    'arn': arn,
                                    'is_api_resource': True,
                                    'route_count': 0,
                                },
                                cloud_resource_id=f"apigw-{api_id}-nostage",
                            ))
                            waste.append({'category_name': 'Orphaned API Gateway', 'value': 0})
                            continue

                        for stage in stages:
                            stage_name = stage.get('stageName', 'unknown')
                            stage_arn = f"arn:aws:apigateway:{region}::/restapis/{api_id}/stages/{stage_name}"
                            cache_enabled = bool(stage.get('cacheClusterEnabled', False))
                            cache_size = float(stage.get('cacheClusterSize', '0') or '0')

                            # Missing telemetry is not evidence of zero traffic.
                            end_time = datetime.now(timezone.utc)
                            start_time = end_time - timedelta(days=7)
                            dimensions = [
                                {'Name': 'ApiName', 'Value': api_name},
                                {'Name': 'Stage', 'Value': stage_name},
                            ]
                            metric_collection: Dict[str, str] = {}

                            def collect_metric(metric_name: str) -> Optional[float]:
                                try:
                                    statistic = (
                                        {'ExtendedStatistics': ['p99']}
                                        if metric_name == 'Latency' else {'Statistics': ['Sum']}
                                    )
                                    resp = cw_client.get_metric_statistics(
                                        Namespace='AWS/ApiGateway',
                                        MetricName=metric_name,
                                        Dimensions=dimensions,
                                        StartTime=start_time,
                                        EndTime=end_time,
                                        Period=604800,
                                        **statistic,
                                    )
                                    dps = resp.get('Datapoints', [])
                                    if not dps:
                                        metric_collection[metric_name] = 'no_data'
                                        return None
                                    values = [
                                        dp.get('ExtendedStatistics', {}).get('p99')
                                        if metric_name == 'Latency' else dp.get('Sum')
                                        for dp in dps
                                    ]
                                    if any(
                                        isinstance(value, bool)
                                        or not isinstance(value, (int, float))
                                        or not math.isfinite(value)
                                        or value < 0
                                        for value in values
                                    ):
                                        metric_collection[metric_name] = 'invalid_data'
                                        logger.warning(
                                            "API Gateway %s metric has invalid datapoints in %s", metric_name, region,
                                        )
                                        return None
                                    value = float(values[0] if metric_name == 'Latency' else sum(values))
                                    if not math.isfinite(value) or (metric_name != 'Latency' and not value.is_integer()):
                                        metric_collection[metric_name] = 'invalid_data'
                                        logger.warning("API Gateway %s metric has an invalid total in %s", metric_name, region)
                                        return None
                                    metric_collection[metric_name] = 'available'
                                    return value
                                except Exception as error:
                                    metric_collection[metric_name] = 'error'
                                    self._handle_scan_error(f"API Gateway CloudWatch {metric_name}", error, region)
                                    return None

                            request_count = collect_metric('Count')
                            invocations_7d = int(request_count) if request_count is not None else None
                            error_4xx = collect_metric('4XXError')
                            error_5xx = collect_metric('5XXError')
                            latency_p99 = collect_metric('Latency')
                            cache_hits = collect_metric('CacheHitCount') if cache_enabled else None
                            cache_misses = collect_metric('CacheMissCount') if cache_enabled else None

                            cache_hit_rate = None
                            if cache_hits is not None and cache_misses is not None and (cache_hits + cache_misses) > 0:
                                cache_hit_rate = round((cache_hits / (cache_hits + cache_misses)) * 100, 2)

                            error_rate_4xx = None
                            error_rate_5xx = None
                            if invocations_7d is not None and invocations_7d > 0:
                                if error_4xx is not None:
                                    error_rate_4xx = round((error_4xx / invocations_7d) * 100, 2)
                                if error_5xx is not None:
                                    error_rate_5xx = round((error_5xx / invocations_7d) * 100, 2)

                            # Determine status
                            status = 'Unknown' if invocations_7d is None else 'Active'
                            if invocations_7d == 0:
                                status = 'Zombie'

                            meta = {
                                'api_id': api_id,
                                'api_name': api_name,
                                'api_type': 'REST',
                                'stage_name': stage_name,
                                'endpoint_type': endpoint_type,
                                'invocations_7d': invocations_7d,
                                'metric_collection': metric_collection,
                                'avg_daily_invocations': round(invocations_7d / 7, 1) if invocations_7d is not None else None,
                                'error_rate_4xx': error_rate_4xx,
                                'error_rate_5xx': error_rate_5xx,
                                'latency_p99_ms': round(latency_p99, 1) if latency_p99 is not None else None,
                                'cache_enabled': cache_enabled,
                                'cache_hit_rate': cache_hit_rate,
                                'cache_size_gb': cache_size,
                                'throttle_burst_limit': stage.get('methodSettings', {}).get('*/*', {}).get('throttlingBurstLimit'),
                                'throttle_rate_limit': stage.get('methodSettings', {}).get('*/*', {}).get('throttlingRateLimit'),
                                'created_date': created_date,
                                'arn': stage_arn,
                                'is_api_resource': True,
                            }

                            resources.append(ScannedResource(
                                resource_name=f"{api_name}/{stage_name}",
                                service_type='AWS API Gateway',
                                cost=0.0,
                                status=status,
                                region=region,
                                region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                                created_by='Unknown',
                                metadata=meta,
                                cloud_resource_id=f"apigw-{api_id}-{stage_name}",
                            ))

                            if status == 'Zombie':
                                waste.append({'category_name': 'Ghost API Gateway', 'value': 0})

            except Exception as e:
                self._handle_scan_error("API Gateway REST", e, region)

            # --- HTTP/WebSocket APIs (apigatewayv2) ---
            try:
                v2_client = self._get_client('apigatewayv2', region)
                apis_resp = v2_client.get_apis()

                for api in apis_resp.get('Items', []):
                    api_id = api.get('ApiId', '')
                    api_name = api.get('Name', api_id)
                    protocol = api.get('ProtocolType', 'HTTP')

                    try:
                        stages_resp = v2_client.get_stages(ApiId=api_id)
                        v2_stages = stages_resp.get('Items', [])
                    except Exception:
                        v2_stages = []

                    for stage in v2_stages:
                        stage_name = stage.get('StageName', '$default')
                        stage_arn = f"arn:aws:apigateway:{region}::/apis/{api_id}/stages/{stage_name}"

                        meta = {
                            'api_id': api_id,
                            'api_name': api_name,
                            'api_type': protocol,
                            'stage_name': stage_name,
                            'endpoint_type': 'REGIONAL',
                            'invocations_7d': -1,
                            'created_date': str(api.get('CreatedDate', '')),
                            'arn': stage_arn,
                            'is_api_resource': True,
                        }

                        resources.append(ScannedResource(
                            resource_name=f"{api_name}/{stage_name}",
                            service_type='AWS API Gateway',
                            cost=0.0,
                            status='Active',
                            region=region,
                            region_compliance='compliant' if region in APPROVED_REGIONS else 'shadow_it',
                            created_by='Unknown',
                            metadata=meta,
                            cloud_resource_id=f"apigw-v2-{api_id}-{stage_name}",
                        ))

            except Exception as e:
                self._handle_scan_error("API Gateway HTTP/WS", e, region)

            return resources, waste, savings

        return await loop.run_in_executor(self.executor, scan)

    # -------------------------------------------------------------------
    # IAM (Global — not per-region)
    # -------------------------------------------------------------------
    
    async def _scan_iam(self) -> List[ScannedResource]:
        """Scan IAM users and roles (global, not per-region)."""
        loop = asyncio.get_event_loop()
        
        def scan():
            resources = []
            try:
                client = self._get_client('iam', 'us-east-1')
                
                # IAM Users
                try:
                    users_resp = client.list_users()
                    for user in users_resp.get('Users', []):
                        resources.append(ScannedResource(
                            resource_name=user['UserName'],
                            service_type='AWS IAM User',
                            cost=0.0,
                            status='Active',
                            region='global',
                            region_compliance='compliant',
                            metadata={
                                'user_id': user.get('UserId'),
                                'arn': user.get('Arn'),
                                'created': str(user.get('CreateDate', '')),
                                'password_last_used': str(user.get('PasswordLastUsed', 'Never'))
                            }
                        ))
                except ClientError as e:
                    logger.warning(f"IAM Users scan error: {e}")
                
                # IAM Roles
                try:
                    roles_resp = client.list_roles()
                    for role in roles_resp.get('Roles', []):
                        role_name = role['RoleName']
                        is_service_role = 'aws-service-role' in role.get('Path', '')
                        
                        resources.append(ScannedResource(
                            resource_name=role_name,
                            service_type='AWS IAM Role',
                            cost=0.0,
                            status='Active',
                            region='global',
                            region_compliance='compliant',
                            metadata={
                                'role_id': role.get('RoleId'),
                                'arn': role.get('Arn'),
                                'path': role.get('Path'),
                                'is_service_linked': is_service_role,
                                'created': str(role.get('CreateDate', ''))
                            }
                        ))
                except ClientError as e:
                    logger.warning(f"IAM Roles scan error: {e}")
                
            except ClientError as e:
                logger.warning(f"IAM scan error: {e}")
            
            return resources
        
        return await loop.run_in_executor(self.executor, scan)
    
    # -------------------------------------------------------------------
    # DB Format Conversion
    # -------------------------------------------------------------------
    
    def to_db_resources(self, resources: List[ScannedResource], user_id: str, integration_id: str) -> List[Dict]:
        """Convert scanned resources to database format with intelligent deduplication."""
        unique_resources = {}
        
        for r in resources:
            cloud_resource_id = (
                (r.metadata or {}).get('instance_id') or
                (r.metadata or {}).get('volume_id') or
                (r.metadata or {}).get('allocation_id') or
                (r.metadata or {}).get('subnet_id') or
                (r.metadata or {}).get('route_table_id') or
                (r.metadata or {}).get('nacl_id') or
                (r.metadata or {}).get('igw_id') or
                (r.metadata or {}).get('group_id') or
                (r.metadata or {}).get('dhcp_options_id') or
                (r.metadata or {}).get('key_pair_id') or
                (r.metadata or {}).get('vpc_id') or
                (r.metadata or {}).get('user_id') or
                (r.metadata or {}).get('role_id') or
                (r.metadata or {}).get('arn') or
                (r.metadata or {}).get('resource_id') or 
                f"aws-{r.resource_name}-{r.region}"
            )
            
            # Prepare metadata
            metadata = {
                'aws_region': r.region,
                'is_shadow_it': r.region_compliance == 'shadow_it',
                **(r.metadata or {})
            }
            if not metadata.get('cost_source'):
                metadata['cost_source'] = (
                    COST_SOURCE_ACTUAL if float(r.cost or 0) > 0 else COST_SOURCE_BILLING_UNAVAILABLE
                )
            if metadata['cost_source'] == COST_SOURCE_BILLING_UNAVAILABLE:
                metadata.setdefault(
                    'pricing_note',
                    'Exact AWS resource cost requires Cost Explorer billing data for this resource.',
                )
                resource_cost_status = getattr(self, 'resource_cost_status', '')
                resource_cost_message = getattr(self, 'resource_cost_message', '')
                if resource_cost_status and resource_cost_status != 'not_checked':
                    metadata.setdefault('resource_cost_status', resource_cost_status)
                if resource_cost_message:
                    metadata['pricing_note'] = resource_cost_message
            
            if cloud_resource_id in unique_resources:
                existing = unique_resources[cloud_resource_id]
                # Merge metadata
                existing['metadata'].update(metadata)
                # Keep highest cost
                if r.cost > existing['cost']:
                    existing['cost'] = r.cost
            else:
                unique_resources[cloud_resource_id] = {
                    'resource_name': r.resource_name,
                    'service_type': r.service_type,
                    'cost': r.cost,
                    'status': r.status,
                    'created_by': r.created_by,
                    'region_compliance': r.region_compliance,
                    'provider': 'aws',
                    'cloud_resource_id': cloud_resource_id,
                    'user_id': user_id,
                    'integration_id': integration_id,
                    'metadata': metadata
                }
                
        return list(unique_resources.values())
