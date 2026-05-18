import { auth } from '@clerk/nextjs/server';
import {
    buildBackendAuthHeaders,
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from '@/app/api/_shared/backend-auth';
import { BACKEND_URL } from '@/lib/config';

function isLoopbackBackendUrl(value: string): boolean {
    try {
        const hostname = new URL(value).hostname.toLowerCase();
        return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
    } catch {
        return false;
    }
}

type TriggerScanOptions = {
    token?: string | null;
    userId?: string | null;
};

type ArchitectureProvider = "aws" | "azure" | "gcp";

function normalizeArchitectureProvider(provider: string): ArchitectureProvider {
    const normalized = provider?.toLowerCase();
    if (normalized === "aws" || normalized === "azure" || normalized === "gcp") {
        return normalized;
    }
    throw new Error(`Invalid architecture provider: ${provider}`);
}

export type BackendIntegration = {
    id: string;
    provider: string;
    name: string;
    status: string;
    last_scan: string | null;
    regions: string[];
    created_at?: string | null;
    account_identifier?: string | null;
    monthly_budget_limit?: number | null;
    alert_phone_number_masked?: string | null;
    alert_slack_webhook_configured?: boolean;
};

export type FinanceScope = "portfolio" | "integration";
export type FinanceReportCadence = "manual" | "weekly" | "monthly";

export type FinanceForecastDriver = {
    dimension: string;
    key: string;
    delta_amount: number;
};

export type FinanceForecastResponse = {
    scope: FinanceScope;
    integration_id?: string | null;
    as_of: string;
    currency: string;
    history_days_used: number;
    forecast_method: string;
    forecast_stable: boolean;
    actual_mtd_spend: number;
    forecast_eom_spend: number;
    budget_limit?: number | null;
    budget_source: string;
    variance_amount?: number | null;
    variance_pct?: number | null;
    status: string;
    trend: string;
    drivers: FinanceForecastDriver[];
    message?: string | null;
};

export type FinanceBudgetEvent = {
    id: string;
    scope: FinanceScope;
    integration_id?: string | null;
    provider?: string | null;
    account_name?: string | null;
    event_type: "approaching_budget" | "forecasted_over_budget" | "over_budget" | "recovered";
    severity: "warning" | "critical" | "info";
    title: string;
    message: string;
    current_status: string;
    previous_status?: string | null;
    currency: string;
    budget_limit?: number | null;
    budget_source: string;
    actual_mtd_spend: number;
    forecast_eom_spend: number;
    variance_amount?: number | null;
    variance_pct?: number | null;
    created_at: string;
};

export type FinanceBudgetEventsResponse = {
    events: FinanceBudgetEvent[];
    count: number;
};

export type FinanceSpendHistoryPoint = {
    spend_date: string;
    amount: number;
    currency: string;
};

export type FinanceSpendHistoryResponse = {
    scope: FinanceScope;
    integration_id?: string | null;
    currency: string;
    history: FinanceSpendHistoryPoint[];
    count: number;
    days_requested: number;
};

export type CloudCommitment = {
    id: string;
    provider: string;
    type: string;
    name: string;
    status: string;
    start_date: string;
    end_date: string;
    commitment_amount: number;
    currency: string;
    region?: string | null;
    utilization_pct: number;
    savings_amount: number;
    coverage_type: string;
};

export type FinanceCommitmentsResponse = {
    commitments: CloudCommitment[];
    count: number;
};

export type FinanceSettings = {
    portfolio_budget_limit?: number | null;
    report_recipients: string[];
    report_cadence: FinanceReportCadence;
    alert_thresholds: {
        warning_pct: number;
        critical_pct: number;
    };
};

export type BackendReportType =
    | "monthly_executive_summary"
    | "budget_variance"
    | "provider_spend_summary"
    | "board_pack";

export type BackendReportRecord = {
    id: string;
    report_type: BackendReportType;
    title: string;
    summary: string;
    status: string;
    period_start: string;
    period_end: string;
    generated_at: string;
    created_at: string;
    currency: string;
    file_size_bytes: number;
    delivery_channels: string[];
    delivery_status: string;
    metadata: Record<string, unknown>;
    data: Record<string, unknown>;
};

export type BillAnalysisOpportunity = {
    category: string;
    current_cloud: string;
    current_cost: number;
    recommended_cloud: string;
    recommended_cost: number;
    savings: number;
    savings_pct: number;
    reasoning?: string | null;
    migration_risk?: string | null;
    migration_note?: string | null;
    all_cloud_costs?: Record<string, number>;
};

export type BillAnalysisTopService = {
    service: string;
    cost: number;
};

export type BillExecutiveFindingAction = {
    name: string;
    difficulty: "Easy" | "Medium" | "Hard" | string;
    time_required: string;
    monthly_saving_min: number;
    monthly_saving_max: number;
    risk: "None" | "Low" | "Medium" | "High" | string;
    savings_source?: string | null;
    validation_required?: boolean;
    calculation?: string | null;
    evidence_lines?: string[];
    confidence_reason?: string | null;
};

export type BillExecutiveFinding = {
    rank: number;
    service: string;
    monthly_cost: number;
    pct_of_bill: number;
    severity: "critical" | "high" | "medium" | "low" | "optimized";
    title: string;
    what_we_found: string;
    why_inefficient: string | null;
    how_to_fix: string[];
    actions: BillExecutiveFindingAction[];
    savings_source?: string | null;
    validation_required?: boolean;
    calculation?: string | null;
    evidence_lines?: string[];
    confidence_reason?: string | null;
    keep: boolean;
};

export type BillExecutiveQuickWin = {
    action: string;
    time: string;
    saving: number;
    risk: "None" | "Low" | "Medium" | "High" | string;
};

export type BillExecutiveRoadmapPhase = {
    phase: string;
    timeframe: string;
    actions: string[];
    expected_saving_min: number;
    expected_saving_max: number;
};

export type BillExecutiveCrossCloudComparison = {
    service: string;
    aws_current: number | null;
    aws_optimised: number | null;
    gcp: number | null;
    azure: number | null;
};

export type BillExecutiveClientScripts = {
    opening: string;
    explain_biggest_issue: string;
    handle_objection: string;
    closing: string;
};

export type BillExecutiveReport = {
    headline: string;
    waste_grade: "A" | "B" | "C" | "D" | "F";
    waste_score: number;
    waste_grade_explanation: string;
    total_spend: number;
    existing_savings_active: number;
    additional_savings_min: number;
    additional_savings_max: number;
    optimised_bill_min: number;
    optimised_bill_max: number;
    annual_savings_min: number;
    annual_savings_max: number;
    reduction_pct_min: number;
    reduction_pct_max: number;
    findings: BillExecutiveFinding[];
    quick_wins: BillExecutiveQuickWin[];
    roadmap: BillExecutiveRoadmapPhase[];
    cross_cloud_comparison: BillExecutiveCrossCloudComparison[];
    executive_summary: string;
    client_scripts: BillExecutiveClientScripts;
    implementation_timeline_days: number;
    confidence: "high" | "medium" | "low";
    benchmark_context: string;
    analysis_source: string;
    verification_status: string;
};

export type BillAnalysisRecord = {
    id: string;
    analysis_id?: string;
    status: string;
    source_type: string;
    filename: string;
    provider: string;
    provider_detected: string;
    source_format: string;
    source_parser: string;
    rows_parsed: number;
    total_analyzed_spend: number;
    total_potential_savings: number;
    currency: string;
    spend_by_category: Record<string, number>;
    top_services: BillAnalysisTopService[];
    discounts_applied: Record<string, string>;
    arbitrage_opportunities: BillAnalysisOpportunity[];
    executive_report?: BillExecutiveReport | null;
    cloudfront_insights?: {
        summary?: {
            total_monthly_savings_available?: number;
            opportunities_count?: number;
        };
        opportunities?: Array<Record<string, unknown>>;
    } | null;
    gpu_insights?: {
        total_gpu_spend: number;
        total_potential_savings: number;
        gpu_instances_found: Array<{ sku: string; cost: number }>;
        arbitrage_opportunities: Array<{ gpu_type: string; savings: number; alternative_cloud: string }>;
        ghost_gpus: Array<{ sku: string; cost: number; message: string }>;
    } | null;
    source_metadata: Record<string, unknown>;
    top_categories?: string[];
    created_at: string;
};

type BackendReportsListResponse = {
    reports: BackendReportRecord[];
    count: number;
};

type BackendQueryValue = string | number | null | undefined;

type FinanceQueryOptions = {
    scope?: FinanceScope;
    integrationId?: string;
    days?: number;
};

type CreateReportOptions = {
    reportType: BackendReportType;
    startDate?: string;
    endDate?: string;
};

export type CreateBackendIntegrationRequest = {
    provider: "aws" | "azure" | "gcp";
    name: string;
    regions?: string[];
    auth_type?: "role" | "keys";
    role_arn?: string;
    external_id?: string;
    access_key_id?: string;
    secret_access_key?: string;
    tenant_id?: string;
    client_id?: string;
    client_secret?: string;
    subscription_id?: string;
    project_id?: string;
    service_account_email?: string;
    private_key?: string;
    billing_export_table?: string;
};

export type CreateAutomatedSyncIntegrationRequest = {
    provider: "aws" | "azure" | "gcp";
    storage_path: string;
    credential: string;
    aws_discount?: number;
    azure_discount?: number;
    gcp_discount?: number;
};

export type BackendStatsResponse = {
    total_spend: number;
    potential_savings: number;
    active_resources_count: number;
    ai_confidence_score: number;
    carbon_footprint_kg: number;
    cost_of_inaction_6mo: number;
};

export type BackendResourcesResponse = {
    resources: Record<string, unknown>[];
    count: number;
};

export type BackendSpendHistoryPoint = {
    spend_date: string;
    amount: number;
};

export type BackendSpendHistoryResponse = {
    history: BackendSpendHistoryPoint[];
    count: number;
    days_requested: number;
};

export type BackendNotificationRecord = {
    id: string;
    recommendation: string;
    metadata?: Record<string, unknown>;
    created_at: string;
    status: string;
    type: string;
    resource_id: string;
    action?: string;
    [key: string]: unknown;
};

export type BackendNotificationsResponse = {
    notifications: BackendNotificationRecord[];
    count: number;
};

export type BackendWasteDistributionItem = {
    category_name: string;
    value: number;
};

export type BackendWasteDistributionResponse = {
    waste_distribution: BackendWasteDistributionItem[];
    count: number;
};

export type BackendGovernancePolicy = {
    id: string;
    name: string;
    status: "Pass" | "Fail";
    severity: "Critical" | "High" | "Medium" | "Low";
    reason: string;
    framework: string;
};

export type BackendGovernancePolicyRecord = {
    id: string;
    name: string;
    description: string;
    policy_type: string;
    is_active: boolean;
    compliance_rate: number;
    violations: number;
    created_at: string;
};

export type BackendGovernanceTrendPoint = {
    date: string;
    score: number;
};

export type BackendGovernanceFrameworkSummaryItem = {
    framework: string;
    pass: number;
    fail: number;
    total: number;
};

export type BackendGovernanceAgentNotification = {
    id: string;
    recommendation: string;
    status: string;
    type: string;
    resource_id: string;
    created_at: string;
    metadata: Record<string, unknown>;
};

export type BackendGovernanceSecurityResource = {
    id: string;
    resource_id: string;
    resource_name: string;
    resource_type: string;
    provider: string;
    region: string;
    status: string;
};

export type BackendGovernancePolicyViolation = {
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
};

export type BackendGovernanceAnalysisResponse = {
    score: {
        value: number;
        trend: "up" | "down" | "stable";
        rating: "Excellent" | "Good" | "Fair" | "Critical";
    };
    tagging: {
        missingTags: number;
        costImpact: number;
        assets: Array<{
            id: string;
            name: string;
            missing: string[];
        }>;
    };
    budget: {
        projectedSpend: number;
        budgetLimit: number;
        burnRate: number;
        status: "Safe" | "Warning" | "Excess";
        alert: string;
    };
    officeHours: {
        savings: number;
        enabled: boolean;
        recommendation: string;
    };
    policies: BackendGovernancePolicy[];
    trends: BackendGovernanceTrendPoint[];
    frameworkSummary: BackendGovernanceFrameworkSummaryItem[];
    agentNotifications: BackendGovernanceAgentNotification[];
    resources: BackendGovernanceSecurityResource[];
    policyViolations: BackendGovernancePolicyViolation[];
};

export type BackendGovernancePoliciesResponse = {
    policies: BackendGovernancePolicyRecord[];
    count: number;
};

export type BackendSecurityPostureRating = "No data" | "Strong" | "Moderate" | "Weak" | "Critical";

export type BackendSecurityPostureSummary = {
    score: number;
    rating: BackendSecurityPostureRating;
    critical: number;
    high: number;
    open: number;
    exposed_resources: number;
    monitored_resources: number;
    last_detected_at?: string | null;
};

export type BackendSecurityBreakdownItem = {
    name: string;
    count: number;
};

export type BackendSecurityFinding = {
    id: string;
    resource_id: string;
    resource: string;
    provider: string;
    region: string;
    category: string;
    severity: "critical" | "high" | "medium" | "low" | "info";
    status: string;
    description: string;
    detected_at: string;
    source: "policy_violation" | "agent_notification";
    remediation: string;
};

export type BackendSecurityExposedResource = {
    id: string;
    resource_id: string;
    resource_name: string;
    resource_type: string;
    provider: string;
    region: string;
    highest_severity: "critical" | "high" | "medium" | "low" | "info";
    risk_count: number;
    exposure: string;
    status: string;
};

export type BackendSecurityPostureResponse = {
    summary: BackendSecurityPostureSummary;
    findingsBySeverity: BackendSecurityBreakdownItem[];
    findingsByCategory: BackendSecurityBreakdownItem[];
    activeFindings: BackendSecurityFinding[];
    exposedResources: BackendSecurityExposedResource[];
    recentAlerts: BackendSecurityFinding[];
};

async function getBackendAuthHeaders(): Promise<Record<string, string> | null> {
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext || !hasBackendAuthCandidate(BACKEND_URL, authContext)) {
            return null;
        }

        return buildBackendAuthHeaders(BACKEND_URL, authContext);
    } catch {
        if (process.env.NODE_ENV === "development") {
            console.error("Failed to get auth headers");
        }
    }

    return null;
}

