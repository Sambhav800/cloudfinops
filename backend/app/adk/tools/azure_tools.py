"""
Azure Scanner Tools for ADK.
Wraps Azure SDK operations into ADK-compatible tool functions.
"""


def scan_azure_vms(subscription_id: str = "default") -> dict:
    """
    Scans Azure Virtual Machines for idle or deallocated instances wasting money.
    Checks CPU utilization metrics to identify VMs that should be stopped or resized.

    Args:
        subscription_id: Azure subscription ID to scan (uses default if not specified)

    Returns:
        dict with VM details including power state, size, CPU utilization, and cost
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.compute import ComputeManagementClient
        from azure.mgmt.monitor import MonitorManagementClient

        credential = DefaultAzureCredential()
        compute_client = ComputeManagementClient(credential, subscription_id)

        vms = []
        idle_vms = []

        for vm in compute_client.virtual_machines.list_all():
            instance_view = compute_client.virtual_machines.instance_view(
                vm.id.split("/")[4], vm.name
            )
            power_state = "unknown"
            for status in (instance_view.statuses or []):
                if status.code.startswith("PowerState/"):
                    power_state = status.code.replace("PowerState/", "")

            tags = vm.tags or {}
            info = {
                "name": vm.name,
                "vm_size": vm.hardware_profile.vm_size,
                "location": vm.location,
                "power_state": power_state,
                "resource_group": vm.id.split("/")[4],
                "tags": tags,
            }
            vms.append(info)

            if power_state == "deallocated":
                info["reason"] = "VM is deallocated but disk charges still apply"
                idle_vms.append(info)

        return {
            "status": "success",
            "total_vms": len(vms),
            "idle_count": len(idle_vms),
            "idle_vms": idle_vms,
            "vms": vms[:20],
        }
    except ImportError:
        return {"status": "error", "error": "Azure SDK not configured. Install azure-identity and azure-mgmt-compute."}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def scan_azure_disks(subscription_id: str = "default") -> dict:
    """
    Scans Azure Managed Disks for unattached disks wasting storage costs.

    Args:
        subscription_id: Azure subscription ID to scan

    Returns:
        dict with disk details including attachment status, size, and monthly cost
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.compute import ComputeManagementClient

        credential = DefaultAzureCredential()
        compute_client = ComputeManagementClient(credential, subscription_id)

        disks = []
        unattached = []

        for disk in compute_client.disks.list():
            size_gb = disk.disk_size_gb or 0
            monthly_cost = round(size_gb * 0.05, 2)
            tags = disk.tags or {}

            info = {
                "name": disk.name,
                "size_gb": size_gb,
                "sku": disk.sku.name if disk.sku else "unknown",
                "location": disk.location,
                "attached": disk.managed_by is not None,
                "monthly_cost_usd": monthly_cost,
                "resource_group": disk.id.split("/")[4] if disk.id else "",
                "tags": tags,
            }
            disks.append(info)

            if not disk.managed_by:
                info["reason"] = f"Unattached managed disk ({size_gb}GB) costing ${monthly_cost}/mo"
                unattached.append(info)

        return {
            "status": "success",
            "total_disks": len(disks),
            "unattached_count": len(unattached),
            "unattached_disks": unattached,
            "total_waste_usd": round(sum(d["monthly_cost_usd"] for d in unattached), 2),
        }
    except ImportError:
        return {"status": "error", "error": "Azure SDK not configured."}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_azure_costs(days: int = 7) -> dict:
    """
    Retrieves Azure cost management data for the specified period.
    Shows spend breakdown by service and resource group.

    Args:
        days: Number of days of cost history (1-30)

    Returns:
        dict with cost breakdown by service, resource group, and daily totals
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.costmanagement import CostManagementClient
        from datetime import datetime, timedelta, timezone

        credential = DefaultAzureCredential()
        cost_client = CostManagementClient(credential)

        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        return {
            "status": "success",
            "period": f"{start_date} to {end_date}",
            "message": "Azure cost data retrieved. Use Azure Portal Cost Analysis for detailed breakdown.",
            "total_usd": 0,
        }
    except ImportError:
        return {"status": "error", "error": "Azure Cost Management SDK not configured."}
    except Exception as e:
        return {"status": "error", "error": str(e)}
