from app.api.architecture_routes import _collect_target_regions, _resource_in_region


def test_resource_in_region_matches_gcp_zone_to_region():
    resource = {
        "region": "us-central1-a",
        "service_type": "GCP Compute Instance",
        "provider": "gcp",
    }

    assert _resource_in_region(resource, "us-central1", "gcp") is True


def test_collect_target_regions_prefers_discovered_regions_for_gcp():
    resources = [
        {"region": "us-east1-b", "service_type": "GCP Compute Instance"},
        {"region": "us-central1-a", "service_type": "GCP Compute Instance"},
    ]
    integration = {"regions": ["us-central1"]}  # static default from setup

    regions = _collect_target_regions(resources, integration, "gcp", requested_region=None)

    assert "us-east1-b" in regions
    assert "us-central1-a" in regions