function appendQueryParams(url: URL, query: Record<string, BackendQueryValue>) {
    for (const [key, value] of Object.entries(query)) {
        if (value === null || value === undefined || value === "") {
            continue;
        }

        url.searchParams.append(key, String(value));
    }
}

async function getBackendJson<T>(
    path: string,
    query: Record<string, BackendQueryValue> = {},
): Promise<T | null> {
    const headers = await getBackendAuthHeaders();
    if (!headers) {
        return null;
    }

    try {
        const url = new URL(`${BACKEND_URL}${path}`);
        appendQueryParams(url, query);

        const response = await fetch(url.toString(), {
            headers,
            next: { revalidate: 60 },
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => "");
            console.error(`[API] Backend request failed (${response.status}) for ${path}: ${errorText}`);
            return null;
        }

        return await response.json() as T;
    } catch (error) {
        console.error(`[API] Failed to fetch backend path ${path}:`, error);
        return null;
    }
}

async function postBackendJson<T>(
    path: string,
    body: Record<string, unknown>,
): Promise<{ data: T | null; error: string | null; status: number }> {
    const authContext = await getBackendAuthContext();
    const url = new URL(`${BACKEND_URL}${path}`);
    if (!authContext || !hasBackendAuthCandidate(url.toString(), authContext)) {
        return { data: null, error: "Unauthorized", status: 401 };
    }

    try {
        const response = await fetchWithBackendAuthFallback(fetch, url.toString(), {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
            cache: "no-store",
        }, authContext);

        if (!response.ok) {
            let errorMessage = `Backend request failed with status ${response.status}`;

            try {
                const errorPayload = await response.json();
                if (typeof errorPayload?.detail === "string" && errorPayload.detail.trim()) {
                    errorMessage = errorPayload.detail;
                }
            } catch {
                const errorText = await response.text().catch(() => "");
                if (errorText.trim()) {
                    errorMessage = errorText;
                }
            }

            console.error(`[API] Backend POST failed (${response.status}) for ${path}: ${errorMessage}`);
            return { data: null, error: errorMessage, status: response.status };
        }

        return {
            data: await response.json() as T,
            error: null,
            status: response.status,
        };
    } catch (error) {
        console.error(`[API] Failed to POST backend path ${path}:`, error);
        return { data: null, error: "Failed to reach backend service", status: 500 };
    }
}

