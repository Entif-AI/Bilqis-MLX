"""Declarative pre-release developmental targets for future factory releases.

This module is deliberately *not* an admission path.  A developmental target
names one semantic learning step, its prerequisite structure, the kinds of
understanding that must eventually be demonstrated, and the source contract
that would be required to turn it into an executable factory capability.

There is no generator, oracle, grade owner, source adapter, or Course mutation
here.  Those remain release-time authority and cannot be inferred from this
planning artifact.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import re


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()


class RepresentationLayer(str, Enum):
    """Persistent distinction between meaning, structure, and realization."""

    SEMANTIC_IDENTITY = "SEMANTIC_IDENTITY"
    STRUCTURAL_COMPOSITION = "STRUCTURAL_COMPOSITION"
    SURFACE_REALIZATION = "SURFACE_REALIZATION"


class UnderstandingProjection(str, Enum):
    """Independent views that can prove more than rote direct execution."""

    EXECUTE = "EXECUTE"
    DISCRIMINATE = "DISCRIMINATE"
    TRANSFER = "TRANSFER"
    COMPOSE = "COMPOSE"
    INVERT = "INVERT"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    EXPLAIN = "EXPLAIN"


@dataclass(frozen=True)
class DevelopmentalTarget:
    """One candidate-only semantic step, prior to source/admission binding."""

    capability_id: str
    stage: int
    title: str
    prerequisites: tuple[str, ...]
    layers: tuple[RepresentationLayer, ...]
    projections: tuple[UnderstandingProjection, ...]
    source_requirements: tuple[str, ...]
    purpose: str

    def __post_init__(self) -> None:
        if (not isinstance(self.capability_id, str) or
                re.fullmatch(r"DEV\.[A-Z][A-Z0-9_]+", self.capability_id) is None or
                type(self.stage) is not int or self.stage < 1 or
                not isinstance(self.title, str) or not self.title.strip() or
                not isinstance(self.purpose, str) or not self.purpose.strip()):
            raise ValueError("DEVELOPMENT_TARGET_IDENTITY_INVALID")
        for values, kind, code in (
                (self.prerequisites, str,
                 "DEVELOPMENT_TARGET_PREREQUISITES_INVALID"),
                (self.layers, RepresentationLayer,
                 "DEVELOPMENT_TARGET_LAYERS_INVALID"),
                (self.projections, UnderstandingProjection,
                 "DEVELOPMENT_TARGET_PROJECTIONS_INVALID"),
                (self.source_requirements, str,
                 "DEVELOPMENT_TARGET_SOURCE_REQUIREMENTS_INVALID")):
            if (not values or len(set(values)) != len(values) or
                    any(not isinstance(item, kind) for item in values) or
                    (kind is str and any(not item.strip() for item in values))):
                raise ValueError(code)


@dataclass(frozen=True)
class DevelopmentalStaircase:
    """A candidate prerequisite DAG whose leaves may become future releases."""

    version: str
    baseline_capabilities: tuple[str, ...]
    targets: tuple[DevelopmentalTarget, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.version, str) or not self.version or
                not self.baseline_capabilities or
                len(set(self.baseline_capabilities)) !=
                len(self.baseline_capabilities) or
                any(not isinstance(item, str) or not item
                    for item in self.baseline_capabilities) or
                not self.targets):
            raise ValueError("DEVELOPMENT_STAIRCASE_IDENTITY_INVALID")
        target_map = {item.capability_id: item for item in self.targets}
        if len(target_map) != len(self.targets):
            raise ValueError("DEVELOPMENT_STAIRCASE_DUPLICATE_TARGET")
        allowed = set(self.baseline_capabilities) | set(target_map)
        for target in self.targets:
            if any(item not in allowed for item in target.prerequisites):
                raise ValueError("DEVELOPMENT_STAIRCASE_UNKNOWN_PREREQUISITE")
            for prerequisite in target.prerequisites:
                earlier = target_map.get(prerequisite)
                if earlier is not None and earlier.stage >= target.stage:
                    raise ValueError(
                        "DEVELOPMENT_STAIRCASE_PREREQUISITE_NOT_EARLIER")
        self._assert_acyclic(target_map)

    @staticmethod
    def _assert_acyclic(target_map: dict[str, DevelopmentalTarget]) -> None:
        visiting, visited = set(), set()

        def visit(identity: str) -> None:
            if identity in visiting:
                raise ValueError("DEVELOPMENT_STAIRCASE_CYCLE")
            if identity in visited:
                return
            visiting.add(identity)
            target = target_map[identity]
            for prerequisite in target.prerequisites:
                if prerequisite in target_map:
                    visit(prerequisite)
            visiting.remove(identity)
            visited.add(identity)

        for identity in target_map:
            visit(identity)

    @property
    def target_map(self) -> dict[str, DevelopmentalTarget]:
        return {item.capability_id: item for item in self.targets}

    def digest(self) -> str:
        payload = {
            "version": self.version,
            "baseline_capabilities": self.baseline_capabilities,
            "targets": [
                {
                    **asdict(item),
                    "layers": [value.value for value in item.layers],
                    "projections": [value.value for value in item.projections],
                }
                for item in self.targets
            ],
        }
        return _digest(payload)

    def validate_completed(self, completed: tuple[str, ...]) -> None:
        known = set(self.baseline_capabilities) | set(self.target_map)
        if (len(set(completed)) != len(completed) or
                any(item not in known for item in completed)):
            raise ValueError("DEVELOPMENT_COMPLETION_SCOPE_INVALID")
        complete = set(completed)
        for identity in complete & set(self.target_map):
            missing = set(self.target_map[identity].prerequisites) - complete
            if missing:
                raise ValueError(
                    "DEVELOPMENT_COMPLETION_PREREQUISITE_GAP:" +
                    identity + ":" + ",".join(sorted(missing)))

    def frontier(self, completed: tuple[str, ...]) -> tuple[DevelopmentalTarget, ...]:
        """Return every lowest-friction target whose prerequisites are complete."""
        self.validate_completed(completed)
        complete = set(completed)
        return tuple(
            target for target in self.targets
            if target.capability_id not in complete and
            set(target.prerequisites) <= complete)

    def stages(self) -> tuple[tuple[DevelopmentalTarget, ...], ...]:
        numbers = sorted({item.stage for item in self.targets})
        return tuple(
            tuple(item for item in self.targets if item.stage == stage)
            for stage in numbers)


def post_boolean_staircase() -> DevelopmentalStaircase:
    """Load the declarative research profile without admitting its targets."""
    from ..profiles.developmental import post_boolean_staircase as build
    return build()
