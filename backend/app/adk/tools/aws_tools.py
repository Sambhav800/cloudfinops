"""
AWS Scanner Tools for ADK.
Wraps existing Boto3-based scanning into ADK-compatible tool functions.
"""
import json
import asyncio
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig


def _get_boto_client(service: str, region: str = "us-east-1"):
    """Get a boto3 client using environment credentials or default profile."""
    return boto3.client(
        service,
        region_name=region,
        config=BotoConfig(retries={"max_attempts": 2, "mode": "adaptive"}),
    )


def scan_aws_ec2(region: str = "us-east-1") -> dict:
    """
    Scans AWS EC2 instances in the specified region using Boto3.
    Identifies running, stopped, and zombie instances with their costs and tags.

    Args:
        region: AWS region to scan (e.g., "us-east-1", "us-west-2", "eu-west-1")

    Returns:
        dict with instance details including state, type, launch time, and tags
    """
    try:
        ec2 = _get_boto_client("ec2", region)
        response = ec2.describe_instances()

        instances = []
        zombies = []

        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                state = instance["State"]["Name"]
                instance_id = instance["InstanceId"]
                instance_type = instance.get("InstanceType", "unknown")
                launch_time = str(instance.get("LaunchTime", ""))
                tags = {
                    t["Key"]: t["Value"]
                    for t in instance.get("Tags", [])
                }

                info = {
                    "instance_id": instance_id,
                    "instance_type": instance_type,
                    "state": state,
                    "region": region,
                    "launch_time": launch_time,
                    "tags": tags,
                    "name": tags.get("Name", instance_id),
                }
                instances.append(info)

                if state == "stopped":
                    info["reason"] = "Instance is stopped but not terminated — incurring EBS charges"
                    zombies.append(info)

        return {
            "status": "success",
            "region": region,
            "total_instances": len(instances),
            "running": len([i for i in instances if i["state"] == "running"]),
            "stopped": len([i for i in instances if i["state"] == "stopped"]),
            "zombies_found": len(zombies),
            "zombies": zombies,
            "instances": instances[:20],
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "region": region}


def scan_aws_ebs_volumes(region: str = "us-east-1") -> dict:
    """
    Scans AWS EBS volumes for orphaned/unattached volumes that are wasting money.
    Unattached volumes still incur storage charges without providing value.

    Args:
        region: AWS region to scan (e.g., "us-east-1")

    Returns:
        dict with volume details including attachment status, size, and cost estimate
    """
    try:
        ec2 = _get_boto_client("ec2", region)
        response = ec2.describe_volumes()

        volumes = []
        unattached = []

        for vol in response.get("Volumes", []):
            volume_id = vol["VolumeId"]
            size_gb = vol.get("Size", 0)
            vol_type = vol.get("VolumeType", "gp3")
            state = vol.get("State", "unknown")
            attachments = vol.get("Attachments", [])
            tags = {t["Key"]: t["Value"] for t in vol.get("Tags", [])}

            cost_per_gb = {"gp3": 0.08, "gp2": 0.10, "io1": 0.125, "st1": 0.045, "sc1": 0.015}.get(vol_type, 0.08)
            monthly_cost = round(size_gb * cost_per_gb, 2)

            info = {
                "volume_id": volume_id,
                "size_gb": size_gb,
                "volume_type": vol_type,
                "state": state,
                "attached": len(attachments) > 0,
                "monthly_cost_usd": monthly_cost,
                "region": region,
                "tags": tags,
            }
            volumes.append(info)

            if not attachments and state == "available":
                info["reason"] = f"Unattached {vol_type} volume ({size_gb}GB) costing ${monthly_cost}/mo"
                unattached.append(info)

        return {
            "status": "success",
            "region": region,
            "total_volumes": len(volumes),
            "unattached_count": len(unattached),
            "unattached_volumes": unattached,
            "total_waste_usd": round(sum(v["monthly_cost_usd"] for v in unattached), 2),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "region": region}


def get_aws_cost_breakdown(days: int = 7) -> dict:
    """
    Retrieves AWS Cost Explorer data showing daily spend and cost breakdown by service.
    Identifies cost spikes and top spending services.

    Args:
        days: Number of days of cost history to retrieve (1-30)

    Returns:
        dict with daily costs, top services, total spend, and spike detection
    """
    from datetime import datetime, timedelta, timezone

    try:
        ce = _get_boto_client("ce", "us-east-1")
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        response = ce.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        daily_totals = []
        service_totals: dict = {}

        for result in response.get("ResultsByTime", []):
            day_total = 0.0
            for group in result.get("Groups", []):
                service = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                service_totals[service] = service_totals.get(service, 0) + amount
                day_total += amount
            daily_totals.append({
                "date": result["TimePeriod"]["Start"],
                "total_usd": round(day_total, 2),
            })

        top_services = sorted(service_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        total = round(sum(d["total_usd"] for d in daily_totals), 2)

        avg_daily = total / max(len(daily_totals), 1)
        spike_detected = any(d["total_usd"] > avg_daily * 1.5 for d in daily_totals[-3:])

        return {
            "status": "success",
            "period": f"{start_date} to {end_date}",
            "total_usd": total,
            "avg_daily_usd": round(avg_daily, 2),
            "spike_detected": spike_detected,
            "top_services": [{"service": s, "total_usd": round(a, 2)} for s, a in top_services],
            "daily_costs": daily_totals[-7:],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