async function deleteBackendJson(
    path: string,
): Promise<{ error: string | null; status: number }> {
    const authContext = await getBackendAuthContext();
    const url = new URL(`${BACKEND_URL}${path}`);
    if (!authContext || !hasBackendAuthCandidate(url.toString(), authContext)) {
        return { error: "Unauthorized", status: 401 };
    }

    try {
        const response = await fetchWithBackendAuthFallback(fetch, url.toString(), {
            method: "DELETE",
            cache: "no-store",
        }, authContext);

        if (response.ok) {
            return { error: null, status: response.status };
        }

        let errorMessage = `Backend request failed with status ${response.status}`;

        try {
            const errorPayload = await response.json();
            if (typeof errorPayload?.detail === "string" && errorPayload.detail.trim()) {
                errorMessage = errorPayload.detail;
            }
        } catch {
            const errorText = await response.text().catch(() => "");
            if (errorText.trim()) {
                errorMessage = errorText;
            }
        }

        console.error(`[API] Backend DELETE failed (${response.status}) for ${path}: ${errorMessage}`);
        return { error: errorMessage, status: response.status };
    } catch (error) {
        console.error(`[API] Failed to DELETE backend path ${path}:`, error);
        return { error: "Failed to reach backend service", status: 500 };
    }
}

