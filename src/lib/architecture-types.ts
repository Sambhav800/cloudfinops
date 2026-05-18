/**
 * TypeScript types for Architecture Page V2.
 *
 * These mirror the backend dataclass contracts in
 * backend/app/architecture/contracts.py — keep in sync.
 */

// ---------------------------------------------------------------------------
// Graph Node
// ---------------------------------------------------------------------------

export interface GraphNode {
    id: string;
    cloud_resource_id: string;
    name: string;
    service_type: string; // ec2, rds, vpc, s3, lambda, igw, iam, ebs, eip, sg, subnet, eks, ecs, alb
    region: string;
    cost: number;
    status: string; // Active, Zombie, Stopped
    waste_type: string | null;
    tags: Record<string, string>;
    metadata: Record<string, unknown>;
    severity: "none" | "low" | "medium" | "high" | "critical";
    drilldown_key: string | null;
    parent: string | null;
    node_type: "resource" | "group" | "standalone";
}

// ---------------------------------------------------------------------------
// Graph Edge
// ---------------------------------------------------------------------------

export interface GraphEdge {
    source: string;
    target: string;
    kind: "contains" | "routes_to" | "attached_to" | "security_applies_to";
    label: string | null;
    style: "solid" | "dotted";
}

// ---------------------------------------------------------------------------
// Coverage Report
// ---------------------------------------------------------------------------

export interface CoverageReport {
    detected_services: string[];
    missing_services: string[];
    access_denied_services: string[];
    microservices_available: boolean;
    warnings: CoverageWarning[];
}

export interface CoverageWarning {
    type: string;
    message: string;
}

// ---------------------------------------------------------------------------
// Graph Data (nodes + edges bundle)
// ---------------------------------------------------------------------------

export interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

// ---------------------------------------------------------------------------
// View Data (graph + mermaid + warnings)
// ---------------------------------------------------------------------------

export interface ViewData {
    graph: GraphData;
    mermaid: string;
    warnings: CoverageWarning[];
}

// ---------------------------------------------------------------------------
// VPC Index Entry
// ---------------------------------------------------------------------------

export interface VpcIndexEntry {
    vpc_id: string;
    name: string;
    monthly_cost: number;
    waste_cost: number;
}

// ---------------------------------------------------------------------------
// Region-level result
// ---------------------------------------------------------------------------

export interface RegionGraphResult {
    region: string;
    coverage: CoverageReport;
    views: Record<string, ViewData>;
    vpc_index: VpcIndexEntry[];
}

// ---------------------------------------------------------------------------
// Top-level graph response
// ---------------------------------------------------------------------------

export interface GraphResponse {
    provider: string;
    integration_id: string;
    generated_at: string;
    regions: RegionGraphResult[];
}

// ---------------------------------------------------------------------------
// Proposed Architecture contracts
// ---------------------------------------------------------------------------

export interface ChangeItem {
    resource_id: string;
    resource_name: string;
    service_type: string;
    change_type:
    | "terminate"
    | "downsize"
    | "migrate"
    | "add_replica"
    | "enable_multi_az"
    | "add_monitoring"
    | "tighten_security"
    | "enable_encryption";
    current_state: string;
    proposed_state: string;
    monthly_savings: number;
    risk_level: "low" | "medium" | "high";
    reasoning: string;
}

export interface ProposedResult {
    mode: "cost_optimized" | "reliability_security_optimized";
    integration_id: string;
    region: string;
    proposed_mermaid: string;
    change_list: ChangeItem[];
    estimated_savings: number;
    risk_tradeoffs: string;
    warnings: CoverageWarning[];
}

// ---------------------------------------------------------------------------
// API error shape
// ---------------------------------------------------------------------------

export interface ArchitectureApiError {
    status: number;
    detail: string;
}

// ---------------------------------------------------------------------------
// View identifiers
// ---------------------------------------------------------------------------

export type CurrentViewId =
    | "topology_summary"
    | "cost_hotspots"
    | "microservices"
    | "vpc_detail";

export type ProposedMode =
    | "cost_optimized"
    | "reliability_security_optimized";

export type ViewId = CurrentViewId | "proposed_cost" | "proposed_reliability";
