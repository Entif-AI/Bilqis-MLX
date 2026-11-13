"""Grade-neutral rule profiles for source-qualified Factory families."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.semantics.cognitive_operators.registry import (
    OperatorRegistry, operator_grant_digest,
)
from bilqis_mlx.errors import ErrorBus, FACTORY
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter
from bilqis_mlx.semantics.foundation.core import Signature

from .capability_identity_contracts import CapabilityIdentityInput


BOOLEAN_COVERAGE = ("truth-table", "polarity", "legal-connective-pattern")
NUMERIC_COVERAGE = ("number", "successor", "arithmetic", "range", "overflow")
WORLD_COVERAGE = ("state",)
_BOOLEAN = ("BOOL_AND", "BOOL_IFF", "BOOL_IMPLIES", "BOOL_OR", "BOOL_XOR")
_NUMERIC = ("ADD", "DIV", "MOD", "MUL", "SUB")
_WORLD = ("IS_OCCURRED",)
_WORLD_SOURCE_COORDINATES = (
    ("WORLD.IS_OCCURRED", "ithkuil:LEXSENSE-294d00be074a56", "IS_OCCURRED"),
)
_WORLD_SOURCE_CAPABILITIES = tuple(item[0] for item in _WORLD_SOURCE_COORDINATES)
_WORLD_SOURCE_NON_OPERATOR_CAPABILITIES = (
    "WORLD.ACTOR_OF", "WORLD.BEFORE", "WORLD.DIRECT_CAUSE",
)
SOURCE_COORDINATE_WIDTH = 3


def _fail(reason: str) -> None:
    ErrorBus.raise_(FACTORY.SEMANTIC_RULE.INVALID, reason=reason)


def world_source_operator_classification(
        capability_id: str) -> tuple[str, str | None, str | None] | None:
    """Project the Factory-owned qualified-world operator classification."""
    matches = tuple(item for item in _WORLD_SOURCE_COORDINATES
                    if item[0] == capability_id)
    if len(matches) == 1:
        _, semantic_root, operator_id = matches[0]
        return ("OPERATOR", semantic_root, operator_id)
    if capability_id in _WORLD_SOURCE_NON_OPERATOR_CAPABILITIES:
        return ("NON_OPERATOR", None, None)
    return None


@dataclass(frozen=True)
class SemanticRuleProfile:
    identity: CapabilityIdentityInput
    coverage: tuple[str, ...]
    operator_ids: tuple[str, ...]
    source_adapter_id: str | None = None
    source_contract_sha256: str | None = None
    source_capability_ids: tuple[str, ...] = ()
    source_coordinates: tuple[tuple[str, str, str], ...] = ()

    def __post_init__(self) -> None:
        if (type(self.identity) is not CapabilityIdentityInput
                or not self.coverage or not self.operator_ids
                or self.operator_ids != tuple(sorted(set(self.operator_ids)))
                or (self.source_contract_sha256 is not None
                    and self.source_adapter_id is None)
                or (self.source_capability_ids
                    and self.source_adapter_id is None)
                or self.source_capability_ids
                != tuple(sorted(set(self.source_capability_ids)))
                or any(len(item) != SOURCE_COORDINATE_WIDTH
                    or any(type(value) is not str or not value
                    for value in item) for item in self.source_coordinates)
                or len({item[0] for item in self.source_coordinates})
                != len(self.source_coordinates)
                or (self.source_coordinates and tuple(sorted(
                    item[0] for item in self.source_coordinates))
                    != self.source_capability_ids)):
            _fail("FACTORY_SEMANTIC_RULE_PROFILE_INVALID")


class SemanticRuleRegistry:
    def __init__(self, version: str, profiles: tuple[SemanticRuleProfile, ...]):
        if not isinstance(version, str) or not version:
            _fail("FACTORY_SEMANTIC_RULE_REGISTRY_INVALID")
        self.version = version
        self.profiles = profiles
        keys = tuple(item.identity.canonical_payload() for item in profiles)
        if (not profiles or any(type(item) is not SemanticRuleProfile for item in profiles)
                or len(keys) != len(set(keys))):
            _fail("FACTORY_SEMANTIC_RULE_DUPLICATE")

    def require(self, identity: CapabilityIdentityInput) -> SemanticRuleProfile:
        if type(identity) is not CapabilityIdentityInput:
            raise TypeError
        matches = tuple(item for item in self.profiles
                        if item.identity.canonical_payload() == identity.canonical_payload())
        if len(matches) != 1:
            _fail("FACTORY_SEMANTIC_RULE_MISSING")
        return matches[0]


def _profile(registry: OperatorRegistry, semantic_id: str, family: str, operator_id: str, signature: Signature,
             answers: tuple[str, ...], coverage: tuple[str, ...],
             operator_ids: tuple[str, ...]) -> SemanticRuleProfile:
    if type(registry) is not OperatorRegistry:
        raise TypeError
    for covered_operator_id in operator_ids:
        registry.resolve(covered_operator_id)
    return SemanticRuleProfile(CapabilityIdentityInput(
        semantic_id, family, operator_id, signature, answers), coverage, operator_ids)


def default_semantic_rule_registry(
        semantic_release: str,
        world_source: RegisteredSourceAdapter | None = None) -> SemanticRuleRegistry:
    from bilqis_mlx.semantics.cognitive_operators.registry import default_registry
    operators = default_registry(semantic_release)
    profiles = [
        _profile(operators, "legacy:cogal.operator.AND", "boolean_composition", "BOOL_AND", Signature(("Boolean", "Boolean"), "Boolean"),
                 ("binary",), BOOLEAN_COVERAGE, _BOOLEAN),
        _profile(operators, "bilqis.numeric/v1:school.op.ADD", "numeric_composition", "ADD", Signature(("Number", "Number"), "Number"),
                 ("integer",), NUMERIC_COVERAGE, _NUMERIC),
    ]
    if world_source is not None:
        profiles.append(world_rule_profile(operators, world_source))
    return SemanticRuleRegistry(
        "bilqis.factory.semantic-rule-registry/v1", tuple(profiles))


def world_rule_profile(
        operators: OperatorRegistry,
        source: RegisteredSourceAdapter | None = None) -> SemanticRuleProfile:
    """Require source-owned world evidence in addition to operator declarations."""
    if type(operators) is not OperatorRegistry:
        raise TypeError
    if source is not None:
        from bilqis_mlx.source_adapters.world_rules import require_registered_source
        try:
            require_registered_source(source)
        except (TypeError, ValueError):
            _fail("FACTORY_WORLD_RULE_SOURCE_AUTHORITY_UNAVAILABLE")
    for operator_id in _WORLD:
        operators.resolve(operator_id)
    return SemanticRuleProfile(
        CapabilityIdentityInput(
            "ithkuil:LEXSENSE-294d00be074a56", "qualified_world_model",
            "IS_OCCURRED",
            Signature(("EventStatus",), "Boolean"),
            ("binary",)),
        WORLD_COVERAGE, tuple(sorted(_WORLD)),
        "source.bamf.qualified-world/v1",
        None if source is None else source.descriptor.implementation_sha256,
        tuple(sorted(_WORLD_SOURCE_CAPABILITIES)),
        tuple(sorted(_WORLD_SOURCE_COORDINATES)),
    )
