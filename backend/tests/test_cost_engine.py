import asyncio

import pytest

from app.core.cost_engine import CostMapper


@pytest.fixture(autouse=True)
def disable_infracost(monkeypatch):
    async def _no_price(*args, **kwargs):
        return None

    monkeypatch.setattr("app.core.cost_engine.price_service.get_infracost_price", _no_price)


def test_aws_instance_pricing_falls_back_to_known_reference_rates():
    mapper = CostMapper()
    plan = {
        "resource_changes": [
            {
                "type": "aws_instance",
                "address": "aws_instance.web",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "instance_type": "t3.large",
                        "root_block_device": [
                            {"volume_size": 100, "volume_type": "gp3"},
                        ],
                    },
                },
            }
        ]
    }

    result = asyncio.run(mapper.estimate_monthly_cost(plan))

    assert result["delta_monthly_cost"] == 68.74
    assert result["resources"][0]["after"] == 68.74
    assert result["resources"][0]["pricing_source"] == "heuristic_estimate"


def test_aws_eip_pricing_falls_back_to_network_baseline():
    mapper = CostMapper()
    plan = {
        "resource_changes": [
            {
                "type": "aws_eip",
                "address": "aws_eip.static",
                "change": {
                    "actions": ["create"],
                    "after": {},
                },
            }
        ]
    }

    result = asyncio.run(mapper.estimate_monthly_cost(plan))

    assert result["delta_monthly_cost"] == 3.65
    assert result["resources"][0]["pricing_source"] == "heuristic_estimate"


def test_rds_multi_az_pricing_uses_database_and_storage_heuristics():
    mapper = CostMapper()
    plan = {
        "resource_changes": [
            {
                "type": "aws_db_instance",
                "address": "aws_db_instance.db",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "instance_class": "db.t3.medium",
                        "multi_az": True,
                        "allocated_storage": 100,
                        "storage_type": "gp2",
                    },
                },
            }
        ]
    }

    result = asyncio.run(mapper.estimate_monthly_cost(plan))

    assert result["delta_monthly_cost"] == 110.78
    assert result["resources"][0]["resource_family"] == "database"


def test_ebs_io1_pricing_uses_volume_and_iops_heuristics():
    mapper = CostMapper()
    plan = {
        "resource_changes": [
            {
                "type": "aws_ebs_volume",
                "address": "aws_ebs_volume.data",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "type": "io1",
                        "size": 100,
                        "iops": 1000,
                    },
                },
            }
        ]
    }

    result = asyncio.run(mapper.estimate_monthly_cost(plan))

    assert result["delta_monthly_cost"] == 77.50
    assert result["resources"][0]["notes"]


def test_update_action_diff_uses_before_and_after_estimates():
    mapper = CostMapper()
    plan = {
        "resource_changes": [
            {
                "type": "aws_instance",
                "address": "aws_instance.web",
                "change": {
                    "actions": ["update"],
                    "before": {"instance_type": "t3.micro"},
                    "after": {"instance_type": "t3.medium"},
                },
            }
        ]
    }

    result = asyncio.run(mapper.estimate_monthly_cost(plan))

    assert result["delta_monthly_cost"] == 22.78
    assert result["resources"][0]["before"] == 7.59
    assert result["resources"][0]["after"] == 30.37


def test_azure_vm_resource_stays_visible_with_heuristic_cost():
    mapper = CostMapper()
    plan = {
        "resource_changes": [
            {
                "type": "azurerm_linux_virtual_machine",
                "address": "azurerm_linux_virtual_machine.web",
                "provider_name": "registry.terraform.io/hashicorp/azurerm",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "vm_size": "Standard_B2s",
                        "os_disk": [{"disk_size_gb": 64, "storage_account_type": "Premium_LRS"}],
                        "location": "eastus",
                    },
                },
            }
        ]
    }

    result = asyncio.run(mapper.estimate_monthly_cost(plan))

    assert result["resources"][0]["provider"] == "azure"
    assert result["resources"][0]["after"] == 30.37
    assert result["resources"][0]["pricing_source"] == "heuristic_estimate"


def test_gcp_compute_resource_uses_machine_and_disk_reference_tables():
    mapper = CostMapper()
    plan = {
        "resource_changes": [
            {
                "type": "google_compute_instance",
                "address": "google_compute_instance.api",
                "provider_name": "registry.terraform.io/hashicorp/google",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "machine_type": "e2-standard-4",
                        "zone": "us-central1-a",
                        "boot_disk": [
                            {
                                "initialize_params": [
                                    {"size": 100, "type": "pd-ssd"},
                                ]
                            }
                        ],
                    },
                },
            }
        ]
    }

    result = asyncio.run(mapper.estimate_monthly_cost(plan))

    assert result["resources"][0]["provider"] == "gcp"
    assert result["resources"][0]["region"] == "us-central1"
    assert result["resources"][0]["after"] == 114.89


