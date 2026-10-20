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
    """Candidate developmental DAG beginning after compositional Boolean identity.

    The sequence keeps semantic identity, structural composition, and surface
    realization distinct.  Branches open only where the semantic novelty can be
    isolated without forcing morphology to carry unresolved reasoning burdens.
    """
    S = RepresentationLayer
    P = UnderstandingProjection
    targets = (
        DevelopmentalTarget(
            "DEV.LAW_SCHEMA", 1, "Law identity and metavariable schema",
            ("B.IDBOOLOPS", "B.COMPOSITE"),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.INVERT, P.COUNTERFACTUAL),
            ("independent formal-law source with law identity and rewrite oracle",),
            "Recognize one invariant transformation across renamed symbols and "
            "instantiate it over unseen expressions."),
        DevelopmentalTarget(
            "DEV.TYPE_DISCIPLINE", 2, "Typed argument discipline",
            ("DEV.LAW_SCHEMA",),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION),
            (P.DISCRIMINATE, P.TRANSFER, P.COMPOSE, P.COUNTERFACTUAL),
            ("typed source signatures with independently checkable legal and illegal applications",),
            "Treat argument/result categories as semantic constraints rather than "
            "surface labels."),
        DevelopmentalTarget(
            "DEV.ORDERED_ROLES", 3, "Ordered argument roles",
            ("DEV.TYPE_DISCIPLINE",),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.INVERT, P.COUNTERFACTUAL),
            ("source relation whose argument permutation can change denotation",),
            "Bind values to stable semantic roles instead of treating inputs as an "
            "unordered bag."),
        DevelopmentalTarget(
            "DEV.SCOPE", 4, "Hierarchy and scope",
            ("DEV.ORDERED_ROLES", "DEV.LAW_SCHEMA"),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.COMPOSE, P.INVERT,
             P.COUNTERFACTUAL),
            ("source-grounded nested expressions with contrastive attachment or scope",),
            "Recover and manipulate hierarchical attachment when token inventory is "
            "held constant."),
        DevelopmentalTarget(
            "DEV.FEATURE_DIMENSION", 4, "Orthogonal feature dimension",
            ("DEV.TYPE_DISCIPLINE",),
            (S.SEMANTIC_IDENTITY,),
            (P.DISCRIMINATE, P.TRANSFER, P.COUNTERFACTUAL),
            ("finite source-declared category with mutually exclusive values",),
            "Learn category/value identity independently from lexical or surface form."),
        DevelopmentalTarget(
            "DEV.FEATURE_BUNDLE", 5, "Productive feature bundles",
            ("DEV.FEATURE_DIMENSION",),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION),
            (P.TRANSFER, P.COMPOSE, P.INVERT, P.COUNTERFACTUAL),
            ("two or more independently attested feature dimensions with held-out legal combinations",),
            "Compose known dimensions into unseen combinations without memorizing "
            "whole bundles."),
        DevelopmentalTarget(
            "DEV.RELATION_FRAME", 5, "Relational and event frames",
            ("DEV.ORDERED_ROLES",),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.INVERT, P.COUNTERFACTUAL),
            ("source-grounded n-ary relation or event-role inventory",),
            "Generalize ordered roles into reusable participant frames."),
        DevelopmentalTarget(
            "DEV.REALIZATION", 6, "Semantic identity to surface realization",
            ("DEV.FEATURE_BUNDLE",),
            (S.SEMANTIC_IDENTITY, S.SURFACE_REALIZATION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.INVERT, P.COUNTERFACTUAL),
            ("source-attested mapping from underlying feature identity to surface exponent",),
            "Keep what a feature means distinct from how that feature is realized."),
        DevelopmentalTarget(
            "DEV.ALLOMORPHY", 7, "Context-conditioned realization",
            ("DEV.REALIZATION",),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION, S.SURFACE_REALIZATION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.INVERT, P.COUNTERFACTUAL),
            ("source-attested underlying identity, conditioning context, and alternate surface forms",),
            "Predict a surface alternant from context without changing the underlying "
            "semantic identity."),
        DevelopmentalTarget(
            "DEV.ROLE_BINDING", 7, "Overt role binding",
            ("DEV.RELATION_FRAME", "DEV.REALIZATION"),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION, S.SURFACE_REALIZATION),
            (P.EXECUTE, P.DISCRIMINATE, P.TRANSFER, P.INVERT, P.COUNTERFACTUAL),
            ("source-attested role marking whose interpretation is separable from linear order",),
            "Map semantic participant roles to overt structure while resisting "
            "position-only heuristics."),
        DevelopmentalTarget(
            "DEV.MULTIFEATURE_COMPOSITION", 8, "Reversible multi-feature composition",
            ("DEV.ALLOMORPHY", "DEV.SCOPE", "DEV.FEATURE_BUNDLE"),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION, S.SURFACE_REALIZATION),
            (P.EXECUTE, P.TRANSFER, P.COMPOSE, P.INVERT, P.COUNTERFACTUAL),
            ("source-attested multi-component forms with recoverable component contributions",),
            "Generate and parse unseen combinations while preserving scope and "
            "context-conditioned realization."),
        DevelopmentalTarget(
            "DEV.COUNTERFACTUAL_EXPLANATION", 9,
            "Counterfactual rule transfer and structured explanation",
            ("DEV.MULTIFEATURE_COMPOSITION", "DEV.ROLE_BINDING", "DEV.LAW_SCHEMA"),
            (S.SEMANTIC_IDENTITY, S.STRUCTURAL_COMPOSITION, S.SURFACE_REALIZATION),
            (P.TRANSFER, P.COUNTERFACTUAL, P.EXPLAIN),
            ("source rules with perturbable conditions plus an inspectable causal derivation trace",),
            "Predict the consequence of one changed rule or feature and emit the "
            "rule/binding/result trace that explains it."),
    )
    return DevelopmentalStaircase(
        version="bilqis.mlx.post-boolean-development/v1",
        baseline_capabilities=("B.IDBOOLOPS", "B.COMPOSITE"),
        targets=targets,
    )
