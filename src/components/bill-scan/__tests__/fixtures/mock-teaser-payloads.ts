/**
 * Mock TeaserReportPayload factories for bill-scan E2E smoke tests.
 *
 * These produce structurally complete payloads that mirror the real backend
 * response shape from POST /api/scan/public-upload, allowing tests to verify
 * rendering logic without hitting the network.
 */

import type { TeaserReportPayload, FindingTeaser, WasteGrade } from "../../types";

/* ─── Individual finding factories ─── */

function finding(overrides: Partial<FindingTeaser> = {}): FindingTeaser {
    return {
        service: "Amazon EC2",
        cost: 4250.0,
        pct_of_total: 33.1,
        what_we_found:
            "Your EC2 fleet has 14 instances running 24/7, but utilization averages only 12% during off-peak hours.",
        optimization_options:
            "Right-size to t3.medium, enable auto-scaling, consider Savings Plans for baseline load.",
        risk_level: "high",
        category: "Compute",
        estimated_impact: 637.5,
        ...overrides,
    };
}

/* ─── 8-service payload — proves report renders ALL services (not capped at 3) ─── */

const EIGHT_SERVICE_FINDINGS: FindingTeaser[] = [
    finding({ service: "Amazon EC2", cost: 4250.0, pct_of_total: 33.1, risk_level: "high", category: "Compute" }),
    finding({ service: "Amazon RDS", cost: 2890.5, pct_of_total: 22.5, risk_level: "high", category: "Database",
        what_we_found: "Multi-AZ RDS instances with provisioned IOPS running at 8% average CPU.",
        optimization_options: "Switch to Aurora Serverless v2, eliminate unused read replicas." }),
    finding({ service: "Amazon S3", cost: 1245.0, pct_of_total: 9.7, risk_level: "medium", category: "Storage",
        what_we_found: "85% of objects are in S3 Standard with no lifecycle policies.",
        optimization_options: "Enable Intelligent-Tiering, add lifecycle rules for infrequent access." }),
    finding({ service: "Amazon CloudFront", cost: 980.75, pct_of_total: 7.6, risk_level: "low", category: "Networking",
        what_we_found: "CloudFront distributions with sub-optimal cache hit ratio of 62%.",
        optimization_options: "Increase default TTL, enable Origin Shield." }),
    finding({ service: "Elastic Load Balancing", cost: 1520.3, pct_of_total: 11.8, risk_level: "medium", category: "Networking",
        what_we_found: "Multiple idle ALBs with <100 req/min detected.",
        optimization_options: "Consolidate ALBs, remove unused target groups." }),
    finding({ service: "Amazon DynamoDB", cost: 875.2, pct_of_total: 6.8, risk_level: "low", category: "Database",
        what_we_found: "Provisioned capacity tables with auto-scaling disabled.",
        optimization_options: "Switch to on-demand mode or enable auto-scaling." }),
    finding({ service: "AWS Lambda", cost: 340.5, pct_of_total: 2.7, risk_level: "low", category: "Compute",
        what_we_found: "Lambda functions with over-provisioned memory (3 GB for simple transforms).",
        optimization_options: "Right-size memory allocations using AWS Lambda Power Tuning." }),
    finding({ service: "NAT Gateway", cost: 745.25, pct_of_total: 5.8, risk_level: "medium", category: "Networking",
        what_we_found: "NAT Gateway data processing costs are 40% of networking spend.",
        optimization_options: "Use VPC endpoints for S3/DynamoDB, consider NAT instances for dev environments." }),
];

/* ─── Payload factory ─── */

export function makeTeaserPayload(overrides: Partial<TeaserReportPayload> = {}): TeaserReportPayload {
    return {
        provider_detected: "aws",
        total_analyzed_spend: 12847.5,
        currency: "USD",
        by_category: {
            Compute: 4590.5,
            Database: 3765.7,
            Storage: 1245.0,
            Networking: 3246.3,
        },
        waste_grade: "C" as WasteGrade,
        waste_grade_label: "Moderate — significant savings on the table",
        estimated_monthly_savings_min: 2054.0,
        estimated_monthly_savings_max: 3084.0,
        top_findings_teaser: EIGHT_SERVICE_FINDINGS,
        remediation_status: "SIGNUP_REQUIRED",
        rows_parsed: 1247,
        total_services_detected: 8,
        services_above_5pct: 5,
        cost_concentration_top3_pct: 67.4,
        existing_credits_detected: 0,
        analysis_depth: "service-level",
        annual_waste_so_far: 20540.0,
        cost_of_waiting_30d: 2569.0,
        benchmark_percentile: 30,
        benchmark_label: "worse than 70% of companies your size",
        quick_win: {
            title: "Migrate EBS gp2 → gp3",
            saving_estimate: 245.0,
            time_required: "5 minutes per volume",
            risk: "none",
            description:
                "gp3 is 20% cheaper with better baseline performance. Zero-downtime migration via AWS Console or CLI.",
        },
        cross_cloud_hint: {
            message: "Azure Spot VMs could reduce your compute costs by an additional 15-25%.",
            provider_compared: "azure",
            potential_saving_pct: 20,
        },
        ...overrides,
    };
}

/* ─── Grade-specific factory ─── */

export function makeTeaserPayloadForGrade(grade: WasteGrade): TeaserReportPayload {
    const gradeConfigs: Record<WasteGrade, Partial<TeaserReportPayload>> = {
        A: {
            waste_grade: "A",
            waste_grade_label: "Excellent — minimal waste detected",
            estimated_monthly_savings_min: 120,
            estimated_monthly_savings_max: 250,
        },
        B: {
            waste_grade: "B",
            waste_grade_label: "Good — small optimizations available",
            estimated_monthly_savings_min: 500,
            estimated_monthly_savings_max: 900,
        },
        C: {
            waste_grade: "C",
            waste_grade_label: "Moderate — significant savings on the table",
            estimated_monthly_savings_min: 2054,
            estimated_monthly_savings_max: 3084,
        },
        D: {
            waste_grade: "D",
            waste_grade_label: "Poor — high waste detected",
            estimated_monthly_savings_min: 4200,
            estimated_monthly_savings_max: 5800,
        },
        F: {
            waste_grade: "F",
            waste_grade_label: "Critical — severe overspend detected",
            estimated_monthly_savings_min: 7500,
            estimated_monthly_savings_max: 10200,
        },
    };

    return makeTeaserPayload(gradeConfigs[grade]);
}

/* ─── Provider-specific factory ─── */

export function makeTeaserPayloadForProvider(
    provider: "aws" | "azure" | "gcp" | "generic",
): TeaserReportPayload {
    return makeTeaserPayload({ provider_detected: provider });
}

/* ─── Minimal payload (fewest optional fields) ─── */

export function makeMinimalTeaserPayload(): TeaserReportPayload {
    return {
        provider_detected: "generic",
        total_analyzed_spend: 500,
        currency: "USD",
        by_category: { Other: 500 },
        waste_grade: "B",
        waste_grade_label: "Good — small optimizations available",
        estimated_monthly_savings_min: 40,
        estimated_monthly_savings_max: 100,
        top_findings_teaser: [
            finding({ service: "Generic Service", cost: 500, pct_of_total: 100, risk_level: "low", category: "Other" }),
        ],
        remediation_status: "SIGNUP_REQUIRED",
        rows_parsed: 42,
        total_services_detected: 1,
        services_above_5pct: 1,
        cost_concentration_top3_pct: 100,
        existing_credits_detected: 0,
        analysis_depth: "service-level",
    };
}