def test_usage_based_resources_stay_visible_instead_of_disappearing():
    mapper = CostMapper()
    plan = {
        "resource_changes": [
            {
                "type": "aws_lambda_function",
                "address": "aws_lambda_function.handler",
                "change": {
                    "actions": ["create"],
                    "after": {},
                },
            }
        ]
    }

    result = asyncio.run(mapper.estimate_monthly_cost(plan))

    assert result["delta_monthly_cost"] == 0.0
    assert len(result["resources"]) == 1
    assert result["resources"][0]["pricing_source"] == "usage_based"
    assert "usage-based" in result["resources"][0]["notes"].lower()


def test_unsupported_resources_are_reported_as_unestimated():
    mapper = CostMapper()
    plan = {
        "resource_changes": [
            {
                "type": "aws_new_unmodeled_service",
                "address": "aws_new_unmodeled_service.preview",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["create"],
                    "after": {},
                },
            }
        ]
    }

    result = asyncio.run(mapper.estimate_monthly_cost(plan))

    assert result["delta_monthly_cost"] == 0.0
    assert result["resources"] == []
    assert result["summary"]["total_resources"] == 1
    assert result["summary"]["priced_resources"] == 0
    assert result["summary"]["unsupported_resources"] == 1
    assert result["summary"]["unestimated_resources"] == 1
    assert result["unestimated_resources"][0]["resource_type"] == "aws_new_unmodeled_service"
    assert result["unestimated_resources"][0]["pricing_source"] == "unsupported"
    assert result["unestimated_resources"][0]["reason"]


def test_empty_plan_returns_zero_summary_without_errors():
    mapper = CostMapper()

    result = asyncio.run(mapper.estimate_monthly_cost({"resource_changes": []}))

    assert result["delta_monthly_cost"] == 0.0
    assert result["resources"] == []
    assert result["summary"] == {
        "total_resources": 0,
        "priced_resources": 0,
        "exact_pricing_resources": 0,
        "estimated_resources": 0,
        "usage_based_resources": 0,
        "unsupported_resources": 0,
        "unestimated_resources": 0,
    }
    assert result["unestimated_resources"] == []
    assert result["findings"] == []


def _plan_with_resource(resource_type, attributes, provider_name=""):
    return {
        "resource_changes": [
            {
                "type": resource_type,
                "address": f"{resource_type}.example",
                "provider_name": provider_name,
                "change": {
                    "actions": ["create"],
                    "after": attributes,
                },
            }
        ]
    }


