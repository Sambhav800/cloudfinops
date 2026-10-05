"""
API Intelligence Service — aggregates API Gateway/APIM/Endpoints data from scanned resources.
Provides ghost API detection, cache waste analysis, throttle optimization,
cost-per-request efficiency ranking, and shadow API identification across AWS, Azure, and GCP.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

_API_SERVICE_KEYWORDS = (
    "api gateway", "api management", "cloud endpoints",
    "gcp api gateway", "apigee",
)


def _nonnegative_metric(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _is_api_resource(resource: dict[str, Any]) -> bool:
    """True if resource is an API Gateway/APIM/Endpoint."""
    meta = resource.get("metadata") or {}
    if meta.get("is_api_resource"):
        return True
    service_type = str(resource.get("service_type") or "").lower()
    return any(k in service_type for k in _API_SERVICE_KEYWORDS)


def _detect_provider(resource: dict[str, Any]) -> str:
    provider = str(resource.get("provider") or "").lower()
    if provider in ("aws", "azure", "gcp"):
        return provider
    svc = str(resource.get("service_type") or "").lower()
    if "azure" in svc:
        return "azure"
    if "gcp" in svc or "google" in svc:
        return "gcp"
    return "aws"


def _build_fix_command(resource: dict[str, Any], provider: str) -> str:
    """Generate provider-specific CLI fix commands for ghost APIs."""
    meta = resource.get("metadata") or {}

    if provider == "aws":
        api_id = meta.get("api_id", "API_ID")
        stage_name = meta.get("stage_name", "STAGE")
        region = resource.get("region", "us-east-1")
        api_type = meta.get("api_type", "REST")
        if api_type == "REST":
            return (
                f"# Delete idle REST API stage:\n"
                f"aws apigateway delete-stage --rest-api-id {api_id} --stage-name {stage_name} --region {region}\n"
                f"# Or delete the entire API (if all stages are idle):\n"
                f"aws apigateway delete-rest-api --rest-api-id {api_id} --region {region}"
            )
        else:
            return (
                f"# Delete idle HTTP/WebSocket API stage:\n"
                f"aws apigatewayv2 delete-stage --api-id {api_id} --stage-name {stage_name} --region {region}\n"
                f"# Or delete the entire API:\n"
                f"aws apigatewayv2 delete-api --api-id {api_id} --region {region}"
            )
    elif provider == "gcp":
        api_name = meta.get("api_name", "API_NAME")
        region = resource.get("region", "us-central1")
        project = meta.get("project_id", "PROJECT_ID")
        return (
            f"# Delete idle GCP API Gateway:\n"
            f"gcloud api-gateway gateways delete {api_name} --location={region} --project={project}\n"
            f"# Or disable the API config:\n"
            f"gcloud api-gateway api-configs delete CONFIG_ID --api={api_name} --project={project}"
        )
    else:
        service_name = meta.get("service_name", "SERVICE_NAME")
        rg = meta.get("resource_group", "RESOURCE_GROUP")
        api_id = meta.get("api_id", "API_ID")
        return (
            f"# Delete idle Azure API Management API:\n"
            f"az apim api delete --resource-group {rg} --service-name {service_name} --api-id {api_id} --yes\n"
            f"# Or deallocate the entire APIM instance (if all APIs idle):\n"
            f"az apim delete --resource-group {rg} --name {service_name} --yes"
        )


class ApiIntelligenceService:
    """
    Multi-cloud API Intelligence service for scanned resources.
    Works on resources already saved to MongoDB.
    """

    def get_api_summary(
        self,
        resources: list[dict[str, Any]],
        integration_id: str | None = None,
    ) -> dict[str, Any]:
        """Full API intelligence report."""
        api_resources = [r for r in resources if _is_api_resource(r)]

        if not api_resources:
            return {
                "api_resources": [],
                "ghost_apis": [],
                "cache_waste": [],
                "throttle_issues": [],
                "shadow_apis": [],
                "cost_per_request_ranking": [],
                "total_api_count": 0,
                "total_api_spend": 0.0,
                "total_api_waste": 0.0,
                "ghost_api_count": 0,
                "cache_waste_monthly": 0.0,
                "providers_detected": [],
                "ai_narrative": "No API resources detected in this integration.",
            }

        ghost_apis = self.get_ghost_apis(api_resources)
        cache_waste = self.get_cache_waste(api_resources)
        throttle_issues = self.get_throttle_analysis(api_resources)
        shadow_apis = self.get_shadow_apis(resources, api_resources)
        cost_ranking = self.get_api_cost_per_request(api_resources)

        total_spend = round(sum(float(r.get("cost") or 0) for r in api_resources), 2)
        ghost_cost = round(sum(float(g["monthly_cost"]) for g in ghost_apis), 2)
        cache_waste_cost = round(sum(float(c.get("wasted_monthly", 0)) for c in cache_waste), 2)
        providers = list(set(_detect_provider(r) for r in api_resources))

        enriched = []
        for r in api_resources:
            meta = r.get("metadata") or {}
            provider = _detect_provider(r)
            enriched.append({
                "id": r.get("id") or r.get("cloud_resource_id"),
                "name": r.get("resource_name", "Unknown"),
                "api_type": meta.get("api_type", "REST"),
                "stage_name": meta.get("stage_name", ""),
                "endpoint_type": meta.get("endpoint_type", ""),
                "invocations_7d": _nonnegative_metric(meta.get("invocations_7d")),
                "error_rate_4xx": _nonnegative_metric(meta.get("error_rate_4xx")),
                "error_rate_5xx": _nonnegative_metric(meta.get("error_rate_5xx")),
                "latency_p99_ms": _nonnegative_metric(meta.get("latency_p99_ms")),
                "cache_enabled": meta.get("cache_enabled", False),
                "cache_hit_rate": meta.get("cache_hit_rate"),
                "monthly_cost": float(r.get("cost") or 0),
                "status": r.get("status", "Active"),
                "provider": provider,
                "region": r.get("region", ""),
                "is_ghost": any(g["resource_id"] == (r.get("id") or r.get("cloud_resource_id")) for g in ghost_apis),
            })

        narrative = self._build_narrative(
            api_count=len(api_resources),
            ghost_count=len(ghost_apis),
            total_spend=total_spend,
            ghost_cost=ghost_cost,
            cache_waste_cost=cache_waste_cost,
            shadow_count=len(shadow_apis),
            providers=providers,
        )

        return {
            "api_resources": enriched,
            "ghost_apis": ghost_apis,
            "cache_waste": cache_waste,
            "throttle_issues": throttle_issues,
            "shadow_apis": shadow_apis,
            "cost_per_request_ranking": cost_ranking[:20],
            "total_api_count": len(api_resources),
            "total_api_spend": total_spend,
            "total_api_waste": ghost_cost + cache_waste_cost,
            "ghost_api_count": len(ghost_apis),
            "cache_waste_monthly": cache_waste_cost,
            "providers_detected": providers,
            "ai_narrative": narrative,
        }

    def get_ghost_apis(self, api_resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """APIs with 0 invocations for 7+ days."""
        ghosts = []
        for r in api_resources:
            meta = r.get("metadata") or {}
            invocations = _nonnegative_metric(meta.get("invocations_7d"))
            if invocations is None:
                continue
            monthly_cost = float(r.get("cost") or 0)
            provider = _detect_provider(r)

            is_ghost = (
                invocations == 0
                or (invocations < 10 and monthly_cost > 50)
            )

            if is_ghost:
                resource_id = r.get("id") or r.get("cloud_resource_id") or ""
                ghosts.append({
                    "resource_id": resource_id,
                    "name": r.get("resource_name", "Unknown"),
                    "api_type": meta.get("api_type", "REST"),
                    "stage_name": meta.get("stage_name", ""),
                    "provider": provider,
                    "monthly_cost": monthly_cost,
                    "annual_cost": round(monthly_cost * 12, 2),
                    "invocations_7d": invocations,
                    "ghost_reason": (
                        "Zero invocations in 7 days — API is completely idle."
                        if invocations == 0
                        else f"Only {invocations} invocations in 7 days — near-zero traffic."
                    ),
                    "fix_command": _build_fix_command(r, provider),
                })

        ghosts.sort(key=lambda x: x["monthly_cost"], reverse=True)
        return ghosts

    def get_cache_waste(self, api_resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """APIs with cache enabled but low hit rate."""
        waste = []
        for r in api_resources:
            meta = r.get("metadata") or {}
            cache_enabled = meta.get("cache_enabled", False)
            if not cache_enabled:
                continue

            hit_rate = meta.get("cache_hit_rate")
            if hit_rate is None:
                continue

            cache_size = meta.get("cache_size_gb", 0.5)
            # AWS API Gateway cache pricing: ~$0.02/hr per 0.5GB
            cache_hourly_cost = (cache_size / 0.5) * 0.02
            cache_monthly_cost = round(cache_hourly_cost * 730, 2)

            if hit_rate < 5.0:
                wasted = cache_monthly_cost
                waste.append({
                    "resource_id": r.get("id") or r.get("cloud_resource_id") or "",
                    "name": r.get("resource_name", "Unknown"),
                    "stage_name": meta.get("stage_name", ""),
                    "provider": _detect_provider(r),
                    "cache_hit_rate": round(hit_rate, 2),
                    "cache_size_gb": cache_size,
                    "cache_monthly_cost": cache_monthly_cost,
                    "wasted_monthly": wasted,
                    "recommendation": (
                        "Disable API cache — hit rate is below 5%. "
                        f"You're paying ${cache_monthly_cost:.0f}/mo for a cache that's almost never used."
                    ),
                })

        waste.sort(key=lambda x: x["wasted_monthly"], reverse=True)
        return waste

    def get_throttle_analysis(self, api_resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """APIs with misconfigured throttle limits."""
        issues = []
        for r in api_resources:
            meta = r.get("metadata") or {}
            burst_limit = meta.get("throttle_burst_limit")
            rate_limit = meta.get("throttle_rate_limit")
            invocations_7d = _nonnegative_metric(meta.get("invocations_7d"))

            if burst_limit is None or rate_limit is None or invocations_7d is None:
                continue

            avg_daily = invocations_7d / 7 if invocations_7d > 0 else 0
            avg_per_second = avg_daily / 86400
            error_rate_4xx = _nonnegative_metric(meta.get("error_rate_4xx"))

            # Over-provisioned: burst limit is 100x+ actual traffic
            if burst_limit > 100 and avg_per_second > 0 and burst_limit > avg_per_second * 100:
                issues.append({
                    "resource_id": r.get("id") or r.get("cloud_resource_id") or "",
                    "name": r.get("resource_name", "Unknown"),
                    "issue": "over_provisioned",
                    "burst_limit": burst_limit,
                    "rate_limit": rate_limit,
                    "actual_avg_rps": round(avg_per_second, 4),
                    "recommendation": (
                        f"Burst limit ({burst_limit}) is {int(burst_limit / max(avg_per_second, 0.001))}x "
                        f"your actual traffic ({avg_per_second:.2f} req/s). "
                        "Consider reducing to prevent accidental cost spikes from abuse or bugs."
                    ),
                })
            # Under-provisioned: getting throttled (check 429s via error rates)
            elif error_rate_4xx is not None and error_rate_4xx > 10:
                issues.append({
                    "resource_id": r.get("id") or r.get("cloud_resource_id") or "",
                    "name": r.get("resource_name", "Unknown"),
                    "issue": "under_provisioned",
                    "burst_limit": burst_limit,
                    "rate_limit": rate_limit,
                    "error_rate_4xx": meta.get("error_rate_4xx", 0),
                    "recommendation": (
                        f"High 4xx error rate ({meta.get('error_rate_4xx', 0):.1f}%) suggests throttling. "
                        "Increase burst/rate limits or investigate client retry storms."
                    ),
                })

        return issues

    def get_api_cost_per_request(self, api_resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Cost efficiency ranking — most expensive per request first."""
        ranking = []
        for r in api_resources:
            meta = r.get("metadata") or {}
            monthly_cost = float(r.get("cost") or 0)
            invocations_7d = _nonnegative_metric(meta.get("invocations_7d"))

            if invocations_7d is None or invocations_7d <= 0 or monthly_cost <= 0:
                continue

            monthly_invocations = (invocations_7d / 7) * 30
            cost_per_request = monthly_cost / monthly_invocations if monthly_invocations > 0 else 0

            ranking.append({
                "resource_id": r.get("id") or r.get("cloud_resource_id") or "",
                "name": r.get("resource_name", "Unknown"),
                "provider": _detect_provider(r),
                "monthly_cost": monthly_cost,
                "monthly_invocations": round(monthly_invocations),
                "cost_per_1k_requests": round(cost_per_request * 1000, 4),
                "invocations_7d": invocations_7d,
            })

        ranking.sort(key=lambda x: x["cost_per_1k_requests"], reverse=True)
        return ranking

    def get_shadow_apis(
        self,
        all_resources: list[dict[str, Any]],
        api_resources: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Resources serving HTTP that are NOT behind any gateway (compliance risk)."""
        gateway_api_ids = set()
        for r in api_resources:
            meta = r.get("metadata") or {}
            gateway_api_ids.add(meta.get("api_id", ""))
            gateway_api_ids.add(r.get("resource_name", ""))

        shadow = []
        for r in all_resources:
            if _is_api_resource(r):
                continue
            meta = r.get("metadata") or {}
            service_type = str(r.get("service_type") or "").lower()

            # Lambda with function URL, Cloud Run with public URL, App Service
            has_public_url = (
                meta.get("function_url")
                or meta.get("url")
                or ("cloud run" in service_type and meta.get("ingress") == "all")
                or ("lambda" in service_type and meta.get("function_url_enabled"))
                or ("app service" in service_type)
            )

            if has_public_url:
                name = r.get("resource_name", "")
                if name not in gateway_api_ids:
                    shadow.append({
                        "resource_id": r.get("id") or r.get("cloud_resource_id") or "",
                        "name": name,
                        "service_type": r.get("service_type", ""),
                        "provider": _detect_provider(r),
                        "url": meta.get("url") or meta.get("function_url") or "",
                        "risk": "compliance",
                        "reason": (
                            "This resource has a public HTTP endpoint but is NOT behind "
                            "any API Gateway. Traffic bypasses rate limiting, auth, and logging."
                        ),
                    })

        return shadow[:20]

    def _build_narrative(
        self,
        api_count: int,
        ghost_count: int,
        total_spend: float,
        ghost_cost: float,
        cache_waste_cost: float,
        shadow_count: int,
        providers: list[str],
    ) -> str:
        provider_str = ", ".join(p.upper() for p in sorted(providers))
        parts = [
            f"You have {api_count} API resource{'s' if api_count != 1 else ''} "
            f"across {provider_str or 'your cloud'} costing ${total_spend:,.0f}/month."
        ]
        if ghost_count:
            parts.append(
                f"{ghost_count} API{'s' if ghost_count != 1 else ''} "
                f"{'are' if ghost_count != 1 else 'is'} idle (ghost), "
                f"wasting ${ghost_cost:,.0f}/month (${ghost_cost * 12:,.0f}/year)."
            )
        if cache_waste_cost > 0:
            parts.append(
                f"Cache waste: ${cache_waste_cost:,.0f}/month on caches with <5% hit rate."
            )
        if shadow_count:
            parts.append(
                f"{shadow_count} resource{'s' if shadow_count != 1 else ''} "
                f"serving HTTP without a gateway (shadow APIs — compliance risk)."
            )
        return " ".join(parts)