/**
 * Trigger a resource scan on the Python backend.
 */
export async function triggerBackendScan(
    integrationId: string,
    tokenOrOptions?: string | null | TriggerScanOptions
) {
    let authContext = { token: null as string | null, userId: null as string | null };

    if (typeof tokenOrOptions === 'string' || tokenOrOptions === null) {
        authContext = {
            token: tokenOrOptions,
            userId: null,
        };
    } else if (tokenOrOptions) {
        authContext = {
            token: tokenOrOptions.token ?? null,
            userId: tokenOrOptions.userId ?? null,
        };
    }

    if (!authContext.token || !authContext.userId) {
        const sharedAuthContext = await getBackendAuthContext();
        authContext = {
            token: authContext.token ?? sharedAuthContext?.token ?? null,
            userId: authContext.userId ?? sharedAuthContext?.userId ?? null,
        };
    }

    const scanUrl = `${BACKEND_URL}/api/scan`;
    if (!hasBackendAuthCandidate(scanUrl, authContext)) {
        throw new Error('Unauthorized: No Clerk token available for backend scan');
    }

    console.log(`[API] Triggering scan for ${integrationId} on ${BACKEND_URL}`);

    try {
        const response = await fetchWithBackendAuthFallback(fetch, scanUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ integration_id: integrationId }),
        }, authContext);

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`[API] Backend scan failed (${response.status}): ${errorText}`);
            throw new Error(`Backend scan failed: ${response.status} ${errorText}`);
        }

        const data = await response.json();
        console.log(`[API] Scan triggered:`, data);
        return data;
    } catch (error) {
        console.error('[API] Failed to trigger backend scan:', error);
        throw error;
    }
}

