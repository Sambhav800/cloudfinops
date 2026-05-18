export type Provider = "aws" | "azure" | "gcp" | "kubernetes" | "unknown";

export type NormalizedStatus = "healthy" | "zombie" | "waste" | "non_compliant" | "unknown";

export type CostStatus = "actual" | "catalog_estimate" | "unavailable" | "no_direct_charge";

export type ResourceRow = {
    id?: string | null;
    user_id: string;
    integration_id: string;
    provider: Provider;
    cloud_resource_id: string | null;
    resource_name: string;
    service_type: string;
    region: string;
    region_compliance: "compliant" | "non_compliant" | string;
    status: NormalizedStatus;
    waste_type: string | null;
    waste_reason: string | null;
    confidence_score: number;
    cost: number;
    cost_source: string;
    cost_status: CostStatus;
    cost_label: string;
    annual_cost_label: string;
    monthly_cost_available: boolean;
    carbon_footprint_kg: number;
    tags: Record<string, any>;
    metadata: Record<string, any>;
    metrics_data: Record<string, any>;
    governance_violations: any[];
    last_scanned_at: string | null;
    created_at?: string | null;
};

const VALID_PROVIDERS: ReadonlySet<Provider> = new Set([
    "aws",
    "azure",
    "gcp",
    "kubernetes",
    "unknown",
]);

const NON_COMPLIANT_WASTE_TYPES = new Set(["security_risk", "governance_violation"]);
const WASTE_WASTE_TYPES = new Set(["orphan_disk", "orphan_nic", "stopped_vm", "deallocated_vm", "waste"]);
const COMPLIANCE_VALUES = new Set(["compliant", "non_compliant", "shadow_it"]);
const NO_DIRECT_CHARGE_SOURCE_VALUES = new Set(["no_direct_charge", "included", "free"]);
const BILLING_UNAVAILABLE_SOURCE_VALUES = new Set(["billing_unavailable", "pricing_unavailable", "unknown"]);
const CATALOG_ESTIMATE_SOURCE_VALUES = new Set(["catalog_estimate", "estimated"]);
const RESOURCE_LEVEL_COST_UNAVAILABLE_LABEL = "No resource-level cost match";
export const DISPLAY_CURRENCY = "INR";
export const DISPLAY_LOCALE = "en-IN";
const DEFAULT_USD_TO_INR_RATE = 83;
const NO_DIRECT_CHARGE_SERVICE_PATTERNS = [
    "gcp service",
    "gcp route",
    "gcp firewall",
    "gcp network",
    "gcp subnetwork",
    "gcp serviceaccount",
    "gcp service account",
    "gcp serviceaccountkey",
    "gcp service account key",
    "gcp project",
    "gcp namespace",
    "gcp entrygroup",
    "gcp entry group",
    "gcp logbucket",
    "gcp log bucket",
    "gcp quotapreference",
    "gcp projectbillinginfo",
    "gcp internalrange",
    "security group",
    "security-group-rule",
    "network security group",
    "route table",
    "internet gateway",
    "network acl",
    "dhcp options",
    "key pair",
    "iam user",
    "iam role",
    "vpc",
    "subnet",
    "firewall",
    "service account",
    "network-interface",
    "resource-explorer",
    "athena:datacatalog",
    "athena:workgroup",
    "payments",
];

function asRecord(value: unknown): Record<string, any> {
    return value && typeof value === "object" && !Array.isArray(value)
        ? (value as Record<string, any>)
        : {};
}

function normalizeString(value: unknown): string {
    if (typeof value === "string") {
        return value.trim();
    }

    if (value == null) {
        return "";
    }

    return String(value).trim();
}

function normalizeNullableString(value: unknown): string | null {
    const normalized = normalizeString(value);
    return normalized ? normalized : null;
}

