import {
    type BackendGovernanceAgentNotification,
    getBackendGovernanceAnalysis,
    getBackendGovernancePolicies,
    getBackendReports,
    getBackendIntegrations,
    getBackendNotifications,
    getBackendResources,
    type BackendGovernancePolicyViolation,
    getBackendSpendHistory,
    getBackendStats,
    type BackendGovernanceSecurityResource,
    getBackendSecurityPosture,
    type BackendSecurityBreakdownItem,
    type BackendSecurityExposedResource,
    type BackendSecurityFinding,
    type BackendSecurityPostureResponse,
    type BackendSecurityPostureRating,
    getBackendWasteDistribution,
    type BackendGovernanceAnalysisResponse,
    type BackendGovernancePolicyRecord,
    type BackendNotificationRecord,
    type BackendReportRecord,
    getDashboardSummary,
    type DashboardSummaryResponse,
} from "@/lib/api";
import {
    normalizeResourceRows,
    toDisplayInrAmount,
    type CostStatus,
    type NormalizedStatus,
    type Provider,
    type ResourceRow,
} from "@/lib/resources/contract";

type MetadataRecord = Record<string, unknown>;
type DashboardStatsRow = {
    integration_id?: string;
    total_spend?: number;
    potential_savings?: number;
    active_resources_count?: number;
    ai_confidence_score?: number;
    carbon_footprint_kg?: number;
    cost_of_inaction_6mo?: number;
};
type DailySpendRow = { spend_date: string; amount: number };
type IntegrationLookupRow = {
    id: string;
    provider: string;
    status?: string;
};
type NotificationRow = {
    id: string;
    recommendation: string;
    metadata?: MetadataRecord;
    created_at: string;
    status: string;
    type: string;
    resource_id: string;
    action?: string;
};
type ArchitectureIntegration = {
    id: string;
    provider: string;
    name: string | null;
    regions?: string[] | null;
    last_scan?: string | null;
    created_at?: string | null;
};

export interface CloudResource {
    id: string;
    user_id: string;
    integration_id: string;
    provider: Provider;
    cloud_resource_id: string | null;
    resource_name: string;
    service_type: string;
    resource_type: string;
    region: string;
    monthly_cost: number;
    cost: number;
    monthly_cost_available: boolean;
    cost_source: string;
    cost_status: CostStatus;
    cost_label: string;
    annual_cost_label: string;
    utilization: number;
    status: NormalizedStatus;
    waste_type: string | null;
    waste_reason: string | null;
    confidence_score: number;
    created_by: string;
    region_compliance: string;
    cpu_utilization: number;
    memory_utilization: number;
    storage_utilization: number;
    carbon_footprint_kg: number;
    tags: MetadataRecord;
    metadata: MetadataRecord;
    metrics_data: MetadataRecord;
    governance_violations: unknown[];
    last_scanned_at: string | null;
    created_at?: string | null;
}

export interface ActionItem {
    id: string;
    title: string;
    description: string;
    resource_name: string;
    resource_type: string;
    action_type: string;
    estimated_savings: number;
    risk_level: string;
    status: 'pending' | 'approved' | 'rejected' | 'completed';
    created_at: string;
    provider?: string;
    resource_id?: string;
    metadata: Record<string, unknown>;
}

export interface ReportItem {
    id: string;
    title: string;
    report_type: string;
    summary: string;
    period_start: string;
    period_end: string;
    status: string;
    created_at: string;
    file_size: string;
    data: Record<string, unknown>;
}

export interface AlertItem {
    id: string;
    title: string;
    message: string;
    severity: string;
    alert_type: string;
    is_read: boolean;
    created_at: string;
}

export interface GovernancePolicyItem {
    id: string;
    name: string;
    description: string;
    policy_type: string;
    is_active: boolean;
    compliance_rate: number;
    violations: number;
    created_at: string;
}

const WASTE_STATUSES = new Set<NormalizedStatus>(["zombie", "waste"]);

function isWasteStatus(status: NormalizedStatus): boolean {
    return WASTE_STATUSES.has(status);
}

function toMetricNumber(value: unknown): number {
    const parsed = typeof value === "number"
        ? value
        : typeof value === "string"
            ? Number(value)
            : 0;

    return Number.isFinite(parsed) ? parsed : 0;
}

function sourceCurrencyForProvider(provider: string): string {
    const normalized = provider.trim().toLowerCase();
    return normalized === "aws" || normalized === "azure" ? "USD" : "INR";
}

function toProviderDisplayAmount(value: unknown, provider: string): number {
    return toDisplayInrAmount(toMetricNumber(value), sourceCurrencyForProvider(provider));
}

function normalizePendingActionRiskLevel(value: unknown): string {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "critical") {
        return "high";
    }
    if (normalized === "high" || normalized === "medium" || normalized === "low") {
        return normalized;
    }
    return "low";
}

function normalizePendingActionType(rawActionType: unknown, rawActionLabel: unknown): string {
    const normalized = [
        String(rawActionType || "").trim().toLowerCase(),
        String(rawActionLabel || "").trim().toLowerCase(),
    ]
        .filter(Boolean)
        .join(" ");

    if (!normalized) {
        return "optimize";
    }
    if (
        normalized.includes("rightsize")
        || normalized.includes("resize")
        || normalized.includes("smaller")
        || normalized.includes("downsize")
    ) {
        return "rightsize";
    }
    if (
        normalized.includes("savings plan")
        || normalized.includes("reserved instance")
        || normalized.includes("commitment")
        || normalized.includes("purchase_ri")
    ) {
        return "purchase_ri";
    }
    if (
        normalized.includes("stop")
        || normalized.includes("shutdown")
        || normalized.includes("shut down")
        || normalized.includes("deallocate")
    ) {
        return "stop";
    }
    if (
        normalized.includes("delete")
        || normalized.includes("terminate")
        || normalized.includes("remove")
    ) {
        return "terminate";
    }
    return "optimize";
}

function formatPendingActionDate(createdAt: string): string {
    const parsed = new Date(createdAt);
    if (Number.isNaN(parsed.getTime())) {
        return String(createdAt || "");
    }
    return parsed.toLocaleDateString();
}