/**
 * Combined dashboard summary — all data in one call.
 */
export interface DashboardSummaryResponse {
    stats: {
        total_spend: number;
        potential_savings: number;
        active_resources_count: number;
        ai_confidence_score: number;
        carbon_footprint_kg: number;
        cost_of_inaction_6mo: number;
    } | null;
    resources: Record<string, unknown>[];
    resource_count: number;
    waste_distribution: BackendWasteDistributionItem[];
    spend_history: BackendSpendHistoryPoint[];
    permission_alert: Record<string, unknown> | null;
    integrations: BackendIntegration[];
    integration_count: number;
}

export async function getDashboardSummary(): Promise<DashboardSummaryResponse | null> {
    return getBackendJson<DashboardSummaryResponse>("/api/dashboard/summary");
}

/**
 * Get dashboard stats from Python backend.
 */
export async function getBackendStats(integrationId?: string): Promise<BackendStatsResponse | null> {
    return getBackendJson<BackendStatsResponse>("/api/stats", {
        integration_id: integrationId,
    });
}

export async function getBackendResources(
    integrationId?: string,
): Promise<BackendResourcesResponse | null> {
    return getBackendJson<BackendResourcesResponse>("/api/resources", {
        integration_id: integrationId,
    });
}

export async function getBackendSpendHistory(
    days = 30,
    integrationId?: string,
): Promise<BackendSpendHistoryResponse | null> {
    return getBackendJson<BackendSpendHistoryResponse>("/api/spend-history", {
        days,
        integration_id: integrationId,
    });
}

export async function getBackendNotifications(
    status?: string,
): Promise<BackendNotificationsResponse | null> {
    return getBackendJson<BackendNotificationsResponse>("/api/notifications", {
        status,
    });
}

export async function getBackendWasteDistribution(
    integrationId?: string,
): Promise<BackendWasteDistributionResponse | null> {
    return getBackendJson<BackendWasteDistributionResponse>("/api/waste-distribution", {
        integration_id: integrationId,
    });
}

export async function getBackendGovernanceAnalysis(): Promise<BackendGovernanceAnalysisResponse | null> {
    return getBackendJson<BackendGovernanceAnalysisResponse>("/api/governance/analysis");
}