@pytest.mark.parametrize(
    ("resource_type", "attributes", "provider_name"),
    [
        ("aws_ebs_volume", {"type": "gp3", "size": 100}, "registry.terraform.io/hashicorp/aws"),
        (
            "aws_autoscaling_group",
            {"desired_capacity": 2, "launch_template": [{"instance_type": "t3.micro"}]},
            "registry.terraform.io/hashicorp/aws",
        ),
        (
            "aws_eks_node_group",
            {"instance_types": ["t3.small"], "scaling_config": [{"desired_size": 2}]},
            "registry.terraform.io/hashicorp/aws",
        ),
        ("aws_lb", {"load_balancer_type": "application"}, "registry.terraform.io/hashicorp/aws"),
        ("aws_nat_gateway", {}, "registry.terraform.io/hashicorp/aws"),
        ("aws_rds_cluster", {"instance_class": "db.t3.medium", "allocated_storage": 20}, "registry.terraform.io/hashicorp/aws"),
        ("aws_elasticache_cluster", {"node_type": "cache.t3.micro", "num_cache_nodes": 2}, "registry.terraform.io/hashicorp/aws"),
        ("azurerm_linux_virtual_machine", {"vm_size": "Standard_B2s", "location": "eastus"}, "registry.terraform.io/hashicorp/azurerm"),
        ("azurerm_windows_virtual_machine", {"vm_size": "Standard_D2s_v3", "location": "eastus"}, "registry.terraform.io/hashicorp/azurerm"),
        ("azurerm_managed_disk", {"storage_account_type": "StandardSSD_LRS", "disk_size_gb": 64}, "registry.terraform.io/hashicorp/azurerm"),
        ("azurerm_public_ip", {"allocation_method": "Static"}, "registry.terraform.io/hashicorp/azurerm"),
        ("azurerm_lb", {"sku": "Standard"}, "registry.terraform.io/hashicorp/azurerm"),
        ("azurerm_application_gateway", {"sku": [{"name": "Standard_v2"}]}, "registry.terraform.io/hashicorp/azurerm"),
        ("azurerm_app_service_plan", {"sku_name": "B1"}, "registry.terraform.io/hashicorp/azurerm"),
        (
            "azurerm_kubernetes_cluster",
            {"default_node_pool": [{"node_count": 2, "vm_size": "Standard_B2s"}]},
            "registry.terraform.io/hashicorp/azurerm",
        ),
        ("azurerm_mssql_database", {"sku_name": "S1"}, "registry.terraform.io/hashicorp/azurerm"),
        ("google_compute_instance", {"machine_type": "e2-small", "zone": "us-central1-a"}, "registry.terraform.io/hashicorp/google"),
        ("google_compute_disk", {"type": "pd-standard", "size": 50, "zone": "us-central1-a"}, "registry.terraform.io/hashicorp/google"),
        ("google_compute_address", {"address_type": "EXTERNAL", "region": "us-central1"}, "registry.terraform.io/hashicorp/google"),
        (
            "google_container_cluster",
            {"node_config": [{"machine_type": "e2-small"}], "node_count": 2, "location": "us-central1"},
            "registry.terraform.io/hashicorp/google",
        ),
        (
            "google_sql_database_instance",
            {"settings": [{"tier": "db-n1-standard-1"}], "region": "us-central1"},
            "registry.terraform.io/hashicorp/google",
        ),
    ],
)
def test_expanded_resource_types_remain_visible_with_pricing_labels(resource_type, attributes, provider_name):
    mapper = CostMapper()

    result = asyncio.run(mapper.estimate_monthly_cost(_plan_with_resource(resource_type, attributes, provider_name)))

    assert result["resources"], f"{resource_type} should stay visible"
    assert result["unestimated_resources"] == []
    assert result["resources"][0]["pricing_source"] in {
        "exact_api",
        "heuristic_estimate",
        "usage_based",
    }
    assert result["resources"][0]["resource_family"]


def test_aws_ebs_volume_catalog_mapping_can_return_exact_api(monkeypatch):
    async def _catalog_price(*args, **kwargs):
        return 0.01

    monkeypatch.setattr("app.core.cost_engine.price_service.get_infracost_price", _catalog_price)
    mapper = CostMapper()

    result = asyncio.run(
        mapper.estimate_monthly_cost(
            _plan_with_resource(
                "aws_ebs_volume",
                {"type": "gp3", "size": 100},
                "registry.terraform.io/hashicorp/aws",
            )
        )
    )

    assert result["resources"][0]["pricing_source"] == "exact_api"
    assert result["resources"][0]["after"] == 1.0


def test_gp2_ebs_volume_generates_best_practice_finding_without_unverified_impact():
    mapper = CostMapper()

    result = asyncio.run(
        mapper.estimate_monthly_cost(
            _plan_with_resource(
                "aws_ebs_volume",
                {"type": "gp2", "size": 100},
                "registry.terraform.io/hashicorp/aws",
            )
        )
    )

    finding = result["findings"][0]
    assert finding["finding_id"] == "ebs-gp2-to-gp3"
    assert finding["monthly_impact"] is None
    assert finding["confidence"] == "medium"


def test_previous_generation_ec2_generates_best_practice_finding():
    mapper = CostMapper()

    result = asyncio.run(
        mapper.estimate_monthly_cost(
            _plan_with_resource(
                "aws_instance",
                {"instance_type": "t2.medium"},
                "registry.terraform.io/hashicorp/aws",
            )
        )
    )

    assert any(finding["finding_id"] == "ec2-old-generation" for finding in result["findings"])


def test_public_ip_generates_best_practice_finding():
    mapper = CostMapper()

    result = asyncio.run(
        mapper.estimate_monthly_cost(
            _plan_with_resource("aws_eip", {}, "registry.terraform.io/hashicorp/aws")
        )
    )

    assert any(finding["finding_id"] == "public-ipv4-cost" for finding in result["findings"])


def test_nat_gateway_generates_best_practice_finding():
    mapper = CostMapper()

    result = asyncio.run(
        mapper.estimate_monthly_cost(
            _plan_with_resource("aws_nat_gateway", {}, "registry.terraform.io/hashicorp/aws")
        )
    )

    assert any(finding["finding_id"] == "nat-gateway-baseline" for finding in result["findings"])