function mapPendingActionRow(action: NotificationRow): ActionItem {
    const meta = (action.metadata as MetadataRecord) || {};
    const status = action.status === "pending" || action.status === "approved" || action.status === "rejected" || action.status === "completed"
        ? action.status
        : "pending";
    const title = pickFirstString(
        action.recommendation,
        meta["resource_name"],
        `Action: ${action.type}`,
    ) ?? `Action: ${action.type}`;
    const description = pickFirstString(
        meta["description"],
        meta["ai_reasoning"],
        action.recommendation,
        "No description available",
    ) ?? "No description available";
    const resourceName = pickFirstString(
        meta["resource_name"],
        action.resource_id,
        action.recommendation,
        "Unknown resource",
    ) ?? "Unknown resource";
    const resourceType = pickFirstString(
        meta["resource_type"],
        action.type,
        "Cloud Resource",
    ) ?? "Cloud Resource";
    const actionType = normalizePendingActionType(meta["action_type"], action.action);

    return {
        id: action.id,
        title,
        description,
        resource_name: resourceName,
        resource_type: resourceType,
        action_type: actionType,
        estimated_savings: toMetricNumber(meta["estimated_savings"] ?? meta["potential_savings"]),
        risk_level: normalizePendingActionRiskLevel(meta["severity"] ?? meta["risk_level"]),
        status,
        created_at: formatPendingActionDate(action.created_at),
        provider: pickFirstString(
            meta["provider"],
            meta["cloud_provider"],
            meta["cloud"],
            "",
        ) ?? undefined,
        resource_id: pickFirstString(action.resource_id, "") ?? undefined,
        metadata: meta,
    };
}

function dedupePendingActionNotifications(
    notifications: BackendNotificationRecord[],
): BackendNotificationRecord[] {
    const seen = new Set<string>();

    return notifications.filter((notification) => {
        const metadata = (notification.metadata as MetadataRecord) || {};
        const integrationId = typeof metadata.integration_id === "string" ? metadata.integration_id : "unknown";
        const resourceName = pickFirstString(metadata["resource_name"], notification.resource_id, "");
        const actionType = normalizePendingActionType(metadata["action_type"], notification.action);
        const key = [
            integrationId,
            notification.type || "",
            actionType,
            resourceName || "",
            notification.recommendation || "",
            notification.status || "",
        ].join("|");

        if (seen.has(key)) {
            return false;
        }
        seen.add(key);
        return true;
    });
}

function dedupeAlertNotifications(
    notifications: BackendNotificationRecord[],
): BackendNotificationRecord[] {
    const seen = new Map<string, boolean>();

    return notifications.filter((notification) => {
        const metadata = (notification.metadata as MetadataRecord) || {};
        const integrationId = typeof metadata.integration_id === "string" ? metadata.integration_id : "unknown";
        const key = [
            integrationId,
            notification.type || "",
            notification.resource_id || "",
            notification.recommendation || "",
        ].join("|");

        if (seen.has(key)) {
            return false;
        }
        seen.set(key, true);
        return true;
    });
}

function mapAlertSeverity(severity: string): string {
    if (severity === "high") return "critical";
    if (severity === "medium") return "warning";
    return "info";
}

function formatAlertTimeAgo(dateStr: string): string {
    const now = new Date();
    const date = new Date(dateStr);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return new Date(dateStr).toLocaleDateString();
}

function mapBackendReportToReportItem(report: BackendReportRecord): ReportItem {
    return {
        id: report.id,
        title: report.title,
        report_type: report.report_type,
        summary: report.summary,
        period_start: new Date(report.period_start).toLocaleDateString(),
        period_end: new Date(report.period_end).toLocaleDateString(),
        status: report.status,
        created_at: new Date(report.created_at).toLocaleDateString(),
        file_size: `${Math.round((toMetricNumber(report.file_size_bytes) || 0) / 1024)}KB`,
        data: report.data || {},
    };
}

function pickFirstString(...values: unknown[]): string | null {
    for (const value of values) {
        if (typeof value === "string" && value.trim()) {
            return value;
        }
    }

    return null;
}

function getCreatedBy(resource: ResourceRow): string {
    return pickFirstString(
        resource.tags["Owner"],
        resource.tags["owner"],
        resource.metadata["created_by"],
        resource.metadata["CreatedBy"],
        resource.metadata["owner"],
    ) ?? "System";
}

function isShadowResource(resource: ResourceRow): boolean {
    return resource.region_compliance === "shadow_it" || resource.metadata["is_shadow_it"] === true;
}

function normalizeServiceType(resource: ResourceRow): string {
    return String(resource.service_type || "").trim().toLowerCase();
}

function getResourceStateSignals(resource: ResourceRow): string[] {
    const metadata = resource.metadata || {};
    const metrics = resource.metrics_data || {};

    return [
        String(resource.status || "").trim().toLowerCase(),
        pickFirstString(
            metadata["state"],
            metadata["instance_state"],
            metadata["power_state"],
            metadata["resource_state"],
            metadata["status"],
            metrics["state"],
            metrics["status"],
        )?.toLowerCase() ?? "",
    ].filter(Boolean);
}

function hasAnySignal(resource: ResourceRow, expected: string[]): boolean {
    const signals = getResourceStateSignals(resource);
    return signals.some((signal) => expected.includes(signal));
}

function countWasteBuckets(resources: ResourceRow[]) {
    const idleCount = resources.filter((resource) => {
        const serviceType = normalizeServiceType(resource);
        return serviceType.includes("ec2") && hasAnySignal(resource, ["zombie", "idle", "stopped"]);
    }).length;

    const ebsCount = resources.filter((resource) => {
        const serviceType = normalizeServiceType(resource);
        const wasteType = String(resource.waste_type || "").trim().toLowerCase();
        return serviceType.includes("ebs") && (
            hasAnySignal(resource, ["zombie"]) || wasteType.includes("orphan")
        );
    }).length;

    const ipCount = resources.filter((resource) => {
        const serviceType = normalizeServiceType(resource);
        return serviceType.includes("ip") && hasAnySignal(resource, ["zombie", "waste"]);
    }).length;

    const denominator = idleCount + ebsCount + ipCount;

    return {
        idleCount,
        ebsCount,
        ipCount,
        idlePercent: denominator > 0 ? (idleCount / denominator) * 100 : 0,
        ebsPercent: denominator > 0 ? (ebsCount / denominator) * 100 : 0,
        ipPercent: denominator > 0 ? (ipCount / denominator) * 100 : 0,
    };
}

