"""Grade-neutral rule profiles for source-qualified Factory families."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.semantics.cognitive_operators.registry import (
    OperatorRegistry, operator_grant_digest,
)
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter
from bilqis_mlx.semantics.foundation.core import Signature

from .capability_identity_contracts import CapabilityIdentityInput


BOOLEAN_COVERAGE = ("truth-table", "polarity", "legal-connective-pattern")
NUMERIC_COVERAGE = ("number", "successor", "arithmetic", "range", "overflow")
WORLD_COVERAGE = ("actor", "time", "state", "causal-relation")
_BOOLEAN = ("BOOL_AND", "BOOL_IFF", "BOOL_IMPLIES", "BOOL_OR", "BOOL_XOR")
_NUMERIC = ("ADD", "DIV", "MOD", "MUL", "SUB")
_WORLD = ("BEFORE", "IS_OCCURRED", "ROLE_LOOKUP")
_WORLD_SOURCE_CAPABILITIES = (
    "WORLD.ACTOR_OF", "WORLD.BEFORE", "WORLD.IS_OCCURRED",
    "WORLD.DIRECT_CAUSE",
)


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
                or any(len(item) != 3 or any(type(value) is not str or not value
                    for value in item) for item in self.source_coordinates)
                or len({item[0] for item in self.source_coordinates})
                != len(self.source_coordinates)
                or (self.source_coordinates and tuple(sorted(
                    item[0] for item in self.source_coordinates))
                    != self.source_capability_ids)):
            raise ValueError("FACTORY_SEMANTIC_RULE_PROFILE_INVALID")


class SemanticRuleRegistry:
    def __init__(self, version: str, profiles: tuple[SemanticRuleProfile, ...]):
        if not isinstance(version, str) or not version:
            raise ValueError("FACTORY_SEMANTIC_RULE_REGISTRY_INVALID")
        self.version = version
        self.profiles = profiles
        keys = tuple(item.identity.canonical_payload() for item in profiles)
        if (not profiles or any(type(item) is not SemanticRuleProfile for item in profiles)
                or len(keys) != len(set(keys))):
            raise ValueError("FACTORY_SEMANTIC_RULE_DUPLICATE")

    def require(self, identity: CapabilityIdentityInput) -> SemanticRuleProfile:
        if type(identity) is not CapabilityIdentityInput:
            raise TypeError("FACTORY_SEMANTIC_RULE_IDENTITY_REQUIRED")
        matches = tuple(item for item in self.profiles
                        if item.identity.canonical_payload() == identity.canonical_payload())
        if len(matches) != 1:
            raise ValueError("FACTORY_SEMANTIC_RULE_MISSING")
        return matches[0]


def _profile(registry: OperatorRegistry, semantic_id: str, family: str, operator_id: str, signature: Signature,
             answers: tuple[str, ...], coverage: tuple[str, ...],
             operator_ids: tuple[str, ...]) -> SemanticRuleProfile:
    if type(registry) is not OperatorRegistry:
        raise TypeError("FACTORY_SEMANTIC_RULE_OPERATOR_REGISTRY_REQUIRED")
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
        raise TypeError("FACTORY_SEMANTIC_RULE_OPERATOR_REGISTRY_REQUIRED")
    if source is not None:
        from bilqis_mlx.source_adapters.world_rules import require_registered_source
        try:
            require_registered_source(source)
        except (TypeError, ValueError):
            raise ValueError(
                "FACTORY_WORLD_RULE_SOURCE_AUTHORITY_UNAVAILABLE") from None
    for operator_id in _WORLD:
        operators.resolve(operator_id)
    return SemanticRuleProfile(
        CapabilityIdentityInput(
            "source.bamf.qualified-world/v1", "qualified_world_model",
            "SOURCE_WORLD_QUERY",
            Signature(("WorldRecord", "WorldQuery"), "Boolean"),
            ("binary",)),
        WORLD_COVERAGE, tuple(sorted(_WORLD)),
        "source.bamf.qualified-world/v1",
        None if source is None else source.descriptor.implementation_sha256,
        tuple(sorted(_WORLD_SOURCE_CAPABILITIES)),
        tuple(sorted((
            ("WORLD.ACTOR_OF", "ithkuil:ATOM-5d7116db8e1508",
             "SOURCE_WORLD_ACTOR_OF"),
            ("WORLD.BEFORE", "ithkuil:ATOM-ef7cf17b427af9",
             "SOURCE_WORLD_BEFORE"),
            ("WORLD.IS_OCCURRED", "ithkuil:LEXSENSE-294d00be074a56",
             "SOURCE_WORLD_IS_OCCURRED"),
            ("WORLD.DIRECT_CAUSE", "ithkuil:LEXSENSE-59819df75e3137",
             "SOURCE_WORLD_DIRECT_CAUSE"),
        ))),
    )
