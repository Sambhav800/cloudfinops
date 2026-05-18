from app.api.architecture_routes import _build_generic_proposed_result


def test_generic_gcp_proposed_result_is_derived_from_scanned_resources():
    resources = [
        {
            "cloud_resource_id": "gcp-vm-1",
            "resource_name": "prod-api-vm",
            "service_type": "GCP Compute Instance",
            "region": "us-central1-a",
            "cost": 480,
            "status": "Active",
        },
        {
            "cloud_resource_id": "gcp-db-1",
            "resource_name": "orders-db",
            "service_type": "Cloud SQL",
            "region": "us-central1-b",
            "cost": 320,
            "status": "Active",
        },
    ]

    result = _build_generic_proposed_result(
        provider="gcp",
        integration_id="int-1",
        region="us-central1",
        resources=resources,
        mode="cost_optimized",
    )

    assert result.change_list
    assert result.estimated_savings > 0
    assert "prod-api-vm" in result.proposed_mermaid
    assert "orders-db" in result.proposed_mermaid
    assert "GKE Autopilot Cluster" not in result.proposed_mermaid
    assert "Cloud Load Balancing" not in result.proposed_mermaid


def test_generic_azure_reliability_result_uses_real_resources_and_cost_delta():
    resources = [
        {
            "cloud_resource_id": "az-vm-1",
            "resource_name": "billing-vm-01",
            "service_type": "Azure Virtual Machine",
            "region": "eastus",
            "cost": 260,
            "status": "Active",
        },
        {
            "cloud_resource_id": "az-db-1",
            "resource_name": "billing-sql-01",
            "service_type": "Azure SQL Database",
            "region": "eastus",
            "cost": 190,
            "status": "Active",
        },
    ]

    result = _build_generic_proposed_result(
        provider="azure",
        integration_id="int-2",
        region="eastus",
        resources=resources,
        mode="reliability_security_optimized",
    )

    assert result.change_list
    assert result.estimated_savings <= 0
    assert any(change.monthly_savings <= 0 for change in result.change_list)
    assert "billing-vm-01" in result.proposed_mermaid
    assert "billing-sql-01" in result.proposed_mermaid
    assert "AKS Cluster" not in result.proposed_mermaid
    assert "Azure Front Door" not in result.proposed_mermaid


def test_generic_proposed_result_surfaces_cost_provenance_and_metadata_backed_reasoning():
    resources = [
        {
            "cloud_resource_id": "gcp-vm-2",
            "resource_name": "checkout-api-vm",
            "service_type": "GCP Compute Instance",
            "region": "us-central1-a",
            "cost": 410,
            "status": "Active",
            "metadata": {
                "machine_type": "e2-standard-4",
                "network": "prod-vpc",
                "public_ip": "34.11.22.33",
                "cost_source": "actual",
            },
        },
        {
            "cloud_resource_id": "gcp-db-2",
            "resource_name": "checkout-sql",
            "service_type": "Cloud SQL",
            "region": "us-central1-b",
            "cost": 240,
            "status": "Active",
            "metadata": {
                "tier": "db-custom-2-8192",
                "network": "prod-vpc",
                "cost_source": "estimated",
            },
        },
    ]

    result = _build_generic_proposed_result(
        provider="gcp",
        integration_id="int-4",
        region="us-central1",
        resources=resources,
        mode="reliability_security_optimized",
    )

    assert result.change_list
    assert any("e2-standard-4" in change.reasoning for change in result.change_list)
    assert any(warning["type"] == "estimated_cost_data" for warning in result.warnings)
    assert any(warning["type"] == "inferred_relationships" for warning in result.warnings)
    assert "checkout-api-vm" in result.proposed_mermaid
    assert "checkout-sql" in result.proposed_mermaid
    assert "cost basis" not in result.proposed_mermaid.lower()


def test_generic_proposed_result_returns_empty_state_when_region_has_no_resources():
    result = _build_generic_proposed_result(
        provider="azure",
        integration_id="int-3",
        region="westeurope",
        resources=[],
        mode="cost_optimized",
    )

    assert result.proposed_mermaid == ""
    assert result.change_list == []
    assert result.estimated_savings == 0
    assert result.warnings == [
        {
            "type": "no_resources_found",
            "message": "No AZURE resources found in region westeurope. Run a scan first.",
        }
    ]