export async function getDashboardMetrics() {
    const [stats, integrations, resourcesResponse] = await Promise.all([
        getBackendStats(),
        getBackendIntegrations(),
        getBackendResources(),
    ]);
    if (!stats || !integrations || !resourcesResponse) return null;

    const activeIntegrations = integrations.filter((integration) =>
        String(integration.status || "").trim().toLowerCase() === "active"
    ) as IntegrationLookupRow[];
    const resources = normalizeResourceRows(resourcesResponse.resources ?? []);
    const integrationStats = await Promise.all(
        activeIntegrations.map(async (integration) => ({
            integration,
            stats: await getBackendStats(integration.id),
        }))
    );

    const {
        idleCount,
        ebsCount,
        ipCount,
        idlePercent,
        ebsPercent,
        ipPercent,
    } = countWasteBuckets(resources);

    const providerMap = new Map<string, { spend: number; resources: number; savings: number }>();
    for (const provider of ["aws", "azure", "gcp"]) {
        providerMap.set(provider, { spend: 0, resources: 0, savings: 0 });
    }

    for (const item of integrationStats) {
        const provider = String(item.integration.provider || "").trim().toLowerCase();
        if (provider !== "aws" && provider !== "azure" && provider !== "gcp") {
            continue;
        }

        const current = providerMap.get(provider);
        if (!current || !item.stats) {
            continue;
        }

        current.spend += toProviderDisplayAmount(item.stats.total_spend, provider);
        current.savings += toProviderDisplayAmount(item.stats.potential_savings, provider);
        current.resources += toMetricNumber(item.stats.active_resources_count);
    }

    const providerCostsArray = ["aws", "azure", "gcp"]
        .map((provider) => {
            const data = providerMap.get(provider) ?? { spend: 0, resources: 0, savings: 0 };
            const label = provider === "gcp" ? "GCP" : provider.charAt(0).toUpperCase() + provider.slice(1);

            return {
                provider: label,
                spend: Math.round(data.spend * 100) / 100,
                resources: data.resources,
                savings: Math.round(data.savings * 100) / 100,
            };
        })
        .filter((provider) => provider.spend > 0 || provider.resources > 0 || provider.savings > 0);
    const displayTotalSpend = providerCostsArray.length > 0
        ? Math.round(providerCostsArray.reduce((sum, provider) => sum + provider.spend, 0) * 100) / 100
        : toDisplayInrAmount(stats.total_spend, "INR");
    const displayPotentialSavings = providerCostsArray.length > 0
        ? Math.round(providerCostsArray.reduce((sum, provider) => sum + provider.savings, 0) * 100) / 100
        : toDisplayInrAmount(stats.potential_savings, "INR");

    return {
        totalSpend: displayTotalSpend,
        potentialSavings: displayPotentialSavings,
        totalResources: toMetricNumber(stats.active_resources_count),
        confidence: {
            score: toMetricNumber(stats.ai_confidence_score),
        },
        carbon: {
            monthly: parseFloat(toMetricNumber(stats.carbon_footprint_kg).toFixed(2)),
            annual: parseFloat((toMetricNumber(stats.carbon_footprint_kg) * 12).toFixed(2)),
            trees: Math.round(toMetricNumber(stats.carbon_footprint_kg) * 0.5),
            cars: Math.round(toMetricNumber(stats.carbon_footprint_kg) * 0.05),
        },
        costOfInaction: Math.round(displayPotentialSavings * 6 * 100) / 100,
        annualSavings: Math.round(displayPotentialSavings * 12 * 100) / 100,
        wasteSources: {
            idleEC2: Math.round(idlePercent),
            orphanedEBS: Math.round(ebsPercent),
            unusedIPs: Math.round(ipPercent),
        },
        infraHealth: {
            idleEC2: idleCount,
            unattachedEBS: ebsCount,
            unusedIPs: ipCount,
        },
        providerCosts: providerCostsArray,
        monthlySavings: displayPotentialSavings,
    };
}

/**
 * Combined dashboard data fetch — single API call replaces 10+ separate calls.
 */