export async function getBackendGovernancePolicies(): Promise<BackendGovernancePoliciesResponse | null> {
    return getBackendJson<BackendGovernancePoliciesResponse>("/api/governance/policies");
}

export async function getBackendSecurityPosture(): Promise<BackendSecurityPostureResponse | null> {
    return getBackendJson<BackendSecurityPostureResponse>("/api/security/posture");
}

export async function getBackendIntegrations(): Promise<BackendIntegration[] | null> {
    const authContext = await getBackendAuthContext();
    const integrationsUrl = `${BACKEND_URL}/api/integrations`;
    if (!authContext || !hasBackendAuthCandidate(integrationsUrl, authContext)) {
        return null;
    }

    try {
        const response = await fetchWithBackendAuthFallback(fetch, integrationsUrl, {
            cache: "no-store",
        }, authContext);

        if (!response.ok) {
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error("Failed to fetch backend integrations:", error);
        return null;
    }
}

export async function createBackendIntegration(
    payload: CreateBackendIntegrationRequest,
): Promise<{ integration: BackendIntegration | null; error: string | null; status: number }> {
    const response = await postBackendJson<BackendIntegration>("/api/integrations", payload);
    return {
        integration: response.data,
        error: response.error,
        status: response.status,
    };
}

export async function createBackendAutomatedSyncIntegration(
    payload: CreateAutomatedSyncIntegrationRequest,
): Promise<{ integration: BackendIntegration | null; error: string | null; status: number }> {
    const response = await postBackendJson<BackendIntegration>("/api/integrations/automated-sync", payload);
    return {
        integration: response.data,
        error: response.error,
        status: response.status,
    };
}

export async function deleteBackendIntegration(
    integrationId: string,
): Promise<{ error: string | null; status: number }> {
    return deleteBackendJson(`/api/integrations/${encodeURIComponent(integrationId)}`);
}

export async function getFinanceForecast(options: FinanceQueryOptions = {}): Promise<FinanceForecastResponse | null> {
    return getBackendJson<FinanceForecastResponse>("/api/finance/forecast", {
        scope: options.scope ?? "portfolio",
        integration_id: options.integrationId,
        days: options.days ?? 60,
    });
}

export async function getFinanceSpendHistory(options: FinanceQueryOptions = {}): Promise<FinanceSpendHistoryResponse | null> {
    return getBackendJson<FinanceSpendHistoryResponse>("/api/finance/spend-history", {
        scope: options.scope ?? "portfolio",
        integration_id: options.integrationId,
        days: options.days ?? 60,
    });
}

export async function getFinanceSettings(): Promise<FinanceSettings | null> {
    return getBackendJson<FinanceSettings>("/api/finance/settings");
}

export async function getCommitments(): Promise<CloudCommitment[]> {
    const response = await getBackendJson<FinanceCommitmentsResponse>("/api/finance/commitments");
    return response?.commitments ?? [];
}

export async function getFinanceBudgetEvents(limit = 10): Promise<FinanceBudgetEvent[]> {
    const response = await getBackendJson<FinanceBudgetEventsResponse>("/api/finance/budget-events", {
        limit,
    });
    return response?.events ?? [];
}

export async function syncFinanceBudgetEvents(): Promise<number> {
    const response = await postBackendJson<{ events_created: number }>("/api/finance/budget-events/sync", {});
    return response.data?.events_created ?? 0;
}

export async function getBackendReports(): Promise<BackendReportRecord[]> {
    const response = await getBackendJson<BackendReportsListResponse>("/api/reports");
    return response?.reports ?? [];
}

export async function createBackendReport(options: CreateReportOptions): Promise<{
    report: BackendReportRecord | null;
    error: string | null;
}> {
    const response = await postBackendJson<BackendReportRecord>("/api/reports/generate", {
        report_type: options.reportType,
        start_date: options.startDate || undefined,
        end_date: options.endDate || undefined,
    });

    return {
        report: response.data,
        error: response.error,
    };
}

export async function getLatestBillAnalysis(): Promise<BillAnalysisRecord | null> {
    return getBackendJson<BillAnalysisRecord>("/api/bill-analyses/latest");
}

export async function getBillAnalyses(limit = 10): Promise<BillAnalysisRecord[]> {
    const response = await getBackendJson<{ analyses: BillAnalysisRecord[]; count: number }>("/api/bill-analyses", {
        limit,
    });
    return response?.analyses ?? [];
}

export async function getBillAnalysis(analysisId: string): Promise<BillAnalysisRecord | null> {
    return getBackendJson<BillAnalysisRecord>(`/api/bill-analyses/${encodeURIComponent(analysisId)}`);
}

/** @deprecated use SimulationEstimateResponseV2 for the simulator UI. */
export type FinanceEstimationResponse = {
    delta_monthly_cost: number;
    currency: string;
    summary: {
        total_resources: number;
        priced_resources: number;
        exact_pricing_resources: number;
        estimated_resources: number;
        usage_based_resources: number;
        unsupported_resources: number;
        unestimated_resources?: number;
    };
    resources: Array<{
        name: string;
        type: string;
        provider: string;
        region: string;
        action: string;
        resource_family: string;
        pricing_source: string;
        before: number;
        after: number;
        notes?: string;
    }>;
    unestimated_resources?: Array<{
        resource_address: string;
        resource_type: string;
        provider: string;
        region?: string | null;
        action: string;
        reason: string;
    }>;
};

export type PricedResource = {
    resource_address: string;
    resource_type: string;
    action: "create" | "update" | "delete" | "no-op";
    provider: "aws" | "azure" | "gcp" | "generic";
    region: string | null;
    resource_family: "compute" | "storage" | "network" | "database" | "serverless" | "kubernetes" | "other";
    before_monthly: number;
    after_monthly: number;
    delta_monthly: number;
    hourly_rate: number | null;
    pricing_source: "exact_api" | "heuristic_estimate" | "usage_based" | "unsupported";
    pricing_basis: string | null;
    confidence: "high" | "medium" | "low";
    notes: string | null;
    source_provenance: string | null;
};

export type UnestimatedResource = {
    resource_address: string;
    resource_type: string;
    provider: string;
    region?: string | null;
    action: string;
    reason: string;
};

export type BestPracticeFinding = {
    resource_address: string;
    finding_id: string;
    severity: "critical" | "high" | "medium" | "low";
    monthly_impact: number | null;
    annual_impact: number | null;
    evidence: string;
    remediation: string;
    confidence: "high" | "medium" | "low";
};

export type SimulationPolicyResult = {
    status: "pass" | "warn" | "fail";
    blocking_reasons: string[];
    warnings: string[];
    markdown_summary: string;
};

export type SimulationEstimateResponseV2 = {
    schema_version: "2026-04-simulator-v2";
    currency: "USD";
    monthly: { before: number; after: number; delta: number };
    annual: { before: number; after: number; delta: number };
    summary: {
        total_resources: number;
        priced_resources: number;
        exact_resources: number;
        estimated_resources: number;
        usage_based_resources: number;
        unestimated_resources: number;
    };
    resources: PricedResource[];
    unestimated_resources: UnestimatedResource[];
    findings: BestPracticeFinding[];
    policy: SimulationPolicyResult | null;
};

export type SimulationHistoryRun = {
    _id: string;
    id: string;
    source_type: "terraform_plan" | "commitment_scenario" | string;
    source_hash: string;
    filename: string | null;
    summary: SimulationEstimateResponseV2["summary"];
    monthly: SimulationEstimateResponseV2["monthly"];
    annual: SimulationEstimateResponseV2["annual"];
    findings_count: number;
    policy: SimulationPolicyResult | null;
    created_at: string;
};

export type SimulationHistoryResponse = {
    runs: SimulationHistoryRun[];
};

/**
 * Estimate the monthly cost impact of a Terraform plan.
 */
export async function estimateTerraformPlan(plan: Record<string, unknown>, filename?: string | null): Promise<{
    data: SimulationEstimateResponseV2 | null;
    error: string | null;
}> {
    const authContext = await getBackendAuthContext();
    const url = new URL(`${BACKEND_URL}/api/finance/estimate`);
    if (!authContext || !hasBackendAuthCandidate(url.toString(), authContext)) {
        return { data: null, error: "Unauthorized" };
    }

    try {
        const response = await fetchWithBackendAuthFallback(fetch, url.toString(), {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Simulator-Version": "v2",
            },
            body: JSON.stringify({ plan, filename: filename ?? undefined }),
            cache: "no-store",
        }, authContext);

        if (!response.ok) {
            let errorMessage = `Backend request failed with status ${response.status}`;

            try {
                const errorPayload = await response.json();
                if (typeof errorPayload?.detail === "string" && errorPayload.detail.trim()) {
                    errorMessage = errorPayload.detail;
                }
            } catch {
                const errorText = await response.text().catch(() => "");
                if (errorText.trim()) {
                    errorMessage = errorText;
                }
            }

            console.error(`[API] Backend simulator estimate failed (${response.status}): ${errorMessage}`);
            return { data: null, error: errorMessage };
        }

        return {
            data: await response.json() as SimulationEstimateResponseV2,
            error: null,
        };
    } catch (error) {
        console.error("[API] Failed to estimate Terraform plan:", error);
        return { data: null, error: "Failed to reach backend service" };
    }
}

