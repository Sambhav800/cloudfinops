/**
 * Mock fixtures for Architecture Page V2 development.
 *
 * Used when NEXT_PUBLIC_USE_MOCK_ARCH=true.
 * Shapes match backend contracts exactly.
 */

import type {
    GraphResponse,
    GraphNode,
    GraphEdge,
    CoverageReport,
    ViewData,
    RegionGraphResult,
    VpcIndexEntry,
    ProposedResult,
    ChangeItem,
} from "./architecture-types";
import { formatInrCurrency, toDisplayInrAmount } from "./resources/contract";

// ---------------------------------------------------------------------------
// Helper: build a node
// ---------------------------------------------------------------------------

function node(
    id: string,
    name: string,
    serviceType: string,
    region: string,
    cost: number,
    status: string,
    opts: Partial<GraphNode> = {}
): GraphNode {
    return {
        id,
        cloud_resource_id: opts.cloud_resource_id ?? id,
        name,
        service_type: serviceType,
        region,
        cost,
        status,
        waste_type: opts.waste_type ?? null,
        tags: opts.tags ?? {},
        metadata: opts.metadata ?? {},
        severity: opts.severity ?? "none",
        drilldown_key: opts.drilldown_key ?? null,
        parent: opts.parent ?? null,
        node_type: opts.node_type ?? "resource",
    };
}

function edge(
    source: string,
    target: string,
    kind: GraphEdge["kind"],
    style: GraphEdge["style"] = "solid",
    label: string | null = null
): GraphEdge {
    return { source, target, kind, label, style };
}

function formatMockInr(monthlyUsd: number): string {
    return formatInrCurrency(toDisplayInrAmount(monthlyUsd, "USD"), {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });
}

// ---------------------------------------------------------------------------
// Region 1: us-east-1 (2 VPCs, 8 nodes, 10 edges)
// ---------------------------------------------------------------------------

const usEast1Nodes: GraphNode[] = [
    // Region group
    node("reg_us_east_1", "us-east-1", "region", "us-east-1", 485, "Active", {
        node_type: "group",
    }),
    // VPC 1
    node("vpc_vpc_prod", "prod-vpc", "vpc", "us-east-1", 420, "Active", {
        cloud_resource_id: "vpc-aaa111",
        node_type: "group",
        drilldown_key: "vpc-aaa111",
        parent: "reg_us_east_1",
        metadata: { cidr_block: "10.0.0.0/16" },
    }),
    // EC2 active
    node("ec2_web1", "web-server-1", "ec2", "us-east-1", 72, "Active", {
        cloud_resource_id: "i-0abc111",
        parent: "vpc_vpc_prod",
        tags: { Env: "prod", Team: "platform" },
        metadata: { instance_type: "m5.large", avg_cpu_7d: 45 },
    }),
    // EC2 zombie
    node("ec2_dev_old", "dev-legacy-box", "ec2", "us-east-1", 48, "Zombie", {
        cloud_resource_id: "i-0abc222",
        parent: "vpc_vpc_prod",
        waste_type: "idle_vm",
        severity: "high",
        tags: {},
        metadata: { instance_type: "t3.medium", avg_cpu_7d: 0.3 },
    }),
    // RDS
    node("rds_prod", "prod-db", "rds", "us-east-1", 185, "Active", {
        cloud_resource_id: "prod-db",
        parent: "vpc_vpc_prod",
        tags: { Env: "prod" },
        metadata: { engine: "mysql", instance_class: "db.r5.large", multi_az: false },
    }),
    // EBS orphan (waste)
    node("ebs_orphan", "vol-orphan", "ebs", "us-east-1", 5, "Zombie", {
        cloud_resource_id: "vol-orphan",
        parent: "vpc_vpc_prod",
        waste_type: "orphaned_disk",
        severity: "medium",
        metadata: { size_gb: 50, volume_type: "gp2", attached_to: null },
    }),
    // Security group with risk
    node("sg_open", "web-sg-public", "sg", "us-east-1", 0, "Active", {
        cloud_resource_id: "sg-bbb999",
        parent: "vpc_vpc_prod",
        severity: "critical",
        metadata: { is_overly_permissive: true, ingress_rules: "0.0.0.0/0:80,443,22" },
    }),
    // IGW
    node("igw_main", "igw-main", "igw", "us-east-1", 0, "Active", {
        cloud_resource_id: "igw-main",
    }),
    // VPC 2
    node("vpc_vpc_staging", "staging-vpc", "vpc", "us-east-1", 65, "Active", {
        cloud_resource_id: "vpc-bbb222",
        node_type: "group",
        drilldown_key: "vpc-bbb222",
        parent: "reg_us_east_1",
        metadata: { cidr_block: "10.1.0.0/16" },
    }),
    // EC2 in staging
    node("ec2_staging", "staging-api", "ec2", "us-east-1", 35, "Active", {
        cloud_resource_id: "i-0abc333",
        parent: "vpc_vpc_staging",
        tags: { Env: "staging" },
        metadata: { instance_type: "t3.small", avg_cpu_7d: 12 },
    }),
    // S3 standalone
    node("sa_s3", "3 S3 Buckets", "s3", "us-east-1", 18, "Active", {
        node_type: "standalone",
        metadata: { bucket_count: 3 },
    }),
    // Lambda standalone
    node("sa_lambda", "5 Lambda Functions", "lambda", "us-east-1", 4, "Active", {
        node_type: "standalone",
        metadata: { function_count: 5 },
    }),
];