export async function getDashboardPageData() {
    const summary = await getDashboardSummary();
    if (!summary) {
        return { stats: null, resources: [] as CloudResource[], wasteData: [], spendData: [], permissionAlert: null, activeIntegrationCount: 0, integrations: [] };
    }

    // Transform stats (same logic as getDashboardMetrics)
    const rawStats = summary.stats;
    let stats = null;
    if (rawStats) {
        const totalSpend = toDisplayInrAmount(toMetricNumber(rawStats.total_spend), "USD");
        const potentialSavings = toDisplayInrAmount(toMetricNumber(rawStats.potential_savings), "USD");
        stats = {
            totalSpend,
            potentialSavings,
            totalResources: toMetricNumber(rawStats.active_resources_count),
            confidence: { score: toMetricNumber(rawStats.ai_confidence_score) },
            carbon: {
                monthly: parseFloat(toMetricNumber(rawStats.carbon_footprint_kg).toFixed(2)),
                annual: parseFloat((toMetricNumber(rawStats.carbon_footprint_kg) * 12).toFixed(2)),
                trees: Math.round(toMetricNumber(rawStats.carbon_footprint_kg) * 0.5),
                cars: Math.round(toMetricNumber(rawStats.carbon_footprint_kg) * 0.05),
            },
            costOfInaction: Math.round(potentialSavings * 6 * 100) / 100,
            annualSavings: Math.round(potentialSavings * 12 * 100) / 100,
            wasteSources: { idleEC2: 0, orphanedEBS: 0, unusedIPs: 0 },
            infraHealth: { idleEC2: 0, unattachedEBS: 0, unusedIPs: 0 },
            providerCosts: [] as { provider: string; spend: number; resources: number; savings: number }[],
            monthlySavings: potentialSavings,
        };
    }

    // Transform resources
    const resourceRows = normalizeResourceRows(summary.resources as ResourceRow[]);
    const resources: CloudResource[] = resourceRows.map((resource, index) => {
        const metadata = resource.metadata;
        const metricsData = resource.metrics_data;
        const cpuUtilization = toMetricNumber(metricsData["cpu_utilization"] ?? metadata["cpu_utilization"] ?? metadata["cpu_utilization_avg"]);
        const memoryUtilization = toMetricNumber(metricsData["memory_utilization"] ?? metadata["memory_utilization"] ?? metadata["memory_utilization_avg"]);
        const storageUtilization = toMetricNumber(metricsData["storage_utilization"]) || toMetricNumber(metadata["storage_utilization"]) || 0;
        return {
            id: resource.id ?? resource.cloud_resource_id ?? `${resource.provider}-${resource.integration_id || "integration"}-${index}`,
            user_id: resource.user_id,
            integration_id: resource.integration_id,
            provider: resource.provider,
            cloud_resource_id: resource.cloud_resource_id,
            resource_name: resource.resource_name,
            service_type: resource.service_type,
            resource_type: resource.service_type,
            region: resource.region,
            monthly_cost: resource.cost,
            cost: resource.cost,
            monthly_cost_available: resource.monthly_cost_available,
            cost_source: resource.cost_source,
            cost_status: resource.cost_status,
            cost_label: resource.cost_label,
            annual_cost_label: resource.annual_cost_label,
            utilization: isWasteStatus(resource.status) ? 0 : cpuUtilization,
            status: resource.status,
            waste_type: resource.waste_type,
            waste_reason: resource.waste_reason,
            confidence_score: resource.confidence_score,
            created_by: getCreatedBy(resource),
            region_compliance: isShadowResource(resource) ? 'shadow_it' : resource.region_compliance,
            cpu_utilization: cpuUtilization,
            memory_utilization: memoryUtilization,
            storage_utilization: storageUtilization,
            carbon_footprint_kg: resource.carbon_footprint_kg,
            tags: resource.tags,
            metadata,
            metrics_data: metricsData,
            governance_violations: resource.governance_violations,
            last_scanned_at: resource.last_scanned_at,
            created_at: resource.created_at ?? null,
        };
    });

    // Compute waste buckets for stats enrichment
    if (stats && resourceRows.length > 0) {
        const { idleCount, ebsCount, ipCount, idlePercent, ebsPercent, ipPercent } = countWasteBuckets(resourceRows);
        stats.wasteSources = { idleEC2: Math.round(idlePercent), orphanedEBS: Math.round(ebsPercent), unusedIPs: Math.round(ipPercent) };
        stats.infraHealth = { idleEC2: idleCount, unattachedEBS: ebsCount, unusedIPs: ipCount };
    }

    // Build providerCosts from integrations + resources
    if (stats && summary.integrations) {
        const integrationProviderMap = new Map<string, string>();
        for (const integ of summary.integrations) {
            if (integ.id && integ.provider) {
                integrationProviderMap.set(String(integ.id), String(integ.provider).toLowerCase());
            }
        }
        const providerAgg = new Map<string, { spend: number; resources: number; savings: number }>();
        for (const provider of ["aws", "azure", "gcp"]) {
            providerAgg.set(provider, { spend: 0, resources: 0, savings: 0 });
        }
        for (const resource of resourceRows) {
            const provider = integrationProviderMap.get(String(resource.integration_id || ""))
                || String(resource.provider || "").toLowerCase();
            const agg = providerAgg.get(provider);
            if (agg) {
                agg.spend += toDisplayInrAmount(toMetricNumber(resource.cost), sourceCurrencyForProvider(provider));
                agg.resources += 1;
            }
        }
        const totalProviderSpend = Array.from(providerAgg.values()).reduce((s, a) => s + a.spend, 0);
        if (stats.potentialSavings > 0 && totalProviderSpend > 0) {
            for (const [, agg] of providerAgg) {
                agg.savings = Math.round((agg.spend / totalProviderSpend) * stats.potentialSavings * 100) / 100;
            }
        }
        stats.providerCosts = ["aws", "azure", "gcp"]
            .map((p) => {
                const data = providerAgg.get(p)!;
                return { provider: p === "gcp" ? "GCP" : p.charAt(0).toUpperCase() + p.slice(1), spend: Math.round(data.spend * 100) / 100, resources: data.resources, savings: data.savings };
            })
            .filter((p) => p.spend > 0 || p.resources > 0);
    }

    // Transform waste distribution
    const wasteData = (summary.waste_distribution || []).map((item) => ({
        category_name: item.category_name,
        value: toMetricNumber(item.value),
    }));

    // Transform spend history (same logic as getDailySpend)
    type DailyRow = { spend_date?: string; amount?: unknown };
    const spendRows = (summary.spend_history || []) as DailyRow[];
    const aggregatedByDay = new Map<string, number>();
    for (const row of spendRows) {
        const spendDate = String(row.spend_date || "").slice(0, 10);
        if (!spendDate) continue;
        aggregatedByDay.set(spendDate, (aggregatedByDay.get(spendDate) || 0) + toMetricNumber(row.amount));
    }
    const spendData = Array.from(aggregatedByDay.entries())
        .sort(([left], [right]) => left.localeCompare(right))
        .slice(-7)
        .map(([spendDate, amount]) => ({
            date: new Date(spendDate).toLocaleDateString('en-US', { weekday: 'short' }),
            amount: Math.round(amount * 100) / 100,
        }));

    // Permission alert
    const permissionAlert = summary.permission_alert as (Record<string, unknown> & { recommendation?: string; action?: string; metadata?: Record<string, unknown> }) | null;

    return {
        stats,
        resources,
        wasteData,
        spendData,
        permissionAlert,
        activeIntegrationCount: summary.integration_count,
        integrations: summary.integrations,
    };
}

