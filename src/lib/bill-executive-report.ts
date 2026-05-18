import type {
    BillExecutiveCrossCloudComparison,
    BillExecutiveFinding,
    BillExecutiveFindingAction,
    BillExecutiveQuickWin,
    BillExecutiveReport,
    BillExecutiveRoadmapPhase,
} from "@/lib/api";

function asObject(value: unknown): Record<string, unknown> | null {
    return value && typeof value === "object" && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : null;
}

function asString(value: unknown, fallback = ""): string {
    return typeof value === "string" ? value : fallback;
}

function asNumber(value: unknown, fallback = 0): number {
    return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asStringArray(value: unknown): string[] {
    return Array.isArray(value)
        ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
        : [];
}

function scoreToGrade(score: number): BillExecutiveReport["waste_grade"] {
    if (score <= 20) return "A";
    if (score <= 40) return "B";
    if (score <= 60) return "C";
    if (score <= 80) return "D";
    return "F";
}

function normalizeFindingAction(value: unknown): BillExecutiveFindingAction | null {
    const raw = asObject(value);
    if (!raw) {
        return null;
    }

    return {
        name: asString(raw.name, "Review service usage"),
        difficulty: asString(raw.difficulty, "Medium"),
        time_required: asString(raw.time_required, "1 day"),
        monthly_saving_min: asNumber(raw.monthly_saving_min),
        monthly_saving_max: asNumber(raw.monthly_saving_max),
        risk: asString(raw.risk, "Low"),
        savings_source: asString(raw.savings_source) || null,
        validation_required: Boolean(raw.validation_required),
        calculation: asString(raw.calculation) || null,
        evidence_lines: asStringArray(raw.evidence_lines),
        confidence_reason: asString(raw.confidence_reason) || null,
    };
}

function normalizeFinding(value: unknown): BillExecutiveFinding | null {
    const raw = asObject(value);
    if (!raw) {
        return null;
    }

    const howToFix = asStringArray(raw.how_to_fix);
    const actions = Array.isArray(raw.actions)
        ? raw.actions
            .map((item) => normalizeFindingAction(item))
            .filter((item): item is BillExecutiveFindingAction => item !== null)
        : [];

    return {
        rank: asNumber(raw.rank, 0),
        service: asString(raw.service, "Unknown Service"),
        monthly_cost: asNumber(raw.monthly_cost),
        pct_of_bill: asNumber(raw.pct_of_bill),
        severity: asString(raw.severity, "medium") as BillExecutiveFinding["severity"],
        title: asString(raw.title, "Review this service line item"),
        what_we_found: asString(raw.what_we_found),
        why_inefficient: asString(raw.why_inefficient),
        how_to_fix: howToFix,
        actions,
        savings_source: asString(raw.savings_source) || null,
        validation_required: Boolean(raw.validation_required),
        calculation: asString(raw.calculation) || null,
        evidence_lines: asStringArray(raw.evidence_lines),
        confidence_reason: asString(raw.confidence_reason) || null,
        keep: Boolean(raw.keep),
    };
}

function normalizeQuickWin(value: unknown): BillExecutiveQuickWin | null {
    const raw = asObject(value);
    if (!raw) {
        return null;
    }

    return {
        action: asString(raw.action, "Review the highest-value action"),
        time: asString(raw.time, "1 day"),
        saving: asNumber(raw.saving),
        risk: asString(raw.risk, "Low"),
    };
}

function normalizeRoadmapPhase(value: unknown): BillExecutiveRoadmapPhase | null {
    const raw = asObject(value);
    if (!raw) {
        return null;
    }

    const actions = Array.isArray(raw.actions)
        ? raw.actions.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
        : [];

    return {
        phase: asString(raw.phase, "Phase"),
        timeframe: asString(raw.timeframe, "TBD"),
        actions,
        expected_saving_min: asNumber(raw.expected_saving_min),
        expected_saving_max: asNumber(raw.expected_saving_max),
    };
}

function normalizeComparisonRow(value: unknown): BillExecutiveCrossCloudComparison | null {
    const raw = asObject(value);
    if (!raw) {
        return null;
    }

    return {
        service: asString(raw.service, "Other"),
        aws_current: raw.aws_current == null ? null : asNumber(raw.aws_current),
        aws_optimised: raw.aws_optimised == null ? null : asNumber(raw.aws_optimised),
        gcp: raw.gcp == null ? null : asNumber(raw.gcp),
        azure: raw.azure == null ? null : asNumber(raw.azure),
    };
}

/**
 * Maps spaceless-lowercase service names → canonical spelling.
 * Used to fix PDF extraction artifacts like "Elastic Load Balan cing U SD".
 */
const CANONICAL_SERVICES: Record<string, string> = {
    elasticloadbalancing: "Elastic Load Balancing",
    relationaldatabaseservice: "Relational Database Service",
    virtualprivatecloud: "Virtual Private Cloud",
    elasticcomputecloud: "Elastic Compute Cloud",
    elasticache: "ElastiCache",
    keymanagementservice: "Key Management Service",
    cloudwatch: "CloudWatch",
    secretsmanager: "Secrets Manager",
    simplenotificationservice: "Simple Notification Service",
    simplestorageservice: "Simple Storage Service",
    simplequeueservice: "Simple Queue Service",
    simpleemailservice: "Simple Email Service",
    cloudfront: "CloudFront",
    cloudtrail: "CloudTrail",
    cloudformation: "CloudFormation",
    dynamodb: "DynamoDB",
    eventbridge: "EventBridge",
    guardduty: "GuardDuty",
    opensearch: "OpenSearch",
    opensearchservice: "OpenSearch Service",
    redshift: "Redshift",
    sagemaker: "SageMaker",
    stepfunctions: "Step Functions",
    systemsmanager: "Systems Manager",
    directconnect: "Direct Connect",
    elasticbeanstalk: "Elastic Beanstalk",
    elasticfilesystem: "Elastic File System",
    elasticblockstore: "Elastic Block Store",
    elastickubernetesservice: "Elastic Kubernetes Service",
    elasticcontainerservice: "Elastic Container Service",
    elasticcontainerregistry: "Elastic Container Registry",
    elasticmapreduce: "Elastic MapReduce",
    applicationloadbalancer: "Application Load Balancer",
    networkloadbalancer: "Network Load Balancer",
    gatewayloadbalancer: "Gateway Load Balancer",
    savingsplansdiscounts: "Savings Plans Discounts",
    datatransfer: "Data Transfer",
    certificatemanager: "Certificate Manager",
    configservice: "Config Service",
    costexplorer: "Cost Explorer",
    webapplicationfirewall: "Web Application Firewall",
    apprunner: "App Runner",
    appsync: "AppSync",
    appflow: "AppFlow",
};

const CANONICAL_KEYS_SORTED = Object.keys(CANONICAL_SERVICES).sort(
    (a, b) => b.length - a.length,
);

/**
 * Clean a single service name using dictionary lookup.
 * Strips trailing USD artifacts, collapses whitespace, matches canonical form.
 */
export function cleanServiceName(raw: string): string {
    if (!raw) return raw;

    const cleaned = raw.replace(/[\s]*U[\s]*S[\s]*D[\s]*$/i, "").trim();
    if (!cleaned) return raw.trim();

    const spaceless = cleaned.replace(/\s+/g, "").toLowerCase();

    for (const key of CANONICAL_KEYS_SORTED) {
        if (spaceless === key) {
            return CANONICAL_SERVICES[key];
        }
        if (spaceless.startsWith(key)) {
            // Reconstruct suffix from original string
            let charCount = 0;
            let suffixStart = cleaned.length;
            for (let i = 0; i < cleaned.length; i++) {
                if (cleaned[i] === " ") continue;
                charCount++;
                if (charCount >= key.length) {
                    suffixStart = i + 1;
                    break;
                }
            }
            const suffix = cleaned.slice(suffixStart).trim();
            if (suffix) {
                return `${CANONICAL_SERVICES[key]} ${suffix}`;
            }
            return CANONICAL_SERVICES[key];
        }
    }

    return cleaned;
}

/**
 * Build a replacement map from dirty → clean service names found in findings,
 * then apply replacements to any text string.
 */
function buildServiceReplacements(findings: BillExecutiveFinding[]): Array<[RegExp, string]> {
    const replacements: Array<[RegExp, string]> = [];
    for (const f of findings) {
        const dirty = f.service;
        const clean = cleanServiceName(dirty);
        if (dirty !== clean && dirty.length > 3) {
            replacements.push([
                new RegExp(dirty.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g"),
                clean,
            ]);
        }
    }
    return replacements;
}

function cleanText(text: string | null, replacements: Array<[RegExp, string]>): string {
    if (!text) return text ?? "";
    let result = text;
    for (const [pattern, replacement] of replacements) {
        result = result.replace(pattern, replacement);
    }
    return result;
}

export function normalizeBillExecutiveReport(report: unknown): BillExecutiveReport | null {
    const raw = asObject(report);
    if (!raw) {
        return null;
    }

    if (
        !Array.isArray(raw.findings)
        || !Array.isArray(raw.quick_wins)
        || !Array.isArray(raw.roadmap)
        || !Array.isArray(raw.cross_cloud_comparison)
    ) {
        return null;
    }

    const clientScripts = asObject(raw.client_scripts);
    if (!clientScripts) {
        return null;
    }

    const findings = raw.findings
        .map((item) => normalizeFinding(item))
        .filter((item): item is BillExecutiveFinding => item !== null);
    const quickWins = raw.quick_wins
        .map((item) => normalizeQuickWin(item))
        .filter((item): item is BillExecutiveQuickWin => item !== null);
    const roadmap = raw.roadmap
        .map((item) => normalizeRoadmapPhase(item))
        .filter((item): item is BillExecutiveRoadmapPhase => item !== null);
    const crossCloudComparison = raw.cross_cloud_comparison
        .map((item) => normalizeComparisonRow(item))
        .filter((item): item is BillExecutiveCrossCloudComparison => item !== null);
    const wasteScore = asNumber(raw.waste_score);
    const reportedGrade = asString(raw.waste_grade).toUpperCase();
    const wasteGrade = (["A", "B", "C", "D", "F"].includes(reportedGrade)
        ? reportedGrade
        : scoreToGrade(wasteScore)) as BillExecutiveReport["waste_grade"];

    // Build replacement map from dirty → clean service names, then apply
    const serviceReplacements = buildServiceReplacements(findings);

    // Clean service names in finding objects
    for (const f of findings) {
        f.service = cleanServiceName(f.service);
        f.title = cleanText(f.title, serviceReplacements);
        f.what_we_found = cleanText(f.what_we_found, serviceReplacements);
        f.why_inefficient = cleanText(f.why_inefficient, serviceReplacements);
        f.how_to_fix = f.how_to_fix.map((step) => cleanText(step, serviceReplacements));
    }

    // Clean quick wins
    for (const qw of quickWins) {
        qw.action = cleanText(qw.action, serviceReplacements);
    }

    // Clean roadmap phases
    for (const phase of roadmap) {
        phase.phase = cleanText(phase.phase, serviceReplacements);
        phase.actions = phase.actions.map((a) => cleanText(a, serviceReplacements));
    }

    // Clean cross-cloud rows
    for (const row of crossCloudComparison) {
        row.service = cleanServiceName(row.service);
    }

    return {
        headline: cleanText(asString(raw.headline), serviceReplacements),
        waste_grade: wasteGrade,
        waste_score: wasteScore,
        waste_grade_explanation: cleanText(asString(raw.waste_grade_explanation), serviceReplacements),
        total_spend: asNumber(raw.total_spend),
        existing_savings_active: asNumber(raw.existing_savings_active),
        additional_savings_min: asNumber(raw.additional_savings_min),
        additional_savings_max: asNumber(raw.additional_savings_max),
        optimised_bill_min: asNumber(raw.optimised_bill_min),
        optimised_bill_max: asNumber(raw.optimised_bill_max),
        annual_savings_min: asNumber(raw.annual_savings_min),
        annual_savings_max: asNumber(raw.annual_savings_max),
        reduction_pct_min: asNumber(raw.reduction_pct_min),
        reduction_pct_max: asNumber(raw.reduction_pct_max),
        findings,
        quick_wins: quickWins,
        roadmap,
        cross_cloud_comparison: crossCloudComparison,
        executive_summary: cleanText(asString(raw.executive_summary), serviceReplacements),
        client_scripts: {
            opening: cleanText(asString(clientScripts.opening), serviceReplacements),
            explain_biggest_issue: cleanText(asString(clientScripts.explain_biggest_issue), serviceReplacements),
            handle_objection: cleanText(asString(clientScripts.handle_objection), serviceReplacements),
            closing: cleanText(asString(clientScripts.closing), serviceReplacements),
        },
        implementation_timeline_days: asNumber(raw.implementation_timeline_days),
        confidence: asString(raw.confidence, "medium") as BillExecutiveReport["confidence"],
        benchmark_context: cleanText(asString(raw.benchmark_context), serviceReplacements),
        analysis_source: asString(raw.analysis_source, "unknown"),
        verification_status: asString(raw.verification_status, "unknown"),
    };
}


export function hasRenderableBillExecutiveReport(report: unknown): boolean {
    return normalizeBillExecutiveReport(report) !== null;
}