const usEast1Edges: GraphEdge[] = [
    edge("reg_us_east_1", "vpc_vpc_prod", "contains"),
    edge("reg_us_east_1", "vpc_vpc_staging", "contains"),
    edge("igw_main", "vpc_vpc_prod", "routes_to"),
    edge("vpc_vpc_prod", "ec2_web1", "contains"),
    edge("vpc_vpc_prod", "ec2_dev_old", "contains"),
    edge("vpc_vpc_prod", "rds_prod", "contains"),
    edge("vpc_vpc_prod", "ebs_orphan", "contains"),
    edge("sg_open", "ec2_web1", "security_applies_to"),
    edge("vpc_vpc_staging", "ec2_staging", "contains"),
    edge("reg_us_east_1", "sa_s3", "contains", "dotted"),
    edge("reg_us_east_1", "sa_lambda", "contains", "dotted"),
    edge("ebs_orphan", "ec2_dev_old", "attached_to", "dotted", "was attached"),
];

const usEast1Coverage: CoverageReport = {
    detected_services: ["ec2", "rds", "ebs", "eip", "vpc", "subnet", "igw", "sg", "s3", "lambda", "iam"],
    missing_services: ["eks", "ecs", "alb", "cloudtrail", "config"],
    access_denied_services: ["cloudtrail"],
    microservices_available: false,
    warnings: [
        { type: "microservices_unavailable", message: "Microservices view unavailable: requires EKS or ECS scan permissions" },
    ],
};

const usEast1VpcIndex: VpcIndexEntry[] = [
    { vpc_id: "vpc-aaa111", name: "prod-vpc", monthly_cost: 420, waste_cost: 53 },
    { vpc_id: "vpc-bbb222", name: "staging-vpc", monthly_cost: 65, waste_cost: 0 },
];

const usEast1TopologyMermaid = `flowchart TD
    subgraph reg_us_east_1["🌍 us-east-1"]
        vpc_vpc_prod["🔒 prod-vpc\\n3 EC2 · 1 RDS · 1 EBS\\n${formatMockInr(420)}/mo | ⚠ ${formatMockInr(53)} waste"]:::active
        vpc_vpc_staging["🔒 staging-vpc\\n1 EC2\\n${formatMockInr(65)}/mo"]:::active
    end
    igw_igw_main["🌐 igw-main"]
    igw_igw_main --> vpc_vpc_prod
    subgraph sa_group["🌐 Global / Standalone"]
        sa_s3["📂 3 S3 Buckets | ${formatMockInr(18)}/mo"]
        sa_lambda["⚡ 5 Lambda Functions | ${formatMockInr(4)}/mo"]
    end

    classDef active fill:#065f46,stroke:#10b981,color:#ecfdf5
    classDef zombie fill:#7f1d1d,stroke:#ef4444,color:#fef2f2`;

const usEast1HotspotsMermaid = `flowchart TD
    subgraph reg_us_east_1["🌍 us-east-1 — ${formatMockInr(485)}/mo"]
        rds_prod["💰 prod-db\\nRDS · ${formatMockInr(185)}/mo"]:::hotspot_red
        ec2_web1["💰 web-server-1\\nEC2 · ${formatMockInr(72)}/mo"]:::hotspot_orange
        ec2_dev_old["🔴 dev-legacy-box\\nEC2 ZOMBIE · ${formatMockInr(48)}/mo"]:::hotspot_red
        ec2_staging["💰 staging-api\\nEC2 · ${formatMockInr(35)}/mo"]:::hotspot_yellow
        sa_s3["📂 S3 · ${formatMockInr(18)}/mo"]:::hotspot_green
        ebs_orphan["🔴 vol-orphan\\nEBS WASTE · ${formatMockInr(5)}/mo"]:::hotspot_yellow
    end

    classDef hotspot_green fill:#065f46,stroke:#10b981,color:#ecfdf5
    classDef hotspot_yellow fill:#713f12,stroke:#eab308,color:#fef9c3
    classDef hotspot_orange fill:#7c2d12,stroke:#f97316,color:#fff7ed
    classDef hotspot_red fill:#7f1d1d,stroke:#ef4444,color:#fef2f2`;