export async function getDailySpend() {
    const response = await getBackendSpendHistory(30);
    if (!response) {
        return [];
    }

    const spendRows = (Array.isArray(response.history) ? response.history : []) as DailySpendRow[];
    if (spendRows.length === 0) {
        return [];
    }

    const aggregatedByDay = new Map<string, number>();
    for (const row of spendRows) {
        const spendDate = String(row.spend_date || "").slice(0, 10);
        if (!spendDate) {
            continue;
        }

        aggregatedByDay.set(spendDate, (aggregatedByDay.get(spendDate) || 0) + toMetricNumber(row.amount));
    }

    return Array.from(aggregatedByDay.entries())
        .sort(([left], [right]) => left.localeCompare(right))
        .slice(-7)
        .map(([spendDate, amount]) => ({
            date: new Date(spendDate).toLocaleDateString('en-US', { weekday: 'short' }),
            amount: Math.round(amount * 100) / 100,
        }));
}

export async function getWasteDistribution() {
    const response = await getBackendWasteDistribution();
    if (!response || response.waste_distribution.length === 0) return [];

    return response.waste_distribution.map((item) => ({
        category_name: item.category_name,
        value: toMetricNumber(item.value),
    }));
}

export async function getRecentAlerts() {
    const response = await getBackendNotifications();
    if (!response) return [];

    const recentAlerts = dedupeAlertNotifications(response.notifications)
        .sort((left, right) =>
            new Date(String(right.created_at || "")).getTime() - new Date(String(left.created_at || "")).getTime()
        )
        .slice(0, 5);

    return recentAlerts.map((alert) => ({
        id: alert.id,
        title: alert.recommendation,
        severity: ((alert.metadata as MetadataRecord | undefined)?.severity as string | undefined) || "info",
        time: new Date(alert.created_at).toLocaleDateString(),
        status: alert.status,
    }));
}

export async function getTopResources() {
    const resources = await getAllResources();
    return resources
        .filter((resource) => isWasteStatus(resource.status))
        .sort((left, right) => right.cost - left.cost)
        .slice(0, 5)
        .map((resource) => ({
            name: resource.resource_name,
            type: resource.service_type,
            cost: resource.cost,
            utilization: 0,
        }));
}



export async function getAllResources(): Promise<CloudResource[]> {
    // Demo mode removed
    // const user = await currentUser();
    // const isDemo = user?.emailAddresses?.some(e => e.emailAddress === 'sambhavpal5@gmail.com');
    // if (isDemo) { ... }

    const response = await getBackendResources();
    if (!response) return [];

    const resources = normalizeResourceRows(response.resources ?? []);

    return resources.map((resource, index) => {
        const metadata = resource.metadata;
        const metricsData = resource.metrics_data;
        const cpuUtilization = toMetricNumber(
            metricsData["cpu_utilization"]
            ?? metadata["cpu_utilization"]
            ?? metadata["cpu_utilization_avg"]
        );
        const memoryUtilization = toMetricNumber(
            metricsData["memory_utilization"]
            ?? metadata["memory_utilization"]
            ?? metadata["memory_utilization_avg"]
        );
        const storageUtilization = toMetricNumber(metricsData["storage_utilization"])
            || toMetricNumber(metadata["storage_utilization"])
            || (() => {
                const diskIo = toMetricNumber(metadata["disk_io"]);
                return diskIo > 0 ? Math.min(100, Math.floor(diskIo / 50)) : 0;
            })();

        return {
            id: resource.id ?? resource.cloud_resource_id ?? `${resource.provider}-${resource.integration_id || "integration"}-${index}`,
            user_id: resource.user_id,
            integration_id: resource.integration_id,
            provider: resource.provider,
            cloud_resource_id: resource.cloud_resource_id,
            resource_name: resource.resource_name,
            service_type: resource.service_type,
            resource_type: resource.service_type,
            region: resource.region,
            monthly_cost: resource.cost,
            cost: resource.cost,
            monthly_cost_available: resource.monthly_cost_available,
            cost_source: resource.cost_source,
            cost_status: resource.cost_status,
            cost_label: resource.cost_label,
            annual_cost_label: resource.annual_cost_label,
            utilization: isWasteStatus(resource.status) ? 0 : cpuUtilization,
            status: resource.status,
            waste_type: resource.waste_type,
            waste_reason: resource.waste_reason,
            confidence_score: resource.confidence_score,
            created_by: getCreatedBy(resource),
            region_compliance: isShadowResource(resource) ? 'shadow_it' : resource.region_compliance,
            cpu_utilization: cpuUtilization,
            memory_utilization: memoryUtilization,
            storage_utilization: storageUtilization,
            carbon_footprint_kg: resource.carbon_footprint_kg,
            tags: resource.tags,
            metadata,
            metrics_data: metricsData,
            governance_violations: resource.governance_violations,
            last_scanned_at: resource.last_scanned_at,
            created_at: resource.created_at ?? null,
        };
    });
}

export async function getPendingActions(): Promise<ActionItem[]> {
    // Demo mode removed
    // const user = await currentUser();
    // const isDemo = user?.emailAddresses?.some(e => e.emailAddress === 'sambhavpal5@gmail.com');
    // if (isDemo) { ... }

    const response = await getBackendNotifications();
    if (!response) return [];

    const pendingActions = response.notifications.filter((notification) =>
        notification.status === "pending"
        || notification.status === "approved"
        || notification.status === "rejected"
    );

    return dedupePendingActionNotifications(pendingActions)
        .map((action) => mapPendingActionRow(action as NotificationRow));
}

export async function getReports(): Promise<ReportItem[]> {
    // Demo mode removed
    // const user = await currentUser();
    // const isDemo = user?.emailAddresses?.some(e => e.emailAddress === 'sambhavpal5@gmail.com');
    // if (isDemo) { ... }

    const reports = await getBackendReports();
    return reports.map(mapBackendReportToReportItem);
}