export async function getSimulationHistory(): Promise<SimulationHistoryResponse | null> {
    return getBackendJson<SimulationHistoryResponse>("/api/finance/estimate/history");
}

/**
 * Get AWS architecture diagrams from Python backend.
 */
export async function getArchitecture(integrationId: string, region?: string, vpcId?: string, viewType: 'summary' | 'hotspots' | 'vpc_detail' = 'summary') {
    const { getToken } = await auth();
    const token = await getToken();

    if (!token) return null;

    try {
        const url = new URL(`${BACKEND_URL}/api/architecture/aws/current`);
        url.searchParams.append('integration_id', integrationId);
        url.searchParams.append('view', viewType);

        if (region) url.searchParams.append('region', region);
        if (vpcId) url.searchParams.append('vpc_id', vpcId);

        const response = await fetch(url.toString(), {
            headers: { 'Authorization': `Bearer ${token}` },
            cache: 'no-store' // Keep it fresh
        });

        if (!response.ok) {
            console.error(`Failed to fetch architecture: ${response.status}`);
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error('Failed to fetch backend architecture:', error);
        return null;
    }
}

/**
 * Get AWS architecture graph JSON (nodes + edges + coverage) from Python backend.
 */
export async function getArchitectureGraph(
    integrationId: string,
    provider: string,
    region?: string,
    view?: string,
    vpcId?: string,
): Promise<{ data: unknown } | { error: { status: number; detail: string } }> {
    const headers = await getBackendAuthHeaders();
    if (!headers) return { error: { status: 401, detail: 'Unauthorized' } };

    let architectureProvider: ArchitectureProvider;
    try {
        architectureProvider = normalizeArchitectureProvider(provider);
    } catch (error) {
        return {
            error: {
                status: 400,
                detail: error instanceof Error ? error.message : "Invalid architecture provider",
            },
        };
    }

    try {
        const url = new URL(`${BACKEND_URL}/api/architecture/${architectureProvider}/graph`);
        url.searchParams.set('integration_id', integrationId);
        if (region) url.searchParams.set('region', region);
        if (view) url.searchParams.set('view', view);
        if (vpcId) url.searchParams.set('vpc_id', vpcId);

        const response = await fetch(url.toString(), {
            headers,
            cache: 'no-store',
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`[API] Graph fetch failed (${response.status}): ${errorText}`);
            return { error: { status: response.status, detail: errorText } };
        }

        return { data: await response.json() };
    } catch (error) {
        console.error('[API] Failed to fetch architecture graph:', error);
        return { error: { status: 500, detail: String(error) } };
    }
}

/**
 * Generate proposed architecture via AI (POST).
 * Only called when user explicitly clicks "Generate".
 */
export async function generateProposedArchitecture(
    integrationId: string,
    provider: string,
    region: string,
    mode: string,
    constraints?: string[],
): Promise<{ data: unknown } | { error: { status: number; detail: string } }> {
    const headers = await getBackendAuthHeaders();
    if (!headers) return { error: { status: 401, detail: 'Unauthorized' } };

    let architectureProvider: ArchitectureProvider;
    try {
        architectureProvider = normalizeArchitectureProvider(provider);
    } catch (error) {
        return {
            error: {
                status: 400,
                detail: error instanceof Error ? error.message : "Invalid architecture provider",
            },
        };
    }

    try {
        const url = new URL(`${BACKEND_URL}/api/architecture/${architectureProvider}/proposed`);
        url.searchParams.set('integration_id', integrationId);
        url.searchParams.set('region', region);
        url.searchParams.set('mode', mode);

        const response = await fetch(url.toString(), {
            method: 'POST',
            headers: {
                ...headers,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ constraints: constraints ?? [] }),
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`[API] Proposed generation failed (${response.status}): ${errorText}`);
            return { error: { status: response.status, detail: errorText } };
        }

        return { data: await response.json() };
    } catch (error) {
        console.error('[API] Failed to generate proposed architecture:', error);
        return { error: { status: 500, detail: String(error) } };
    }
}
