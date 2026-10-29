"""C04.1 deterministic route applicability, independent of grade labels."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..errors import ErrorBus, SCHOOL


ROUTE_SPEC_SCHEMA = "bilqis.c04.route-spec/v1"
ROUTE_REGISTRY_SCHEMA = "bilqis.c04.route-registry/v2"


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_SOLVER.INVALID, reason=reason)


class RouteKind(str, Enum):
    EXACT = "EXACT"
    CACHED_COMPOSITION = "CACHED_COMPOSITION"
    NEURAL_COMPOSITION = "NEURAL_COMPOSITION"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class RouteSpec:
    kind: RouteKind
    priority: int
    applicability: str
    schema_version: str = ROUTE_SPEC_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.kind, RouteKind)
                or type(self.priority) is not int or self.priority < 0
                or not isinstance(self.applicability, str)
                or not self.applicability
                or self.schema_version != ROUTE_SPEC_SCHEMA):
            _invalid("BAMF_C04_ROUTE_SPEC_INVALID")


@dataclass(frozen=True)
class RouteRegistry:
    specs: tuple[RouteSpec, ...]
    schema_version: str = ROUTE_REGISTRY_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.specs, tuple)
                or len(self.specs) != len(RouteKind)
                or any(not isinstance(spec, RouteSpec)
                       for spec in self.specs)
                or tuple(spec.kind for spec in self.specs)
                != tuple(RouteKind)
                or tuple(spec.priority for spec in self.specs)
                != tuple(range(len(RouteKind)))
                or self.schema_version != ROUTE_REGISTRY_SCHEMA):
            _invalid("BAMF_C04_ROUTE_REGISTRY_INVALID")

    def rank(self, kind: RouteKind) -> int:
        return next(spec.priority for spec in self.specs if spec.kind is kind)


def default_route_registry() -> RouteRegistry:
    return RouteRegistry((
        RouteSpec(RouteKind.EXACT, 0, "APPLICABLE_SOURCE_QUALIFIED_PURE"),
        RouteSpec(RouteKind.CACHED_COMPOSITION, 1,
                  "QUALIFIED_SAME_SOURCE_AND_RIGHTS"),
        RouteSpec(RouteKind.NEURAL_COMPOSITION, 2,
                  "BOUNDED_UNRESOLVED_DAG_PROPOSAL"),
        RouteSpec(RouteKind.DETERMINISTIC_FALLBACK, 3,
                  "SOURCE_QUALIFIED_FALLBACK_AFTER_INVALID_NEURAL"),
        RouteSpec(RouteKind.UNRESOLVED, 4, "NO_ADMISSIBLE_ROUTE"),
    ))