export async function getGovernancePolicies(): Promise<GovernancePolicyItem[]> {
    const response = await getBackendGovernancePolicies();
    if (!response) return [];

    return response.policies.map(mapBackendGovernancePolicyToItem);
}

export async function getPermissionAlerts() {
    const response = await getBackendNotifications('pending');
    if (!response) return null;

    const permissionAlerts = response.notifications
        .filter((notification): notification is NotificationRow =>
            String(notification.type || '').trim().toLowerCase() === 'permission_alert'
        )
        .sort((left, right) =>
            new Date(String(right.created_at || '')).getTime() - new Date(String(left.created_at || '')).getTime()
        );

    return permissionAlerts[0] ?? null;
}

export async function getAllAlerts(): Promise<AlertItem[]> {
    const response = await getBackendNotifications();
    if (!response) return [];

    const alertRows = response.notifications as BackendNotificationRecord[];
    if (alertRows.length === 0) return [];

    return dedupeAlertNotifications(alertRows).map((alert) => ({
        id: alert.id,
        title: alert.recommendation || `Alert: ${alert.type}`,
        message: (alert.metadata as MetadataRecord)?.description as string || alert.recommendation,
        severity: mapAlertSeverity((alert.metadata as MetadataRecord)?.severity as string || 'info'),
        alert_type: alert.type,
        is_read: alert.status !== 'pending',
        created_at: formatAlertTimeAgo(alert.created_at)
    }));
}

// --- Governance Rules Engine Data ---

export interface GovernancePolicy {
    id: string;
    name: string;
    status: 'Pass' | 'Fail';
    severity: 'Critical' | 'High' | 'Medium' | 'Low';
    reason: string;
    framework: string;
}

export interface GovernanceSecurityViolation {
    id: string;
    policy_id: string;
    resource_id: string;
    resource: string;
    provider: string;
    category: string;
    rule_category: string;
    severity: string;
    status: string;
    description: string;
    message: string;
    detected_at: string;
    created_at: string;
}

export interface GovernanceSecurityNotification {
    id: string;
    recommendation: string;
    status: string;
    type: string;
    resource_id: string;
    created_at: string;
    metadata: MetadataRecord;
}

export interface GovernanceSecurityResource {
    id: string;
    resource_id: string;
    resource_name: string;
    resource_type: string;
    provider: string;
    region: string;
    status: string;
}

export interface GovernanceData {
    score: {
        value: number;
        trend: 'up' | 'down' | 'stable';
        rating: 'Excellent' | 'Good' | 'Fair' | 'Critical';
    };
    tagging: {
        missingTags: number;
        costImpact: number;
        assets: { id: string; name: string; missing: string[] }[];
    };
    budget: {
        projectedSpend: number;
        budgetLimit: number;
        burnRate: number; // percentage
        status: 'Safe' | 'Warning' | 'Excess';
        alert: string;
    };
    officeHours: {
        savings: number;
        enabled: boolean;
        recommendation: string;
    };
    policies: GovernancePolicy[];
    trends: { date: string; score: number }[];
    frameworkSummary: { framework: string; pass: number; fail: number; total: number }[];
    agentNotifications: GovernanceSecurityNotification[];
    resources: GovernanceSecurityResource[];
    policyViolations: GovernanceSecurityViolation[];
}

export type SecuritySeverity = "critical" | "high" | "medium" | "low" | "info";

export interface SecurityPostureSummary {
    score: number;
    rating: BackendSecurityPostureRating;
    critical: number;
    high: number;
    open: number;
    exposedResources: number;
    monitoredResources: number;
    lastDetectedAt: string | null;
}

export interface SecurityBreakdownItem {
    name: string;
    count: number;
}

export interface SecurityFinding {
    id: string;
    resource_id: string;
    resource: string;
    provider: string;
    region: string;
    category: string;
    severity: SecuritySeverity;
    status: string;
    description: string;
    detected_at: string;
    source: "policy_violation" | "agent_notification";
    remediation: string;
}

export interface SecurityExposedResource {
    id: string;
    resource_id: string;
    resource_name: string;
    resource_type: string;
    provider: string;
    region: string;
    highest_severity: SecuritySeverity;
    risk_count: number;
    exposure: string;
    status: string;
}

export interface SecurityPosture {
    summary: SecurityPostureSummary;
    findingsBySeverity: SecurityBreakdownItem[];
    findingsByCategory: SecurityBreakdownItem[];
    activeFindings: SecurityFinding[];
    exposedResources: SecurityExposedResource[];
    recentAlerts: SecurityFinding[];
}

export async function getGovernanceAnalysis(): Promise<GovernanceData> {
    const response = await getBackendGovernanceAnalysis();
    if (!response) {
        return getZeroGovernanceData();
    }

    return mapBackendGovernanceAnalysis(response);
}

export async function getSecurityPosture(): Promise<SecurityPosture> {
    const response = await getBackendSecurityPosture();
    if (!response) {
        return getZeroSecurityPosture();
    }

    return mapBackendSecurityPosture(response);
}

function mapBackendGovernancePolicyToItem(
    policy: BackendGovernancePolicyRecord,
): GovernancePolicyItem {
    return {
        id: policy.id,
        name: policy.name,
        description: pickFirstString(policy.description, policy.policy_type) ?? policy.policy_type,
        policy_type: policy.policy_type,
        is_active: Boolean(policy.is_active),
        compliance_rate: toMetricNumber(policy.compliance_rate),
        violations: toMetricNumber(policy.violations),
        created_at: new Date(policy.created_at).toLocaleDateString(),
    };
}

function getZeroGovernanceData(): GovernanceData {
    return {
        score: { value: 0, trend: 'stable', rating: 'Fair' },
        tagging: { missingTags: 0, costImpact: 0, assets: [] },
        budget: { projectedSpend: 0, budgetLimit: 0, burnRate: 0, status: 'Safe', alert: 'No data yet.' },
        officeHours: { savings: 0, enabled: false, recommendation: 'Run a scan to generate insights.' },
        policies: [],
        trends: [],
        frameworkSummary: [],
        agentNotifications: [],
        resources: [],
        policyViolations: [],
    };
}

