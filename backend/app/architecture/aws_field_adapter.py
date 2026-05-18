"""
AWS field adapter.

Single adapter layer so the rest of the pipeline doesn't care about
scanner field names or variations in the MongoDB resources table.

Data contract (from to_db_resources in aws.py):
  - region is stored in `region_compliance` column (NOT compliance data)
  - metadata JSONB contains all scanner fields PLUS `aws_region`, `is_shadow_it`
  - cloud_resource_id is first non-null from metadata identity fields
  - status is 'Active' or 'Zombie' (set by scanner), may be overridden by AI
  - waste_type / waste_reason set by AI post-processing (may be None)
"""

from typing import Any, Dict, List, Optional

# Map service_type strings → canonical kinds.
# This lookup is exhaustive for the current AWS scanner (13 scan methods).
_SERVICE_TYPE_MAP = {
    "AWS EC2 Instance":      "ec2",
    "AWS EBS Volume":        "ebs",
    "AWS Elastic IP":        "eip",
    "AWS VPC":               "vpc",
    "AWS Subnet":            "subnet",
    "AWS Security Group":    "sg",
    "AWS Route Table":       "route_table",
    "AWS Internet Gateway":  "igw",
    "AWS Network ACL":       "nacl",
    "AWS DHCP Options":      "dhcp",
    "AWS Key Pair":          "key_pair",
    "AWS S3 Bucket":         "s3",
    "AWS RDS Instance":      "rds",
    "AWS Lambda Function":   "lambda",
    "AWS IAM User":          "iam",
    "AWS IAM Role":          "iam",
}


def get_service_kind(row: Dict[str, Any]) -> str:
    """Classify a resource row into a canonical service kind."""
    st = row.get("service_type", "")
    kind = _SERVICE_TYPE_MAP.get(st)
    if kind:
        return kind

    # Fallback: pattern match on service_type substring
    st_lower = st.lower()
    for fragment, k in [
        ("ec2", "ec2"), ("ebs", "ebs"), ("elastic ip", "eip"),
        ("vpc", "vpc"), ("subnet", "subnet"), ("security group", "sg"),
        ("internet gateway", "igw"), ("rds", "rds"), ("s3", "s3"),
        ("lambda", "lambda"), ("iam", "iam"),
        ("eks", "eks"), ("ecs", "ecs"), ("alb", "alb"),
        ("load balancer", "alb"),
    ]:
        if fragment in st_lower:
            return k
    return "unknown"


def _meta(row: Dict[str, Any]) -> Dict[str, Any]:
    """Safely get the metadata dict."""
    return row.get("metadata") or {}


def get_region(row: Dict[str, Any]) -> str:
    """
    Get the AWS region for a resource.

    MongoDB stores region in `region_compliance` (historical naming).
    Metadata also has `aws_region`. We prefer metadata since it's set
    directly by the scanner.
    """
    m = _meta(row)
    return m.get("aws_region") or row.get("region_compliance") or row.get("region") or "unknown"


def get_vpc_id(row: Dict[str, Any]) -> Optional[str]:
    """Get vpc_id from metadata. Works for EC2, Subnet, SG, Route Table, NACL, RDS."""
    return _meta(row).get("vpc_id") or None


def get_subnet_id(row: Dict[str, Any]) -> Optional[str]:
    """Get subnet_id from metadata. Works for EC2, Subnet resources."""
    return _meta(row).get("subnet_id") or None


def get_instance_id(row: Dict[str, Any]) -> Optional[str]:
    """Get EC2 instance_id from metadata."""
    return _meta(row).get("instance_id") or None


def get_sg_ids(row: Dict[str, Any]) -> List[str]:
    """Get security group IDs from EC2 metadata."""
    sgs = _meta(row).get("security_groups")
    if isinstance(sgs, list):
        return [s for s in sgs if isinstance(s, str)]
    return []


def get_rds_vpc_id(row: Dict[str, Any]) -> Optional[str]:
    """Get VPC ID for an RDS instance. Requires GAP-1 scanner patch."""
    return _meta(row).get("vpc_id") or None


def get_rds_subnet_ids(row: Dict[str, Any]) -> List[str]:
    """Get subnet IDs for an RDS instance. Requires GAP-1 scanner patch."""
    sids = _meta(row).get("subnet_ids")
    if isinstance(sids, list):
        return [s for s in sids if isinstance(s, str)]
    return []


def get_igw_vpc_ids(row: Dict[str, Any]) -> List[str]:
    """Get attached VPC IDs for an Internet Gateway."""
    vpcs = _meta(row).get("attached_vpcs")
    if isinstance(vpcs, list):
        return [v for v in vpcs if isinstance(v, str)]
    return []


def get_eip_instance_id(row: Dict[str, Any]) -> Optional[str]:
    """Get the EC2 instance ID associated with an EIP."""
    return _meta(row).get("instance_id") or None


def get_volume_attached_instance_id(row: Dict[str, Any]) -> Optional[str]:
    """Get the EC2 instance ID that an EBS volume is attached to."""
    return _meta(row).get("attached_to") or None


def get_name(row: Dict[str, Any]) -> str:
    """Get human-readable name, falling back to cloud_resource_id."""
    return (
        row.get("resource_name")
        or row.get("cloud_resource_id")
        or "(unnamed)"
    )


def get_cost(row: Dict[str, Any]) -> float:
    """Get resource cost, defaulting to 0."""
    try:
        return float(row.get("cost", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def get_status(row: Dict[str, Any]) -> str:
    """Get normalized status."""
    raw = row.get("status", "Unknown") or "Unknown"
    return raw.capitalize()


def is_waste(row: Dict[str, Any]) -> bool:
    """Check if a resource is considered waste (zombie, stopped, or has waste_type)."""
    status = get_status(row).lower()
    wt = row.get("waste_type")
    return status in ("zombie", "stopped", "waste") or bool(wt)


def get_vpc_cidr(row: Dict[str, Any]) -> str:
    """Get CIDR block for a VPC resource."""
    return _meta(row).get("cidr_block") or ""


def get_subnet_az(row: Dict[str, Any]) -> str:
    """Get availability zone for a subnet resource."""
    return _meta(row).get("availability_zone") or ""


def get_ec2_instance_type(row: Dict[str, Any]) -> str:
    """Get EC2 instance type."""
    return _meta(row).get("instance_type") or ""


def get_rds_engine(row: Dict[str, Any]) -> str:
    """Get RDS engine name."""
    return _meta(row).get("engine") or ""


def get_rds_instance_class(row: Dict[str, Any]) -> str:
    """Get RDS instance class."""
    return _meta(row).get("instance_class") or ""


def get_ebs_size_gb(row: Dict[str, Any]) -> int:
    """Get EBS volume size in GB."""
    try:
        return int(_meta(row).get("size_gb", 0) or 0)
    except (TypeError, ValueError):
        return 0


def get_ebs_volume_type(row: Dict[str, Any]) -> str:
    """Get EBS volume type."""
    return _meta(row).get("volume_type") or ""


def get_eip_public_ip(row: Dict[str, Any]) -> str:
    """Get EIP public IP address."""
    return _meta(row).get("public_ip") or ""


def get_sg_is_risky(row: Dict[str, Any]) -> bool:
    """Check if a security group is overly permissive."""
    return bool(_meta(row).get("is_overly_permissive"))