const usEast1TopologyView: ViewData = {
    graph: { nodes: usEast1Nodes, edges: usEast1Edges },
    mermaid: usEast1TopologyMermaid,
    warnings: [],
};

const usEast1HotspotsView: ViewData = {
    graph: { nodes: usEast1Nodes, edges: usEast1Edges },
    mermaid: usEast1HotspotsMermaid,
    warnings: [],
};

const usEast1Region: RegionGraphResult = {
    region: "us-east-1",
    coverage: usEast1Coverage,
    views: {
        topology_summary: usEast1TopologyView,
        cost_hotspots: usEast1HotspotsView,
    },
    vpc_index: usEast1VpcIndex,
};

// ---------------------------------------------------------------------------
// Region 2: eu-west-1 (1 VPC, 3 nodes, 3 edges)
// ---------------------------------------------------------------------------

const euWest1Nodes: GraphNode[] = [
    node("reg_eu_west_1", "eu-west-1", "region", "eu-west-1", 120, "Active", {
        node_type: "group",
    }),
    node("vpc_vpc_eu", "eu-prod-vpc", "vpc", "eu-west-1", 120, "Active", {
        cloud_resource_id: "vpc-ccc333",
        node_type: "group",
        drilldown_key: "vpc-ccc333",
        parent: "reg_eu_west_1",
    }),
    node("ec2_eu_api", "eu-api-server", "ec2", "eu-west-1", 85, "Active", {
        cloud_resource_id: "i-0eu111",
        parent: "vpc_vpc_eu",
        tags: { Env: "prod", Team: "eu-ops" },
        metadata: { instance_type: "m5.large", avg_cpu_7d: 55 },
    }),
    node("rds_eu", "eu-db", "rds", "eu-west-1", 35, "Active", {
        cloud_resource_id: "eu-db",
        parent: "vpc_vpc_eu",
        metadata: { engine: "postgres", instance_class: "db.t3.medium" },
    }),
];

const euWest1Edges: GraphEdge[] = [
    edge("reg_eu_west_1", "vpc_vpc_eu", "contains"),
    edge("vpc_vpc_eu", "ec2_eu_api", "contains"),
    edge("vpc_vpc_eu", "rds_eu", "contains"),
];

const euWest1Mermaid = `flowchart TD
    subgraph reg_eu_west_1["🌍 eu-west-1"]
        vpc_vpc_eu["🔒 eu-prod-vpc\\n1 EC2 · 1 RDS\\n${formatMockInr(120)}/mo"]:::active
    end

    classDef active fill:#065f46,stroke:#10b981,color:#ecfdf5`;

const euWest1Region: RegionGraphResult = {
    region: "eu-west-1",
    coverage: {
        detected_services: ["ec2", "rds", "vpc"],
        missing_services: ["s3", "lambda", "eks", "ecs", "alb", "iam", "igw"],
        access_denied_services: [],
        microservices_available: false,
        warnings: [
            { type: "microservices_unavailable", message: "Microservices view unavailable: requires EKS or ECS scan permissions" },
        ],
    },
    views: {
        topology_summary: {
            graph: { nodes: euWest1Nodes, edges: euWest1Edges },
            mermaid: euWest1Mermaid,
            warnings: [],
        },
        cost_hotspots: {
            graph: { nodes: euWest1Nodes, edges: euWest1Edges },
            mermaid: euWest1Mermaid,
            warnings: [],
        },
    },
    vpc_index: [{ vpc_id: "vpc-ccc333", name: "eu-prod-vpc", monthly_cost: 120, waste_cost: 0 }],
};

// ---------------------------------------------------------------------------
// Export: mockGraphResponse()
// ---------------------------------------------------------------------------

export function mockGraphResponse(): GraphResponse {
    return {
        provider: "aws",
        integration_id: "mock-integration-001",
        generated_at: new Date().toISOString(),
        regions: [usEast1Region, euWest1Region],
    };
}

// ---------------------------------------------------------------------------
// Export: mockProposedResult()
// ---------------------------------------------------------------------------