function normalizeSecuritySeverity(value: string): SecuritySeverity {
    if (value === "critical" || value === "high" || value === "medium" || value === "low" || value === "info") {
        return value;
    }
    return "medium";
}

function getZeroSecurityPosture(): SecurityPosture {
    return {
        summary: {
            score: 0,
            rating: "No data",
            critical: 0,
            high: 0,
            open: 0,
            exposedResources: 0,
            monitoredResources: 0,
            lastDetectedAt: null,
        },
        findingsBySeverity: [],
        findingsByCategory: [],
        activeFindings: [],
        exposedResources: [],
        recentAlerts: [],
    };
}

function mapBackendGovernanceAgentNotification(
    notification: BackendGovernanceAgentNotification,
): GovernanceSecurityNotification {
    return {
        id: pickFirstString(notification.id, "") ?? "",
        recommendation: pickFirstString(notification.recommendation, "") ?? "",
        status: pickFirstString(notification.status, "pending") ?? "pending",
        type: pickFirstString(notification.type, "notification") ?? "notification",
        resource_id: pickFirstString(notification.resource_id, "") ?? "",
        created_at: pickFirstString(notification.created_at, "") ?? "",
        metadata: typeof notification.metadata === "object" && notification.metadata
            ? notification.metadata
            : {},
    };
}

function mapBackendSecurityBreakdownItem(item: BackendSecurityBreakdownItem): SecurityBreakdownItem {
    return {
        name: pickFirstString(item.name, "security") ?? "security",
        count: toMetricNumber(item.count),
    };
}

function mapBackendSecurityFinding(finding: BackendSecurityFinding): SecurityFinding {
    return {
        id: pickFirstString(finding.id, "") ?? "",
        resource_id: pickFirstString(finding.resource_id, "") ?? "",
        resource: pickFirstString(finding.resource, "Unknown resource") ?? "Unknown resource",
        provider: pickFirstString(finding.provider, "") ?? "",
        region: pickFirstString(finding.region, "") ?? "",
        category: pickFirstString(finding.category, "security") ?? "security",
        severity: normalizeSecuritySeverity(finding.severity),
        status: pickFirstString(finding.status, "open") ?? "open",
        description: pickFirstString(finding.description, "Security finding requires review.") ?? "Security finding requires review.",
        detected_at: pickFirstString(finding.detected_at, "") ?? "",
        source: finding.source === "agent_notification" ? "agent_notification" : "policy_violation",
        remediation: pickFirstString(finding.remediation, "Review the affected resource and remediate the control.") ?? "Review the affected resource and remediate the control.",
    };
}

function mapBackendSecurityExposedResource(resource: BackendSecurityExposedResource): SecurityExposedResource {
    return {
        id: pickFirstString(resource.id, resource.resource_id, "") ?? "",
        resource_id: pickFirstString(resource.resource_id, resource.id, "") ?? "",
        resource_name: pickFirstString(resource.resource_name, "Unknown resource") ?? "Unknown resource",
        resource_type: pickFirstString(resource.resource_type, "resource") ?? "resource",
        provider: pickFirstString(resource.provider, "") ?? "",
        region: pickFirstString(resource.region, "") ?? "",
        highest_severity: normalizeSecuritySeverity(resource.highest_severity),
        risk_count: toMetricNumber(resource.risk_count),
        exposure: pickFirstString(resource.exposure, "Security risk detected") ?? "Security risk detected",
        status: pickFirstString(resource.status, "unknown") ?? "unknown",
    };
}

function mapBackendSecurityPosture(response: BackendSecurityPostureResponse): SecurityPosture {
    return {
        summary: {
            score: Math.max(0, Math.min(100, toMetricNumber(response.summary?.score))),
            rating: response.summary?.rating ?? "No data",
            critical: toMetricNumber(response.summary?.critical),
            high: toMetricNumber(response.summary?.high),
            open: toMetricNumber(response.summary?.open),
            exposedResources: toMetricNumber(response.summary?.exposed_resources),
            monitoredResources: toMetricNumber(response.summary?.monitored_resources),
            lastDetectedAt: pickFirstString(response.summary?.last_detected_at, "") || null,
        },
        findingsBySeverity: Array.isArray(response.findingsBySeverity)
            ? response.findingsBySeverity.map(mapBackendSecurityBreakdownItem)
            : [],
        findingsByCategory: Array.isArray(response.findingsByCategory)
            ? response.findingsByCategory.map(mapBackendSecurityBreakdownItem)
            : [],
        activeFindings: Array.isArray(response.activeFindings)
            ? response.activeFindings.map(mapBackendSecurityFinding)
            : [],
        exposedResources: Array.isArray(response.exposedResources)
            ? response.exposedResources.map(mapBackendSecurityExposedResource)
            : [],
        recentAlerts: Array.isArray(response.recentAlerts)
            ? response.recentAlerts.map(mapBackendSecurityFinding)
            : [],
    };
}

function mapBackendGovernanceSecurityResource(
    resource: BackendGovernanceSecurityResource,
): GovernanceSecurityResource {
    return {
        id: pickFirstString(resource.id, resource.resource_id, "") ?? "",
        resource_id: pickFirstString(resource.resource_id, resource.id, "") ?? "",
        resource_name: pickFirstString(resource.resource_name, resource.resource_id, "Unknown resource") ?? "Unknown resource",
        resource_type: pickFirstString(resource.resource_type, "resource") ?? "resource",
        provider: pickFirstString(resource.provider, "") ?? "",
        region: pickFirstString(resource.region, "") ?? "",
        status: pickFirstString(resource.status, "unknown") ?? "unknown",
    };
}

