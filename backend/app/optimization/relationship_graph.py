"""
Resource Relationship Graph — Dependency mapping for false-positive prevention.

Builds an in-memory graph during each scan from:
1. Provider API data (ASG membership, LB targets, disk attachments)
2. Tag-based inference (dr:true, environment:blue/green, backup-rotation:weekly)
3. Naming convention inference (*-dr, *-standby, *-blue, *-green)

Resources with protective relationships (DR standby, ASG member, blue/green pair,
backup rotation) are shielded from waste classification regardless of utilization signals.

The graph is ephemeral — rebuilt each scan from current state. No persistent storage.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .evidence_collector import ResourceRelationship

logger = logging.getLogger(__name__)


class RelationshipKind(str, Enum):
    FAILOVER_FOR = "failover_for"
    BACKUP_OF = "backup_of"
    MEMBER_OF_ASG = "member_of_asg"
    MEMBER_OF_VMSS = "member_of_vmss"
    MEMBER_OF_INSTANCE_GROUP = "member_of_instance_group"
    BLUE_GREEN_PAIR = "blue_green_pair"
    LOAD_BALANCED_BY = "load_balanced_by"
    ATTACHED_TO = "attached_to"
    SNAPSHOT_OF = "snapshot_of"
    DNS_POINTS_TO = "dns_points_to"
    DEPENDS_ON = "depends_on"


@dataclass
class GraphEdge:
    """A directed relationship between two resources."""

    source_id: str
    target_id: str
    kind: RelationshipKind
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceNode:
    """A resource in the relationship graph."""

    resource_id: str
    resource_name: str
    resource_type: str
    provider: str
    status: str  # active, stopped, etc.
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class ProtectionReason:
    """Why a resource is protected from waste classification."""

    reason: str
    relationship: RelationshipKind
    related_resource_id: Optional[str] = None
    confidence: float = 1.0


# --- Detection patterns ---

# Tags indicating DR/failover purpose
DR_TAG_KEYS = {"dr", "disaster-recovery", "failover", "standby", "ha-role", "replication-role"}
DR_TAG_VALUES = {"dr", "standby", "passive", "secondary", "failover", "warm-standby", "hot-standby"}

# Tags indicating backup/snapshot rotation
BACKUP_TAG_KEYS = {"backup-rotation", "backup-schedule", "snapshot-policy", "retention-policy"}
BACKUP_TAG_VALUES = {"backup", "daily-backup", "weekly-backup", "snapshot-source"}

# Tags indicating blue/green or canary deployment
DEPLOYMENT_TAG_KEYS = {"deployment", "deployment-group", "deploy-slot"}
DEPLOYMENT_TAG_VALUES = {"blue", "green", "canary", "shadow", "staging-slot"}

# Name patterns
DR_NAME_RE = re.compile(
    r".*[-_\.](dr|failover|standby|passive|secondary|replica|hot-standby|warm-standby)[-_\.]?.*",
    re.IGNORECASE,
)
BLUE_GREEN_NAME_RE = re.compile(
    r".*[-_\.](blue|green|canary|shadow)[-_\.]?.*",
    re.IGNORECASE,
)
BACKUP_NAME_RE = re.compile(
    r".*[-_\.](backup|bak|snap|archive)[-_\.]?.*",
    re.IGNORECASE,
)

# AWS Auto Scaling Group tag
AWS_ASG_TAG = "aws:autoscaling:groupName"
AWS_FLEET_TAG = "aws:ec2:fleet-id"

# GCP instance group membership indicators
GCP_IG_TAG = "goog-gke-node"
GCP_MIG_TAG = "created-by"  # Points to instance group manager


class ResourceRelationshipGraph:
    """
    In-memory resource dependency graph.

    Built once per scan, used by the classification pipeline's Stage 4
    (Context Application) to determine protection rules.
    """

    def __init__(self):
        self.nodes: Dict[str, ResourceNode] = {}
        self.edges: List[GraphEdge] = []
        self._outgoing: Dict[str, List[GraphEdge]] = defaultdict(list)
        self._incoming: Dict[str, List[GraphEdge]] = defaultdict(list)
        self._asg_groups: Dict[str, Set[str]] = defaultdict(set)  # group_name → member IDs

    def add_node(self, node: ResourceNode) -> None:
        """Add a resource node to the graph."""
        self.nodes[node.resource_id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a relationship edge to the graph."""
        self.edges.append(edge)
        self._outgoing[edge.source_id].append(edge)
        self._incoming[edge.target_id].append(edge)

    def get_protection_reasons(self, resource_id: str) -> List[ProtectionReason]:
        """
        Get all reasons this resource should be protected from waste classification.

        Returns empty list if no protection applies.
        """
        protections: List[ProtectionReason] = []
        node = self.nodes.get(resource_id)

        if not node:
            return protections

        # Check outgoing edges (this resource IS something for another)
        for edge in self._outgoing.get(resource_id, []):
            protection = self._evaluate_edge_protection(edge, direction="outgoing")
            if protection:
                protections.append(protection)

        # Check incoming edges (something points TO this resource)
        for edge in self._incoming.get(resource_id, []):
            protection = self._evaluate_edge_protection(edge, direction="incoming")
            if protection:
                protections.append(protection)

        # Check group membership
        for group_name, members in self._asg_groups.items():
            if resource_id in members:
                protections.append(ProtectionReason(
                    reason=f"Member of auto-scaling group: {group_name}",
                    relationship=RelationshipKind.MEMBER_OF_ASG,
                    confidence=1.0,
                ))
                break

        return protections

    def get_relationships_for_evidence(
        self, resource_id: str
    ) -> List[ResourceRelationship]:
        """Convert graph edges to ResourceRelationship objects for EvidenceBundle."""
        relationships: List[ResourceRelationship] = []

        for edge in self._outgoing.get(resource_id, []):
            target_node = self.nodes.get(edge.target_id)
            relationships.append(ResourceRelationship(
                kind=edge.kind.value,
                target_resource_id=edge.target_id,
                target_status=target_node.status if target_node else None,
                metadata=edge.metadata,
            ))

        for edge in self._incoming.get(resource_id, []):
            source_node = self.nodes.get(edge.source_id)
            relationships.append(ResourceRelationship(
                kind=f"target_of_{edge.kind.value}",
                target_resource_id=edge.source_id,
                target_status=source_node.status if source_node else None,
                metadata=edge.metadata,
            ))

        return relationships

    def build_from_resources(self, resources: List[Dict[str, Any]]) -> None:
        """
        Build the relationship graph from scanned resources.

        Infers relationships from tags, naming patterns, and provider-specific
        metadata. This is the main entry point called during scan orchestration.
        """
        # Phase 1: Add all nodes
        for r in resources:
            resource_id = r.get("cloud_resource_id") or r.get("resource_name", "")
            node = ResourceNode(
                resource_id=resource_id,
                resource_name=r.get("resource_name", ""),
                resource_type=r.get("service_type", ""),
                provider=r.get("provider", ""),
                status=r.get("status", ""),
                tags=r.get("tags", {}),
            )
            self.add_node(node)

        # Phase 2: Infer relationships
        for r in resources:
            resource_id = r.get("cloud_resource_id") or r.get("resource_name", "")
            tags = r.get("tags", {})
            name = r.get("resource_name", "")
            provider = r.get("provider", "")
            metadata = r.get("metadata", {})

            # AWS Auto Scaling Group membership
            if AWS_ASG_TAG in tags:
                group_name = tags[AWS_ASG_TAG]
                self._asg_groups[group_name].add(resource_id)
                self.add_edge(GraphEdge(
                    source_id=resource_id,
                    target_id=f"asg:{group_name}",
                    kind=RelationshipKind.MEMBER_OF_ASG,
                    metadata={"group_name": group_name},
                ))

            # AWS Fleet membership
            if AWS_FLEET_TAG in tags:
                fleet_id = tags[AWS_FLEET_TAG]
                self._asg_groups[f"fleet:{fleet_id}"].add(resource_id)

            # GCP Instance Group membership
            if provider == "gcp":
                created_by = metadata.get("created_by", "")
                if "instanceGroupManagers" in str(created_by):
                    self._asg_groups[f"gcp-mig:{created_by}"].add(resource_id)
                    self.add_edge(GraphEdge(
                        source_id=resource_id,
                        target_id=f"mig:{created_by}",
                        kind=RelationshipKind.MEMBER_OF_INSTANCE_GROUP,
                    ))
                if GCP_IG_TAG in tags:
                    self._asg_groups[f"gke:{tags[GCP_IG_TAG]}"].add(resource_id)

            # Tag-based DR/failover inference
            self._infer_dr_from_tags(resource_id, tags)

            # Tag-based backup inference
            self._infer_backup_from_tags(resource_id, tags)

            # Tag-based blue/green inference
            self._infer_deployment_from_tags(resource_id, tags)

            # Name-based inference
            self._infer_from_name(resource_id, name)

            # Disk attachment relationships
            if r.get("service_type") in ("AWS EBS Volume", "Azure Managed Disk", "GCP Persistent Disk"):
                attached_to = metadata.get("attached_to") or metadata.get("managed_by")
                if attached_to:
                    self.add_edge(GraphEdge(
                        source_id=resource_id,
                        target_id=attached_to,
                        kind=RelationshipKind.ATTACHED_TO,
                    ))

            # Load balancer backend membership
            lb_targets = metadata.get("target_group") or metadata.get("backend_pool")
            if lb_targets:
                self.add_edge(GraphEdge(
                    source_id=resource_id,
                    target_id=lb_targets,
                    kind=RelationshipKind.LOAD_BALANCED_BY,
                ))

    def _infer_dr_from_tags(self, resource_id: str, tags: Dict[str, str]) -> None:
        """Infer DR/failover relationship from tags."""
        tags_lower = {k.lower(): v.lower() for k, v in tags.items()}

        for key in tags_lower:
            if key in DR_TAG_KEYS:
                self.add_edge(GraphEdge(
                    source_id=resource_id,
                    target_id="__dr_group__",
                    kind=RelationshipKind.FAILOVER_FOR,
                    metadata={"detected_via": f"tag_key:{key}"},
                ))
                return

        for value in tags_lower.values():
            if value in DR_TAG_VALUES:
                self.add_edge(GraphEdge(
                    source_id=resource_id,
                    target_id="__dr_group__",
                    kind=RelationshipKind.FAILOVER_FOR,
                    metadata={"detected_via": f"tag_value:{value}"},
                ))
                return

    def _infer_backup_from_tags(self, resource_id: str, tags: Dict[str, str]) -> None:
        """Infer backup/snapshot relationship from tags."""
        tags_lower = {k.lower(): v.lower() for k, v in tags.items()}

        for key in tags_lower:
            if key in BACKUP_TAG_KEYS:
                self.add_edge(GraphEdge(
                    source_id=resource_id,
                    target_id="__backup_group__",
                    kind=RelationshipKind.BACKUP_OF,
                    metadata={"detected_via": f"tag_key:{key}"},
                ))
                return

        for value in tags_lower.values():
            if value in BACKUP_TAG_VALUES:
                self.add_edge(GraphEdge(
                    source_id=resource_id,
                    target_id="__backup_group__",
                    kind=RelationshipKind.BACKUP_OF,
                    metadata={"detected_via": f"tag_value:{value}"},
                ))
                return

    def _infer_deployment_from_tags(self, resource_id: str, tags: Dict[str, str]) -> None:
        """Infer blue/green deployment relationship from tags."""
        tags_lower = {k.lower(): v.lower() for k, v in tags.items()}

        for key in tags_lower:
            if key in DEPLOYMENT_TAG_KEYS:
                value = tags_lower[key]
                if value in DEPLOYMENT_TAG_VALUES:
                    self.add_edge(GraphEdge(
                        source_id=resource_id,
                        target_id=f"__deploy_group__:{value}",
                        kind=RelationshipKind.BLUE_GREEN_PAIR,
                        metadata={"slot": value},
                    ))
                    return

    def _infer_from_name(self, resource_id: str, name: str) -> None:
        """Infer relationships from resource naming patterns."""
        if not name:
            return

        if DR_NAME_RE.match(name):
            self.add_edge(GraphEdge(
                source_id=resource_id,
                target_id="__dr_group__",
                kind=RelationshipKind.FAILOVER_FOR,
                metadata={"detected_via": "name_pattern"},
            ))
        elif BLUE_GREEN_NAME_RE.match(name):
            self.add_edge(GraphEdge(
                source_id=resource_id,
                target_id="__deploy_group__",
                kind=RelationshipKind.BLUE_GREEN_PAIR,
                metadata={"detected_via": "name_pattern"},
            ))
        elif BACKUP_NAME_RE.match(name):
            self.add_edge(GraphEdge(
                source_id=resource_id,
                target_id="__backup_group__",
                kind=RelationshipKind.BACKUP_OF,
                metadata={"detected_via": "name_pattern"},
            ))

    def _evaluate_edge_protection(
        self, edge: GraphEdge, direction: str
    ) -> Optional[ProtectionReason]:
        """Evaluate whether an edge provides protection."""

        protective_kinds = {
            RelationshipKind.FAILOVER_FOR: "DR/failover standby resource",
            RelationshipKind.BACKUP_OF: "Part of backup rotation",
            RelationshipKind.MEMBER_OF_ASG: "Managed by auto-scaling group",
            RelationshipKind.MEMBER_OF_VMSS: "Managed by VM scale set",
            RelationshipKind.MEMBER_OF_INSTANCE_GROUP: "Managed by instance group",
            RelationshipKind.BLUE_GREEN_PAIR: "Part of blue/green deployment",
            RelationshipKind.DNS_POINTS_TO: "Referenced by DNS record",
        }

        if edge.kind in protective_kinds:
            related_id = edge.target_id if direction == "outgoing" else edge.source_id
            return ProtectionReason(
                reason=protective_kinds[edge.kind],
                relationship=edge.kind,
                related_resource_id=related_id,
            )

        # Load balanced resources get partial protection (30% confidence reduction)
        if edge.kind == RelationshipKind.LOAD_BALANCED_BY:
            related_id = edge.target_id if direction == "outgoing" else edge.source_id
            return ProtectionReason(
                reason="Behind active load balancer (may receive traffic)",
                relationship=edge.kind,
                related_resource_id=related_id,
                confidence=0.7,  # Partial protection
            )

        return None

    @property
    def stats(self) -> Dict[str, int]:
        """Graph statistics for logging."""
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "asg_groups": len(self._asg_groups),
            "protected_resources": sum(
                1 for nid in self.nodes if self.get_protection_reasons(nid)
            ),
        }
