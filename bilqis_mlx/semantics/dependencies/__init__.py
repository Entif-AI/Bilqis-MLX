"""Immutable, source-qualified immediate-dependency index for BAMF C09.

The index records direct edges, not a speculative transitive closure.
Source owners qualify corrections; this module does not mint source rights.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from graphlib import CycleError, TopologicalSorter
import re

from ...errors import ErrorBus, SCHOOL


DEPENDENCY_REF_SCHEMA = "bilqis.c09.dependency-ref/v1"
ARTIFACT_NODE_SCHEMA = "bilqis.c09.artifact-node/v1"
DEPENDENCY_INDEX_SCHEMA = "bilqis.c09.dependency-index/v1"
REVERSE_EDGE_SCHEMA = "bilqis.c09.reverse-edge/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_REVALIDATION.INVALID, reason=reason)


class DependencyKind(str, Enum):
    SOURCE = "SOURCE"
    OPERATOR = "OPERATOR"
    RELEASE = "RELEASE"
    POLICY = "POLICY"
    TIME = "TIME"
    RIGHTS = "RIGHTS"
    ARTIFACT = "ARTIFACT"


class ArtifactKind(str, Enum):
    ATLAS_FEATURE = "ATLAS_FEATURE"
    PACKED_FRAME = "PACKED_FRAME"
    MOTIF = "MOTIF"
    EXACT_CACHE = "EXACT_CACHE"
    OPERATOR_COMPOSITION = "OPERATOR_COMPOSITION"
    CAPABILITY_SUPPORT = "CAPABILITY_SUPPORT"


@dataclass(frozen=True, order=True)
class DependencyRef:
    kind: DependencyKind
    key: str
    schema_version: str = DEPENDENCY_REF_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.kind, DependencyKind)
                or not isinstance(self.key, str) or not self.key
                or self.schema_version != DEPENDENCY_REF_SCHEMA):
            _invalid("BAMF_C09_DEPENDENCY_REF_INVALID")


@dataclass(frozen=True)
class ArtifactNode:
    artifact_id: str
    kind: ArtifactKind
    content_digest: str
    eligible: bool
    immediate_dependencies: tuple[DependencyRef, ...]
    impact: int
    exigency: int
    schema_version: str = ARTIFACT_NODE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.artifact_id, str) or not self.artifact_id
                or not isinstance(self.kind, ArtifactKind)
                or not isinstance(self.content_digest, str)
                or not _SHA256.fullmatch(self.content_digest)
                or type(self.eligible) is not bool
                or not isinstance(self.immediate_dependencies, tuple)
                or not self.immediate_dependencies
                or any(not isinstance(ref, DependencyRef)
                       for ref in self.immediate_dependencies)
                or self.immediate_dependencies != tuple(
                    sorted(set(self.immediate_dependencies)))
                or DependencyRef(DependencyKind.ARTIFACT, self.artifact_id)
                in self.immediate_dependencies
                or any(type(value) is not int or not 0 <= value <= 4
                       for value in (self.impact, self.exigency))
                or self.schema_version != ARTIFACT_NODE_SCHEMA):
            _invalid("BAMF_C09_ARTIFACT_NODE_INVALID")

    @property
    def reference(self) -> DependencyRef:
        return DependencyRef(DependencyKind.ARTIFACT, self.artifact_id)


@dataclass(frozen=True)
class ReverseEdge:
    dependency: DependencyRef
    dependents: tuple[str, ...]
    schema_version: str = REVERSE_EDGE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.dependency, DependencyRef)
                or not self.dependents
                or any(not isinstance(key, str) or not key
                       for key in self.dependents)
                or self.dependents != tuple(sorted(set(self.dependents)))
                or self.schema_version != REVERSE_EDGE_SCHEMA):
            _invalid("BAMF_C09_REVERSE_EDGE_INVALID")


@dataclass(frozen=True)
class DependencyIndex:
    nodes: tuple[ArtifactNode, ...]
    schema_version: str = DEPENDENCY_INDEX_SCHEMA
    reverse_edges: tuple[ReverseEdge, ...] = field(init=False)

    def __post_init__(self) -> None:
        if (not isinstance(self.nodes, tuple)
                or any(not isinstance(node, ArtifactNode) for node in self.nodes)
                or self.nodes != tuple(sorted(
                    self.nodes, key=lambda node: node.artifact_id))
                or len({node.artifact_id for node in self.nodes}) != len(self.nodes)
                or self.schema_version != DEPENDENCY_INDEX_SCHEMA):
            _invalid("BAMF_C09_DEPENDENCY_INDEX_INVALID")
        identifiers = {node.artifact_id for node in self.nodes}
        predecessors = {}
        reverse: dict[DependencyRef, list[str]] = {}
        for node in self.nodes:
            deps = tuple(ref.key for ref in node.immediate_dependencies
                         if ref.kind is DependencyKind.ARTIFACT)
            if any(dep not in identifiers for dep in deps):
                _invalid("BAMF_C09_DEPENDENCY_ARTIFACT_MISSING")
            predecessors[node.artifact_id] = deps
            for ref in node.immediate_dependencies:
                reverse.setdefault(ref, []).append(node.artifact_id)
        try:
            tuple(TopologicalSorter(predecessors).static_order())
        except CycleError:
            _invalid("BAMF_C09_DEPENDENCY_CYCLE")
        object.__setattr__(self, "reverse_edges", tuple(
            ReverseEdge(ref, tuple(sorted(ids)))
            for ref, ids in sorted(reverse.items())
        ))

    @classmethod
    def build(cls, nodes: tuple[ArtifactNode, ...]) -> "DependencyIndex":
        if not isinstance(nodes, tuple):
            _invalid("BAMF_C09_DEPENDENCY_INDEX_INVALID")
        return cls(tuple(sorted(nodes, key=lambda node: node.artifact_id)))

    def node(self, artifact_id: str) -> ArtifactNode:
        for node in self.nodes:
            if node.artifact_id == artifact_id:
                return node
        _invalid("BAMF_C09_ARTIFACT_UNKNOWN")

    def direct_dependents(self, ref: DependencyRef) -> tuple[ArtifactNode, ...]:
        if not isinstance(ref, DependencyRef):
            _invalid("BAMF_C09_DEPENDENCY_REF_INVALID")
        edge = next(
            (edge for edge in self.reverse_edges if edge.dependency == ref),
            None,
        )
        if edge is None:
            return ()
        return tuple(self.node(artifact_id) for artifact_id in edge.dependents)

    def replace_node(self, updated: ArtifactNode) -> "DependencyIndex":
        if not isinstance(updated, ArtifactNode):
            _invalid("BAMF_C09_ARTIFACT_NODE_INVALID")
        self.node(updated.artifact_id)
        return DependencyIndex.build(tuple(
            updated if node.artifact_id == updated.artifact_id else node
            for node in self.nodes
        ))