function mapBackendGovernancePolicyViolation(
    violation: BackendGovernancePolicyViolation,
): GovernanceSecurityViolation {
    return {
        id: pickFirstString(violation.id, "") ?? "",
        policy_id: pickFirstString(violation.policy_id, "") ?? "",
        resource_id: pickFirstString(violation.resource_id, "") ?? "",
        resource: pickFirstString(violation.resource, violation.resource_id, "—") ?? "—",
        provider: pickFirstString(violation.provider, "") ?? "",
        category: pickFirstString(violation.category, violation.rule_category, "other") ?? "other",
        rule_category: pickFirstString(violation.rule_category, violation.category, "other") ?? "other",
        severity: pickFirstString(violation.severity, "low") ?? "low",
        status: pickFirstString(violation.status, "open") ?? "open",
        description: pickFirstString(violation.description, violation.message, "—") ?? "—",
        message: pickFirstString(violation.message, violation.description, "—") ?? "—",
        detected_at: pickFirstString(violation.detected_at, violation.created_at, "") ?? "",
        created_at: pickFirstString(violation.created_at, violation.detected_at, "") ?? "",
    };
}

function mapBackendGovernanceAnalysis(
    response: BackendGovernanceAnalysisResponse,
): GovernanceData {
    return {
        score: {
            value: toMetricNumber(response.score?.value),
            trend: response.score?.trend === "down" || response.score?.trend === "stable" ? response.score.trend : "up",
            rating: response.score?.rating === "Excellent" || response.score?.rating === "Good" || response.score?.rating === "Critical"
                ? response.score.rating
                : "Fair",
        },
        tagging: {
            missingTags: toMetricNumber(response.tagging?.missingTags),
            costImpact: toMetricNumber(response.tagging?.costImpact),
            assets: Array.isArray(response.tagging?.assets)
                ? response.tagging.assets.map((asset) => ({
                    id: pickFirstString(asset?.id, asset?.name, "") ?? "",
                    name: pickFirstString(asset?.name, "Unknown Asset") ?? "Unknown Asset",
                    missing: Array.isArray(asset?.missing) ? asset.missing.filter((tag): tag is string => typeof tag === "string" && tag.trim().length > 0) : [],
                }))
                : [],
        },
        budget: {
            projectedSpend: toMetricNumber(response.budget?.projectedSpend),
            budgetLimit: toMetricNumber(response.budget?.budgetLimit),
            burnRate: toMetricNumber(response.budget?.burnRate),
            status: response.budget?.status === "Warning" || response.budget?.status === "Excess" ? response.budget.status : "Safe",
            alert: pickFirstString(response.budget?.alert, "Infrastructure is well-optimized") ?? "Infrastructure is well-optimized",
        },
        officeHours: {
            savings: toMetricNumber(response.officeHours?.savings),
            enabled: Boolean(response.officeHours?.enabled),
            recommendation: pickFirstString(response.officeHours?.recommendation, "No schedule changes recommended") ?? "No schedule changes recommended",
        },
        policies: Array.isArray(response.policies)
            ? response.policies.map((policy, index) => ({
                id: pickFirstString(policy?.id, `pol-${index}`) ?? `pol-${index}`,
                name: pickFirstString(policy?.name, "AI Governance Rule") ?? "AI Governance Rule",
                status: policy?.status === "Fail" ? "Fail" : "Pass",
                severity: policy?.severity === "Critical" || policy?.severity === "High" || policy?.severity === "Low"
                    ? policy.severity
                    : "Medium",
                reason: pickFirstString(policy?.reason, "Verified by AI Engine") ?? "Verified by AI Engine",
                framework: pickFirstString(policy?.framework, "FinOps") ?? "FinOps",
            }))
            : [],
        trends: Array.isArray(response.trends)
            ? response.trends.map((trend) => ({
                date: pickFirstString(trend?.date, "Unknown") ?? "Unknown",
                score: Math.max(0, Math.min(100, toMetricNumber(trend?.score))),
            }))
            : [],
        frameworkSummary: Array.isArray(response.frameworkSummary)
            ? response.frameworkSummary.map((framework) => ({
                framework: pickFirstString(framework?.framework, "FinOps") ?? "FinOps",
                pass: toMetricNumber(framework?.pass),
                fail: toMetricNumber(framework?.fail),
                total: toMetricNumber(framework?.total),
            }))
            : [],
        agentNotifications: Array.isArray(response.agentNotifications)
            ? response.agentNotifications.map(mapBackendGovernanceAgentNotification)
            : [],
        resources: Array.isArray(response.resources)
            ? response.resources.map(mapBackendGovernanceSecurityResource)
            : [],
        policyViolations: Array.isArray(response.policyViolations)
            ? response.policyViolations.map(mapBackendGovernancePolicyViolation)
            : [],
    };
}

export async function getActiveAwsIntegration(): Promise<ArchitectureIntegration | null> {
    const supported = await getActiveArchitectureIntegrations();
    return supported.find((integration) => (integration.provider || "").toLowerCase() === "aws") ?? null;
}

export async function getActiveArchitectureIntegrations(): Promise<ArchitectureIntegration[]> {
    const integrations = ((await getBackendIntegrations()) ?? []).filter((integration) => {
        const provider = (integration.provider || '').toLowerCase();
        const status = (integration.status || '').toLowerCase();
        return (provider === 'aws' || provider === 'azure' || provider === 'gcp')
            && status === "active";
    }).map((integration) => ({
        id: integration.id,
        provider: integration.provider,
        name: integration.name ?? null,
        regions: Array.isArray(integration.regions) ? integration.regions : [],
        last_scan: integration.last_scan ?? null,
        created_at: integration.created_at ?? null,
    })) as ArchitectureIntegration[];

    const toSortableTime = (value?: string | null) => {
        if (!value) return 0;
        const parsed = Date.parse(value);
        return Number.isFinite(parsed) ? parsed : 0;
    };

    integrations.sort((left, right) => {
        const leftLastScan = toSortableTime(left.last_scan);
        const rightLastScan = toSortableTime(right.last_scan);
        if (leftLastScan !== rightLastScan) {
            return rightLastScan - leftLastScan;
        }

        const leftCreated = toSortableTime(left.created_at);
        const rightCreated = toSortableTime(right.created_at);
        return rightCreated - leftCreated;
    });

    return integrations;
}

export async function getActiveArchitectureIntegration() {
    const supported = await getActiveArchitectureIntegrations();
    return supported.length > 0 ? supported[0] : null;
}