function normalizeNumber(value: unknown): number {
    const parsed = typeof value === "number"
        ? value
        : typeof value === "string"
            ? Number(value)
            : 0;

    return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeCurrencyCode(value: unknown): string {
    return normalizeString(value).toUpperCase();
}

function getUsdToInrRate(): number {
    const configuredRate = Number(process.env.NEXT_PUBLIC_USD_TO_INR_RATE);
    return Number.isFinite(configuredRate) && configuredRate > 0
        ? configuredRate
        : DEFAULT_USD_TO_INR_RATE;
}

export function toDisplayInrAmount(value: unknown, sourceCurrency = DISPLAY_CURRENCY): number {
    const amount = normalizeNumber(value);
    const currency = normalizeCurrencyCode(sourceCurrency);
    if (currency === "USD") {
        return Math.round(amount * getUsdToInrRate() * 100) / 100;
    }
    return Math.round(amount * 100) / 100;
}

export function formatInrCurrency(
    value: unknown,
    options: Intl.NumberFormatOptions = {},
): string {
    const amount = normalizeNumber(value);
    const defaultFractionDigits = Math.abs(amount) >= 1000 ? 0 : 2;

    return new Intl.NumberFormat(DISPLAY_LOCALE, {
        style: "currency",
        currency: DISPLAY_CURRENCY,
        minimumFractionDigits: defaultFractionDigits,
        maximumFractionDigits: defaultFractionDigits,
        ...options,
    }).format(amount);
}

function normalizeCostSource(value: unknown): string {
    return normalizeString(value).toLowerCase();
}

function normalizeProvider(value: unknown): Provider {
    const normalized = normalizeString(value).toLowerCase();
    return VALID_PROVIDERS.has(normalized as Provider)
        ? (normalized as Provider)
        : "unknown";
}

function normalizeStatus(rawStatus: unknown, wasteType: string | null): NormalizedStatus {
    const normalizedWasteType = normalizeString(wasteType).toLowerCase();

    if (normalizedWasteType) {
        if (NON_COMPLIANT_WASTE_TYPES.has(normalizedWasteType)) {
            return "non_compliant";
        }

        if (normalizedWasteType.includes("zombie")) {
            return "zombie";
        }

        if (WASTE_WASTE_TYPES.has(normalizedWasteType)) {
            return "waste";
        }
    }

    switch (normalizeString(rawStatus).toLowerCase()) {
        case "healthy":
        case "active":
            return "healthy";
        case "zombie":
            return "zombie";
        case "waste":
            return "waste";
        case "non_compliant":
            return "non_compliant";
        case "":
        case "unknown":
            return "unknown";
        default:
            return "unknown";
    }
}

function isNoDirectChargeResource(serviceType: string, metadata: Record<string, any>): boolean {
    const service = normalizeString(serviceType).toLowerCase();
    const source = normalizeCostSource(metadata.cost_source);
    if (NO_DIRECT_CHARGE_SOURCE_VALUES.has(source)) {
        return true;
    }

    return NO_DIRECT_CHARGE_SERVICE_PATTERNS.some((pattern) => service.includes(pattern));
}

function resolveCostStatus(
    cost: number,
    serviceType: string,
    metadata: Record<string, any>,
): CostStatus {
    const source = normalizeCostSource(metadata.cost_source);
    if (source === "actual") {
        return "actual";
    }
    if (CATALOG_ESTIMATE_SOURCE_VALUES.has(source) && cost > 0) {
        return "catalog_estimate";
    }
    if (isNoDirectChargeResource(serviceType, metadata)) {
        return "no_direct_charge";
    }
    if (BILLING_UNAVAILABLE_SOURCE_VALUES.has(source) || cost === 0) {
        return "unavailable";
    }
    return "unavailable";
}

function resolveResourceCostCurrency(
    provider: Provider,
    row: Record<string, any>,
    metadata: Record<string, any>,
): string {
    return normalizeCurrencyCode(metadata.currency)
        || normalizeCurrencyCode(metadata.billing_currency)
        || normalizeCurrencyCode(row.currency)
        || normalizeCurrencyCode(row.cost_currency)
        || (provider === "aws" || provider === "azure" ? "USD" : DISPLAY_CURRENCY);
}

function formatCostLabel(cost: number, status: CostStatus): string {
    if (status === "actual") {
        return `MTD actual ${formatInrCurrency(cost)}`;
    }
    if (status === "catalog_estimate") {
        return `Catalog/mo est. ${formatInrCurrency(cost)}`;
    }
    if (status === "no_direct_charge") {
        return "No direct charge";
    }
    return RESOURCE_LEVEL_COST_UNAVAILABLE_LABEL;
}

function formatAnnualCostLabel(cost: number, status: CostStatus): string {
    if (status === "actual") {
        return "Forecast view";
    }
    if (status === "catalog_estimate") {
        return `Catalog/yr est. ${formatInrCurrency(cost * 12, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
    }
    if (status === "no_direct_charge") {
        return "No direct charge";
    }
    return RESOURCE_LEVEL_COST_UNAVAILABLE_LABEL;
}

function createEmptyResourceRow(): ResourceRow {
    return {
        id: null,
        user_id: "",
        integration_id: "",
        provider: "unknown",
        cloud_resource_id: null,
        resource_name: "Unknown Resource",
        service_type: "Unknown",
        region: "global",
        region_compliance: "compliant",
        status: "unknown",
        waste_type: null,
        waste_reason: null,
        confidence_score: 0,
        cost: 0,
        cost_source: "",
        cost_status: "unavailable",
        cost_label: RESOURCE_LEVEL_COST_UNAVAILABLE_LABEL,
        annual_cost_label: RESOURCE_LEVEL_COST_UNAVAILABLE_LABEL,
        monthly_cost_available: false,
        carbon_footprint_kg: 0,
        tags: {},
        metadata: {},
        metrics_data: {},
        governance_violations: [],
        last_scanned_at: null,
        created_at: null,
    };
}

export function normalizeResourceRow(input: any): ResourceRow {
    try {
        const row = asRecord(input);
        const metadata = asRecord(row.metadata);
        const tags = asRecord(row.tags);
        const metricsData = asRecord(row.metrics_data);

        let regionCompliance = normalizeString(row.region_compliance) || "compliant";
        let region = normalizeString(row.region);

        if (!region && typeof metadata.aws_region === "string" && metadata.aws_region.trim()) {
            region = metadata.aws_region.trim();
        }

        const normalizedCompliance = regionCompliance.toLowerCase();
        if ((!region || region === "unknown" || region === "global")
            && regionCompliance
            && !COMPLIANCE_VALUES.has(normalizedCompliance)) {
            region = regionCompliance;
            regionCompliance = "compliant";
        }

        if (metadata.is_shadow_it === true) {
            regionCompliance = "shadow_it";
        }

        const wasteType = normalizeNullableString(row.waste_type);
        const serviceType = normalizeString(row.service_type || row.resource_type) || "Unknown";
        const provider = normalizeProvider(row.provider);
        const rawCost = normalizeNumber(row.cost ?? row.monthly_cost);
        const cost = toDisplayInrAmount(rawCost, resolveResourceCostCurrency(provider, row, metadata));
        const costStatus = resolveCostStatus(rawCost, serviceType, metadata);
        const costSource = normalizeCostSource(metadata.cost_source);

        return {
            ...createEmptyResourceRow(),
            id: normalizeNullableString(row.id),
            user_id: normalizeString(row.user_id),
            integration_id: normalizeString(row.integration_id),
            provider,
            cloud_resource_id: normalizeNullableString(row.cloud_resource_id),
            resource_name: normalizeString(row.resource_name || row.name || row.cloud_resource_id) || "Unknown Resource",
            service_type: serviceType,
            region: region || "global",
            region_compliance: regionCompliance || "compliant",
            status: normalizeStatus(row.status, wasteType),
            waste_type: wasteType,
            waste_reason: normalizeNullableString(row.waste_reason),
            confidence_score: normalizeNumber(row.confidence_score),
            cost,
            cost_source: costSource,
            cost_status: costStatus,
            cost_label: formatCostLabel(cost, costStatus),
            annual_cost_label: formatAnnualCostLabel(cost, costStatus),
            monthly_cost_available: costStatus === "actual",
            carbon_footprint_kg: normalizeNumber(row.carbon_footprint_kg),
            tags,
            metadata,
            metrics_data: metricsData,
            governance_violations: Array.isArray(row.governance_violations) ? row.governance_violations : [],
            last_scanned_at: normalizeNullableString(row.last_scanned_at),
            created_at: normalizeNullableString(row.created_at),
        };
    } catch {
        return createEmptyResourceRow();
    }
}

export function normalizeResourceRows(list: any[]): ResourceRow[] {
    if (!Array.isArray(list)) {
        return [];
    }

    return list.map((item) => normalizeResourceRow(item));
}