export function mockProposedResult(
    mode: "cost_optimized" | "reliability_security_optimized" = "cost_optimized"
): ProposedResult {
    if (mode === "cost_optimized") {
        const changeList: ChangeItem[] = [
            {
                resource_id: "i-0abc222",
                resource_name: "dev-legacy-box",
                service_type: "ec2",
                change_type: "terminate",
                current_state: "Zombie t3.medium — 0.3% avg CPU",
                proposed_state: "Terminated",
                monthly_savings: 48,
                risk_level: "low",
                reasoning: "Instance idle for 30+ days with no inbound connections. Safe to terminate.",
            },
            {
                resource_id: "vol-orphan",
                resource_name: "vol-orphan",
                service_type: "ebs",
                change_type: "terminate",
                current_state: "Orphaned 50GB gp2 — unattached",
                proposed_state: "Deleted",
                monthly_savings: 5,
                risk_level: "low",
                reasoning: "Unattached EBS volume. Snapshot exists. No data loss risk.",
            },
            {
                resource_id: "i-0abc111",
                resource_name: "web-server-1",
                service_type: "ec2",
                change_type: "downsize",
                current_state: "m5.large — 45% avg CPU",
                proposed_state: "m5.medium",
                monthly_savings: 24,
                risk_level: "medium",
                reasoning: "CPU headroom allows downsizing. Monitor for 1 week after change.",
            },
        ];

        return {
            mode: "cost_optimized",
            integration_id: "mock-integration-001",
            region: "us-east-1",
            proposed_mermaid: `flowchart TD
    subgraph reg_us_east_1["🌍 us-east-1 — Optimized"]
        subgraph vpc_prod["🔒 prod-vpc"]
            ec2_web1["🟡 web-server-1\\nm5.large → m5.medium"]
            ec2_dev_old["🔴 [REMOVED] dev-legacy-box"]
            rds_prod["🟢 prod-db\\n${formatMockInr(185)}/mo"]
            ebs_orphan["🔴 [REMOVED] vol-orphan"]
        end
        subgraph vpc_staging["🔒 staging-vpc"]
            ec2_staging["🟢 staging-api"]
        end
    end

    classDef active fill:#065f46,stroke:#10b981,color:#ecfdf5
    classDef zombie fill:#7f1d1d,stroke:#ef4444,color:#fef2f2`,
            change_list: changeList,
            estimated_savings: 77,
            risk_tradeoffs:
                "Low risk overall. Two terminations target confirmed zombie resources. " +
                "One downsize (web-server-1) has medium risk — monitor CPU after change. " +
                `Total monthly savings: ${formatMockInr(77)}/mo (${formatMockInr(924)}/year).`,
            warnings: [],
        };
    }

    // reliability_security_optimized
    const changeList: ChangeItem[] = [
        {
            resource_id: "prod-db",
            resource_name: "prod-db",
            service_type: "rds",
            change_type: "enable_multi_az",
            current_state: "Single-AZ db.r5.large",
            proposed_state: "Multi-AZ db.r5.large",
            monthly_savings: -148,
            risk_level: "low",
            reasoning: "Single-AZ RDS is a single point of failure. Multi-AZ adds automatic failover within 60s.",
        },
        {
            resource_id: "sg-bbb999",
            resource_name: "web-sg-public",
            service_type: "sg",
            change_type: "tighten_security",
            current_state: "Ingress 0.0.0.0/0 on ports 80,443,22",
            proposed_state: "Restrict SSH (22) to VPN CIDR only",
            monthly_savings: 0,
            risk_level: "medium",
            reasoning: "Open SSH to the world is a critical security risk. Restrict to known IP ranges.",
        },
    ];

    return {
        mode: "reliability_security_optimized",
        integration_id: "mock-integration-001",
        region: "us-east-1",
        proposed_mermaid: `flowchart TD
    subgraph reg_us_east_1["🌍 us-east-1 — Hardened"]
        subgraph vpc_prod["🔒 prod-vpc"]
            ec2_web1["🟢 web-server-1"]
            rds_prod["🟡 prod-db → Multi-AZ"]
            rds_replica["🔵 [NEW] prod-db-replica"]
            sg_open["🟡 web-sg-public → SSH restricted"]
        end
    end

    classDef active fill:#065f46,stroke:#10b981,color:#ecfdf5`,
        change_list: changeList,
        estimated_savings: -148,
        risk_tradeoffs:
            `Reliability improvements increase cost by ${formatMockInr(148)}/mo but eliminate single points of failure. ` +
            "Multi-AZ RDS provides automatic failover (RTO < 60s vs hours for manual restore). " +
            "Tightening SSH reduces attack surface significantly.",
        warnings: [],
    };
}
